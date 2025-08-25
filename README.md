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
                                     └──────────────────▶ │ Local GGUF Model   │◀──────▶│ Micro-Advice     │
                                                          │ (llama.cpp)        │        │ Output           │
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
- **GGUF Models**: Quantized for efficient local inference
- **Metal GPU Support**: Optimized for Apple Silicon
- **Configurable**: Adjust model size, GPU layers, context window

## 🚀 Quick Start

### 1. Installation

```bash
git clone https://github.com/ramper-labs/InnerBoard-local.git
cd InnerBoard-local
```

**For macOS (Apple Silicon):**
```bash
CMAKE_ARGS="-DLLAMA_METAL=on" pip install llama-cpp-python
pip install -r requirements.txt
```

**For other systems:**
```bash
pip install -r requirements.txt
```

### 2. Download a Model

**Option A: Quick Test (Small Model)**
```bash
# Download a small model for testing (~400MB)
hf download bartowski/Qwen2.5-0.5B-Instruct-GGUF --include "*Q4_K_M.gguf" --local-dir ft/data
export GGUF_MODEL_PATH="ft/data/Qwen2.5-0.5B-Instruct-Q4_K_M.gguf"
```

**Option B: Production (Full Model)**
```bash
# Download the full gpt-oss-20b model (~14GB)
hf download Maziyar/gpt-oss-20b-GGUF --include "*Q5_K_M.gguf" --local-dir ft/data
export GGUF_MODEL_PATH="ft/data/gpt-oss-20b.Q5_K_M.gguf"
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

- `GGUF_MODEL_PATH`: Path to your GGUF model file
- `N_GPU_LAYERS`: Number of layers to offload to GPU (-1 for all, 0 for CPU-only)
- `N_CTX`: Context window size (default: 2048)

### Example Configurations

**High Performance (GPU):**
```bash
export GGUF_MODEL_PATH="ft/data/gpt-oss-20b.Q5_K_M.gguf"
export N_GPU_LAYERS=-1
export N_CTX=4096
```

**CPU Only:**
```bash
export GGUF_MODEL_PATH="ft/data/Qwen2.5-0.5B-Instruct-Q4_K_M.gguf"
export N_GPU_LAYERS=0
export N_CTX=2048
```

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

You can use any GGUF model by setting the path:
```bash
export GGUF_MODEL_PATH="/path/to/your/model.gguf"
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

Enable verbose mode for troubleshooting:
```bash
export LLAMA_LOG_LEVEL=1
python -m app.main add --text "Your reflection"
```

## 🛡️ Security Features

- **Encrypted Storage**: All reflections encrypted at rest using Fernet (AES-128)
- **Network Isolation**: Automatic network blocking during AI processing
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
2. **Models**: Test and optimize different GGUF models
3. **UI**: Add Streamlit interface for better UX
4. **Export**: Implement privacy-preserving analytics

## 📄 License

Licensed under the Apache License 2.0. See [LICENSE](LICENSE) for details.

## 🙏 Acknowledgments

- Built on [llama.cpp](https://github.com/ggerganov/llama.cpp) for efficient local inference
- Uses [OpenAI's gpt-oss models](https://huggingface.co/openai/gpt-oss-20b) for reasoning
- Inspired by the need for private, offline onboarding support

---

*InnerBoard-local: Your private onboarding companion that stays on your device.*