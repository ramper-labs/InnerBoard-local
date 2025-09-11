#!/usr/bin/env bash
set -euo pipefail

# Cross-platform native quickstart for developers (macOS/Linux)
# - Creates Python venv, installs package, ensures Ollama is running, pulls model,
#   copies example.env -> .env, initializes vault, runs health.

BLUE="\033[0;34m"; GREEN="\033[0;32m"; YELLOW="\033[1;33m"; RED="\033[0;31m"; NC="\033[0m"
say() { echo -e "${BLUE}$*${NC}"; }
ok() { echo -e "${GREEN}✓ $*${NC}"; }
warn() { echo -e "${YELLOW}⚠ $*${NC}"; }
die() { echo -e "${RED}✗ $*${NC}" >&2; exit 1; }

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    die "Missing required command: $1"
  fi
}

# Resolve script directory; when run via curl|bash, fall back to current directory
if [[ -n "${BASH_SOURCE:-}" ]]; then
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
else
  SCRIPT_DIR="$PWD"
fi
cd "$SCRIPT_DIR"

say "InnerBoard-local quickstart (native: macOS/Linux)"

# Args and environment
PW="${INNERBOARD_KEY_PASSWORD:-}"
AUTO_YES=0
NON_INTERACTIVE=0
IS_TTY=0
if [ -t 0 ] && [ -t 1 ]; then IS_TTY=1; fi
TTY_INPUT=""
if [ -r /dev/tty ]; then TTY_INPUT="/dev/tty"; fi

while [ $# -gt 0 ]; do
  case "$1" in
    --password=*)
      PW="${1#*=}"
      shift
      ;;
    --password)
      shift
      PW="${1-}"
      [ -z "$PW" ] && die "--password requires a value"
      shift
      ;;
    --yes|-y)
      AUTO_YES=1
      shift
      ;;
    --non-interactive|--ci)
      NON_INTERACTIVE=1
      shift
      ;;
    *)
      # ignore unknown args for forward-compat
      shift
      ;;
  esac
done

# Preconditions
require_cmd python3 || true
require_cmd git || true

# If not in the project directory (e.g., running via curl|bash), clone and enter repo
if [ ! -f pyproject.toml ] && [ ! -f setup.py ] && [ ! -d app ]; then
  say "Project not found in current directory. Cloning InnerBoard-local..."
  git clone https://github.com/ramper-labs/InnerBoard-local.git || die "Failed to clone repository"
  cd InnerBoard-local || die "Failed to enter repository directory"
fi

# Python version info
PYV="$(python3 -c 'import sys; print("%d.%d"%sys.version_info[:2])' 2>/dev/null || echo "0.0")"
case "$PYV" in
  3.10|3.11|3.12|3.13) : ;; 
  *) warn "Detected Python $PYV. Recommended: 3.11 (3.10–3.13 supported)." ;;
esac

# Ensure venv
if [ ! -d .venv ]; then
  say "Creating virtual environment (.venv)"
  python3 -m venv .venv || die "Failed to create virtual environment"
fi

# Activate venv (shellcheck disable=SC1091)
source .venv/bin/activate || die "Failed to activate virtual environment"
ok "Virtual environment ready"

# Do not auto-create .env; inform user if missing
if [ ! -f .env ]; then
  warn ".env not found; defaults will be used. To customize, copy example.env to .env"
fi

say "Installing InnerBoard-local (editable)"
pip install --upgrade pip >/dev/null 2>&1 || true
pip install -e . || die "pip install failed"
ok "Package installed"

# Ensure Ollama present and running
if ! command -v ollama >/dev/null 2>&1; then
  say "Ollama not found. Attempting to install..."
  if [[ "${OSTYPE:-}" == darwin* ]]; then
    if command -v brew >/dev/null 2>&1; then
      brew install ollama || die "Failed to install Ollama via Homebrew"
    else
      die "Homebrew not found. Install Homebrew (https://brew.sh/) or install Ollama manually from https://ollama.com"
    fi
  else
    curl -fsSL https://ollama.com/install.sh | sh || die "Failed to install Ollama via install.sh"
  fi
fi

say "Starting Ollama service"
if [[ "${OSTYPE:-}" == darwin* ]]; then
  (brew services start ollama >/dev/null 2>&1 || true)
fi
if ! pgrep -x ollama >/dev/null 2>&1; then
  (ollama serve >/dev/null 2>&1 &) || true
fi

# Wait for Ollama API
say "Waiting for Ollama (http://localhost:11434)"
for i in {1..30}; do
  if curl -fsS http://localhost:11434/api/tags >/dev/null 2>&1; then
    ok "Ollama is responding"
    break
  fi
  sleep 1
  if [ "$i" -eq 30 ]; then die "Ollama did not start"; fi
done

say "Pulling default model (gpt-oss:20b)"
ollama pull gpt-oss:20b || warn "Model pull failed; you can retry later: ollama pull gpt-oss:20b"

say "Vault password setup"
if [ -n "${PW:-}" ]; then
  : # password provided via flag or env
else
  if [ -n "$TTY_INPUT" ] && [ "$NON_INTERACTIVE" -ne 1 ]; then
    attempts=0
    while :; do
      attempts=$((attempts+1))
      read -s -p "Enter vault password: " __PW1 < "$TTY_INPUT"; echo
      read -s -p "Confirm vault password: " __PW2 < "$TTY_INPUT"; echo
      if [ -z "${__PW1}" ]; then warn "Password cannot be empty"; fi
      if [ "${__PW1}" = "${__PW2}" ] && [ -n "${__PW1}" ]; then PW="${__PW1}"; unset __PW1 __PW2; break; fi
      if [ $attempts -ge 3 ]; then die "Passwords did not match after 3 attempts"; fi
      warn "Passwords do not match. Try again."
    done
  else
    die "Non-interactive run detected. Provide a password via --password or INNERBOARD_KEY_PASSWORD."
  fi
fi

say "Initializing vault"
if innerboard init --password "${PW}"; then
  ok "Vault initialized"
else
  warn "Vault init may require manual run: innerboard init"
fi

# Offer to save password (skip in non-interactive contexts)
if [ -n "$TTY_INPUT" ] && [ "$NON_INTERACTIVE" -ne 1 ]; then
  read -r -p "Save password to .env (plaintext)? [y/N]: " __ANS < "$TTY_INPUT" || true
  case "${__ANS}" in
    y|Y|yes|YES)
      if [ ! -f .env ]; then
        : > .env
      fi
      # Update or append INNERBOARD_KEY_PASSWORD safely (portable awk)
      awk -v kv="INNERBOARD_KEY_PASSWORD=${PW}" '
        BEGIN{set=0}
        /^INNERBOARD_KEY_PASSWORD=/{print kv; set=1; next}
        {print}
        END{if(!set) print kv}
      ' .env > .env.tmp && mv .env.tmp .env
      chmod 600 .env 2>/dev/null || true
      ok "Saved password to .env (plaintext). Consider protecting this file."
      ;;
    *)
      say "Password not saved to .env"
      ;;
  esac
  unset __ANS
else
  say "Skipping .env save prompt (non-interactive)."
fi
unset PW

say "Running health check"
if innerboard health --detailed; then
  ok "Health check passed"
else
  warn "Health check reported issues"
fi

echo
ok "Setup complete!"
ABS_REPO_DIR="$(pwd)"
echo "Next steps (run in your shell):"
echo "  cd ${ABS_REPO_DIR}"
echo "  source .venv/bin/activate"
echo "Then try:"
echo "  innerboard record"
echo "  innerboard add \"My reflection\""
echo "  innerboard prep --show-sre"
