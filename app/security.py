"""
Enhanced security features for InnerBoard-local.
Provides secure key management, validation, and cryptographic operations.
"""

import os
import hashlib
import secrets
import base64
from pathlib import Path
from typing import Optional, Tuple
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization
from app.config import config
from app.logging_config import get_logger
from app.exceptions import (
    KeyNotFoundError,
    InvalidKeyError,
    EncryptionError,
    ValidationError,
)

logger = get_logger(__name__)


class SecureKeyManager:
    """Enhanced key management with PBKDF2 derivation and validation."""

    SALT_SIZE = 32
    KEY_SIZE = 32
    ITERATIONS = 100_000

    def __init__(self, key_path: Optional[Path] = None):
        self.key_path = key_path or config.key_path
        self._master_key: Optional[bytes] = None
        self._salt: Optional[bytes] = None

    def generate_master_key(self, password: Optional[str] = None) -> bytes:
        """
        Generate a new master key using PBKDF2 with a random salt.

        Args:
            password: Optional password for key derivation (uses random if None)

        Returns:
            bytes: The derived master key
        """
        # Generate random salt
        salt = secrets.token_bytes(self.SALT_SIZE)

        # Use password if provided, otherwise use random data
        if password:
            password_bytes = password.encode("utf-8")
        else:
            password_bytes = secrets.token_bytes(32)

        # Derive key using PBKDF2
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=self.KEY_SIZE,
            salt=salt,
            iterations=self.ITERATIONS,
        )

        derived_key = kdf.derive(password_bytes)

        # Convert to Fernet-compatible format (URL-safe base64)
        master_key = base64.urlsafe_b64encode(derived_key)

        self._master_key = master_key
        self._salt = salt

        logger.info("Generated new master key with PBKDF2 derivation")
        return master_key

    def save_master_key(self, password: Optional[str] = None) -> None:
        """Save the master key and salt to disk securely."""
        if not self._master_key or not self._salt:
            raise EncryptionError("No master key available to save")

        # Create key data structure
        key_data = {
            "version": 1,
            "salt": base64.b64encode(self._salt).decode("utf-8"),
            "key_hash": hashlib.sha256(self._master_key).hexdigest(),
            "iterations": self.ITERATIONS,
        }

        # Encrypt master key with password if provided
        if password:
            # Derive encryption key from password
            enc_kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=self._salt,
                iterations=self.ITERATIONS // 10,  # Faster for encryption
            )
            enc_key = enc_kdf.derive(password.encode("utf-8"))
            cipher = Fernet(base64.urlsafe_b64encode(enc_key))

            # Encrypt the master key
            encrypted_key = cipher.encrypt(self._master_key)
            key_data["encrypted_key"] = base64.b64encode(encrypted_key).decode("utf-8")
        else:
            # Store key directly (less secure but compatible)
            key_data["master_key"] = self._master_key.decode("utf-8")

        # Write to file atomically
        import json
        import tempfile

        key_data_json = json.dumps(key_data, indent=2)

        # Write to temporary file first
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, dir=self.key_path.parent
        ) as temp_file:
            temp_file.write(key_data_json)
            temp_path = Path(temp_file.name)

        # Atomic move to final location
        temp_path.replace(self.key_path)

        logger.info(f"Master key saved to {self.key_path}")

    def load_master_key(self, password: Optional[str] = None) -> bytes:
        """
        Load master key from disk with validation.

        Args:
            password: Password for decryption if key is encrypted

        Returns:
            bytes: The master key

        Raises:
            KeyNotFoundError: If key file doesn't exist
            InvalidKeyError: If key validation fails
        """
        if not self.key_path.exists():
            raise KeyNotFoundError(f"Key file not found: {self.key_path}")

        try:
            import json

            with open(self.key_path, "r") as f:
                key_data = json.load(f)

            version = key_data.get("version", 0)

            if version == 1:
                return self._load_v1_key(key_data, password)
            else:
                # Legacy format (unencrypted)
                return self._load_legacy_key()

        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Invalid key file format: {e}")
            raise InvalidKeyError("Invalid key file format")

    def _load_v1_key(self, key_data: dict, password: Optional[str]) -> bytes:
        """Load version 1 key format."""
        salt = base64.b64decode(key_data["salt"])
        stored_hash = key_data["key_hash"]
        iterations = key_data["iterations"]

        if "encrypted_key" in key_data:
            # Password-protected key
            if not password:
                raise InvalidKeyError("Password required for encrypted key")

            encrypted_key = base64.b64decode(key_data["encrypted_key"])

            # Derive decryption key
            enc_kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=iterations // 10,
            )
            enc_key = enc_kdf.derive(password.encode("utf-8"))
            cipher = Fernet(base64.urlsafe_b64encode(enc_key))

            try:
                master_key = cipher.decrypt(encrypted_key)
            except InvalidToken:
                raise InvalidKeyError("Invalid password")

        else:
            # Unencrypted key (legacy compatibility)
            master_key = key_data["master_key"].encode("utf-8")

        # Validate key integrity
        computed_hash = hashlib.sha256(master_key).hexdigest()
        if computed_hash != stored_hash:
            raise InvalidKeyError("Key integrity check failed")

        self._master_key = master_key
        self._salt = salt
        logger.info("Master key loaded and validated")

        return master_key

    def _load_legacy_key(self) -> bytes:
        """Load legacy key format for backward compatibility."""
        try:
            with open(self.key_path, "rb") as f:
                key_data = f.read()

            # Validate it's a proper Fernet key
            Fernet(key_data)  # This will raise if invalid

            self._master_key = key_data
            logger.info("Legacy key format loaded")

            return key_data
        except Exception as e:
            raise InvalidKeyError(f"Failed to load legacy key: {e}")

    def validate_key_strength(self, key: bytes) -> Tuple[bool, str]:
        """
        Validate key strength and provide feedback.

        Args:
            key: The key to validate (can be raw bytes or base64 encoded)

        Returns:
            Tuple[bool, str]: (is_strong, feedback_message)
        """
        # If key is base64 encoded, decode it first
        try:
            decoded_key = base64.urlsafe_b64decode(key)
        except Exception:
            decoded_key = key

        if len(decoded_key) < 16:
            return False, "Key too short (minimum 16 bytes)"

        # Check for low entropy (simple patterns)
        if decoded_key == decoded_key[0:1] * len(decoded_key):
            return False, "Key contains repetitive pattern"

        return True, "Key strength acceptable"

    def rotate_key(self, new_password: Optional[str] = None) -> bytes:
        """Rotate to a new master key."""
        logger.info("Starting key rotation")

        # Generate new key
        new_master_key = self.generate_master_key(new_password)

        # Save new key
        self.save_master_key(new_password)

        logger.info("Key rotation completed")
        return new_master_key

    def validate_key_strength(self, key: bytes) -> Tuple[bool, str]:
        """
        Validate key strength and provide feedback.

        Returns:
            Tuple[bool, str]: (is_strong, feedback_message)
        """
        if len(key) < 16:
            return False, "Key too short (minimum 16 bytes)"

        # Check for low entropy (simple patterns)
        if key == key[0:1] * len(key):
            return False, "Key contains repetitive pattern"

        return True, "Key strength acceptable"


class InputValidator:
    """Comprehensive input validation for security."""

    MAX_TEXT_LENGTH = 10000
    MAX_REFLECTION_LENGTH = 5000
    ALLOWED_CHARACTERS = set(
        "abcdefghijklmnopqrstuvwxyz"
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        "0123456789"
        " .,!?-()[]{}:;\"'\n\t_"
        "áéíóúàèìòùâêîôûäëïöüÿñç"
        "ÁÉÍÓÚÀÈÌÒÙÂÊÎÔÛÄËÏÖÜŸÑÇ"
    )

    @classmethod
    def validate_reflection_text(cls, text: str) -> str:
        """
        Validate reflection text for security and safety.

        Args:
            text: The reflection text to validate

        Returns:
            str: The validated and sanitized text

        Raises:
            ValidationError: If validation fails
        """
        if not text:
            raise ValidationError("Reflection text cannot be empty")

        if len(text) > cls.MAX_REFLECTION_LENGTH:
            raise ValidationError(
                f"Reflection text too long ({len(text)} > {cls.MAX_REFLECTION_LENGTH})"
            )

        # Check for potentially harmful characters
        invalid_chars = set(text) - cls.ALLOWED_CHARACTERS
        if invalid_chars:
            raise ValidationError(
                f"Reflection contains invalid characters: {''.join(sorted(invalid_chars))}"
            )

        # Check for SQL injection patterns (basic)
        dangerous_patterns = [
            "DROP",
            "DELETE",
            "UPDATE",
            "INSERT",
            "ALTER",
            "UNION",
            "SELECT",
            "SCRIPT",
            "JAVASCRIPT",
            "<script",
            "<?php",
            "<%",
            "<asp",
        ]

        text_upper = text.upper()
        for pattern in dangerous_patterns:
            if pattern in text_upper:
                raise ValidationError(
                    f"Potentially dangerous content detected: {pattern}"
                )

        return text.strip()

    @classmethod
    def validate_filename(cls, filename: str) -> str:
        """Validate filename for security."""
        if not filename:
            raise ValidationError("Filename cannot be empty")

        # Check for path traversal attempts
        if ".." in filename or "/" in filename or "\\" in filename:
            raise ValidationError("Invalid filename: path traversal detected")

        # Check for invalid characters
        invalid_chars = set('<>:"|?*')
        if any(char in filename for char in invalid_chars):
            raise ValidationError("Invalid filename: contains invalid characters")

        # Check for dangerous extensions
        dangerous_ext = [".exe", ".bat", ".cmd", ".sh", ".py", ".js"]
        if any(filename.lower().endswith(ext) for ext in dangerous_ext):
            raise ValidationError(f"Dangerous file extension not allowed: {filename}")

        return filename

    @classmethod
    def sanitize_output(cls, text: str) -> str:
        """Sanitize output text to prevent injection attacks."""
        if not text:
            return ""

        # Basic HTML/XML escaping
        text = text.replace("&", "&amp;")
        text = text.replace("<", "&lt;")
        text = text.replace(">", "&gt;")
        text = text.replace('"', "&quot;")
        text = text.replace("'", "&#x27;")

        return text


class SecureRandom:
    """Secure random number generation utilities."""

    @staticmethod
    def generate_session_id(length: int = 32) -> str:
        """Generate a secure session ID."""
        return secrets.token_hex(length)

    @staticmethod
    def generate_nonce(length: int = 16) -> bytes:
        """Generate a cryptographic nonce."""
        return secrets.token_bytes(length)

    @staticmethod
    def generate_password(length: int = 16) -> str:
        """Generate a secure random password with guaranteed character types."""
        if length < 4:
            raise ValueError("Password length must be at least 4 characters")

        # Ensure at least one character from each type
        lowers = "abcdefghijklmnopqrstuvwxyz"
        uppers = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        digits = "0123456789"
        specials = "!@#$%^&*"

        # Start with one guaranteed character from each type
        password = [
            secrets.choice(lowers),
            secrets.choice(uppers),
            secrets.choice(digits),
            secrets.choice(specials),
        ]

        # Fill the rest randomly
        all_chars = lowers + uppers + digits + specials
        for _ in range(length - 4):
            password.append(secrets.choice(all_chars))

        # Shuffle the password
        secrets.SystemRandom().shuffle(password)

        return "".join(password)


def secure_delete_file(file_path: Path) -> None:
    """Securely delete a file by overwriting it first."""
    if not file_path.exists():
        return

    try:
        # Get file size
        size = file_path.stat().st_size

        # Overwrite with random data
        with open(file_path, "wb") as f:
            f.write(secrets.token_bytes(size))

        # Delete the file
        file_path.unlink()

        logger.info(f"Securely deleted file: {file_path}")

    except Exception as e:
        logger.warning(f"Failed to securely delete {file_path}: {e}")
        # Fallback to regular delete
        try:
            file_path.unlink()
        except Exception:
            pass


def main():
    """Demonstrate security features."""
    print("=== InnerBoard Security Features Demo ===")

    # Key management demo
    print("\n1. Key Management:")
    key_manager = SecureKeyManager()

    # Generate and validate key
    master_key = key_manager.generate_master_key()
    is_strong, feedback = key_manager.validate_key_strength(master_key)
    print(f"Generated key strength: {'Strong' if is_strong else 'Weak'} - {feedback}")

    # Input validation demo
    print("\n2. Input Validation:")
    validator = InputValidator()

    test_texts = [
        "This is a normal reflection.",
        "DROP TABLE reflections;",  # Should fail
        "Normal text with <script>alert('xss')</script>",  # Should fail
        "",  # Should fail
        "A" * 6000,  # Should fail (too long)
    ]

    for text in test_texts:
        try:
            validated = validator.validate_reflection_text(text)
            print(f"✓ Valid: '{text[:50]}...'")
        except ValidationError as e:
            print(f"✗ Invalid: {e}")

    # Secure random demo
    print("\n3. Secure Random Generation:")
    session_id = SecureRandom.generate_session_id()
    password = SecureRandom.generate_password()
    print(f"Session ID: {session_id[:16]}...")
    print(f"Generated password: {password}")

    print("\nSecurity demo complete!")


if __name__ == "__main__":
    main()
