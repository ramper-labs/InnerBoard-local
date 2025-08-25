"""
Handles loading and running the local LLM using llama-cpp-python.
"""

import os
from llama_cpp import Llama
from typing import List, Dict

# Allow overriding the model path via environment variable for testing/switching models
MODEL_PATH = os.getenv("GGUF_MODEL_PATH", "ft/data/gpt-oss-20b.Q5_K_M.gguf")

# Optional tuning via env vars
ENV_N_GPU_LAYERS = os.getenv("N_GPU_LAYERS")
ENV_N_CTX = os.getenv("N_CTX")

class LocalLLM:
    """
    A wrapper for a local GGUF model using llama-cpp-python.
    """
    def __init__(self):
        """
        Initializes and loads the GGUF model.
        """
        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(
                f"Model file not found at {MODEL_PATH}. "
                "Please download the GGUF model and place it in the ft/data/ directory, "
                "or set GGUF_MODEL_PATH to a valid .gguf file."
            )

        n_gpu_layers = int(ENV_N_GPU_LAYERS) if ENV_N_GPU_LAYERS is not None else -1
        n_ctx = int(ENV_N_CTX) if ENV_N_CTX is not None else 2048

        print(f"Loading model: {MODEL_PATH}...")
        self.llm = Llama(
            model_path=MODEL_PATH,
            n_gpu_layers=n_gpu_layers,  # Offload layers to the GPU if available
            n_ctx=n_ctx,                # Context window size
            verbose=False,              # Suppress verbose llama.cpp output
        )
        print("Model loaded successfully.")

    def generate(self, messages: List[Dict[str, str]], max_new_tokens: int = 512) -> str:
        """
        Generates a response from the model given a conversation history.

        Args:
            messages (List[Dict[str, str]]): A list of message dictionaries.
            max_new_tokens (int): The maximum number of new tokens to generate.

        Returns:
            str: The content of the assistant's response.
        """
        response = self.llm.create_chat_completion(
            messages=messages,
            max_tokens=max_new_tokens,
            temperature=0.7,
            top_p=0.95,
        )
        
        if response and "choices" in response and response["choices"]:
            return response["choices"][0]["message"]["content"]
        
        return "Error: Could not generate a valid response."

def main():
    """
    Demonstrates the LocalLLM class with the new GGUF backend.
    """
    print("--- GGUF LLM Loader Demonstration ---")
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
