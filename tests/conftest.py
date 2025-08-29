"""
Pytest configuration and fixtures for InnerBoard-local tests.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock
from typing import Generator

from app.config import config
from app.storage import EncryptedVault
from app.security import SecureKeyManager
from app.cache import cache_manager


@pytest.fixture(scope="session")
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for the test session."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def temp_db_path(temp_dir: Path) -> Path:
    """Create a temporary database path for testing."""
    return temp_dir / "test.db"


@pytest.fixture
def temp_key_path(temp_dir: Path) -> Path:
    """Create a temporary key path for testing."""
    return temp_dir / "test.key"


@pytest.fixture
def secure_key_manager(temp_key_path: Path) -> SecureKeyManager:
    """Create a secure key manager for testing."""
    return SecureKeyManager(temp_key_path)


@pytest.fixture
def master_key(secure_key_manager: SecureKeyManager) -> bytes:
    """Generate a master key for testing."""
    return secure_key_manager.generate_master_key("test_password")


@pytest.fixture
def encrypted_vault(temp_db_path: Path, master_key: bytes) -> EncryptedVault:
    """Create an encrypted vault for testing."""
    vault = EncryptedVault(str(temp_db_path), master_key)
    yield vault
    vault.close()


@pytest.fixture(autouse=True)
def clear_caches():
    """Clear all caches before each test."""
    cache_manager.clear_all()


@pytest.fixture
def mock_ollama_client():
    """Mock Ollama client for testing."""
    mock_client = MagicMock()
    mock_response = {
        "message": {
            "content": '{"key_points": ["Test point"], "blockers": ["Test blocker"], "resources_needed": ["Test resource"], "confidence_delta": 0.0}'
        }
    }
    mock_client.chat.return_value = mock_response
    mock_client.list.return_value = {"models": [{"name": "test-model"}]}
    return mock_client


@pytest.fixture
def sample_reflection() -> str:
    """Sample reflection text for testing."""
    return "I struggled with the new authentication system today. The documentation was unclear and I couldn't get the JWT tokens to validate properly. I feel like I'm falling behind on my tasks."


@pytest.fixture
def invalid_reflection_texts() -> list:
    """Invalid reflection texts for validation testing."""
    return [
        "",  # Empty
        "A" * 10000,  # Too long
        "DROP TABLE users;",  # SQL injection
        "<script>alert('xss')</script>",  # XSS
        "SELECT * FROM reflections;",  # SQL injection
        "../../../etc/passwd",  # Path traversal
    ]


@pytest.fixture
def valid_reflection_texts() -> list:
    """Valid reflection texts for testing."""
    return [
        "I learned about Kubernetes ingress controllers today.",
        "Had trouble with the authentication service configuration.",
        "Great progress on the database optimization task!",
        "Working with the team has been very productive.",
        "I need to schedule a meeting with my manager to discuss blockers.",
    ]


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for async tests."""
    import asyncio

    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# Custom markers
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "security: mark test as security-related")
    config.addinivalue_line("markers", "performance: mark test as performance-related")
    config.addinivalue_line("markers", "unit: mark test as unit test")


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on test names."""
    for item in items:
        # Add markers based on test file names
        if "security" in str(item.fspath):
            item.add_marker(pytest.mark.security)
        elif "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "cache" in str(item.fspath):
            item.add_marker(pytest.mark.performance)
        else:
            item.add_marker(pytest.mark.unit)


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Set up test environment."""
    # Disable logging during tests unless explicitly enabled
    import logging

    logging.getLogger("innerboard").setLevel(logging.WARNING)

    # Clean up any leftover test files
    yield

    # Cleanup after all tests
    cache_manager.clear_all()
