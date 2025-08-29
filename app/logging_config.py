"""
Logging configuration for InnerBoard-local.
Provides structured logging with configurable levels and outputs.
"""

import logging
import logging.handlers
from pathlib import Path
from typing import Optional
from app.config import config


class InnerBoardLogger:
    """Centralized logging configuration for InnerBoard-local."""

    def __init__(self):
        self._configured = False

    def configure(
        self, level: Optional[str] = None, log_file: Optional[Path] = None
    ) -> None:
        """Configure logging with the specified level and file."""
        if self._configured:
            return

        level = level or config.log_level
        log_file = log_file or config.log_file

        # Create logger
        logger = logging.getLogger("innerboard")
        logger.setLevel(getattr(logging, level.upper()))

        # Remove any existing handlers
        logger.handlers.clear()

        # Create formatter
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, level.upper()))
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # File handler (if specified)
        if log_file:
            try:
                log_file.parent.mkdir(parents=True, exist_ok=True)
                file_handler = logging.handlers.RotatingFileHandler(
                    log_file, maxBytes=10 * 1024 * 1024, backupCount=5  # 10MB
                )
                file_handler.setLevel(getattr(logging, level.upper()))
                file_handler.setFormatter(formatter)
                logger.addHandler(file_handler)
            except (OSError, IOError) as e:
                logger.warning(f"Could not create log file {log_file}: {e}")

        # Prevent duplicate messages from propagating
        logger.propagate = False

        self._configured = True
        logger.info(f"Logging configured at level {level}")

    def get_logger(self, name: str) -> logging.Logger:
        """Get a logger instance for the specified module/component."""
        if not self._configured:
            self.configure()
        return logging.getLogger(f"innerboard.{name}")


# Global logger instance
logger_instance = InnerBoardLogger()


def get_logger(name: str) -> logging.Logger:
    """Convenience function to get a logger for a specific module."""
    return logger_instance.get_logger(name)


def setup_logging() -> None:
    """Initialize logging system."""
    logger_instance.configure()


# Initialize on import
setup_logging()
