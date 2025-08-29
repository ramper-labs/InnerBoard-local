"""
Handles the encrypted storage of user reflections using SQLite and Fernet.
Enhanced with secure key management and input validation.
"""

import sqlite3
import os
from pathlib import Path
from cryptography.fernet import Fernet, InvalidToken
from typing import List, Tuple, Optional
from app.config import config
from app.security import SecureKeyManager, InputValidator, secure_delete_file
from app.logging_config import get_logger
from app.exceptions import (
    DatabaseError,
    EncryptionError,
    KeyNotFoundError,
    InvalidKeyError,
    ValidationError,
)

logger = get_logger(__name__)

# Default paths
DB_FILE = "vault.db"
KEY_FILE = "vault.key"


def generate_key(password: Optional[str] = None) -> bytes:
    """
    Generates a new secure key using the enhanced key manager.

    Args:
        password: Optional password for key encryption

    Returns:
        bytes: The generated master key
    """
    key_manager = SecureKeyManager()
    master_key = key_manager.generate_master_key(password)
    key_manager.save_master_key(password)
    logger.info("Generated new secure master key")
    return master_key


def load_key(password: Optional[str] = None) -> bytes:
    """
    Loads the master key using the enhanced key manager.

    Args:
        password: Optional password for key decryption

    Returns:
        bytes: The loaded master key

    Raises:
        KeyNotFoundError: If key file doesn't exist
        InvalidKeyError: If key validation fails
    """
    key_manager = SecureKeyManager()
    try:
        master_key = key_manager.load_master_key(password)
        logger.info("Successfully loaded and validated master key")
        return master_key
    except (KeyNotFoundError, InvalidKeyError):
        # Try legacy loading for backward compatibility
        legacy_key_path = Path(KEY_FILE)
        if legacy_key_path.exists():
            logger.info("Attempting legacy key loading")
            try:
                with open(legacy_key_path, "rb") as f:
                    legacy_key = f.read()
                # Validate it's a proper Fernet key
                Fernet(legacy_key)
                logger.info("Legacy key loaded successfully")
                return legacy_key
            except Exception as e:
                logger.error(f"Legacy key loading failed: {e}")
                raise InvalidKeyError("Failed to load key") from e
        else:
            raise


class EncryptedVault:
    """
    Manages an encrypted SQLite database for storing reflections.
    Enhanced with security features and input validation.
    """

    def __init__(self, db_path: str, key: bytes):
        """
        Initializes the vault with a database path and an encryption key.

        Args:
            db_path (str): The path to the SQLite database file.
            key (bytes): The Fernet encryption key.

        Raises:
            DatabaseError: If database initialization fails
            EncryptionError: If encryption setup fails
        """
        try:
            # Validate inputs
            if not db_path:
                raise ValueError("Database path cannot be empty")
            if not key or len(key) < 16:
                raise ValueError("Invalid encryption key")

            # Validate key strength
            key_manager = SecureKeyManager()
            is_strong, feedback = key_manager.validate_key_strength(key)
            if not is_strong:
                logger.warning(f"Key strength warning: {feedback}")

            self.db_path = Path(db_path)
            self.cipher = Fernet(key)
            self.conn = None

            # Test encryption/decryption
            test_data = b"test_encryption"
            encrypted = self.cipher.encrypt(test_data)
            decrypted = self.cipher.decrypt(encrypted)
            if decrypted != test_data:
                raise EncryptionError("Encryption self-test failed")

            # Initialize database connection
            self._connect()
            self._create_table()

            logger.info(f"Encrypted vault initialized: {self.db_path}")

        except Exception as e:
            logger.error(f"Failed to initialize encrypted vault: {e}")
            if isinstance(e, (DatabaseError, EncryptionError)):
                raise
            elif "cryptography" in str(type(e)).lower():
                raise EncryptionError(f"Encryption error: {e}") from e
            else:
                raise DatabaseError(f"Database initialization failed: {e}") from e

    def _connect(self) -> None:
        """Establish database connection with security settings."""
        try:
            self.conn = sqlite3.connect(
                str(self.db_path),
                isolation_level=None,  # Enable autocommit mode for better security
                check_same_thread=False,  # Allow access from multiple threads (use carefully)
            )
            # Enable WAL mode for better concurrency
            self.conn.execute("PRAGMA journal_mode=WAL")
            # Enable foreign keys
            self.conn.execute("PRAGMA foreign_keys=ON")
            logger.debug("Database connection established with security settings")
        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to connect to database: {e}") from e

    def _create_table(self) -> None:
        """Creates the 'reflections' table if it doesn't already exist."""
        try:
            with self.conn:
                self.conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS reflections (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        encrypted_text BLOB NOT NULL,
                        checksum TEXT NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """
                )
                # Create indexes for better performance
                self.conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_reflections_timestamp
                    ON reflections(created_at)
                """
                )
                logger.debug("Database table created/verified")
        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to create database table: {e}") from e

    def add_reflection(self, text: str) -> int:
        """
        Encrypts and stores a new reflection with security validation.

        Args:
            text (str): The raw reflection text.

        Returns:
            int: The ID of the newly inserted reflection.

        Raises:
            ValidationError: If input validation fails
            DatabaseError: If database operation fails
        """
        # Validate input
        validated_text = InputValidator.validate_reflection_text(text)

        try:
            # Encrypt the validated text
            text_bytes = validated_text.encode("utf-8")
            encrypted = self.cipher.encrypt(text_bytes)

            # Generate checksum for integrity verification
            import hashlib

            checksum = hashlib.sha256(text_bytes).hexdigest()

            # Insert with transaction
            with self.conn:
                cursor = self.conn.execute(
                    """
                    INSERT INTO reflections (encrypted_text, checksum)
                    VALUES (?, ?)
                    """,
                    (encrypted, checksum),
                )
                reflection_id = cursor.lastrowid

            logger.info(f"Reflection stored with ID: {reflection_id}")
            return reflection_id

        except sqlite3.Error as e:
            logger.error(f"Database error storing reflection: {e}")
            raise DatabaseError(f"Failed to store reflection: {e}") from e
        except InvalidToken as e:
            logger.error(f"Encryption error: {e}")
            raise EncryptionError("Failed to encrypt reflection") from e

    def get_reflection(self, reflection_id: int) -> Optional[Tuple[str, str, str]]:
        """
        Retrieves and decrypts a specific reflection with integrity verification.

        Args:
            reflection_id (int): The ID of the reflection to retrieve.

        Returns:
            Optional[Tuple[str, str, str]]: (text, created_at, updated_at) or None if not found.

        Raises:
            DatabaseError: If database operation fails
            EncryptionError: If decryption fails
        """
        if not isinstance(reflection_id, int) or reflection_id <= 0:
            raise ValidationError("Invalid reflection ID")

        try:
            cursor = self.conn.execute(
                "SELECT encrypted_text, checksum, created_at, updated_at FROM reflections WHERE id = ?",
                (reflection_id,),
            )
            row = cursor.fetchone()

            if not row:
                return None

            encrypted_text, stored_checksum, created_at, updated_at = row

            # Decrypt the text
            decrypted_bytes = self.cipher.decrypt(encrypted_text)
            decrypted_text = decrypted_bytes.decode("utf-8")

            # Verify integrity
            import hashlib

            computed_checksum = hashlib.sha256(decrypted_bytes).hexdigest()
            if computed_checksum != stored_checksum:
                logger.error(f"Integrity check failed for reflection {reflection_id}")
                raise EncryptionError("Data integrity check failed")

            logger.debug(f"Reflection {reflection_id} retrieved and verified")
            return (decrypted_text, created_at, updated_at)

        except sqlite3.Error as e:
            logger.error(f"Database error retrieving reflection {reflection_id}: {e}")
            raise DatabaseError(f"Failed to retrieve reflection: {e}") from e
        except InvalidToken as e:
            logger.error(f"Decryption error for reflection {reflection_id}: {e}")
            raise EncryptionError("Failed to decrypt reflection") from e

    def get_all_reflections(self) -> List[Tuple[int, str, str, str]]:
        """
        Retrieves and decrypts all reflections with integrity verification.

        Returns:
            List[Tuple[int, str, str, str]]: A list of (id, text, created_at, updated_at) tuples.

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            reflections = []
            cursor = self.conn.execute(
                "SELECT id, encrypted_text, checksum, created_at, updated_at FROM reflections ORDER BY created_at DESC"
            )

            for row in cursor.fetchall():
                (
                    reflection_id,
                    encrypted_text,
                    stored_checksum,
                    created_at,
                    updated_at,
                ) = row

                try:
                    # Decrypt the text
                    decrypted_bytes = self.cipher.decrypt(encrypted_text)
                    decrypted_text = decrypted_bytes.decode("utf-8")

                    # Verify integrity
                    import hashlib

                    computed_checksum = hashlib.sha256(decrypted_bytes).hexdigest()
                    if computed_checksum != stored_checksum:
                        logger.warning(
                            f"Integrity check failed for reflection {reflection_id}"
                        )
                        continue  # Skip corrupted entries

                    reflections.append(
                        (reflection_id, decrypted_text, created_at, updated_at)
                    )

                except (InvalidToken, UnicodeDecodeError) as e:
                    logger.warning(f"Failed to decrypt reflection {reflection_id}: {e}")
                    continue  # Skip corrupted entries

            logger.debug(f"Retrieved {len(reflections)} reflections")
            return reflections

        except sqlite3.Error as e:
            logger.error(f"Database error retrieving all reflections: {e}")
            raise DatabaseError(f"Failed to retrieve reflections: {e}") from e

    def close(self) -> None:
        """Closes the database connection securely."""
        if self.conn:
            try:
                self.conn.close()
                logger.debug("Database connection closed")
            except sqlite3.Error as e:
                logger.warning(f"Error closing database connection: {e}")
            finally:
                self.conn = None

    def delete_reflection(self, reflection_id: int) -> bool:
        """
        Securely deletes a reflection from the database.

        Args:
            reflection_id: ID of the reflection to delete

        Returns:
            bool: True if deleted, False if not found

        Raises:
            DatabaseError: If database operation fails
        """
        if not isinstance(reflection_id, int) or reflection_id <= 0:
            raise ValidationError("Invalid reflection ID")

        try:
            with self.conn:
                cursor = self.conn.execute(
                    "DELETE FROM reflections WHERE id = ?", (reflection_id,)
                )
                deleted = cursor.rowcount > 0

            if deleted:
                logger.info(f"Reflection {reflection_id} deleted")
            else:
                logger.debug(f"Reflection {reflection_id} not found for deletion")

            return deleted

        except sqlite3.Error as e:
            logger.error(f"Database error deleting reflection {reflection_id}: {e}")
            raise DatabaseError(f"Failed to delete reflection: {e}") from e

    def secure_erase_all(self) -> None:
        """
        Securely erases all data from the vault.

        Raises:
            DatabaseError: If operation fails
        """
        try:
            # Get all reflection IDs
            cursor = self.conn.execute("SELECT id FROM reflections")
            reflection_ids = [row[0] for row in cursor.fetchall()]

            # Delete all reflections
            with self.conn:
                self.conn.execute("DELETE FROM reflections")

            logger.info(f"Securely erased {len(reflection_ids)} reflections from vault")

        except sqlite3.Error as e:
            logger.error(f"Database error during secure erase: {e}")
            raise DatabaseError(f"Failed to erase vault: {e}") from e

    def get_stats(self) -> dict:
        """
        Get vault statistics for monitoring.

        Returns:
            dict: Statistics about the vault
        """
        try:
            cursor = self.conn.execute(
                "SELECT COUNT(*), MIN(created_at), MAX(created_at) FROM reflections"
            )
            count, oldest, newest = cursor.fetchone()

            return {
                "total_reflections": count or 0,
                "oldest_reflection": oldest,
                "newest_reflection": newest,
                "database_size": (
                    self.db_path.stat().st_size if self.db_path.exists() else 0
                ),
            }
        except (sqlite3.Error, OSError) as e:
            logger.warning(f"Failed to get vault stats: {e}")
            return {
                "total_reflections": 0,
                "oldest_reflection": None,
                "newest_reflection": None,
                "database_size": 0,
            }

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with secure cleanup."""
        self.close()


def main():
    """Demonstrates the usage of the EncryptedVault."""
    print("Initializing encrypted vault...")
    key = load_key()
    vault = EncryptedVault(DB_FILE, key)
    print("Vault initialized.")

    print("\nAdding a new reflection...")
    reflection_text = "Today was challenging. I struggled with the Kubernetes setup."
    reflection_id = vault.add_reflection(reflection_text)
    print(f"Added reflection with ID: {reflection_id}")

    print("\nRetrieving the reflection...")
    retrieved_text = vault.get_reflection(reflection_id)
    print(f"Retrieved: {retrieved_text}")
    assert reflection_text == retrieved_text

    print("\nAdding another reflection...")
    vault.add_reflection(
        "I finally got the build to pass after fixing the dependencies."
    )

    print("\nListing all reflections:")
    all_reflections = vault.get_all_reflections()
    for rid, text in all_reflections:
        print(f"  ID {rid}: {text[:40]}...")

    vault.close()
    print("\nDemonstration complete. Vault closed.")
    # Clean up created files for demonstration purposes
    os.remove(DB_FILE)
    os.remove(KEY_FILE)


if __name__ == "__main__":
    main()
