# InnerBoard-local

InnerBoard-local is a 100% offline onboarding reflection coach that turns private journaling into structured signals and concrete micro-advice.

## Quick Start

### 1. Installation

First, clone the repository and install the required dependencies.

```bash
git clone <repo-url>
cd innerboard-local
```

For macOS with Apple Silicon (M1/M2/M3), install `llama-cpp-python` with Metal GPU support for the best performance:
```bash
CMAKE_ARGS="-DLLAMA_METAL=on" pip install llama-cpp-python
```

Then, install the rest of the dependencies:
```bash
pip install -r requirements.txt
```

### 2. Download the Model

This application uses a GGUF-quantized version of `gpt-oss-20b` to run efficiently on local hardware.

Please download the recommended model file (~14 GB):
[gpt-oss-20b.Q5_K_M.gguf](https://huggingface.co/Maziyar/gpt-oss-20b-GGUF/blob/main/gpt-oss-20b.Q5_K_M.gguf)

Place the downloaded `.gguf` file into the `ft/data/` directory.

### 3. Running the Application

To add a new reflection and get advice:
```bash
python -m app.main add --text "Your reflection text goes here."
```

To list all your past reflections:
```bash
python -m app.main list
```
---
*This project was initialized based on a detailed technical plan.*
