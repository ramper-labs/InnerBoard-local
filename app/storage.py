"""
Handles the encrypted storage of user reflections using SQLite and Fernet.
"""

import sqlite3
import os
from cryptography.fernet import Fernet
from typing import List, Tuple, Optional

DB_FILE = "vault.db"
KEY_FILE = "vault.key"

def generate_key() -> bytes:
    """Generates a new Fernet key and saves it to a file."""
    key = Fernet.generate_key()
    with open(KEY_FILE, "wb") as key_file:
        key_file.write(key)
    return key

def load_key() -> bytes:
    """Loads the Fernet key from a file, or generates a new one."""
    if not os.path.exists(KEY_FILE):
        return generate_key()
    with open(KEY_FILE, "rb") as key_file:
        return key_file.read()

class EncryptedVault:
    """
    Manages an encrypted SQLite database for storing reflections.
    """
    def __init__(self, db_path: str, key: bytes):
        """
        Initializes the vault with a database path and an encryption key.

        Args:
            db_path (str): The path to the SQLite database file.
            key (bytes): The Fernet encryption key.
        """
        self.db_path = db_path
        self.cipher = Fernet(key)
        self.conn = sqlite3.connect(self.db_path)
        self._create_table()

    def _create_table(self):
        """Creates the 'reflections' table if it doesn't already exist."""
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS reflections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    encrypted_text BLOB NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

    def add_reflection(self, text: str) -> int:
        """
        Encrypts and stores a new reflection.

        Args:
            text (str): The raw reflection text.
        
        Returns:
            int: The ID of the newly inserted reflection.
        """
        encrypted = self.cipher.encrypt(text.encode('utf-8'))
        with self.conn:
            cursor = self.conn.execute(
                "INSERT INTO reflections (encrypted_text) VALUES (?)",
                (encrypted,)
            )
        return cursor.lastrowid

    def get_reflection(self, reflection_id: int) -> Optional[str]:
        """
        Retrieves and decrypts a specific reflection.

        Args:
            reflection_id (int): The ID of the reflection to retrieve.

        Returns:
            Optional[str]: The decrypted reflection text, or None if not found.
        """
        cursor = self.conn.execute(
            "SELECT encrypted_text FROM reflections WHERE id = ?",
            (reflection_id,)
        )
        row = cursor.fetchone()
        if row:
            decrypted = self.cipher.decrypt(row[0])
            return decrypted.decode('utf-8')
        return None

    def get_all_reflections(self) -> List[Tuple[int, str]]:
        """
        Retrieves and decrypts all reflections.

        Returns:
            List[Tuple[int, str]]: A list of (id, decrypted_text) tuples.
        """
        reflections = []
        cursor = self.conn.execute("SELECT id, encrypted_text FROM reflections ORDER BY timestamp DESC")
        for row in cursor.fetchall():
            decrypted_text = self.cipher.decrypt(row[1]).decode('utf-8')
            reflections.append((row[0], decrypted_text))
        return reflections

    def close(self):
        """Closes the database connection."""
        if self.conn:
            self.conn.close()

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
    vault.add_reflection("I finally got the build to pass after fixing the dependencies.")

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
