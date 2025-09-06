"""
Utility functions and helpers for InnerBoard-local.
Provides common functionality used across modules.
"""

import re
import json
from typing import Any, Dict, List, Optional, Union, TypeVar, Callable
from pathlib import Path
from datetime import datetime
from functools import wraps
import hashlib

from app.config import config
from app.logging_config import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


def safe_json_loads(json_str: str, default: Any = None) -> Any:
    """
    Safely parse JSON string with fallback.

    Args:
        json_str: JSON string to parse
        default: Default value if parsing fails

    Returns:
        Parsed JSON data or default value
    """
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning(f"Failed to parse JSON: {e}")
        return default


def safe_json_dumps(data: Any, default: str = "{}") -> str:
    """
    Safely serialize data to JSON with fallback.

    Args:
        data: Data to serialize
        default: Default JSON string if serialization fails

    Returns:
        JSON string or default value
    """
    try:
        return json.dumps(data, indent=2, default=str)
    except (TypeError, ValueError) as e:
        logger.warning(f"Failed to serialize to JSON: {e}")
        return default


def sanitize_filename(filename: str, replacement: str = "_") -> str:
    """
    Sanitize filename by removing/replacing invalid characters.

    Args:
        filename: Original filename
        replacement: Character to replace invalid chars with

    Returns:
        Sanitized filename
    """
    # Remove or replace invalid characters
    invalid_chars = r'[<>:"/\\|?*]'
    sanitized = re.sub(invalid_chars, replacement, filename)

    # Remove leading/trailing dots and spaces
    sanitized = sanitized.strip(". ")

    # Ensure not empty
    if not sanitized:
        sanitized = "unnamed"

    # Limit length
    if len(sanitized) > 255:
        name, ext = sanitized.rsplit(".", 1) if "." in sanitized else (sanitized, "")
        if ext:
            sanitized = name[: 255 - len(ext) - 1] + "." + ext
        else:
            sanitized = name[:255]

    return sanitized


def format_timestamp(
    dt: Union[str, datetime, None], fmt: str = "%Y-%m-%d %H:%M:%S"
) -> str:
    """
    Format timestamp for display.

    Args:
        dt: Datetime object or string
        fmt: Format string

    Returns:
        Formatted timestamp string
    """
    if dt is None:
        return "Unknown"

    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
        except ValueError:
            return dt  # Return as-is if parsing fails

    if isinstance(dt, datetime):
        return dt.strftime(fmt)

    return str(dt)


def calculate_hash(data: Union[str, bytes], algorithm: str = "sha256") -> str:
    """
    Calculate hash of data.

    Args:
        data: Data to hash
        algorithm: Hash algorithm to use

    Returns:
        Hexadecimal hash string
    """
    if isinstance(data, str):
        data = data.encode("utf-8")

    hasher = hashlib.new(algorithm)
    hasher.update(data)
    return hasher.hexdigest()


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Truncate text to maximum length.

    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated

    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text

    return text[: max_length - len(suffix)] + suffix


def format_reflection_preview(text: str, max_length: int = 80) -> str:
    """
    Format reflection text for display preview.

    Args:
        text: The reflection text
        max_length: Maximum preview length

    Returns:
        Formatted preview text
    """
    if not text:
        return ""

    # Get first line and clean it up
    first_line = text.split("\n")[0].strip()

    # Truncate if too long
    if len(first_line) > max_length:
        first_line = first_line[: max_length - 3] + "..."

    return first_line


def retry_on_failure(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
) -> Callable:
    """
    Decorator to retry function on failure.

    Args:
        max_attempts: Maximum number of attempts
        delay: Initial delay between attempts
        backoff: Backoff multiplier
        exceptions: Tuple of exceptions to catch

    Returns:
        Decorated function
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            current_delay = delay
            last_exception = None

            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        logger.warning(
                            f"Attempt {attempt + 1} failed for {func.__name__}: {e}. "
                            f"Retrying in {current_delay}s..."
                        )
                        import time

                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(
                            f"All {max_attempts} attempts failed for {func.__name__}: {e}"
                        )

            raise last_exception

        return wrapper

    return decorator


def validate_email(email: str) -> bool:
    """
    Basic email validation.

    Args:
        email: Email address to validate

    Returns:
        True if valid, False otherwise
    """
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def ensure_directory(path: Union[str, Path]) -> Path:
    """
    Ensure directory exists, creating it if necessary.

    Args:
        path: Directory path

    Returns:
        Path object for the directory
    """
    path_obj = Path(path)
    path_obj.mkdir(parents=True, exist_ok=True)
    return path_obj


def get_file_size_mb(file_path: Union[str, Path]) -> float:
    """
    Get file size in megabytes.

    Args:
        file_path: Path to file

    Returns:
        File size in MB
    """
    path_obj = Path(file_path)
    if not path_obj.exists():
        return 0.0

    size_bytes = path_obj.stat().st_size
    return size_bytes / (1024 * 1024)


def is_valid_json(json_str: str) -> bool:
    """
    Check if string is valid JSON.

    Args:
        json_str: String to validate

    Returns:
        True if valid JSON, False otherwise
    """
    try:
        json.loads(json_str)
        return True
    except (json.JSONDecodeError, TypeError):
        return False


def merge_dicts(*dicts: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge multiple dictionaries.

    Args:
        *dicts: Dictionaries to merge

    Returns:
        Merged dictionary
    """
    result = {}
    for d in dicts:
        if d:
            result.update(d)
    return result


def deep_get(dictionary: Dict[str, Any], keys: List[str], default: Any = None) -> Any:
    """
    Get nested dictionary value safely.

    Args:
        dictionary: Dictionary to search
        keys: List of keys to traverse
        default: Default value if not found

    Returns:
        Value at nested key or default
    """
    current = dictionary

    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default

    return current


class Timer:
    """Simple timer context manager."""

    def __init__(self, name: str = "Operation"):
        self.name = name
        self.start_time = None

    def __enter__(self):
        self.start_time = datetime.now()
        logger.debug(f"Starting {self.name}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration = datetime.now() - self.start_time
            logger.debug(f"{self.name} completed in {duration.total_seconds():.2f}s")


def clean_terminal_log(log_content: str) -> str:
    """
    Clean terminal log by removing line numbers and ANSI escape codes.
    Args:
        log_content: The raw content of the log file.
    Returns:
        Cleaned text.
    """
    import re
    from typing import List
    lines = log_content.splitlines()
    cleaned_lines: List[str] = []
    for line in lines:
        if '|' in line:
            parts = line.split('|', 1)
            if len(parts) == 2:
                content = parts[1]
            else:
                content = line
        else:
            content = line
        content = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', content)
        content = re.sub(r'[\x00-\x1f\x7f]', '', content)
        content = content.strip()
        if content:
            cleaned_lines.append(content)
    print('\n'.join(cleaned_lines))
    return '\n'.join(cleaned_lines)


def main():
    """Demonstrate utility functions."""
    print("=== InnerBoard Utilities Demo ===")

    # Test JSON functions
    print("\n1. JSON Functions:")
    test_data = {"key": "value", "number": 42}
    json_str = safe_json_dumps(test_data)
    print(f"JSON: {json_str}")
    parsed = safe_json_loads(json_str)
    print(f"Parsed: {parsed}")

    # Test filename sanitization
    print("\n2. Filename Sanitization:")
    bad_filename = "file<>with:bad\\chars?.txt"
    clean_filename = sanitize_filename(bad_filename)
    print(f"Original: {bad_filename}")
    print(f"Clean: {clean_filename}")

    # Test text truncation
    print("\n3. Text Truncation:")
    long_text = "This is a very long text that should be truncated to a reasonable length for display purposes."
    short_text = truncate_text(long_text, max_length=50)
    print(f"Original: {long_text}")
    print(f"Truncated: {short_text}")

    # Test hash calculation
    print("\n4. Hash Calculation:")
    test_string = "Hello, World!"
    hash_value = calculate_hash(test_string)
    print(f"String: {test_string}")
    print(f"SHA256: {hash_value}")

    # Test timer
    print("\n5. Timer:")
    with Timer("Demo operation"):
        import time

        time.sleep(0.1)
        print("  Performing some work...")

    print("\nUtilities demo complete!")


if __name__ == "__main__":
    main()
