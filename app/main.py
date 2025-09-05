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
    """Handles adding console activity and generating meeting prep."""
    console_text = args.text
    if not console_text:
        print("Error: The --text argument is required for the 'add' command.")
        return

    print("Adding console activity to the vault...")
    reflection_id = vault.add_reflection(console_text)
    print(f"Entry saved with ID: {reflection_id}")

    print("\nInitializing local AI models (this may take a moment)...")
    try:
        llm = LocalLLM()
        with no_network(allow_loopback=True, allowed_ports=(11434,)):
            print("Model loaded. Running analysis offline...")
            service = AdviceService(llm)

            print("Extracting console session insights...")
            sessions = service.get_console_insights(console_text)

            print("Composing meeting prep...")
            prep = service.get_meeting_prep(sessions)

            print("\n--- Meeting Prep ---")
            if prep.team_update:
                print("\nTeam Update:")
                for item in prep.team_update:
                    print(f"• {item}")
            if prep.manager_update:
                print("\nManager Update:")
                for item in prep.manager_update:
                    print(f"• {item}")
            if prep.recommendations:
                print("\nRecommendations:")
                for item in prep.recommendations:
                    print(f"• {item}")

    except Exception as e:
        print(f"\nAn error occurred during AI processing: {e}", file=sys.stderr)
        print("The entry was saved, but meeting prep could not be generated.", file=sys.stderr)


def handle_list(args, vault: EncryptedVault):
    """Handles listing all stored reflections."""
    print("--- All Reflections ---")
    reflections = vault.get_all_reflections()
    if not reflections:
        print("No reflections found.")
        return

    for rid, text in reflections:
        # Show first line or 80 characters
        preview = text.split("\n")[0]
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
    parser_add = subparsers.add_parser(
        "add", help="Add a new reflection and get advice."
    )
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
