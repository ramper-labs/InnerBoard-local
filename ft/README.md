# Fine-tuning for InnerBoard Terminal Transcript Analysis

This directory contains the synthetic data generation infrastructure for training GPT-OSS models to analyze terminal transcripts and generate structured session reports.

## Files

- **`synth.py`** - Generates synthetic training data with realistic terminal scenarios in GPT-OSS Harmony format
- **`data/`** - Directory for training data (created automatically)
- **`gpt_oss_(20B)_Fine_tuning.ipynb`** - Google Colab notebook for GPT-OSS fine-tuning

## Quick Start

### 1. Generate Training Data

```bash
cd ft/
python synth.py
```

This creates:
- `data/pairs.jsonl` - Input/output pairs for training (128 examples)
- `data/harmony_messages.jsonl` - GPT-OSS Harmony format for Colab training (128 examples)

### 2. Upload to Google Colab

1. Upload `harmony_messages.jsonl` to your Colab environment
2. Open the GPT-OSS fine-tuning notebook
3. Replace the dataset loading section with your data

### 3. Fine-tune with GPT-OSS Colab Notebook

Use the provided Colab notebook to:
- Load the GPT-OSS 20B model with Unsloth optimizations
- Train with LoRA adapters for memory efficiency
- Save the fine-tuned model

## Training Data Format

The synthetic data generator creates realistic terminal scenarios including:

- **Python/pytest testing sessions**
- **Docker build failures** 
- **Git merge conflicts**
- **Node.js builds with security vulnerabilities**
- **Database migration errors**
- **Kubernetes RBAC permission issues**
- **Port conflicts during development**
- **Python version compatibility issues**
- **CI/CD pipeline successes**
- **Environment version checks**
- **Terraform infrastructure planning**
- **Redis connection issues**
- **Webpack build performance problems**
- **MySQL/Laravel database migrations**
- **SSL certificate management**
- **Elasticsearch index operations**
- **Ansible deployment automation**
- **Monitoring and alerting (Prometheus/Grafana)**
- **Load testing with Apache Bench**
- **Database backup verification**
- **Go build compilation errors**
- **Nginx configuration testing**
- **AWS CLI deployment operations**
- **Java Maven test failures**
- **Prometheus metrics querying**

Each scenario generates:
- Realistic terminal output with ANSI codes
- Structured JSON output matching the SRE session schema
- GPT-OSS Harmony format with developer/user/assistant roles

## Model Output Schema

The trained model produces JSON in this format:

```json
[
  {
    "summary": "High-level overview of what happened in this session",
    "key_successes": [
      {
        "desc": "Short description of a concrete success",
        "specifics": "Command(s) or evidence from the transcript",
        "adjacent_context": "Any context like counts, times, branch names"
      }
    ],
    "blockers": [
      {
        "desc": "Problem described succinctly",
        "impact": "What this blocks or risks",
        "owner_hint": "Likely owner or team",
        "resolution_hint": "First debugging direction"
      }
    ],
    "resources": ["Short actionable resources or next steps"]
  }
]
```

## GPT-OSS Harmony Format

The generated data uses OpenAI's Harmony format compatible with GPT-OSS:

```python
{
  "messages": [
    {
      "role": "developer",
      "content": "# Instructions\n\nreasoning language: English\n\nYou convert terminal transcripts..."
    },
    {
      "role": "user", 
      "content": "Terminal transcript:\n[transcript content]"
    },
    {
      "role": "assistant",
      "content": "[JSON output]"
    }
  ]
}
```


## Using the Data in Colab

1. **Generate the data**:
   ```bash
   cd ft/
   python synth.py
   ```

2. **Upload to Colab**: Upload `data/harmony_messages.jsonl` to your Colab environment

3. **Load in the notebook**:
   ```python
   from datasets import load_dataset
   
   # Replace the HuggingFaceH4/Multilingual-Thinking dataset with your data
   dataset = load_dataset('json', data_files='harmony_messages.jsonl', split='train')
   ```

4. **Apply formatting**: The data is already in the correct Harmony format, so you can use it directly with the GPT-OSS tokenizer.

## Next Steps

- **Expand scenarios**: Add more diverse terminal scenarios to `synth.py`
- **Model optimization**: Experiment with different base models and hyperparameters
- **Production deployment**: Package the trained model for easy deployment
- **Continuous learning**: Set up pipeline to retrain on real user data (with privacy controls)
