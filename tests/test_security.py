"""
Tests for security features.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from cryptography.fernet import Fernet

from app.security import (
    SecureKeyManager,
    InputValidator,
    SecureRandom,
    secure_delete_file,
)
from app.exceptions import KeyNotFoundError, InvalidKeyError, ValidationError


class TestSecureKeyManager:
    """Test secure key management functionality."""

    def test_generate_master_key(self):
        """Test master key generation."""
        key_manager = SecureKeyManager()

        # Test with random key
        key1 = key_manager.generate_master_key()
        assert isinstance(key1, bytes)
        assert len(key1) == 44  # Base64 encoded AES-256 key size

        # Test with password
        key2 = key_manager.generate_master_key("test_password")
        assert isinstance(key2, bytes)
        assert key1 != key2  # Should be different

    def test_save_and_load_key(self):
        """Test key saving and loading."""
        with tempfile.TemporaryDirectory() as temp_dir:
            key_path = Path(temp_dir) / "test_key.json"
            key_manager = SecureKeyManager(key_path)

            # Generate and save key
            master_key = key_manager.generate_master_key("test_password")
            key_manager.save_master_key("test_password")

            # Load key with correct password
            new_key_manager = SecureKeyManager(key_path)
            loaded_key = new_key_manager.load_master_key("test_password")

            assert loaded_key == master_key

    def test_invalid_password(self):
        """Test loading key with invalid password."""
        with tempfile.TemporaryDirectory() as temp_dir:
            key_path = Path(temp_dir) / "test_key.json"
            key_manager = SecureKeyManager(key_path)

            # Generate and save key
            key_manager.generate_master_key("correct_password")
            key_manager.save_master_key("correct_password")

            # Try to load with wrong password
            new_key_manager = SecureKeyManager(key_path)
            with pytest.raises(InvalidKeyError):
                new_key_manager.load_master_key("wrong_password")

    def test_key_strength_validation(self):
        """Test key strength validation."""
        key_manager = SecureKeyManager()

        # Test strong key
        strong_key = b"0" * 31 + b"1"  # 32 bytes, not repetitive
        is_strong, feedback = key_manager.validate_key_strength(strong_key)
        assert is_strong
        assert "acceptable" in feedback

        # Test weak key (too short)
        weak_key = b"short"
        is_strong, feedback = key_manager.validate_key_strength(weak_key)
        assert not is_strong
        assert "too short" in feedback

        # Test repetitive key
        repetitive_key = b"A" * 32
        is_strong, feedback = key_manager.validate_key_strength(repetitive_key)
        assert not is_strong
        assert "repetitive" in feedback

    def test_missing_key_file(self):
        """Test loading non-existent key file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            key_path = Path(temp_dir) / "nonexistent_key.json"
            key_manager = SecureKeyManager(key_path)

            with pytest.raises(KeyNotFoundError):
                key_manager.load_master_key()


class TestInputValidator:
    """Test input validation functionality."""

    def test_validate_reflection_text_valid(self):
        """Test validation of valid reflection text."""
        valid_texts = [
            "This is a normal reflection.",
            "I had trouble with Kubernetes today. The pods kept crashing.",
            "Great progress on the authentication module!",
            "Working with the team has been very productive.",
        ]

        for text in valid_texts:
            validated = InputValidator.validate_reflection_text(text)
            assert validated == text.strip()

    def test_validate_reflection_text_invalid(self):
        """Test validation of invalid reflection text."""
        invalid_texts = [
            "",  # Empty
            "A" * 6000,  # Too long
            "DROP TABLE users;",  # SQL injection
            "<script>alert('xss')</script>",  # XSS
            "File: C:\\Windows\\system32",  # Path traversal
        ]

        for text in invalid_texts:
            with pytest.raises(ValidationError):
                InputValidator.validate_reflection_text(text)

    def test_validate_filename(self):
        """Test filename validation."""
        # Valid filenames
        valid_names = [
            "normal_file.txt",
            "file-with-dashes.txt",
            "file_with_underscores.txt",
            "file123.txt",
        ]

        for name in valid_names:
            validated = InputValidator.validate_filename(name)
            assert validated == name

        # Invalid filenames
        invalid_names = [
            "",  # Empty
            "../../../etc/passwd",  # Path traversal
            "file<with>bad:chars?.txt",  # Invalid chars
            "exe_file.exe",  # Dangerous extension
        ]

        for name in invalid_names:
            with pytest.raises(ValidationError):
                InputValidator.validate_filename(name)

    def test_sanitize_output(self):
        """Test output sanitization."""
        dangerous_input = '<script>alert("xss")</script> & "quotes"'
        sanitized = InputValidator.sanitize_output(dangerous_input)

        # HTML entities should be encoded
        assert "<script>" not in sanitized
        assert "</script>" not in sanitized
        assert "&amp;" in sanitized  # Standalone & should be encoded
        assert "&lt;" in sanitized  # < should be encoded
        assert "&gt;" in sanitized  # > should be encoded
        assert "&quot;" in sanitized  # " should be encoded
        # The standalone & in the middle should be encoded to &amp;
        assert (
            sanitized
            == "&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt; &amp; &quot;quotes&quot;"
        )


class TestSecureRandom:
    """Test secure random generation."""

    def test_generate_session_id(self):
        """Test session ID generation."""
        session_id = SecureRandom.generate_session_id()
        assert isinstance(session_id, str)
        assert len(session_id) == 64  # 32 bytes * 2 hex chars

        # Test custom length
        short_id = SecureRandom.generate_session_id(16)
        assert len(short_id) == 32  # 16 bytes * 2 hex chars

    def test_generate_nonce(self):
        """Test nonce generation."""
        nonce = SecureRandom.generate_nonce()
        assert isinstance(nonce, bytes)
        assert len(nonce) == 16

        # Test custom length
        custom_nonce = SecureRandom.generate_nonce(32)
        assert len(custom_nonce) == 32

    def test_generate_password(self):
        """Test password generation."""
        password = SecureRandom.generate_password()
        assert isinstance(password, str)
        assert len(password) == 16

        # Check password contains expected character types
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(c in "!@#$%^&*" for c in password)

        assert has_upper and has_lower and has_digit and has_special

        # Test custom length
        short_password = SecureRandom.generate_password(8)
        assert len(short_password) == 8


class TestSecureDelete:
    """Test secure file deletion."""

    def test_secure_delete_existing_file(self):
        """Test secure deletion of existing file."""
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(b"secret data")
            temp_path = Path(temp_file.name)

        assert temp_path.exists()

        # Secure delete
        secure_delete_file(temp_path)

        assert not temp_path.exists()

    def test_secure_delete_nonexistent_file(self):
        """Test secure deletion of non-existent file."""
        nonexistent = Path("/tmp/nonexistent_file_12345")
        assert not nonexistent.exists()

        # Should not raise error
        secure_delete_file(nonexistent)


class TestIntegration:
    """Integration tests for security features."""

    def test_full_key_lifecycle(self):
        """Test complete key generation, storage, and retrieval cycle."""
        with tempfile.TemporaryDirectory() as temp_dir:
            key_path = Path(temp_dir) / "vault_key.json"

            # Generate key
            key_manager = SecureKeyManager(key_path)
            original_key = key_manager.generate_master_key("test_password")

            # Save key
            key_manager.save_master_key("test_password")

            # Load key
            new_manager = SecureKeyManager(key_path)
            loaded_key = new_manager.load_master_key("test_password")

            assert loaded_key == original_key

    def test_input_validation_pipeline(self):
        """Test input validation in a pipeline."""
        # Valid input
        valid_text = "I learned about Kubernetes ingress controllers today."
        validated = InputValidator.validate_reflection_text(valid_text)
        sanitized = InputValidator.sanitize_output(validated)

        assert validated == valid_text
        assert sanitized == valid_text

        # Invalid input should be caught early
        invalid_text = "SELECT * FROM users; <script>hack()</script>"
        with pytest.raises(ValidationError):
            InputValidator.validate_reflection_text(invalid_text)


if __name__ == "__main__":
    pytest.main([__file__])
