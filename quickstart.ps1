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

Say "Vault password setup"
$max = 3; $try = 0
while ($true) {
  $try += 1
  $pw1 = Read-Host -AsSecureString "Enter vault password"
  $pw2 = Read-Host -AsSecureString "Confirm vault password"
  $bstr1 = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($pw1)
  $bstr2 = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($pw2)
  $p1 = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr1)
  $p2 = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr2)
  [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr1)
  [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr2)
  if ([string]::IsNullOrEmpty($p1)) { Warn "Password cannot be empty" }
  if ($p1 -eq $p2 -and -not [string]::IsNullOrEmpty($p1)) { $PW = $p1; break }
  if ($try -ge $max) { Die "Passwords did not match after $max attempts" }
  Warn "Passwords do not match. Try again."
}

Say "Initializing vault"
try {
  innerboard init --password "$PW"
  Ok "Vault initialized"
} catch {
  Warn "Vault init may require manual run: innerboard init"
}

# Offer to save password to .env (plaintext)
try {
  $save = Read-Host "Save password to .env (plaintext)? [y/N]"
  if ($save -match '^(y|yes)$') {
    if (-not (Test-Path .env)) { New-Item -ItemType File -Path .env -Force | Out-Null }
    $content = Get-Content .env -Raw -ErrorAction SilentlyContinue
    if ($null -eq $content) { $content = "" }
    $lines = $content -split "`n"
    $found = $false
    for ($i=0; $i -lt $lines.Length; $i++) {
      if ($lines[$i] -match '^INNERBOARD_KEY_PASSWORD=') { $lines[$i] = "INNERBOARD_KEY_PASSWORD=$PW"; $found = $true }
    }
    if (-not $found) { $lines += "INNERBOARD_KEY_PASSWORD=$PW" }
    ($lines -join "`n") | Set-Content .env -NoNewline
    try { icacls .env /inheritance:r /grant:r "$env:USERNAME:(R)" | Out-Null } catch { }
    Ok "Saved password to .env (plaintext). Consider protecting this file."
  } else {
    Say "Password not saved to .env"
  }
} catch { Warn "Could not update .env" }
Remove-Variable PW -ErrorAction SilentlyContinue

Say "Running health check"
try {
  innerboard health --detailed
  Ok "Health check passed"
} catch {
  Warn "Health check reported issues"
}

Ok "Setup complete!"
Write-Host "Next steps:"; Write-Host "  .\.venv\Scripts\Activate.ps1"; Write-Host "  innerboard record"; Write-Host "  innerboard add \"My reflection\""; Write-Host "  innerboard prep --show-sre"


