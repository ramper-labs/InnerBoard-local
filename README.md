# InnerBoard-local

**A 100% offline meeting prep assistant that turns your console history into team/manager-ready updates.**

InnerBoard-local analyzes your terminal sessions and produces concise, professional talking points for your next standup or 1:1. Everything runs locally on your machine—no data ever leaves your device.

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

## 🎯 What It Does

- **Record Console Sessions**: Capture interactive terminal activity with timing
- **Extract Insights (SRE)**: Turn raw logs into structured successes, blockers, and resources
- **Compose Meeting Prep (MAC)**: Generate team/manager updates and concrete recommendations
- **100% Local**: Uses local LLMs (Ollama); no data leaves your device
- **Modern CLI**: Beautiful terminal interface with progress indicators and rich formatting

## 🏗️ Architecture

```
┌─────────────────┐   process    ┌──────────────────┐   generate    ┌─────────────────┐
│  Terminal Logs  │ ────────────▶│  SRE Sessions    │ ────────────▶ │  MAC Meeting    │
│  (raw console)  │              │  (structured     │              │  Prep Output    │
└─────────────────┘              │   insights)      │              └─────────────────┘
         │                       └──────────────────┘                       │
         │                                │                                 │
         ▼                                ▼                                 ▼
┌─────────────────┐              ┌──────────────────┐              ┌─────────────────┐
│ Encrypted Vault │◀─────────────│ Local Ollama     │─────────────▶│ Team Updates    │
│ (SQLite+Fernet) │              │ Model Processing │              │ Recommendations │
└─────────────────┘              │ (localhost:11434)│              │ Manager Reports │
                                 └──────────────────┘              └─────────────────┘
```

## ✨ Features

### 🔒 **Industry-Grade Security**
- **PBKDF2 Key Derivation**: 100,000 iterations for cryptographically secure key generation
- **Fernet AES-128 Encryption**: Industry-standard encryption for all stored data
- **Password-Protected Keys**: Optional password encryption of master keys with integrity validation
- **Input Validation**: Comprehensive protection against SQL injection, XSS, path traversal attacks
- **Data Integrity**: SHA256 checksums ensure data hasn't been tampered with
- **Network Isolation**: Only allows loopback connections to Ollama (ports 11434)
- **Secure File Deletion**: Overwrites sensitive files before deletion

### 🧠 **AI-Powered Analysis**
- **SRE (Structured Reflection Extraction)**: Advanced AI extracts structured insights
  - Key successes identification with specifics and context
  - Blocker identification with impact assessment and resolution hints
  - Resource needs assessment and recommendations
  - Session summaries with actionable details
- **MAC (Meeting Advice Composer)**: Generates professional meeting prep content
  - Team updates with progress highlights and next focus areas
  - Manager updates with outcomes, risks, and resource needs
  - Concrete recommendations with actionable next steps
  - Multi-session synthesis for comprehensive reporting

### 🎨 **User-Friendly Low-Touch Experience**
- **Rich Terminal Interface**: Beautiful tables, progress bars, and color-coded output
- **Comprehensive Help**: Detailed command help and usage guidance
- **Error Handling**: User-friendly messages with actionable solutions
- **Progress Indicators**: Real-time feedback during AI processing
- **Multi-format Display**: Tables, panels, structured data, and formatted text

### ⚡ **High Performance**
- **Intelligent Caching**: TTL-based caching (responses, models, reflections)
- **Connection Pooling**: Efficient Ollama client management (max 5 connections)
- **SQLite Optimization**: WAL mode, foreign keys, indexed queries
- **GPU Acceleration**: Leverages platform capabilities via Ollama
- **Memory Management**: Automatic cache cleanup and size limits
- **Thread-Safe Operations**: All caching and connections are thread-safe

### ⚙️ **Flexible Configuration**
- **Environment Variables**: Full configuration via env vars and .env files
- **Auto-loading**: .env files loaded automatically with python-dotenv
- **Dynamic Model Switching**: Easy switching between Ollama models
- **Validation**: Configuration validation with helpful error messages
- **Runtime Updates**: Configuration changes take effect immediately

## 🚀 **Getting Started**

Choose the installation method that works best for you:

### **⚡ Quick Start (Recommended)**
For new users, simply run our automated setup script:

```bash
# Download and run the quick start script
curl -fsSL https://raw.githubusercontent.com/ramper-labs/InnerBoard-local/main/quickstart.sh | bash
```

This script will:
- ✅ Check your system prerequisites
- ✅ Install InnerBoard-local automatically
- ✅ Set up Ollama and download AI models
- ✅ Initialize your encrypted vault
- ✅ Verify everything works

**That's it!** You're ready to start using InnerBoard-local.

---

### **📦 Alternative Installation Methods**

#### **Option A: Manual Installation (Recommended)**

**Prerequisites:**
- Python 3.8+ ([download here](https://python.org/downloads/))
- Git ([download here](https://git-scm.com/downloads))
- Ollama ([download here](https://ollama.com/download))

```bash
# 1. Clone the repository
git clone https://github.com/ramper-labs/InnerBoard-local.git
cd InnerBoard-local

# 2. Install InnerBoard
pip install -e .

# 3. Run automated setup
innerboard setup
```

#### **Option B: Docker Installation (Flaky at the moment)**

```bash
# 1. Clone the repository
git clone https://github.com/ramper-labs/InnerBoard-local.git
cd InnerBoard-local

# 2. Run Docker setup script
./docker-setup.sh
```

Or manually:
```bash
# Build and start services
docker-compose up -d

# Initialize InnerBoard (run once)
docker-compose exec innerboard innerboard init
```

---

### **🔧 Post-Installation Setup**

After installation, verify everything is working:

```bash
# Check system health
innerboard health

# View available commands
innerboard --help
```

---

**System Requirements:**
- **RAM**: 8GB minimum, 16GB recommended
- **Storage**: 20GB free space for AI models
- **OS**: Linux, macOS, or Windows (WSL)

## **🕹️ Record a Console Session**

Use the built-in recorder to capture an interactive shell session. By default, writes are flushed frequently for near-real-time updates; you can disable with `--no-flush`.

```bash
# Start recording (type `exit` to finish)
innerboard record

# Useful options
# --dir PATH      Save session under a custom directory
# --name NAME     Filename (auto-generated if omitted)
# --shell PATH    Shell to launch (defaults to $SHELL or /bin/bash)
# --flush/--no-flush  Control write flushing (default: --flush)
```

Session artifacts (raw log, timing, segments, SRE JSON) are saved under your app data directory, e.g. `~/.local/share/InnerBoard/sessions/` on Linux/WSL.

---

## **🗣️ Generate Meeting Prep**

Aggregate all recorded sessions and produce crisp talking points.

```bash
# Generate concise meeting prep
innerboard prep

# Include detailed SRE insights (verbose)
innerboard prep --show-sre
```

---

## **✍️ Optional: Save a Private Note**

### **Initialize Vault and Add a Note**

```bash
# One-time: create your encrypted vault for notes (password prompt)
innerboard init

# Optional: avoid prompts by exporting your password
export INNERBOARD_KEY_PASSWORD="your_secure_password_here"
```

```bash
# Save a short private note alongside your sessions to remind your future self
innerboard add "Investigated auth token validation; planning staging tests next."
```
---

## **🔧 Suggested Workflow**

1) Record meaningful work sessions: `innerboard record`
2) Optionally jot private notes to remind yourself: `innerboard add "Short note"`
3) Generate prep before standup/1:1: `innerboard prep --show-sre`


## **🎯 Next Steps**

### **Before Standup / 1:1**
- Run `innerboard prep` for concise talking points
- Use `--show-sre` to include detailed context when needed

### **Weekly Review**
- Skim SRE session summaries to spot patterns
- Capture follow-ups as private notes with `innerboard add "..."`

---

## **📋 Quick Reference**

### **Installation & Setup**
| Command | Description | Example |
|---------|-------------|---------|
| `curl -fsSL https://raw.githubusercontent.com/ramper-labs/InnerBoard-local/main/quickstart.sh \| bash` | One-command installation | Quick start script |
| `innerboard setup` | Interactive setup wizard | `innerboard setup --docker` |
| `innerboard health` | Comprehensive health check | `innerboard health --detailed` |
| `./docker-setup.sh` | Docker deployment setup | Automated Docker setup |

### **Core Commands**
| Command | Description | Example |
|---------|-------------|---------|
| `innerboard init` | Initialize encrypted vault | `innerboard init` |
| `innerboard add "text"` | Add private reflection | `innerboard add "Struggling with auth tokens"` |
| `innerboard list` | View saved reflections | `innerboard list --limit 10` |
| `innerboard delete <id>` | Delete specific reflection | `innerboard delete 5 --force` |
| `innerboard del <id>` | Alias for delete | `innerboard del 5 --force` |
| `innerboard clear` | Delete ALL reflections | `innerboard clear --force` |
| `innerboard status` | Vault status and stats | `innerboard status` |

### **Session Recording & Analysis**
| Command | Description | Example |
|---------|-------------|---------|
| `innerboard record` | Record terminal session | `innerboard record --name standup` |
| `innerboard prep` | Generate meeting prep | `innerboard prep --show-sre` |
| `innerboard models` | List available AI models | `innerboard models` |

### **Help Commands**
| Command | Description | Example |
|---------|-------------|---------|
| `innerboard --help` | Show all commands | `innerboard add --help` |


---

## **🚨 Important Security Notes**

- **Your data stays local**: No information leaves your device
- **Encryption**: All reflections are encrypted at rest
- **Network isolation**: Only local Ollama connections allowed during processing
- **Password protection**: Your master key is password-protected
- **Secure deletion**: Sensitive files are overwritten before deletion


### **Configuration File**

```bash
# Create your config file
cp env.example .env
```

### **Available Models**

```bash
# See what models are available
innerboard models

# Expected output:
#    Available   
#  Ollama Models
# ┏━━━━━━━━━━━━━┓
# ┃ Model Name  ┃
# ┡━━━━━━━━━━━━━┩
# │ gpt-oss:20b │
# └─────────────┘
#
# Current model: gpt-oss:20b
```

---

## **🛠️ Troubleshooting Guide**

### **Common Issues**

#### **Setup Issues**

**Quick start script fails:**
```bash
# Try manual installation
git clone https://github.com/ramper-labs/InnerBoard-local.git
cd InnerBoard-local
innerboard setup
```

**Docker setup fails:**
```bash
# Check Docker status
docker --version
docker-compose --version

# Clean and retry
docker system prune -a
./docker-setup.sh
```

#### **Health Check Failures**

**Run detailed health check:**
```bash
innerboard health --detailed
```

**Common health check issues:**
- ❌ **Python Environment**: Upgrade to Python 3.8+
- ❌ **Ollama Service**: Run `ollama serve`
- ❌ **AI Model**: Run `ollama pull gpt-oss:20b`
- ❌ **Vault System**: Run `innerboard init`

#### **"Model not available" Error**
```bash
# Solution: Pull the model
ollama pull gpt-oss:20b

# Check if Ollama is running
ollama list
```

#### **"Password required" Error**
```bash
# Set environment variable
export INNERBOARD_KEY_PASSWORD="your_password"

# Or use the --password flag
innerboard status --password your_password
```

#### **"No such option: --password" Error**
```bash
# Some commands don't support --password flag
# Use environment variable instead:
INNERBOARD_KEY_PASSWORD="your_password" innerboard list
```

#### **Permission Errors**
```bash
# Ensure write permissions in current directory
chmod 755 .
```

#### **Ollama Not Starting**
```bash
# Restart Ollama service
# macOS:
brew services restart ollama

# Linux:
sudo systemctl restart ollama

# Or start manually:
ollama serve
```

### **Getting Help**

```bash
# General help
innerboard --help

# Command-specific help
innerboard add --help
innerboard list --help
```

---

**Backup your vault:**
```bash
# Your encrypted data is in:
# - vault.db (encrypted reflections)
# - vault.key (encrypted master key)
cp vault.db vault.db.backup
cp vault.key vault.key.backup
```

### Test Coverage Areas

| Component | Tests | Status |
|-----------|-------|--------|
| **Security** | 16 tests | ✅ All passing |
| **Caching** | 17 tests | ✅ All passing |
| **Integration** | 11 tests | ✅ All passing |
| **Network Safety** | 6 tests | ✅ All passing |
| **Total** | 50 tests | ✅ All passing |

### Manual Testing Verified
- ✅ First-run setup and recording flow
- ✅ AI analysis with real Ollama models
- ✅ Security validation (blocks SQL injection, XSS)
- ✅ Configuration file loading
- ✅ Error handling and recovery
- ✅ Data persistence and integrity
- ✅ Performance optimization
- ✅ Multi-reflection management

## 📄 License

Licensed under the Apache License 2.0. See [LICENSE](LICENSE) for details.

## 🙏 Acknowledgments

- Powered by [Ollama](https://github.com/ollama/ollama) for local model serving
- Inspired by the need for private, offline meeting preparation
- Built with [Click](https://click.palletsprojects.com/) for CLI, [Rich](https://rich.readthedocs.io/) for UI, [Cryptography](https://cryptography.io/) for security

---

## 📊 Example Output Formats

### Input Terminal Log:
```bash
~/project $ kubectl get pods -n production
NAME                     READY   STATUS    RESTARTS   AGE
auth-service-7d4b8f9c6-x2p9q   1/1     Running   0          2d
~/project $ kubectl describe pod auth-service-7d4b8f9c6-x2p9q -n production
# ... detailed pod information ...
~/project $ git log --oneline -5
a1b2c3d Fix authentication token validation
e4f5g6h Update user service endpoints
# ... more git history ...
```

### SRE Session Output:
```json
[
  {
    "summary": "Investigated authentication service in production, reviewed recent commits for token validation fixes.",
    "key_successes": [
      {
        "desc": "Successfully accessed production Kubernetes cluster",
        "specifics": "kubectl get pods -n production",
        "adjacent_context": "Authentication service pod running stable for 2 days"
      },
      {
        "desc": "Identified recent authentication fixes in git history",
        "specifics": "git log --oneline -5",
        "adjacent_context": "Found commit a1b2c3d fixing token validation"
      }
    ],
    "blockers": [],
    "resources": [
      "kubectl describe pod auth-service-7d4b8f9c6-x2p9q -n production",
      "Git commit a1b2c3d - authentication token validation fix"
    ]
  }
]
```

### MAC Meeting Prep Output:
```json
{
  "team_update": [
    "✅ Successfully accessed production K8s cluster and verified auth service stability",
    "📊 Reviewed recent authentication fixes, found token validation improvements",
    "🎯 Next focus: testing token validation changes in staging environment"
  ],
  "manager_update": [
    "Team has good access to production systems and can debug effectively",
    "Recent authentication fixes appear stable with 2+ days uptime",
    "No current blockers, investigation skills developing well"
  ],
  "recommendations": [
    "Test the authentication token validation fix in staging environment",
    "Document the debugging process for future authentication issues",
    "Schedule follow-up review of authentication service architecture"
  ]
}
```

**Your offline meeting prep companion that stays on your device.** ✨