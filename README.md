# Qwen2.5 Chat Completion Service

A production-ready chat completion service that exposes an **OpenAI-compatible API** (`POST /v1/chat/completions`) backed by the Qwen2.5-1.5B model running on the LLM-8850 NPU accelerator card.

This service mimics OpenAI and Ollama chat completion endpoints, allowing existing chatbot applications to use it as a drop-in replacement without code changes.

## Features

- ✅ **OpenAI-compatible API** - Drop-in replacement for OpenAI's chat completions endpoint
- ✅ **Qwen2.5-1.5B model** - Optimized for LLM-8850 NPU accelerator (GPTQ Int4 quantization)
- ✅ **Chat template support** - Automatic conversion of message arrays to Qwen2.5 prompt format
- ✅ **Persistent model loading** - Model stays loaded in NPU memory (no reload per request)
- ✅ **Health monitoring** - Built-in health checks for tokenizer, model, and NPU status
- ✅ **Systemd integration** - Production-ready service files for deployment
- ✅ **Configurable** - YAML-based configuration with sensible defaults

## Table of Contents

- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [API Reference](#api-reference)
- [Production Deployment](#production-deployment)
- [Development](#development)
- [Troubleshooting](#troubleshooting)
- [License](#license)

## Requirements

### Hardware
- LLM-8850 NPU accelerator card (AXERA AX650)
- Minimum 4GB RAM (8GB+ recommended)
- ARM64 architecture (aarch64)

### Software
- Ubuntu 20.04+ or compatible Linux distribution
- Python 3.8+
- LLM-8850 driver installed (AXCL SDK)
- Git

### Verified Environment
This service assumes the LLM-8850 driver is installed and environment variables are set in `/etc/profile`.

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/gregm123456/Qwen2.5_chat_completion_service_llm8850.git
cd Qwen2.5_chat_completion_service_llm8850
```

### 2. Create a Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Download the Model Repository

The model binaries and tokenizer are NOT included in this repository to keep it lightweight. Run the download script to fetch the pinned model version:

```bash
bash scripts/download_models.sh
```

This will:
- Clone the `Qwen2.5-1.5B-Instruct-GPTQ-Int4` model repository to `models/`
- Checkout a specific pinned commit for reproducibility
- Download ~1.5GB of model data

### 5. Configure the Service (Optional)

Edit `config/config.yaml` to customize:
- Server host/port
- Model paths
- Generation parameters (temperature, max tokens, etc.)
- Tokenizer and model process settings

## Configuration

The service is configured via `config/config.yaml`. Key settings:

```yaml
server:
  host: "0.0.0.0"      # Listen on all interfaces
  port: 8000           # Service port

model:
  name: "Qwen2.5-1.5B-Instruct"
  path: "models/Qwen2.5-1.5B-Instruct-GPTQ-Int4"
  max_tokens: 2048     # Maximum generation length
  temperature: 0.7     # Sampling temperature
```

See the config file for all available options.

## Usage

### Development Mode

Start the service in development mode (with auto-reload):

```bash
source venv/bin/activate
python src/app.py
```

The service will start on `http://localhost:8000`.

### Using the API

#### Example: Chat Completion Request

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen2.5-1.5B-Instruct",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "What is the capital of France?"}
    ],
    "temperature": 0.7,
    "max_tokens": 100
  }'
```

#### Example: Health Check

```bash
curl http://localhost:8000/health
```

### Using with Python (OpenAI Client)

```python
from openai import OpenAI

# Point to your local service
client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="not-needed"  # API key not required for local service
)

response = client.chat.completions.create(
    model="Qwen2.5-1.5B-Instruct",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"}
    ]
)

print(response.choices[0].message.content)
```

## API Reference

### POST /v1/chat/completions

Create a chat completion (OpenAI-compatible).

**Request Body:**
```json
{
  "model": "Qwen2.5-1.5B-Instruct",
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Hello!"}
  ],
  "temperature": 0.7,
  "max_tokens": 2048,
  "top_p": 0.9,
  "stream": false
}
```

**Response:**
```json
{
  "id": "chatcmpl-123",
  "object": "chat.completion",
  "created": 1699564800,
  "model": "Qwen2.5-1.5B-Instruct",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Hello! How can I help you today?"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 20,
    "completion_tokens": 10,
    "total_tokens": 30
  }
}
```

### GET /health

Get service health status.

**Response:**
```json
{
  "status": "ok",
  "details": {
    "tokenizer": "running",
    "model": "loaded",
    "npu": "available",
    "uptime_seconds": 1234
  }
}
```

## Production Deployment

### Using Systemd

1. **Install the service:**

```bash
sudo cp systemd/qwen-chat.service /etc/systemd/system/
sudo systemctl daemon-reload
```

2. **Edit service file** (if needed):

Edit `/etc/systemd/system/qwen-chat.service` to adjust paths, user, and environment.

3. **Enable and start:**

```bash
sudo systemctl enable qwen-chat
sudo systemctl start qwen-chat
```

4. **Check status:**

```bash
sudo systemctl status qwen-chat
sudo journalctl -u qwen-chat -f  # Follow logs
```

See `systemd/README.md` for detailed systemd documentation.

### Reverse Proxy (Nginx)

For production, run the service behind Nginx:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Development

### Project Structure

```
.
├── config/
│   └── config.yaml           # Service configuration
├── models/                   # Downloaded model repo (gitignored)
│   └── Qwen2.5-1.5B-Instruct-GPTQ-Int4/
├── reference_documentation/
│   ├── plan.md              # Implementation plan
│   └── llm_chat_completion.py  # Reference code
├── scripts/
│   └── download_models.sh   # Model download script
├── src/
│   ├── app.py              # FastAPI application
│   ├── chat_completion.py  # Chat completion logic
│   ├── config.py           # Config loader
│   ├── model_manager.py    # Model process manager
│   ├── tokenizer_client.py # Tokenizer HTTP client
│   └── tokenizer_manager.py # Tokenizer process manager
├── systemd/
│   ├── qwen-chat.service   # Systemd unit file
│   └── README.md           # Systemd documentation
├── tests/                  # Unit tests (TODO)
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

### Running Tests

```bash
# TODO: Implement tests
pytest tests/
```

### Code Formatting

```bash
black src/
```

## Troubleshooting

### Service won't start

1. **Check LLM-8850 driver:**
   ```bash
   # Verify driver is loaded
   lsmod | grep axera
   ```

2. **Check model downloaded:**
   ```bash
   ls -la models/Qwen2.5-1.5B-Instruct-GPTQ-Int4/
   ```

3. **Check logs:**
   ```bash
   sudo journalctl -u qwen-chat -n 100
   ```

### Tokenizer connection errors

- Ensure the tokenizer process is running (managed by `TokenizerManager`)
- Check port 12345 is not in use: `netstat -tulpn | grep 12345`

### Model process crashes

- Check NPU availability: `ls -la /dev/axera*`
- Verify user has permissions to access NPU device
- Check model binaries exist and are executable

### API returns 503 errors

- Service is starting but model/tokenizer not ready yet
- Check `/health` endpoint for details on what's failing

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

### Third-Party Software

This service uses the Qwen2.5-1.5B-Instruct-GPTQ-Int4 model from AXERA-TECH:

- **Repository:** https://huggingface.co/AXERA-TECH/Qwen2.5-1.5B-Instruct-GPTQ-Int4
- **Pinned commit:** `01d5a6eb90d9be5dd3de32518ec99c04d9ae5da5`
- **License:** Apache 2.0 (expected)

The model repository is downloaded separately and not included in this repository. The model and its dependencies are subject to their own licenses.

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## Acknowledgments

- **AXERA-TECH** for the Qwen2.5 model optimization and LLM-8850 support
- **Alibaba Cloud** for the Qwen2.5 base model
- **FastAPI** for the excellent web framework

## Support

For issues and questions:
- GitHub Issues: https://github.com/gregm123456/Qwen2.5_chat_completion_service_llm8850/issues
- See `reference_documentation/plan.md` for implementation details
