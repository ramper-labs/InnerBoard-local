#!/usr/bin/env pwsh
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Say($msg) { Write-Host $msg -ForegroundColor Blue }
function Ok($msg) { Write-Host "✓ $msg" -ForegroundColor Green }
function Warn($msg) { Write-Host "! $msg" -ForegroundColor Yellow }
function Die($msg) { Write-Host "✗ $msg" -ForegroundColor Red; exit 1 }

# Determine working directory
# - When run from a file, $PSScriptRoot is populated
# - When piped to iex, use the current directory
$scriptRoot = $PSScriptRoot
if ([string]::IsNullOrEmpty($scriptRoot)) { $scriptRoot = (Get-Location).Path }
Set-Location -Path $scriptRoot -ErrorAction SilentlyContinue

Say "InnerBoard-local quickstart (native: Windows PowerShell)"

# Check prereqs
if (-not (Get-Command py -ErrorAction SilentlyContinue)) { Die "Python (py) not found. Install Python 3.11+ from winget or python.org" }
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { Die "Git not found. Install Git from winget or git-scm.com" }

# If not already in repo, clone it locally (supports iwr ... | iex usage)
if (-not (Test-Path 'setup.py') -and -not (Test-Path 'pyproject.toml') -and -not (Test-Path 'app\cli.py')) {
  Say "Cloning InnerBoard-local repository"
  if (-not (Get-Command git -ErrorAction SilentlyContinue)) { Die "Git not found. Install Git from winget or git-scm.com" }
  git clone https://github.com/ramper-labs/InnerBoard-local.git
  Set-Location InnerBoard-local
}

# Ensure venv
if (-not (Test-Path .venv)) {
  Say "Creating virtual environment (.venv)"
  try { py -3.11 -m venv .venv }
  catch { py -m venv .venv }
}

& .\.venv\Scripts\Activate.ps1
Ok "Virtual environment ready"

# Do not auto-create .env; inform user if missing
if (-not (Test-Path .env)) {
  Warn ".env not found; defaults will be used. To customize, copy example.env to .env"
}

Say "Installing InnerBoard-local (editable)"
python -m pip install --upgrade pip | Out-Null
pip install -e .
Ok "Package installed"

# Ensure Ollama
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
  Say "Ollama not found. Attempting install via winget..."
  if (Get-Command winget -ErrorAction SilentlyContinue) {
    winget install --id Ollama.Ollama -e --accept-package-agreements --accept-source-agreements
  } else {
    Die "winget not available. Install Ollama from https://ollama.com and rerun."
  }
}

Say "Ensure Ollama service is running (launching app if needed)"
try { ollama list | Out-Null } catch { Start-Process "Ollama" -ErrorAction SilentlyContinue | Out-Null; Start-Sleep -Seconds 3 }

Say "Pulling default model (gpt-oss:20b)"
try { ollama pull gpt-oss:20b } catch { Warn "Model pull failed; run manually: ollama pull gpt-oss:20b" }

Say "Initializing vault (you will be prompted for a password)"
try {
  innerboard init
  Ok "Vault initialized"
} catch {
  Warn "Vault init may require manual run: innerboard init"
}

Say "Running health check"
try {
  innerboard health --detailed
  Ok "Health check passed"
} catch {
  Warn "Health check reported issues"
}

Ok "Setup complete!"
Write-Host "Next steps:"; Write-Host "  .\.venv\Scripts\Activate.ps1"; Write-Host "  innerboard record"; Write-Host "  innerboard add \"My reflection\""; Write-Host "  innerboard prep --show-sre"


