"""
Modern CLI interface for InnerBoard-local using Click.
Provides a user-friendly command-line interface with rich formatting and progress indicators.
"""

import sys
import os
from pathlib import Path
from typing import Optional
import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm, Prompt
import json

from app.config import config
from app.storage import EncryptedVault, load_key
from app.llm import LocalLLM
from app.advice import AdviceService
from app.safety import no_network
from app.logging_config import get_logger
from app.exceptions import InnerBoardError, EncryptionError
from app.security import SecureKeyManager
from app.utils import format_timestamp, format_reflection_preview, clean_terminal_log

logger = get_logger(__name__)
console = Console()


def print_welcome():
    """Print welcome message."""
    welcome_text = Text("InnerBoard-local", style="bold blue")
    subtitle = Text("Your private onboarding reflection coach", style="italic cyan")
    console.print(
        Panel.fit(
            f"[bold blue]InnerBoard-local[/bold blue]\n[italic cyan]Your private onboarding reflection coach[/italic cyan]"
        )
    )
    console.print()


def format_reflection_preview(text: str, max_length: int = 80) -> str:
    """Format reflection text for display."""
    lines = text.split("\n")
    preview = lines[0]
    if len(preview) > max_length:
        preview = preview[: max_length - 3] + "..."
    return preview


@click.group()
@click.option("--db-path", type=click.Path(), help="Path to the database file")
@click.option("--key-path", type=click.Path(), help="Path to the encryption key file")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
@click.pass_context
def cli(
    ctx: click.Context, db_path: Optional[str], key_path: Optional[str], verbose: bool
):
    """InnerBoard-local: Your private onboarding reflection coach.

    A 100% offline onboarding reflection coach that turns private journaling
    into structured signals and concrete micro-advice.
    """
    # Store configuration in context
    ctx.ensure_object(dict)

    if db_path:
        ctx.obj["db_path"] = Path(db_path)
    else:
        ctx.obj["db_path"] = config.db_path

    if key_path:
        ctx.obj["key_path"] = Path(key_path)
    else:
        ctx.obj["key_path"] = config.key_path

    if verbose:
        import logging

        logging.getLogger("innerboard").setLevel(logging.DEBUG)

    print_welcome()


@cli.command()
@click.argument("text", required=True)
@click.option("--model", help="Override the default Ollama model")
@click.option("--temperature", type=float, help="Override temperature setting")
@click.pass_context
def add(
    ctx: click.Context, text: str, model: Optional[str], temperature: Optional[float]
):
    """Add a new console activity log and generate meeting prep.

    TEXT: The raw console activity text to analyze.

    Example:
        innerboard add "I'm struggling with the new authentication service..."
    """
    db_path = ctx.obj["db_path"]
    key_path = ctx.obj["key_path"]

    try:
        # Check if vault is initialized
        if not key_path.exists():
            console.print("[red]No encryption key found![/red]")
            console.print(
                "[yellow]Run 'innerboard init' first to set up your vault.[/yellow]"
            )
            sys.exit(1)

        # Load encryption key (with password from env if available)
        password = os.getenv("INNERBOARD_KEY_PASSWORD")
        with console.status("[bold green]Loading encryption key..."):
            key = load_key(password)

        # Initialize vault
        vault = EncryptedVault(db_path, key)

        # Add console text to vault (stored as a reflection entry for now)
        with console.status("[bold green]Saving reflection..."):
            reflection_id = vault.add_reflection(text)

        console.print(f"[green]✓[/green] Entry saved with ID: {reflection_id}")

        # Initialize LLM
        with console.status("[bold green]Initializing AI model..."):
            llm = LocalLLM(model=model if model else config.ollama_model)

        # Process with network guard
        with no_network():
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Analyzing reflection...", total=None)

                # Extract console insights (sessions)
                progress.update(task, description="Extracting console session insights...")
                service = AdviceService(llm)
                sessions = service.get_console_insights(text)

                # Generate meeting prep
                progress.update(task, description="Composing meeting prep...")
                prep = service.get_meeting_prep(sessions)

                progress.update(task, description="Complete!")

        # Display results
        display_meeting_prep(sessions, prep)

    except InnerBoardError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        console.print(f"[red]Unexpected error:[/red] {e}")
        sys.exit(1)
    finally:
        if "vault" in locals():
            vault.close()


@cli.command()
@click.option(
    "--limit", type=int, default=10, help="Maximum number of reflections to show"
)
@click.pass_context
def list(ctx: click.Context, limit: int):
    """List all saved reflections.

    Shows a preview of each reflection with its ID and timestamp.
    """
    db_path = ctx.obj["db_path"]
    key_path = ctx.obj["key_path"]

    try:
        # Check if vault is initialized
        if not key_path.exists():
            console.print("[red]No encryption key found![/red]")
            console.print(
                "[yellow]Run 'innerboard init' first to set up your vault.[/yellow]"
            )
            sys.exit(1)

        # Load encryption key (with password from env if available)
        password = os.getenv("INNERBOARD_KEY_PASSWORD")
        with console.status("[bold green]Loading encryption key..."):
            key = load_key(password)

        # Initialize vault
        vault = EncryptedVault(db_path, key)

        # Get reflections
        reflections = vault.get_all_reflections()

        if not reflections:
            console.print("[yellow]No reflections found.[/yellow]")
            return

        # Create table
        table = Table(title=f"Reflections ({len(reflections)} total)")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Preview", style="white")
        table.add_column("Timestamp", style="dim")

        # Add rows (limited)
        for reflection_id, text, created_at, updated_at in reflections[:limit]:
            preview = format_reflection_preview(text)
            table.add_row(str(reflection_id), preview, str(created_at))

        console.print(table)

        if len(reflections) > limit:
            console.print(
                f"[dim]Showing first {limit} reflections. Use --limit to see more.[/dim]"
            )

    except InnerBoardError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        console.print(f"[red]Unexpected error:[/red] {e}")
        sys.exit(1)
    finally:
        if "vault" in locals():
            vault.close()


@cli.command()
@click.argument("reflection_id", type=int)
@click.pass_context
def show(ctx: click.Context, reflection_id: int):
    """Show a specific reflection and its advice.

    REFLECTION_ID: The ID of the reflection to show.
    """
    db_path = ctx.obj["db_path"]
    key_path = ctx.obj["key_path"]

    try:
        # Check if vault is initialized
        if not key_path.exists():
            console.print("[red]No encryption key found![/red]")
            console.print(
                "[yellow]Run 'innerboard init' first to set up your vault.[/yellow]"
            )
            sys.exit(1)

        # Load encryption key (with password from env if available)
        password = os.getenv("INNERBOARD_KEY_PASSWORD")
        with console.status("[bold green]Loading encryption key..."):
            key = load_key(password)

        # Initialize vault
        vault = EncryptedVault(db_path, key)

        # Get specific reflection
        reflection = vault.get_reflection(reflection_id)

        if not reflection:
            console.print(f"[red]Reflection with ID {reflection_id} not found.[/red]")
            sys.exit(1)

        text, created_at, updated_at = reflection

        # Display reflection
        console.print(f"\n[bold]Reflection #{reflection_id}[/bold] ({created_at})")
        console.print(Panel.fit(text, title="Reflection Text"))

        # Note: Analysis data would need to be stored separately in future versions
        console.print(
            "[yellow]Analysis display not yet implemented for this version.[/yellow]"
        )
        console.print(
            "[dim]Future versions will include stored analysis results.[/dim]"
        )

    except InnerBoardError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        console.print(f"[red]Unexpected error:[/red] {e}")
        sys.exit(1)
    finally:
        if "vault" in locals():
            vault.close()


@cli.command()
@click.option("--force", is_flag=True, help="Skip confirmation prompt")
@click.pass_context
def clear(ctx: click.Context, force: bool):
    """Clear all reflections from the vault.

    This will permanently delete all stored reflections and cannot be undone.
    """
    db_path = ctx.obj["db_path"]

    if not force:
        if not Confirm.ask(
            f"Are you sure you want to delete all reflections from {db_path}?"
        ):
            console.print("[yellow]Operation cancelled.[/yellow]")
            return

    try:
        if db_path.exists():
            db_path.unlink()
            console.print(f"[green]✓[/green] Vault cleared: {db_path}")
        else:
            console.print(f"[yellow]Vault file not found: {db_path}[/yellow]")

    except Exception as e:
        logger.error(f"Failed to clear vault: {e}")
        console.print(f"[red]Error clearing vault:[/red] {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option(
    "--password",
    prompt=True,
    hide_input=True,
    confirmation_prompt=True,
    help="Password to encrypt the vault key (optional but recommended)",
)
@click.option("--force", is_flag=True, help="Overwrite existing vault if it exists")
def init(password: str, force: bool):
    """Initialize InnerBoard vault with encryption key.

    This command creates a new encrypted vault and generates a secure encryption key.
    Run this once when setting up InnerBoard for the first time.
    """
    db_path = config.db_path
    key_path = config.key_path

    # Check if vault already exists
    if db_path.exists() and not force:
        console.print(f"[yellow]Vault already exists at: {db_path}[/yellow]")
        console.print("[yellow]Use --force to overwrite existing vault.[/yellow]")
        return

    if key_path.exists() and not force:
        console.print(f"[yellow]Key file already exists at: {key_path}[/yellow]")
        console.print("[yellow]Use --force to overwrite existing key.[/yellow]")
        return

    try:
        # Clean up existing files if force is used
        if force:
            if db_path.exists():
                db_path.unlink()
                console.print(f"[dim]Removed existing vault: {db_path}[/dim]")
            if key_path.exists():
                key_path.unlink()
                console.print(f"[dim]Removed existing key: {key_path}[/dim]")

        # Generate secure key
        with console.status("[bold green]Generating secure encryption key..."):
            key_manager = SecureKeyManager(key_path)
            master_key = key_manager.generate_master_key(password or None)
            key_manager.save_master_key(password or None)

        console.print(f"[green]✓[/green] Encryption key generated and saved")

        # Create and test vault
        with console.status("[bold green]Creating encrypted vault..."):
            vault = EncryptedVault(str(db_path), master_key)

            # Test vault functionality
            test_reflection = "InnerBoard vault initialized successfully!"
            test_id = vault.add_reflection(test_reflection)
            retrieved = vault.get_reflection(test_id)

            if retrieved and retrieved[0] == test_reflection:
                console.print(f"[green]✓[/green] Vault encryption test passed")
            else:
                raise EncryptionError("Vault encryption test failed")

            vault.close()

        console.print(f"[green]✓[/green] Encrypted vault created: {db_path}")

        # Display setup summary
        console.print("\n[bold green]🎉 Setup Complete![/bold green]")
        console.print(f"Database: {db_path}")
        console.print(f"Key file: {key_path}")

        if password:
            console.print(
                "[yellow]⚠️  Remember your password - you'll need it to access your reflections![/yellow]"
            )
            console.print(
                "[dim]You can set INNERBOARD_KEY_PASSWORD environment variable to avoid entering it each time[/dim]"
            )
        else:
            console.print(
                "[dim]No password set - vault uses random encryption key[/dim]"
            )

        console.print("\n[dim]You can now start adding reflections with:[/dim]")
        console.print('[dim]  innerboard add "Your reflection here"[/dim]')

    except Exception as e:
        console.print(f"[red]Setup failed:[/red] {e}")
        sys.exit(1)


@cli.command()
@click.option("--password", help="Password to decrypt the vault key")
def status(password: Optional[str] = None):
    """Show vault status and statistics."""
    db_path = config.db_path
    key_path = config.key_path

    console.print("[bold]InnerBoard Vault Status[/bold]")
    console.print("=" * 30)

    # Check files
    key_exists = key_path.exists()
    db_exists = db_path.exists()

    console.print(f"Key file:     {'✓' if key_exists else '✗'} {key_path}")
    console.print(f"Vault file:   {'✓' if db_exists else '✗'} {db_path}")

    if not key_exists:
        console.print(
            "\n[yellow]No key file found. Run 'innerboard init' to set up your vault.[/yellow]"
        )
        return

    if not db_exists:
        console.print(
            "\n[yellow]No vault file found. Run 'innerboard init' to create your vault.[/yellow]"
        )
        return

    # Get password from environment if not provided
    if password is None:
        password = os.getenv("INNERBOARD_KEY_PASSWORD")

    try:
        # Load key and vault
        with console.status("[bold green]Loading vault..."):
            key_manager = SecureKeyManager(key_path)
            master_key = key_manager.load_master_key(password)
            vault = EncryptedVault(str(db_path), master_key)

        # Get statistics
        stats = vault.get_stats()

        console.print(f"\n[green]✓[/green] Vault loaded successfully")
        console.print(f"Total reflections: {stats['total_reflections']}")

        if stats["oldest_reflection"]:
            console.print(
                f"Oldest reflection: {format_timestamp(stats['oldest_reflection'])}"
            )

        if stats["newest_reflection"]:
            console.print(
                f"Newest reflection: {format_timestamp(stats['newest_reflection'])}"
            )

        vault_size_mb = stats["database_size"] / (1024 * 1024)
        console.print(".1f")

        # Show recent reflections
        all_reflections = vault.get_all_reflections()
        if all_reflections:
            console.print(f"\n[bold]Recent Reflections:[/bold]")
            recent = all_reflections[:3]  # Show last 3
            for reflection_id, text, created_at, updated_at in recent:
                preview = format_reflection_preview(text)
                timestamp = format_timestamp(created_at)
                console.print(f"  ID {reflection_id}: {preview} [{timestamp}]")

        vault.close()

    except Exception as e:
        console.print(f"[red]Failed to load vault:[/red] {e}")
        if "password" in str(e).lower():
            console.print(
                "[yellow]Try providing the correct password with --password[/yellow]"
            )


@cli.command()
def models():
    """List available Ollama models."""
    try:
        with console.status("[bold green]Checking available models..."):
            llm = LocalLLM()
            available_models = llm.get_available_models()

        if not available_models:
            console.print(
                "[yellow]No models found. Make sure Ollama is running.[/yellow]"
            )
            console.print("[dim]Install Ollama from: https://ollama.com/download[/dim]")
            return

        table = Table(title="Available Ollama Models")
        table.add_column("Model Name", style="cyan")

        for model in available_models:
            table.add_row(model)

        console.print(table)
        console.print(f"\n[dim]Current model: {config.ollama_model}[/dim]")
        console.print(
            "[dim]To use a different model, set OLLAMA_MODEL environment variable[/dim]"
        )

    except InnerBoardError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


def display_meeting_prep(sessions, prep):
    """Display session insights and meeting-prep outputs."""
    console.print("\n[bold blue]📊 Console Session Insights[/bold blue]")

    if not sessions:
        console.print("[dim]No sessions extracted from console activity.[/dim]")
    else:
        for idx, s in enumerate(sessions, 1):
            console.print(Panel.fit(s.summary, title=f"Session {idx} Summary"))
            table = Table()
            table.add_column("Type", style="cyan", no_wrap=True)
            table.add_column("Details", style="white")

            if s.key_successes:
                for ks in s.key_successes:
                    table.add_row(
                        "Success",
                        f"{ks.desc}\n[dim]specifics:[/dim] {ks.specifics}\n[dim]context:[/dim] {ks.adjacent_context}",
                    )
            if s.blockers:
                for b in s.blockers:
                    table.add_row(
                        "Blocker",
                        f"{b.desc}\n[dim]impact:[/dim] {b.impact}\n[dim]owner:[/dim] {b.owner_hint}\n[dim]next:[/dim] {b.resolution_hint}",
                    )
            if s.resources:
                table.add_row("Resources", "\n".join(f"• {r}" for r in s.resources))
            console.print(table)

    console.print("\n[bold green]🗣️ Meeting Prep[/bold green]")

    if prep.team_update:
        console.print("\n[bold]Team Update:[/bold]")
        for item in prep.team_update:
            console.print(f"  • {item}")

    if prep.manager_update:
        console.print("\n[bold]Manager Update:[/bold]")
        for item in prep.manager_update:
            console.print(f"  • {item}")

    if prep.recommendations:
        console.print("\n[bold]Recommendations:[/bold]")
        for item in prep.recommendations:
            console.print(f"  • {item}")


@cli.command()
@click.argument("console_text", required=True)
@click.option("--model", help="Override the default Ollama model")
@click.pass_context
def prep(ctx: click.Context, console_text: str, model: Optional[str]):
    """Generate meeting prep from CONSOLE_TEXT (paste from your shell)."""
    try:
        with console.status("[bold green]Initializing AI model..."):
            llm = LocalLLM(model=model if model else config.ollama_model)
        service = AdviceService(llm)
        with no_network():
            sessions = service.get_console_insights(console_text)
            prep = service.get_meeting_prep(sessions)
        display_meeting_prep(sessions, prep)
    except Exception as e:
        logger.error(f"prep command failed: {e}")
        console.print(f"[red]Error:[/red] {e}")


@cli.command()
@click.argument("log_file", type=click.Path(exists=True))
@click.option("--model", help="Override the default Ollama model")
@click.option("--output", type=click.Path(), help="Path to save the JSON output")
@click.pass_context
def process_log(ctx: click.Context, log_file: str, model: Optional[str], output: Optional[str]):
    """Process terminal log file and generate SRE_output.json format."""
    try:
        # Read log file
        with open(log_file, 'r') as f:
            log_content = f.read()
        # Clean the log
        cleaned_text = clean_terminal_log(log_content)
        with console.status("[bold green]Initializing AI model..."):
            llm = LocalLLM(model=model if model else config.ollama_model)
        service = AdviceService(llm)
        with no_network():
            sessions = service.get_console_insights(cleaned_text)
        # Convert to JSON
        json_data = json.dumps([s.model_dump() for s in sessions], indent=2)
        if output:
            with open(output, 'w') as f:
                f.write(json_data)
            console.print(f"[green]✓[/green] Output saved to {output}")
        else:
            console.print(json_data)
    except Exception as e:
        logger.error(f"process_log command failed: {e}")
        console.print(f"[red]Error:[/red] {e}")


if __name__ == "__main__":
    cli()
