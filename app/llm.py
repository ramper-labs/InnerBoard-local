"""
Handles loading and running the local LLM using the Ollama Python client.
"""

import os
from typing import List, Dict
from ollama import Client

# Allow overriding the Ollama model via environment variable for testing/switching models
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gpt-oss:20b")

class LocalLLM:
    """
    A wrapper around a local Ollama model served on localhost.
    """
    def __init__(self):
        """
        Initializes the Ollama client. Assumes the Ollama server is running locally.
        """

        self.client = Client()
        self.model = OLLAMA_MODEL
        print(f"Using Ollama model: {self.model}")

    def generate(self, messages: List[Dict[str, str]], max_new_tokens: int = 512) -> str:
        """
        Generates a response from the model given a conversation history.

        Args:
            messages (List[Dict[str, str]]): A list of message dictionaries.
            max_new_tokens (int): The maximum number of new tokens to generate.

        Returns:
            str: The content of the assistant's response.
        """
        response = self.client.chat(
            model=self.model,
            messages=messages,
            options={
                "temperature": 0.7,
                "top_p": 0.95,
                "num_predict": max_new_tokens,
            },
        )

        try:
            content = response["message"]["content"]
        except Exception:
            try:
                content = response.message.content
            except Exception:
                content = "Error: Could not generate a valid response."
        return content

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
            {"role": "user", "content": f"Reflection: {reflection_text}"}
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
