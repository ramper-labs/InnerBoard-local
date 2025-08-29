# InnerBoard-local

**A 100% offline onboarding reflection coach that turns private journaling into structured signals and concrete micro-advice.**

InnerBoard-local is designed for new hires who want to reflect privately on their onboarding experience while getting actionable advice. Everything runs locally on your machine—no data ever leaves your device.

## 🎯 What It Does

- **Private Reflection**: Write honest reflections about your onboarding experience
- **Structured Analysis**: AI extracts key points, blockers, and confidence changes from your text
- **Actionable Advice**: Get specific steps and checklists tailored to your situation
- **Zero Egress**: All processing happens offline with encrypted local storage

## 🏗️ Architecture

```
┌──────────────┐  write     ┌─────────────────┐   analyze   ┌────────────────────┐   compose   ┌──────────────────┐
│  Journal CLI │ ─────────▶ │ Encrypted Vault │ ──────────▶ │  SRE (Reflection   │ ──────────▶ │ MAC (Advice      │
│              │            │ (SQLite+Fernet) │            │  Extraction)       │            │  Composer)       │
└──────────────┘            └─────────────────┘            └────────────────────┘            └──────────────────┘
                                     │                               │                               │
                                     │                               ▼                               ▼
                                     │                    ┌────────────────────┐        ┌──────────────────┐
                                     └──────────────────▶ │ Local Ollama Model │◀──────▶│ Micro-Advice     │
                                                          │ (localhost:11434)  │        │ Output           │
                                                          └────────────────────┘        └──────────────────┘
```

## ✨ Features

### 🔒 **Privacy First**
- **Encrypted Storage**: All reflections encrypted with Fernet (AES-128)
- **No Network Calls**: Network guard blocks all egress during processing
- **Local AI**: Models run entirely on your machine

### 🧠 **Smart Processing**
- **SRE (Structured Reflection Extraction)**: Converts raw text to structured data
  - Key points extraction
  - Blocker identification with taxonomy mapping
  - Confidence delta tracking
  - Resource needs assessment
- **MAC (Micro-Advice Composer)**: Generates actionable guidance
  - Concrete steps with timeframes
  - Progress checklists
  - Urgency assessment

### ⚡ **Performance**
- **Ollama Local Serving**: Uses Ollama to run models locally
- **GPU Support**: Leverages your platform's capabilities via Ollama
- **Configurable**: Choose model by name and adjust Ollama host

## 🚀 Quick Start

### 1. Installation

```bash
git clone https://github.com/ramper-labs/InnerBoard-local.git
cd InnerBoard-local
```

**Install Python dependencies:**
```bash
pip install -r requirements.txt
```

**Install and run Ollama:**
- Download Ollama: `https://ollama.com/download`
- Ensure the server is running (default: `http://localhost:11434`).

**Pull a model (example):**
```bash
ollama pull gpt-oss:20b
```

### 2. Select a Model

The default model is `gpt-oss:20b`. To change it:
```bash
export OLLAMA_MODEL="llama3.1"
```

### 3. Usage

**Add a reflection and get advice:**
```bash
python -m app.main add --text "I'm struggling with the new authentication service. The documentation seems outdated and I can't get JWT validation working. Been stuck for hours."
```

**List all your reflections:**
```bash
python -m app.main list
```

## 📋 Example Output

**Input:**
> "I spent the whole day trying to get the Kubernetes ingress to route correctly. The docs are confusing and I couldn't find good examples."

**SRE Output:**
```json
{
  "key_points": ["Ingress routing issues", "Documentation clarity problems"],
  "blockers": ["k8s ingress config", "missing examples"],
  "resources_needed": ["working ingress example", "clearer documentation"],
  "confidence_delta": -0.6
}
```

**MAC Output:**
```json
{
  "steps": [
    "Book a 20-min session with a senior engineer familiar with k8s",
    "Find working ingress examples in the team's repository",
    "Create a personal reference doc with working configs"
  ],
  "checklist": [
    "Session scheduled with k8s expert",
    "Example configs collected",
    "Personal reference created",
    "Test deployment successful"
  ],
  "urgency": "medium"
}
```

## ⚙️ Configuration

### Environment Variables

- `OLLAMA_MODEL`: Name of the model to use (default: `gpt-oss:20b`)
- `OLLAMA_HOST`: Optional custom Ollama host (default: `http://localhost:11434`)

### Example Configuration

Ollama manages CPU/GPU automatically depending on your setup.

## 🧪 Testing

Run the network safety tests:
```bash
pytest tests/test_no_network.py -v
```

Test storage encryption:
```bash
pytest tests/test_storage_crypto.py -v
```

## 📁 Project Structure

```
InnerBoard-local/
├── app/                    # Core application
│   ├── main.py            # CLI interface
│   ├── llm.py             # Local model loader
│   ├── advice.py          # SRE + MAC orchestration
│   ├── storage.py         # Encrypted vault
│   ├── safety.py          # Network guard
│   └── models.py          # Pydantic schemas
├── ft/                    # Fine-tuning assets
│   └── data/              # Model files (gitignored)
├── tests/                 # Test suite
├── prompts/               # System prompts
└── README.md              # This file
```

## 🔧 Advanced Usage

### Custom Models

Use any Ollama model by name:
```bash
export OLLAMA_MODEL="llama3.1"
python -m app.main add --text "Your reflection"
```

### Batch Processing

Process multiple reflections from a file:
```bash
while IFS= read -r line; do
    python -m app.main add --text "$line"

done < reflections.txt
```

### Debugging

Enable verbose logging in your shell as needed; Ollama server logs appear in its console.

## 🛡️ Security Features

- **Encrypted Storage**: All reflections encrypted at rest using Fernet (AES-128)
- **Network Isolation**: Blocks all outbound traffic during AI processing, allowing only loopback to `localhost:11434` for Ollama
- **Local Processing**: No data transmission to external services
- **Memory Safety**: Models run in isolated processes

## 🎯 Use Cases

- **New Employee Onboarding**: Daily reflection and guidance
- **Skill Development**: Track learning progress and blockers  
- **Team Integration**: Identify social and technical challenges
- **Process Improvement**: Structured feedback for onboarding programs

## 🤝 Contributing

This project follows the technical plan for the "Best Local Agent" hackathon category. Key areas for contribution:

1. **Fine-tuning**: Improve SRE accuracy with domain-specific training data
2. **Models**: Test and optimize different Ollama models
3. **UI**: Add Streamlit interface for better UX
4. **Export**: Implement privacy-preserving analytics

## 📄 License

Licensed under the Apache License 2.0. See [LICENSE](LICENSE) for details.

## 🙏 Acknowledgments

- Powered by [Ollama](https://github.com/ollama/ollama) for local model serving
- Inspired by the need for private, offline onboarding support

---

*InnerBoard-local: Your private onboarding companion that stays on your device.*