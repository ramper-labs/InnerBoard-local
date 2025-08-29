"""
Handles loading and running the local LLM using the Ollama Python client.
Enhanced with caching and performance optimizations.
"""

import time
from typing import List, Dict, Optional
from ollama import Client
from app.config import config
from app.logging_config import get_logger
from app.cache import cached_model, ConnectionPool, model_cache
from app.exceptions import LLMError, ModelNotAvailableError, ModelTimeoutError


logger = get_logger(__name__)


class LocalLLM:
    """
    A wrapper around a local Ollama model served on localhost.
    Enhanced with caching and connection pooling for optimal performance.
    """

    # Global connection pool for Ollama clients
    _client_pool = ConnectionPool(lambda: Client(host=config.ollama_host), max_size=5)

    def __init__(self, host: Optional[str] = None, model: Optional[str] = None):
        """
        Initializes the Ollama client. Assumes the Ollama server is running locally.

        Args:
            host: Ollama server host URL. Defaults to config value.
            model: Model name to use. Defaults to config value.
        """
        self.host = host or config.ollama_host
        self.model = model or config.ollama_model
        self.timeout = config.ollama_timeout
        self._client = None

        # Initialize client connection
        self._ensure_client()

    def _ensure_client(self) -> None:
        """Ensure we have a valid client connection."""
        if self._client is None:
            try:
                if self.host == config.ollama_host:
                    # Use connection pool for default host
                    self._client = self._client_pool.get()
                else:
                    # Create new client for custom host
                    self._client = Client(host=self.host)
                logger.debug(f"Ollama client ready for model: {self.model}")
            except Exception as e:
                logger.error(f"Failed to initialize Ollama client: {e}")
                raise LLMError(f"Failed to initialize Ollama client: {e}") from e

    def _return_client(self) -> None:
        """Return client to pool if it's from the default host."""
        if self._client and self.host == config.ollama_host:
            try:
                self._client_pool.put(self._client)
                self._client = None
            except Exception as e:
                logger.warning(f"Failed to return client to pool: {e}")

    @property
    def client(self):
        """Get the Ollama client, ensuring it's available."""
        self._ensure_client()
        return self._client

    @cached_model(ttl=300)  # Cache for 5 minutes
    def _check_model_availability(self) -> bool:
        """Check if the specified model is available."""
        try:
            response = self.client.list()
            available_models = [model["name"] for model in response.get("models", [])]
            return self.model in available_models
        except Exception as e:
            logger.warning(f"Could not check model availability: {e}")
            return False

    def generate(
        self,
        messages: List[Dict[str, str]],
        max_new_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        timeout: Optional[int] = None,
    ) -> str:
        """
        Generates a response from the model given a conversation history.

        Args:
            messages: A list of message dictionaries.
            max_new_tokens: Maximum number of new tokens to generate.
            temperature: Sampling temperature.
            top_p: Top-p sampling parameter.
            timeout: Request timeout in seconds.

        Returns:
            str: The content of the assistant's response.

        Raises:
            ModelNotAvailableError: If the model is not available.
            ModelTimeoutError: If the request times out.
            LLMError: For other LLM-related errors.
        """
        # Use config defaults if not specified
        max_new_tokens = max_new_tokens or config.max_tokens
        temperature = temperature or config.temperature
        top_p = top_p or config.top_p
        timeout = timeout or self.timeout

        # Check model availability
        if not self._check_model_availability():
            logger.error(f"Model {self.model} is not available")
            raise ModelNotAvailableError(f"Model {self.model} is not available")

        logger.debug(
            f"Generating response with model {self.model}, max_tokens={max_new_tokens}"
        )

        try:
            start_time = time.time()

            response = self.client.chat(
                model=self.model,
                messages=messages,
                options={
                    "temperature": temperature,
                    "top_p": top_p,
                    "num_predict": max_new_tokens,
                },
                stream=False,
            )

            duration = time.time() - start_time
            logger.debug(f"LLM request completed in {duration:.2f}s")

            # Extract content from response
            content = self._extract_content(response)
            if not content:
                logger.warning("Empty response from LLM")
                return "Error: Could not generate a valid response."

            logger.debug(f"Generated response of length {len(content)}")
            return content

        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            if "timeout" in str(e).lower():
                raise ModelTimeoutError(f"LLM request timed out: {e}")
            raise LLMError(f"LLM generation failed: {e}")
        finally:
            # Return client to pool
            self._return_client()

    def _extract_content(self, response) -> Optional[str]:
        """Extract content from Ollama response."""
        try:
            # Try different response formats
            if isinstance(response, dict):
                return response.get("message", {}).get("content")
            elif hasattr(response, "message"):
                return getattr(response.message, "content", None)
            else:
                logger.warning(f"Unexpected response format: {type(response)}")
                return None
        except Exception as e:
            logger.warning(f"Failed to extract content from response: {e}")
            return None

    def get_available_models(self) -> List[str]:
        """Get list of available models."""
        try:
            response = self.client.list()
            return [model["name"] for model in response.get("models", [])]
        except Exception as e:
            logger.error(f"Failed to get available models: {e}")
            return []


def main():
    """
    Demonstrates the LocalLLM class with the Ollama backend.
    """
    print("--- Ollama LLM Demonstration ---")
    try:
        llm = LocalLLM()

        print("\n--- SRE Prompt Test ---")
        with open("prompts/sre_system_prompt.txt", "r") as f:
            sre_system_prompt = f.read()

        reflection_text = (
            "I spent most of the day trying to get the Kubernetes ingress to route correctly. "
            "The documentation is a bit confusing and I couldn't find a good example. "
            "I feel like I'm falling behind and my confidence took a hit."
        )

        sre_messages = [
            {"role": "system", "content": sre_system_prompt},
            {"role": "user", "content": f"Reflection: {reflection_text}"},
        ]

        print("User: (Using SRE prompt)")
        sre_response = llm.generate(sre_messages)
        print("Assistant (raw JSON output):")
        print(sre_response)

    except FileNotFoundError as e:
        print(f"\nError: {e}")
    except Exception as e:
        print(f"\nAn error occurred: {e}")


if __name__ == "__main__":
    main()
