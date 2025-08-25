"""
The main command-line interface for the InnerBoard-local agent.
"""

import argparse
from app.storage import EncryptedVault, load_key, DB_FILE
from app.llm import LocalLLM
from app.advice import AdviceService
from app.safety import no_network
import sys

def handle_add(args, vault: EncryptedVault):
    """Handles adding a new reflection and generating advice."""
    reflection_text = args.text
    if not reflection_text:
        print("Error: The --text argument is required for the 'add' command.")
        return

    print("Adding new reflection to the vault...")
    reflection_id = vault.add_reflection(reflection_text)
    print(f"Reflection saved with ID: {reflection_id}")

    print("\nInitializing local AI models (this may take a moment)...")
    try:
        # First, we initialize the LLM, which may require downloading the model
        # on the first run. This part needs network access.
        llm = LocalLLM()

        # Once the model is loaded and cached, all subsequent operations
        # can and should be performed offline.
        with no_network():
            print("Model loaded. Running analysis offline...")
            service = AdviceService(llm)

            print("Analyzing reflection...")
            sre_output = service.get_structured_reflection(reflection_text)
            
            print("Composing advice...")
            mac_output = service.get_micro_advice(sre_output)

            print("\n--- Your Micro-Advice ---")
            print(f"Urgency: {mac_output.urgency.capitalize()}")
            
            print("\nRecommended Steps:")
            for i, step in enumerate(mac_output.steps, 1):
                print(f"{i}. {step}")

            print("\nChecklist:")
            for item in mac_output.checklist:
                print(f"- [ ] {item}")

    except Exception as e:
        print(f"\nAn error occurred during AI processing: {e}", file=sys.stderr)
        print("The reflection was saved, but advice could not be generated.", file=sys.stderr)


def handle_list(args, vault: EncryptedVault):
    """Handles listing all stored reflections."""
    print("--- All Reflections ---")
    reflections = vault.get_all_reflections()
    if not reflections:
        print("No reflections found.")
        return
    
    for rid, text in reflections:
        # Show first line or 80 characters
        preview = text.split('\n')[0]
        if len(preview) > 80:
            preview = preview[:77] + "..."
        print(f"ID {rid}: {preview}")

def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="InnerBoard-local: Your offline onboarding reflection coach."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # 'add' command
    parser_add = subparsers.add_parser("add", help="Add a new reflection and get advice.")
    parser_add.add_argument(
        "-t", "--text", type=str, help="The reflection text to add."
    )

    # 'list' command
    subparsers.add_parser("list", help="List all saved reflections.")

    args = parser.parse_args()

    # Initialize vault
    key = load_key()
    vault = EncryptedVault(DB_FILE, key)

    try:
        if args.command == "add":
            handle_add(args, vault)
        elif args.command == "list":
            handle_list(args, vault)
    finally:
        vault.close()

if __name__ == "__main__":
    main()
