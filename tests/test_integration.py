"""
Integration tests for InnerBoard-local system.
Tests the interaction between multiple components.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import json

from app.config import config
from app.storage import EncryptedVault, generate_key, load_key
from app.llm import LocalLLM
from app.advice import AdviceService
from app.safety import no_network
from app.cache import cache_manager
from app.security import SecureKeyManager, InputValidator
from app.exceptions import InnerBoardError


class TestFullWorkflow:
    """Test complete workflow from reflection to advice."""

    def test_complete_reflection_workflow(self):
        """Test the complete workflow: reflection → storage → analysis → advice."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test.db"
            key_path = Path(temp_dir) / "test.key"

            # Generate secure key
            key_manager = SecureKeyManager(key_path)
            master_key = key_manager.generate_master_key("test_password")
            key_manager.save_master_key("test_password")

            # Create vault
            vault = EncryptedVault(str(db_path), master_key)

            # Add reflection
            test_reflection = "I struggled with Kubernetes networking today. The ingress controller wasn't routing traffic correctly."
            reflection_id = vault.add_reflection(test_reflection)

            # Verify storage
            stored_reflection = vault.get_reflection(reflection_id)
            assert stored_reflection is not None
            stored_text, created_at, updated_at = stored_reflection
            assert stored_text == test_reflection

            # Test reflection listing
            all_reflections = vault.get_all_reflections()
            assert len(all_reflections) == 1
            assert all_reflections[0][1] == test_reflection

            vault.close()

    @patch("app.llm.LocalLLM._check_model_availability")
    @patch("app.llm.ConnectionPool")
    @patch("app.llm.Client")
    def test_ai_workflow_with_mocks(
        self, mock_client_class, mock_connection_pool_class, mock_check_availability
    ):
        """Test AI workflow with mocked Ollama client."""
        # Mock model availability check to return True
        mock_check_availability.return_value = True

        # Mock Ollama client
        mock_client = MagicMock()
        mock_response = {
            "message": {
                "content": '{"key_points": ["Kubernetes networking issues"], "blockers": ["ingress routing"], "resources_needed": ["documentation"], "confidence_delta": -0.3}'
            }
        }
        mock_client.chat.return_value = mock_response
        mock_client_class.return_value = mock_client

        # Mock connection pool
        mock_pool = MagicMock()
        mock_pool.get.return_value = mock_client
        mock_connection_pool_class.return_value = mock_pool

        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test.db"
            key_path = Path(temp_dir) / "test.key"

            # Generate and save key
            key_manager = SecureKeyManager(key_path)
            master_key = key_manager.generate_master_key()
            key_manager.save_master_key()

            # Create vault and LLM
            vault = EncryptedVault(str(db_path), master_key)
            llm = LocalLLM()

            # Create advice service
            service = AdviceService(llm)

            # Test SRE (structured reflection extraction)
            test_text = "I can't get the Kubernetes ingress to work properly."
            sre_result = service.get_structured_reflection(test_text)

            assert sre_result.key_points == ["Kubernetes networking issues"]
            assert sre_result.blockers == ["ingress routing"]
            assert sre_result.resources_needed == ["documentation"]
            assert sre_result.confidence_delta == -0.3

            # Verify mock was called
            mock_client.chat.assert_called()

            vault.close()

    def test_security_integration(self):
        """Test security features working together."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test.db"
            key_path = Path(temp_dir) / "test.key"

            # Test input validation
            valid_text = "This is a valid reflection about my work."
            validated = InputValidator.validate_reflection_text(valid_text)
            assert validated == valid_text

            # Test invalid input
            with pytest.raises(Exception):  # ValidationError
                InputValidator.validate_reflection_text("DROP TABLE users;")

            # Test key management
            key_manager = SecureKeyManager(key_path)
            master_key = key_manager.generate_master_key("secure_password")
            key_manager.save_master_key("secure_password")

            # Test key loading
            loaded_key = key_manager.load_master_key("secure_password")
            assert loaded_key == master_key

            # Test vault with secure key
            vault = EncryptedVault(str(db_path), master_key)
            reflection_id = vault.add_reflection(valid_text)

            retrieved = vault.get_reflection(reflection_id)
            assert retrieved is not None
            assert retrieved[0] == valid_text

            vault.close()


class TestPerformanceOptimization:
    """Test performance optimization features."""

    def test_caching_integration(self):
        """Test caching system integration."""
        # Clear caches
        cache_manager.clear_all()

        # Test with cached function
        from app.cache import cached_response

        call_count = 0

        @cached_response(ttl=10)
        def mock_api_call(endpoint):
            nonlocal call_count
            call_count += 1
            return f"data_from_{endpoint}"

        # First call
        result1 = mock_api_call("users")
        assert call_count == 1

        # Second call (should use cache)
        result2 = mock_api_call("users")
        assert result1 == result2
        assert call_count == 1  # Should not increase

        # Different endpoint
        result3 = mock_api_call("posts")
        assert call_count == 2

    def test_connection_pooling(self):
        """Test connection pooling in LLM."""
        from app.llm import LocalLLM
        from app.cache import ConnectionPool

        # Mock client factory
        call_count = 0

        def mock_factory():
            nonlocal call_count
            call_count += 1
            return MagicMock()

        # Replace the pool
        original_pool = LocalLLM._client_pool
        LocalLLM._client_pool = ConnectionPool(mock_factory, max_size=2)

        try:
            # Create multiple LLM instances
            llm1 = LocalLLM()
            assert call_count == 1

            llm2 = LocalLLM()
            assert call_count == 2

            # Test that they use the pool correctly
            assert llm1._client is not None
            assert llm2._client is not None

        finally:
            # Restore original pool
            LocalLLM._client_pool = original_pool


class TestErrorHandling:
    """Test error handling across components."""

    def test_storage_error_handling(self):
        """Test storage error handling."""
        # Test with invalid key
        invalid_key = b"too_short"

        with pytest.raises(Exception):  # Should raise validation error
            EncryptedVault("test.db", invalid_key)

    def test_network_error_handling(self):
        """Test network error handling."""
        from app.safety import no_network

        with no_network():
            # This should work (no actual network call)
            pass

    def test_validation_error_handling(self):
        """Test input validation error handling."""
        # Test various invalid inputs
        invalid_inputs = [
            "",  # Empty
            "A" * 10000,  # Too long
            "<script>alert('xss')</script>",  # XSS
            "UNION SELECT * FROM users",  # SQL injection
        ]

        for invalid_input in invalid_inputs:
            with pytest.raises(Exception):  # ValidationError
                InputValidator.validate_reflection_text(invalid_input)


class TestConfigurationIntegration:
    """Test configuration system integration."""

    @patch.dict(
        "os.environ",
        {
            "OLLAMA_MODEL": "test-model",
            "OLLAMA_HOST": "http://test-host:1234",
            "MAX_TOKENS": "100",
            "LOG_LEVEL": "DEBUG",
        },
    )
    def test_config_from_environment(self):
        """Test configuration loading from environment."""
        # Force reload config
        import importlib
        import app.config

        importlib.reload(app.config)
        from app.config import config

        assert config.ollama_model == "test-model"
        assert config.ollama_host == "http://test-host:1234"
        assert config.max_tokens == 100
        assert config.log_level == "DEBUG"

    def test_config_validation(self):
        """Test configuration validation."""
        from app.config import AppConfig

        # Valid config
        valid_config = AppConfig()
        valid_config.validate()  # Should not raise

        # Invalid temperature
        invalid_config = AppConfig(temperature=3.0)  # Too high
        with pytest.raises(ValueError):
            invalid_config.validate()


class TestDataPersistence:
    """Test data persistence across sessions."""

    def test_data_persistence(self):
        """Test that data persists correctly."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "persistent.db"
            key_path = Path(temp_dir) / "persistent.key"

            # Session 1: Create data
            key_manager = SecureKeyManager(key_path)
            master_key = key_manager.generate_master_key()
            key_manager.save_master_key()

            vault1 = EncryptedVault(str(db_path), master_key)
            reflection_id = vault1.add_reflection("Persistent test reflection")
            vault1.close()

            # Session 2: Load and verify data
            loaded_key = key_manager.load_master_key()
            vault2 = EncryptedVault(str(db_path), loaded_key)

            retrieved = vault2.get_reflection(reflection_id)
            assert retrieved is not None
            assert retrieved[0] == "Persistent test reflection"

            all_reflections = vault2.get_all_reflections()
            assert len(all_reflections) == 1

            vault2.close()

    def test_concurrent_access_simulation(self):
        """Test concurrent access simulation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "concurrent.db"
            key_path = Path(temp_dir) / "concurrent.key"

            # Generate key
            key_manager = SecureKeyManager(key_path)
            master_key = key_manager.generate_master_key()
            key_manager.save_master_key()

            # Simulate multiple processes accessing the same vault
            vaults = []
            reflection_ids = []

            for i in range(3):
                vault = EncryptedVault(str(db_path), master_key)
                reflection_id = vault.add_reflection(f"Reflection {i}")
                reflection_ids.append(reflection_id)
                vaults.append(vault)

            # Close all vaults
            for vault in vaults:
                vault.close()

            # Verify all data is accessible
            final_vault = EncryptedVault(str(db_path), master_key)
            all_reflections = final_vault.get_all_reflections()
            assert len(all_reflections) == 3

            for i, reflection_id in enumerate(reflection_ids):
                retrieved = final_vault.get_reflection(reflection_id)
                assert retrieved is not None
                assert retrieved[0] == f"Reflection {i}"

            final_vault.close()


class TestSystemHealth:
    """Test system health and monitoring."""

    def test_vault_statistics(self):
        """Test vault statistics generation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "stats.db"
            key_path = Path(temp_dir) / "stats.key"

            # Generate key and create vault
            key_manager = SecureKeyManager(key_path)
            master_key = key_manager.generate_master_key()
            key_manager.save_master_key()

            vault = EncryptedVault(str(db_path), master_key)

            # Add some reflections
            for i in range(5):
                vault.add_reflection(f"Test reflection {i}")

            # Get statistics
            stats = vault.get_stats()

            assert stats["total_reflections"] == 5
            assert stats["database_size"] > 0
            assert "oldest_reflection" in stats
            assert "newest_reflection" in stats

            vault.close()

    def test_cache_statistics(self):
        """Test cache statistics."""
        from app.cache import TTLCache

        cache = TTLCache()

        # Add some data
        cache.set("key1", "value1")
        cache.set("key2", "value2")

        # Generate some hits and misses
        cache.get("key1")  # Hit
        cache.get("key1")  # Hit
        cache.get("nonexistent")  # Miss

        stats = cache.stats()

        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 2 / 3
        assert stats["size"] == 2


if __name__ == "__main__":
    pytest.main([__file__])
