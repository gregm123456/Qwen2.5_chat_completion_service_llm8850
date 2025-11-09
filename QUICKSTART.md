# Qwen2.5 Chat Completion Service - Quick Start Guide

This guide will help you get the Qwen2.5 Chat Completion Service up and running quickly.

## Prerequisites

Before starting, ensure you have:
- ✅ LLM-8850 NPU accelerator card installed and working
- ✅ LLM-8850 driver (AXCL SDK) installed
- ✅ Python 3.8 or higher
- ✅ Git

## Installation Steps

### 1. Clone and Setup

```bash
# Clone the repository
git clone https://github.com/gregm123456/Qwen2.5_chat_completion_service_llm8850.git
cd Qwen2.5_chat_completion_service_llm8850

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Download the Model

```bash
# Download the Qwen2.5 model (this will download ~1.5GB)
bash scripts/download_models.sh
```

This downloads the model to `models/Qwen2.5-1.5B-Instruct-GPTQ-Int4/`.

### 3. Verify Installation

```bash
# Check that model files exist
ls -la models/Qwen2.5-1.5B-Instruct-GPTQ-Int4/

# You should see:
# - qwen2.5_tokenizer.py (or similar tokenizer script)
# - run_qwen2.5_1.5b_gptq_int4_axcl_aarch64.sh (or similar)
# - main_axcl_aarch64 (model binary)
```

### 4. Configure (Optional)

Edit `config/config.yaml` if you want to change defaults:

```yaml
server:
  host: "0.0.0.0"  # Change to 127.0.0.1 for local-only
  port: 8000       # Change port if needed

model:
  temperature: 0.7  # Default sampling temperature
  max_tokens: 2048  # Max generation length
```

### 5. Start the Service

```bash
# Make sure virtual environment is activated
source venv/bin/activate

# Run the service
python src/app.py
```

You should see output like:
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### 6. Test the Service

Open a new terminal and test the API:

```bash
# Health check
curl http://localhost:8000/health

# Chat completion
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen2.5-1.5B-Instruct",
    "messages": [
      {"role": "user", "content": "Hello! What is 2+2?"}
    ]
  }'
```

## Using with OpenAI Client

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="not-needed"
)

response = client.chat.completions.create(
    model="Qwen2.5-1.5B-Instruct",
    messages=[
        {"role": "user", "content": "What is the capital of France?"}
    ]
)

print(response.choices[0].message.content)
```

## Production Deployment

For production use, install as a systemd service:

```bash
# Copy service file
sudo cp systemd/qwen-chat.service /etc/systemd/system/

# Edit paths in service file if needed
sudo nano /etc/systemd/system/qwen-chat.service

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable qwen-chat
sudo systemctl start qwen-chat

# Check status
sudo systemctl status qwen-chat
```

See `systemd/README.md` for detailed systemd documentation.

## Troubleshooting

### Service won't start
- Check LLM-8850 driver is loaded: `lsmod | grep axera`
- Verify model downloaded: `ls models/Qwen2.5-1.5B-Instruct-GPTQ-Int4/`
- Check logs: `sudo journalctl -u qwen-chat -n 100`

### Port already in use
- Change port in `config/config.yaml`
- Or kill process using port: `sudo lsof -ti:8000 | xargs kill -9`

### Permission denied on NPU
- Add your user to NPU device group
- Or run service as user with NPU access

### Model download fails
- Check internet connection
- Try manual clone: `git clone https://huggingface.co/AXERA-TECH/Qwen2.5-1.5B-Instruct-GPTQ-Int4 models/Qwen2.5-1.5B-Instruct-GPTQ-Int4`

## Next Steps

- Read the full [README.md](README.md) for complete documentation
- See [reference_documentation/plan.md](reference_documentation/plan.md) for architecture details
- Configure advanced settings in `config/config.yaml`
- Set up monitoring and logging for production
- Configure reverse proxy (Nginx) for production use

## Getting Help

- Check the [README.md](README.md) troubleshooting section
- Review logs: `sudo journalctl -u qwen-chat -f`
- Open an issue: https://github.com/gregm123456/Qwen2.5_chat_completion_service_llm8850/issues
