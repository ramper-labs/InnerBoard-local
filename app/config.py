"""
Configuration management for InnerBoard-local.
Centralizes all configuration options with environment variable support.
"""

import os
from pathlib import Path
from typing import Optional
from dataclasses import dataclass
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


@dataclass
class AppConfig:
    """Application configuration with validation."""

    # Database
    db_path: Path = Path("vault.db")
    key_path: Path = Path("vault.key")

    # LLM Configuration
    ollama_model: str = "gpt-oss:20b"
    ollama_host: str = "http://localhost:11434"
    ollama_timeout: int = 30
    max_tokens: int = 512

    # Model Parameters
    temperature: float = 0.7
    top_p: float = 0.95

    # Network Safety
    allow_loopback: bool = True
    allowed_ports: tuple = (11434,)

    # Logging
    log_level: str = "INFO"
    log_file: Optional[Path] = None

    # Performance
    enable_caching: bool = True
    cache_ttl_seconds: int = 3600  # 1 hour

    @classmethod
    def from_env(cls) -> "AppConfig":
        """Create configuration from environment variables."""
        return cls(
            # Database
            db_path=Path(os.getenv("INNERBOARD_DB_PATH", "vault.db")),
            key_path=Path(os.getenv("INNERBOARD_KEY_PATH", "vault.key")),
            # LLM Configuration
            ollama_model=os.getenv("OLLAMA_MODEL", "gpt-oss:20b"),
            ollama_host=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
            ollama_timeout=int(os.getenv("OLLAMA_TIMEOUT", "30")),
            max_tokens=int(os.getenv("MAX_TOKENS", "512")),
            # Model Parameters
            temperature=float(os.getenv("MODEL_TEMPERATURE", "0.7")),
            top_p=float(os.getenv("MODEL_TOP_P", "0.95")),
            # Network Safety
            allow_loopback=os.getenv("ALLOW_LOOPBACK", "true").lower() == "true",
            allowed_ports=tuple(
                map(int, os.getenv("ALLOWED_PORTS", "11434").split(","))
            ),
            # Logging
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            log_file=Path(os.getenv("LOG_FILE")) if os.getenv("LOG_FILE") else None,
            # Performance
            enable_caching=os.getenv("ENABLE_CACHING", "true").lower() == "true",
            cache_ttl_seconds=int(os.getenv("CACHE_TTL_SECONDS", "3600")),
        )

    def validate(self) -> None:
        """Validate configuration values."""
        if not 0.0 <= self.temperature <= 2.0:
            raise ValueError(
                f"Temperature must be between 0.0 and 2.0, got {self.temperature}"
            )

        if not 0.0 <= self.top_p <= 1.0:
            raise ValueError(f"Top-p must be between 0.0 and 1.0, got {self.top_p}")

        if self.max_tokens <= 0:
            raise ValueError(f"Max tokens must be positive, got {self.max_tokens}")

        if self.ollama_timeout <= 0:
            raise ValueError(f"Timeout must be positive, got {self.ollama_timeout}")

        if self.cache_ttl_seconds < 0:
            raise ValueError(
                f"Cache TTL must be non-negative, got {self.cache_ttl_seconds}"
            )

        valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.log_level.upper() not in valid_log_levels:
            raise ValueError(
                f"Log level must be one of {valid_log_levels}, got {self.log_level}"
            )


# Global configuration instance
config = AppConfig.from_env()

# Validate on import
try:
    config.validate()
except ValueError as e:
    print(f"Configuration error: {e}")
    raise
