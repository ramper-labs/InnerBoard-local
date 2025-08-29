"""
Custom exceptions for InnerBoard-local application.
Provides structured error handling throughout the codebase.
"""


class InnerBoardError(Exception):
    """Base exception for all InnerBoard-related errors."""

    pass


class ConfigurationError(InnerBoardError):
    """Raised when there's a configuration-related error."""

    pass


class DatabaseError(InnerBoardError):
    """Raised when there's a database-related error."""

    pass


class EncryptionError(InnerBoardError):
    """Raised when there's an encryption/decryption error."""

    pass


class LLMError(InnerBoardError):
    """Raised when there's an LLM-related error."""

    pass


class NetworkError(InnerBoardError):
    """Raised when there's a network-related error."""

    pass


class ValidationError(InnerBoardError):
    """Raised when there's a data validation error."""

    pass


class FileOperationError(InnerBoardError):
    """Raised when there's a file operation error."""

    pass


# Specific error subclasses for more granular error handling


class KeyNotFoundError(EncryptionError):
    """Raised when encryption key is not found."""

    pass


class InvalidKeyError(EncryptionError):
    """Raised when encryption key is invalid."""

    pass


class ModelNotAvailableError(LLMError):
    """Raised when the specified LLM model is not available."""

    pass


class ModelTimeoutError(LLMError):
    """Raised when LLM request times out."""

    pass


class PromptLoadError(InnerBoardError):
    """Raised when system prompts cannot be loaded."""

    pass


class JSONParseError(ValidationError):
    """Raised when JSON parsing fails."""

    pass


class SchemaValidationError(ValidationError):
    """Raised when data doesn't match expected schema."""

    pass


class NetworkAccessBlocked(NetworkError):
    """Raised when network access is blocked but attempted."""

    pass
