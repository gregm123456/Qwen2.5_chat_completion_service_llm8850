# Systemd Service Files

This directory contains systemd unit files for running the Qwen2.5 Chat Completion Service as a system service.

## Installation

### 1. Install the service

```bash
# Copy the service file to systemd directory
sudo cp systemd/qwen-chat.service /etc/systemd/system/

# Reload systemd to recognize the new service
sudo systemctl daemon-reload
```

### 2. Configure paths (if needed)

Edit `/etc/systemd/system/qwen-chat.service` and adjust:
- `User` and `Group` (default: robot)
- `WorkingDirectory` (default: /home/robot/llm8850/Qwen2.5_chat_completion_service_llm8850)
- `Environment PATH` to match your virtualenv location

### 3. Enable and start the service

```bash
# Enable service to start on boot
sudo systemctl enable qwen-chat

# Start the service now
sudo systemctl start qwen-chat

# Check service status
sudo systemctl status qwen-chat
```

## Service Management

### View logs
```bash
# Follow logs in real-time
sudo journalctl -u qwen-chat -f

# View recent logs
sudo journalctl -u qwen-chat -n 100

# View logs since boot
sudo journalctl -u qwen-chat -b
```

### Control the service
```bash
# Stop the service
sudo systemctl stop qwen-chat

# Restart the service
sudo systemctl restart qwen-chat

# Reload configuration (after editing config.yaml)
sudo systemctl reload qwen-chat

# Disable service from starting on boot
sudo systemctl disable qwen-chat
```

## Notes

- The service runs as user `robot` by default. Ensure this user has:
  - Read access to the project directory
  - Execute permissions on the virtualenv Python interpreter
  - Access to the LLM-8850 NPU device (typically requires group membership)
  
- The service sources `/etc/profile` to get LLM-8850 environment variables. If your driver setup uses a different file, update `EnvironmentFile` in the service file.

- The service will automatically restart on failure (with exponential backoff). Check logs if the service enters a crash loop.

- For production deployments, consider:
  - Running as a dedicated service user (not `robot`)
  - Adding additional security hardening options
  - Configuring log rotation
  - Setting up monitoring/alerting for service health
