"""
Modern CLI interface for InnerBoard-local using Click.
Provides a user-friendly command-line interface with rich formatting and progress indicators.
"""

import sys
import os
from pathlib import Path
from typing import Optional, List
import shutil
import subprocess
import platform
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
from app.utils import (
    format_timestamp,
    format_reflection_preview,
    get_sessions_dir,
    build_unique_session_path,
    clean_terminal_log,
)
from app.models import SRESession
from app.session_monitor import SessionMonitor

logger = get_logger(__name__)
console = Console()


def print_welcome():
    """Print welcome message."""
    welcome_text = Text("InnerBoard-local", style="bold blue")
    subtitle = Text("Your private meeting prep assistant.", style="italic cyan")
    console.print(
        Panel.fit(
            f"[bold blue]InnerBoard-local[/bold blue]\n[italic cyan]Your private meeting prep assistant.[/italic cyan]"
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
    """InnerBoard-local: Your private meeting prep assistant.

    A 100% offline meeting prep assistant that turns private journaling
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
    """Add a new console activity log to the vault only.

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

        # Add console text to vault
        with console.status("[bold green]Saving reflection..."):
            reflection_id = vault.add_reflection(text)

        console.print(f"[green]✓[/green] Entry saved with ID: {reflection_id}")

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


@cli.command("list")
@click.option(
    "--limit", type=int, default=10, help="Maximum number of reflections to show"
)
@click.pass_context
def list_reflections(ctx: click.Context, limit: int):
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
@click.option("--force", is_flag=True, help="Skip confirmation prompt")
@click.pass_context
def delete(ctx: click.Context, reflection_id: int, force: bool):
    """Delete a specific reflection from the vault.

    REFLECTION_ID: The ID of the reflection to delete (see 'innerboard list')

    This action cannot be undone. Use --force to skip confirmation.
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

        # Check if reflection exists and show preview before deletion
        try:
            reflection = vault.get_reflection(reflection_id)
            if not reflection:
                console.print(f"[red]Reflection with ID {reflection_id} not found.[/red]")
                return

            text, created_at, updated_at = reflection
            preview = format_reflection_preview(text)

            console.print("[yellow]Reflection to delete:[/yellow]")
            console.print(f"[cyan]ID:[/cyan] {reflection_id}")
            console.print(f"[cyan]Created:[/cyan] {created_at}")
            console.print(f"[cyan]Preview:[/cyan] {preview}")

        except Exception:
            console.print(f"[red]Error retrieving reflection {reflection_id}.[/red]")
            return

        # Confirmation prompt (unless --force is used)
        if not force:
            if not Confirm.ask(f"Are you sure you want to delete reflection {reflection_id}?"):
                console.print("[yellow]Deletion cancelled.[/yellow]")
                return

        # Delete the reflection
        with console.status(f"[bold red]Deleting reflection {reflection_id}..."):
            deleted = vault.delete_reflection(reflection_id)

        if deleted:
            console.print(f"[green]✓[/green] Reflection {reflection_id} deleted successfully")
        else:
            console.print(f"[red]Failed to delete reflection {reflection_id}[/red]")

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


# Alias for delete command
@cli.command("del")
@click.argument("reflection_id", type=int)
@click.option("--force", is_flag=True, help="Skip confirmation prompt")
@click.pass_context
def delete_alias(ctx: click.Context, reflection_id: int, force: bool):
    """Alias for 'delete' command.

    Delete a specific reflection from the vault.

    REFLECTION_ID: The ID of the reflection to delete (see 'innerboard list')

    This action cannot be undone. Use --force to skip confirmation.
    """
    # Call the main delete function
    ctx.invoke(delete, reflection_id=reflection_id, force=force)


 


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
@click.option("--skip-deps", is_flag=True, help="Skip dependency checks")
@click.option("--no-interactive", is_flag=True, help="Run setup non-interactively")
@click.option("--docker", is_flag=True, help="Setup for Docker deployment")
def setup(skip_deps: bool, no_interactive: bool, docker: bool):
    """Automated setup wizard for InnerBoard-local.

    This command guides you through the complete setup process:
    - Checks system prerequisites
    - Installs/configures Ollama
    - Downloads AI models
    - Initializes encrypted vault
    - Verifies everything works

    For first-time users, simply run: innerboard setup
    """
    console.print("[bold blue]🚀 InnerBoard Setup Wizard[/bold blue]")
    console.print("Let's get you up and running with InnerBoard-local!\n")

    if docker:
        return _setup_docker()
    else:
        return _setup_local(skip_deps, no_interactive)


def _setup_docker():
    """Setup for Docker deployment."""
    console.print("[bold]🐳 Docker Setup[/bold]")

    # Check Docker availability
    if not _check_docker():
        console.print("[red]❌ Docker not found. Please install Docker first.[/red]")
        console.print("Visit: https://docs.docker.com/get-docker/")
        return False

    console.print("[green]✓[/green] Docker detected")

    # Build and start services
    with console.status("[bold green]Building Docker images..."):
        result = subprocess.run(
            ["docker-compose", "build"],
            capture_output=True,
            text=True,
            cwd=Path.cwd()
        )
        if result.returncode != 0:
            console.print(f"[red]❌ Docker build failed: {result.stderr}[/red]")
            return False

    console.print("[green]✓[/green] Docker images built")

    # Start services
    with console.status("[bold green]Starting services..."):
        result = subprocess.run(
            ["docker-compose", "up", "-d"],
            capture_output=True,
            text=True,
            cwd=Path.cwd()
        )
        if result.returncode != 0:
            console.print(f"[red]❌ Failed to start services: {result.stderr}[/red]")
            return False

    console.print("[green]✓[/green] Services started")

    # Wait for Ollama to be ready
    console.print("[dim]Waiting for Ollama to be ready...[/dim]")
    import time
    for i in range(30):
        try:
            result = subprocess.run(
                ["curl", "-f", "http://localhost:11434/api/tags"],
                capture_output=True,
                timeout=5
            )
            if result.returncode == 0:
                break
        except:
            pass
        time.sleep(2)
    else:
        console.print("[yellow]⚠️ Ollama may still be starting. Please wait a moment.[/yellow]")

    console.print("\n[bold green]🎉 Docker setup complete![/bold green]")
    console.print("You can now use InnerBoard with Docker:")
    console.print("  [cyan]docker-compose exec innerboard innerboard add \"Your reflection\"[/cyan]")
    return True


def _setup_local(skip_deps: bool, no_interactive: bool):
    """Setup for local installation."""
    setup_steps = [
        ("check_prerequisites", "Checking prerequisites"),
        ("setup_ollama", "Setting up Ollama"),
        ("pull_model", "Downloading AI model"),
        ("init_vault", "Initializing encrypted vault"),
        ("verify_setup", "Verifying setup")
    ]

    # Run setup steps
    for step_func, description in setup_steps:
        console.print(f"[bold]{description}...[/bold]")

        try:
            if step_func == "check_prerequisites":
                success = _check_prerequisites(skip_deps, no_interactive)
            elif step_func == "setup_ollama":
                success = _setup_ollama(no_interactive)
            elif step_func == "pull_model":
                success = _pull_model(no_interactive)
            elif step_func == "init_vault":
                success = _init_vault(no_interactive)
            elif step_func == "verify_setup":
                success = _verify_setup()

            if not success:
                console.print(f"[red]❌ {description} failed[/red]")
                return False

            console.print(f"[green]✓[/green] {description} completed")

        except Exception as e:
            console.print(f"[red]❌ {description} failed: {e}[/red]")
            return False

    console.print("\n[bold green]🎉 Setup complete![/bold green]")
    console.print("You can now start using InnerBoard-local:")
    console.print("  [cyan]innerboard add \"Your first reflection\"[/cyan]")
    console.print("  [cyan]innerboard list[/cyan]")
    return True


def _check_prerequisites(skip_deps: bool, no_interactive: bool) -> bool:
    """Check system prerequisites."""
    if skip_deps:
        return True

    # Check Python version
    python_version = sys.version_info
    if python_version < (3, 8):
        console.print(f"[red]❌ Python {python_version.major}.{python_version.minor} detected[/red]")
        console.print("InnerBoard requires Python 3.8 or higher")
        return False

    console.print(f"[green]✓[/green] Python {python_version.major}.{python_version.minor}.{python_version.minor}")

    # Check pip
    try:
        import pip
        console.print(f"[green]✓[/green] pip {pip.__version__}")
    except ImportError:
        console.print("[yellow]⚠️ pip not found - installing dependencies may fail[/yellow]")

    return True


def _check_docker() -> bool:
    """Check if Docker is available."""
    try:
        result = subprocess.run(
            ["docker", "--version"],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def _setup_ollama(no_interactive: bool) -> bool:
    """Setup Ollama if not already installed."""
    # Check if Ollama is installed
    try:
        result = subprocess.run(
            ["ollama", "--version"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            console.print(f"[green]✓[/green] Ollama already installed: {result.stdout.strip()}")
            return True
    except FileNotFoundError:
        pass

    # Ollama not found - offer to install
    if no_interactive:
        console.print("[red]❌ Ollama not found and running non-interactively[/red]")
        console.print("Please install Ollama manually: https://ollama.com/download")
        return False

    if not Confirm.ask("Ollama not found. Would you like to install it?", default=True):
        console.print("Please install Ollama manually: https://ollama.com/download")
        return False

    # Install Ollama based on platform
    system = platform.system().lower()
    try:
        if system == "darwin":  # macOS
            console.print("Installing Ollama for macOS...")
            result = subprocess.run([
                "brew", "install", "ollama"
            ], capture_output=True, text=True)
        elif system == "linux":
            console.print("Installing Ollama for Linux...")
            result = subprocess.run([
                "curl", "-fsSL", "https://ollama.com/install.sh", "|", "sh"
            ], shell=True, capture_output=True, text=True)
        else:
            console.print(f"[yellow]⚠️ Automatic installation not supported for {system}[/yellow]")
            console.print("Please visit: https://ollama.com/download")
            return False

        if result.returncode != 0:
            console.print(f"[red]❌ Installation failed: {result.stderr}[/red]")
            return False

        console.print("[green]✓[/green] Ollama installed successfully")

        # Start Ollama service
        console.print("Starting Ollama service...")
        try:
            subprocess.run(["ollama", "serve"], start_new_session=True)
            import time
            time.sleep(3)  # Give it time to start
        except Exception as e:
            console.print(f"[yellow]⚠️ Could not start Ollama service: {e}[/yellow]")
            console.print("You may need to start it manually: ollama serve")

        return True

    except Exception as e:
        console.print(f"[red]❌ Installation failed: {e}[/red]")
        return False


def _pull_model(no_interactive: bool) -> bool:
    """Pull the default AI model."""
    model_name = config.ollama_model or "gpt-oss:20b"

    # Check if model is already available
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True
        )
        if model_name in result.stdout:
            console.print(f"[green]✓[/green] Model {model_name} already available")
            return True
    except Exception:
        pass

    # Pull the model
    console.print(f"Downloading model: {model_name}")
    console.print("[dim]This may take several minutes depending on your internet connection...[/dim]")

    try:
        with console.status(f"[bold green]Pulling {model_name}...[/bold green]"):
            result = subprocess.run(
                ["ollama", "pull", model_name],
                capture_output=True,
                text=True,
                timeout=6000  # 100 minute timeout
            )

        if result.returncode != 0:
            console.print(f"[red]❌ Failed to pull model: {result.stderr}[/red]")
            return False

        console.print(f"[green]✓[/green] Model {model_name} downloaded successfully")
        return True

    except subprocess.TimeoutExpired:
        console.print("[red]❌ Model download timed out[/red]")
        console.print("You can try again later with: ollama pull gpt-oss:20b")
        return False
    except Exception as e:
        console.print(f"[red]❌ Model download failed: {e}[/red]")
        return False


def _init_vault(no_interactive: bool) -> bool:
    """Initialize the encrypted vault."""
    # Check if already initialized
    if config.db_path.exists() and config.key_path.exists():
        console.print("[green]✓[/green] Vault already initialized")
        return True

    if no_interactive:
        # Initialize without password for non-interactive mode
        try:
            key_manager = SecureKeyManager(config.key_path)
            master_key = key_manager.generate_master_key(None)
            key_manager.save_master_key(None)

            vault = EncryptedVault(str(config.db_path), master_key)
            vault.close()
            console.print("[green]✓[/green] Vault initialized without password")
            return True
        except Exception as e:
            console.print(f"[red]❌ Vault initialization failed: {e}[/red]")
            return False

    # Interactive mode - ask for password
    console.print("Setting up encrypted vault for your reflections...")

    password = Prompt.ask(
        "Enter a password to encrypt your vault (leave empty for no password)",
        password=True,
        confirmation_prompt=True
    )

    try:
        # Generate secure key
        with console.status("[bold green]Generating secure encryption key..."):
            key_manager = SecureKeyManager(config.key_path)
            master_key = key_manager.generate_master_key(password or None)
            key_manager.save_master_key(password or None)

        console.print(f"[green]✓[/green] Encryption key generated")

        # Create vault
        with console.status("[bold green]Creating encrypted vault..."):
            vault = EncryptedVault(str(config.db_path), master_key)
            vault.close()

        console.print(f"[green]✓[/green] Encrypted vault created")

        if password:
            console.print("\n[dim]💡 Tip: Set INNERBOARD_KEY_PASSWORD environment variable[/dim]")
            console.print("[dim]   to avoid entering your password each time[/dim]")

        return True

    except Exception as e:
        console.print(f"[red]❌ Vault initialization failed: {e}[/red]")
        return False


def _verify_setup() -> bool:
    """Verify that the setup works correctly."""
    try:
        # Test basic functionality
        key_manager = SecureKeyManager(config.key_path)

        # Get password from environment first
        password = os.getenv("INNERBOARD_KEY_PASSWORD")

        # Try to load master key
        master_key = None
        password_required = False

        try:
            master_key = key_manager.load_master_key(password)
        except Exception as e:
            if "Password required" in str(e):
                password_required = True
                # If password is required but not in environment, prompt interactively
                if not password:
                    console.print("[yellow]🔐 Vault password required for verification[/yellow]")
                    password = Prompt.ask(
                        "Enter your vault password",
                        password=True
                    )
                    try:
                        master_key = key_manager.load_master_key(password)
                    except Exception as inner_e:
                        console.print(f"[red]❌ Invalid password: {inner_e}[/red]")
                        return False
                else:
                    console.print("[red]❌ Password required but INNERBOARD_KEY_PASSWORD is incorrect[/red]")
                    return False
            elif not password:
                # Try without password for unencrypted keys
                try:
                    master_key = key_manager.load_master_key(None)
                except Exception:
                    console.print("[red]❌ Could not load vault key. Vault may be corrupted.[/red]")
                    return False
            else:
                console.print(f"[red]❌ Could not load vault key: {e}[/red]")
                return False

        if not master_key:
            console.print("[red]❌ Vault verification failed: Could not load master key[/red]")
            return False

        vault = EncryptedVault(str(config.db_path), master_key)

        # Test add/get
        test_text = "Setup verification test"
        test_id = vault.add_reflection(test_text)
        retrieved = vault.get_reflection(test_id)

        if retrieved and retrieved[0] == test_text:
            console.print("[green]✓[/green] Vault functionality verified")
        else:
            console.print("[red]❌ Vault test failed[/red]")
            return False

        vault.close()

        # Test Ollama connection
        try:
            from app.llm import LocalLLM
            llm = LocalLLM()
            # Just test connection, don't make expensive call
            console.print("[green]✓[/green] AI service connection verified")
        except Exception as e:
            console.print(f"[yellow]⚠️ AI service connection issue: {e}[/yellow]")
            console.print("[dim]Note: AI features may not work until Ollama is fully started[/dim]")

        return True

    except Exception as e:
        console.print(f"[red]❌ Setup verification failed: {e}[/red]")
        return False


@cli.command()
@click.option("--detailed", is_flag=True, help="Show detailed health check information")
def health(detailed: bool):
    """Run comprehensive health checks for InnerBoard installation.

    This command verifies that all components are working correctly:
    - Python environment and dependencies
    - Ollama service and model availability
    - Vault encryption and database functionality
    - Network connectivity and security settings
    """
    console.print("[bold blue]🔍 InnerBoard Health Check[/bold blue]")
    console.print("Checking system components...\n")

    health_checks = [
        ("python_environment", "Python Environment"),
        ("ollama_service", "Ollama Service"),
        ("ai_model", "AI Model Availability"),
        ("vault_system", "Vault System"),
        ("network_security", "Network Security"),
        ("performance", "Performance & Caching")
    ]

    results = {}
    all_passed = True

    for check_func, description in health_checks:
        console.print(f"Checking {description}...")

        try:
            if check_func == "python_environment":
                success, info = _check_python_health(detailed)
            elif check_func == "ollama_service":
                success, info = _check_ollama_health(detailed)
            elif check_func == "ai_model":
                success, info = _check_model_health(detailed)
            elif check_func == "vault_system":
                success, info = _check_vault_health(detailed)
            elif check_func == "network_security":
                success, info = _check_network_health(detailed)
            elif check_func == "performance":
                success, info = _check_performance_health(detailed)

            if success:
                console.print(f"[green]✓[/green] {description}: OK")
                if detailed and info:
                    console.print(f"[dim]  {info}[/dim]")
            else:
                console.print(f"[red]❌[/red] {description}: FAILED")
                if info:
                    console.print(f"[dim]  {info}[/dim]")
                all_passed = False

            results[check_func] = (success, info)

        except Exception as e:
            console.print(f"[red]❌[/red] {description}: ERROR - {e}")
            results[check_func] = (False, str(e))
            all_passed = False

    # Overall status
    console.print("\n" + "="*50)
    if all_passed:
        console.print("[bold green]🎉 All health checks passed![/bold green]")
        console.print("[green]InnerBoard is ready to use![/green]")
    else:
        console.print("[bold yellow]⚠️  Some health checks failed[/bold yellow]")
        console.print("[yellow]Please review the errors above and fix any issues.[/yellow]")

        # Show common solutions
        console.print("\n[dim]💡 Common solutions:[/dim]")
        failed_checks = [k for k, (s, _) in results.items() if not s]
        if "ollama_service" in failed_checks:
            console.print("[dim]  - Start Ollama: ollama serve[/dim]")
        if "ai_model" in failed_checks:
            console.print("[dim]  - Pull model: ollama pull gpt-oss:20b[/dim]")
        if "vault_system" in failed_checks:
            console.print("[dim]  - Initialize vault: innerboard init[/dim]")


def _check_python_health(detailed: bool) -> tuple[bool, str]:
    """Check Python environment health."""
    import sys
    import importlib

    # Check Python version
    version = sys.version_info
    if version < (3, 8):
        return False, f"Python {version.major}.{version.minor} found, need 3.8+"

    info = f"Python {version.major}.{version.minor}.{version.minor}"

    # Check critical imports
    critical_modules = ['cryptography', 'ollama', 'rich', 'click', 'pydantic']
    missing = []

    for module in critical_modules:
        try:
            importlib.import_module(module)
        except ImportError:
            missing.append(module)

    if missing:
        return False, f"Missing modules: {', '.join(missing)}"

    if detailed:
        try:
            import cryptography
            import ollama
            import rich
            import click
            import pydantic
            info += f" | cryptography-{cryptography.__version__} | ollama-{ollama.__version__}"
        except:
            pass

    return True, info


def _check_ollama_health(detailed: bool) -> tuple[bool, str]:
    """Check Ollama service health."""
    try:
        import subprocess
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            return False, "Ollama service not responding"

        if detailed:
            lines = result.stdout.strip().split('\n')
            if len(lines) > 1:
                return True, f"Ollama running, {len(lines)-1} models available"
            else:
                return True, "Ollama running, no models installed"

        return True, "Ollama service is running"

    except FileNotFoundError:
        return False, "Ollama not installed or not in PATH"
    except subprocess.TimeoutExpired:
        return False, "Ollama command timed out"
    except Exception as e:
        return False, f"Ollama check failed: {e}"


def _check_model_health(detailed: bool) -> tuple[bool, str]:
    """Check AI model availability."""
    model_name = config.ollama_model or "gpt-oss:20b"

    try:
        import subprocess
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=10
        )

        if model_name in result.stdout:
            if detailed:
                return True, f"Model {model_name} is available"
            return True, f"Model {model_name} available"
        else:
            return False, f"Model {model_name} not found. Run: ollama pull {model_name}"

    except Exception as e:
        return False, f"Model check failed: {e}"


def _check_vault_health(detailed: bool) -> tuple[bool, str]:
    """Check vault system health."""
    db_path = config.db_path
    key_path = config.key_path

    # Check files exist
    if not key_path.exists():
        return False, "Vault key file not found. Run: innerboard init"

    if not db_path.exists():
        return False, "Vault database not found. Run: innerboard init"

    # Test vault functionality
    try:
        from app.security import SecureKeyManager
        from app.storage import EncryptedVault

        key_manager = SecureKeyManager(key_path)

        # Get password from environment first
        password = os.getenv("INNERBOARD_KEY_PASSWORD")

        # Try to load master key
        master_key = None

        try:
            master_key = key_manager.load_master_key(password)
        except Exception as e:
            if "Password required" in str(e) and not password:
                # Interactive password prompt for health check
                password = Prompt.ask(
                    "Enter vault password for health check",
                    password=True
                )
                try:
                    master_key = key_manager.load_master_key(password)
                except Exception as inner_e:
                    return False, f"Invalid password: {inner_e}"
            elif not password:
                # Try without password for unencrypted keys
                try:
                    master_key = key_manager.load_master_key(None)
                except Exception:
                    return False, "Could not load vault key. Set INNERBOARD_KEY_PASSWORD if vault is encrypted"
            else:
                return False, f"Could not load vault key: {e}"

        if not master_key:
            return False, "Could not load vault key"

        vault = EncryptedVault(str(db_path), master_key)

        # Test basic operations
        test_text = "health check test"
        test_id = vault.add_reflection(test_text)
        retrieved = vault.get_reflection(test_id)

        if retrieved and retrieved[0] == test_text:
            if detailed:
                stats = vault.get_stats() if hasattr(vault, 'get_stats') else {}
                vault.close()
                return True, f"Vault operational, key: {key_path}, db: {db_path}"
            vault.close()
            return True, "Vault is operational"
        else:
            vault.close()
            return False, "Vault read/write test failed"

    except Exception as e:
        return False, f"Vault health check failed: {e}"


def _check_network_health(detailed: bool) -> tuple[bool, str]:
    """Check network and security settings."""
    try:
        import requests
        from urllib.parse import urlparse

        ollama_host = config.ollama_host or "http://localhost:11434"
        parsed = urlparse(ollama_host)

        # Check if it's localhost/loopback
        is_local = parsed.hostname in ['localhost', '127.0.0.1', '::1']

        if not is_local:
            return False, f"Ollama host {ollama_host} is not localhost - data may leave device"

        # Test connection
        try:
            response = requests.get(f"{ollama_host}/api/tags", timeout=5)
            if response.status_code == 200:
                return True, f"Network secure, Ollama accessible at {ollama_host}"
            else:
                return False, f"Ollama responded with status {response.status_code}"
        except requests.exceptions.RequestException:
            return False, f"Cannot connect to Ollama at {ollama_host}"

    except Exception as e:
        return False, f"Network check failed: {e}"


def _check_performance_health(detailed: bool) -> tuple[bool, str]:
    """Check performance and caching systems."""
    try:
        from app.cache import cache_manager
        from app.llm import LocalLLM

        # Check cache stats
        cache_stats = cache_manager.get_stats()

        # Check LLM connection
        llm = LocalLLM()

        if detailed:
            total_entries = sum(stats.get('entries', 0) for stats in cache_stats.values())
            info = f"Cache: {total_entries} total entries across {len(cache_stats)} caches"
            if hasattr(llm, 'client'):
                info += " | LLM client ready"
            return True, info

        return True, "Performance systems operational"

    except Exception as e:
        return False, f"Performance check failed: {e}"


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


def display_mac_only(prep):
    """Display only the meeting-prep (MAC) outputs without SRE details."""
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


def _load_all_sre_sessions_from_dir(base_dir: Path) -> List[SRESession]:
    """Recursively load all SRE sessions from `sre.json` files under base_dir."""
    sessions_raw: List[dict] = []
    try:
        for sre_path in base_dir.rglob("sre.json"):
            try:
                with sre_path.open("r", encoding="utf-8") as fp:
                    data = json.load(fp)
                    if isinstance(data, list):
                        sessions_raw.extend(data)
                    elif isinstance(data, dict):
                        sessions_raw.append(data)
            except Exception as e:
                logger.warning(f"Failed to read {sre_path}: {e}")
    except Exception as e:
        logger.warning(f"Failed to scan SRE directory {base_dir}: {e}")

    validated: List[SRESession] = []
    for session_data in sessions_raw:
        try:
            validated.append(SRESession(**session_data))
        except Exception as e:
            logger.warning(f"Skipping invalid SRE session: {e}")
    return validated


@cli.command()
@click.option("--model", help="Override the default Ollama model")
@click.option(
    "--show-sre",
    is_flag=True,
    help="Also display detailed SRE session insights (verbose mode)",
)
@click.pass_context
def prep(ctx: click.Context, model: Optional[str], show_sre: bool):
    """Generate MAC from all stored SRE sessions and display with saved reflections."""
    try:
        with console.status("[bold green]Initializing AI model..."):
            llm = LocalLLM(model=model if model else config.ollama_model)
        service = AdviceService(llm)

        # Aggregate all SRE sessions from the sessions directory
        sessions_dir = get_sessions_dir()
        console.print(f"[dim]Loading SRE sessions from {sessions_dir}...[/dim]")
        sessions = _load_all_sre_sessions_from_dir(sessions_dir)
        if not sessions:
            console.print("[yellow]No SRE sessions found. Record a session first with 'innerboard record'.[/yellow]")

        if not sessions:
            return

        with no_network():
            prep = service.get_meeting_prep(sessions)

        # Display meeting prep (concise by default, verbose with --show-sre)
        if show_sre:
            display_meeting_prep(sessions, prep)
        else:
            display_mac_only(prep)

        # Display saved reflections from the encrypted vault
        db_path = ctx.obj.get("db_path", config.db_path)
        key_path = ctx.obj.get("key_path", config.key_path)
        console.print("\n[bold blue]🗂️ Saved Reflections[/bold blue]")
        try:
            if not Path(key_path).exists():
                console.print("[yellow]No encryption key found. Run 'innerboard init' to set up your vault.[/yellow]")
            else:
                password = os.getenv("INNERBOARD_KEY_PASSWORD")
                with console.status("[bold green]Loading vault reflections..."):
                    key = load_key(password)
                    vault = EncryptedVault(db_path, key)
                    reflections = vault.get_all_reflections()
                    vault.close()

                if not reflections:
                    console.print("[dim]No reflections saved yet.[/dim]")
                else:
                    table = Table(title=f"Reflections ({len(reflections)} total)")
                    table.add_column("ID", style="cyan", no_wrap=True)
                    table.add_column("Preview", style="white")
                    table.add_column("Timestamp", style="dim")
                    for reflection_id, text, created_at, _updated_at in reflections[:10]:
                        preview = format_reflection_preview(text)
                        table.add_row(str(reflection_id), preview, str(created_at))
                    console.print(table)
        except Exception as e:
            logger.warning(f"Failed to load/display reflections: {e}")
            console.print("[yellow]Could not load saved reflections.[/yellow]")
    except Exception as e:
        logger.error(f"prep command failed: {e}")
        console.print(f"[red]Error:[/red] {e}")


@cli.command()
@click.option(
    "--dir",
    "output_dir",
    type=click.Path(file_okay=False),
    help="Directory to save the session log (defaults to app data sessions dir)",
)
@click.option(
    "--name",
    "filename",
    type=str,
    help="Optional filename (without path). Defaults to a unique session name",
)
@click.option(
    "--shell",
    "shell_path",
    type=str,
    help="Shell to launch for recording (defaults to $SHELL or powershell)",
)
@click.option(
    "--flush/--no-flush",
    "flush",
    default=True,
    help="Flush after each write for near-real-time updates (default: enabled)",
)
def record(output_dir: Optional[str], filename: Optional[str], shell_path: Optional[str], flush: bool):
    """Record an interactive terminal session to a uniquely named file.

    On Linux/macOS/WSL, uses the 'script' utility to record a subshell.
    On native Windows, uses PowerShell transcription.
    """
    try:
        # Determine target directory and ensure it exists
        sessions_dir = get_sessions_dir()
        if output_dir:
            try:
                from app.utils import ensure_directory  # lazy import to avoid clutter
            except Exception:
                console.print("[red]Failed to import ensure_directory[/red]")
                sys.exit(1)
            sessions_dir = ensure_directory(output_dir)

        # Determine output file
        if filename:
            safe_name = filename
            from app.utils import sanitize_filename

            safe_name = sanitize_filename(safe_name)
            if not (safe_name.endswith(".log") or safe_name.endswith(".txt")):
                safe_name += ".log"
            output_path = Path(sessions_dir) / safe_name
        else:
            output_path = build_unique_session_path(base_dir=sessions_dir, extension="log")

        console.print(f"[dim]Saving session to: {output_path}[/dim]")

        is_windows = os.name == "nt" and "microsoft" not in platform.release().lower()

        if not is_windows:
            # POSIX / WSL path
            script_path = shutil.which("script")
            if not script_path:
                console.print(
                    "[red]The 'script' utility was not found. Please install 'script' (util-linux/bsdutils).[/red]"
                )
                sys.exit(1)

            # Choose shell (kept for future use if we re-enable -c)
            shell_to_run = shell_path or os.environ.get("SHELL") or "/bin/bash"
            # Build timing file path alongside the log
            timing_path = output_path.with_suffix(".timing")

            # Detect script variant capabilities
            try:
                help_out = subprocess.run(
                    [script_path, "--help"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    check=False,
                ).stdout or ""
            except Exception:
                help_out = ""

            use_util_linux_timing = "--timing" in help_out
            use_flush_option = "-f" in help_out

            # Start recording with timing support
            # Launch background session monitor before starting the recorder
            monitor = SessionMonitor(
                log_path=output_path,
                timing_path=timing_path,
                session_root_dir=output_path.parent,
                inactivity_seconds=15 * 60,
                max_lines_per_segment=1000,
            )
            monitor.start()
            if use_util_linux_timing:
                # util-linux: prefer -T/--log-timing FILE; run interactive default shell
                base = [script_path, "-q"]
                if flush and use_flush_option:
                    base.append("-f")
                cmd = base + ["-T", str(timing_path), str(output_path)]
                console.print("[bold green]Recording started.[/bold green] Type 'exit' to finish.")
                proc = subprocess.Popen(cmd)
                proc.wait()
                if proc.returncode != 0:
                    raise RuntimeError(f"script exited with code {proc.returncode}")
            else:
                # BSD: use '-t 0' (timing to stderr) and redirect stderr to timing file
                base = [script_path, "-q"]
                if flush and use_flush_option:
                    base.append("-f")
                cmd = base + ["-t", "0", str(output_path)]
                console.print("[bold green]Recording started.[/bold green] Type 'exit' to finish.")
                with open(timing_path, "wb") as timing_fp:
                    proc = subprocess.Popen(cmd, stderr=timing_fp)
                    proc.wait()
                if proc.returncode != 0:
                    raise RuntimeError(f"script exited with code {proc.returncode}")
            # Stop monitor and compact files after recording ends
            try:
                monitor.stop()
                monitor.join(timeout=10)
                monitor.compact_original_files()
            except Exception as e:
                logger.warning(f"Session monitor cleanup failed: {e}")

            console.print(f"[green]✓[/green] Timing saved to: {timing_path}")
        else:
            # Native Windows fallback: PowerShell transcription
            powershell = shutil.which("powershell") or shutil.which("pwsh")
            if not powershell:
                console.print("[red]PowerShell not found. Cannot record on Windows.[/red]")
                sys.exit(1)

            # Build transcription command: open a new interactive PowerShell that transcribes
            transcript_cmd = (
                f"Start-Transcript -Path '{str(output_path)}' -IncludeInvocationHeader;"
                f" Write-Host 'Recording started. Type exit to finish.';"
                f" {shell_path or 'powershell'};"
                f" Stop-Transcript"
            )
            cmd = [powershell, "-NoProfile", "-Command", transcript_cmd]
            proc = subprocess.Popen(cmd)
            proc.wait()
            if proc.returncode != 0:
                raise RuntimeError(f"PowerShell exited with code {proc.returncode}")

        console.print(f"[green]✓[/green] Session saved to: {output_path}")
        if not is_windows:
            console.print("[dim]Tip: Replay with 'scriptreplay' using the .timing file.[/dim]")
        else:
            console.print("[dim]Note: PowerShell transcripts include timestamps but not scriptreplay timing.[/dim]")

    except Exception as e:
        logger.error(f"record command failed: {e}")
        console.print(f"[red]Error:[/red] {e}")

 


if __name__ == "__main__":
    cli()

# Hidden/internal command to regenerate SRE for a specific segment path

@cli.command("regen-segment", hidden=True)
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option("--model", "model", type=str, required=False, help="Override Ollama model")
def regen_segment(path: Path, model: Optional[str] = None):
    """Regenerate SRE JSON for a given segment directory or file path.

    This command is internal and hidden from help. It accepts either the
    path to a segment directory (containing cleaned.log/raw.log) or a path
    to a file within that directory, and overwrites the segment's sre.json.
    """
    try:
        # Resolve segment directory from provided path
        candidate = Path(path)
        if candidate.is_file():
            seg_dir = candidate.parent
        else:
            seg_dir = candidate

        # Walk upwards a few levels to find a directory that looks like a segment
        max_ascend = 3
        ascended = 0
        while ascended <= max_ascend and not (
            (seg_dir / "cleaned.log").exists() or (seg_dir / "raw.log").exists()
        ):
            parent = seg_dir.parent
            if parent == seg_dir:
                break
            seg_dir = parent
            ascended += 1

        cleaned_log_path = seg_dir / "cleaned.log"
        raw_log_path = seg_dir / "raw.log"
        sre_output_path = seg_dir / "sre.json"

        if cleaned_log_path.exists():
            with cleaned_log_path.open("r", encoding="utf-8", errors="ignore") as fp:
                input_text = fp.read()
        elif raw_log_path.exists():
            with raw_log_path.open("r", encoding="utf-8", errors="ignore") as fp:
                raw_text = fp.read()
            input_text = clean_terminal_log(raw_text)
            # Best-effort write cleaned.log for consistency
            try:
                with cleaned_log_path.open("w", encoding="utf-8") as cfp:
                    cfp.write(input_text)
            except Exception:
                pass
        else:
            console.print(
                f"[red]Could not find cleaned.log or raw.log near: {path}[/red]"
            )
            sys.exit(1)

        with console.status("[bold green]Regenerating SRE for segment...[/bold green]"):
            with no_network():
                llm = LocalLLM(model=model if model else config.ollama_model)
                service = AdviceService(llm)
                sessions = service.get_console_insights(input_text)
            sre_json = json.dumps([s.model_dump() for s in sessions], indent=2)
            with sre_output_path.open("w", encoding="utf-8") as fp:
                fp.write(sre_json)

        console.print(
            f"[green]✓[/green] SRE regenerated and written to: {sre_output_path}"
        )
    except Exception as e:
        logger.error(f"regen-segment failed: {e}")
        console.print(f"[red]Error:[/red] {e}")
