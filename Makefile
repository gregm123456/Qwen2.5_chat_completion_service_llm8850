.PHONY: help install download-model test run clean clean-npu dev lint format

# Default target
help:
	@echo "Qwen2.5 Chat Completion Service - Available Commands"
	@echo "===================================================="
	@echo ""
	@echo "Setup & Installation:"
	@echo "  make install         - Create venv and install dependencies"
	@echo "  make download-model  - Download the Qwen2.5 model"
	@echo ""
	@echo "Development:"
	@echo "  make dev             - Run service in development mode"
	@echo "  make run             - Run service (production mode)"
	@echo "  make test            - Run tests"
	@echo "  make lint            - Check code quality"
	@echo "  make format          - Format code with black"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean           - Remove cache files and logs"
	@echo "  make clean-npu       - Force cleanup of NPU device (use when stuck)"
	@echo "  make clean-all       - Remove everything including venv and models"
	@echo ""
	@echo "Production:"
	@echo "  make install-service - Install systemd service"
	@echo "  make start           - Start systemd service"
	@echo "  make stop            - Stop systemd service"
	@echo "  make status          - Check service status"
	@echo "  make logs            - View service logs"
	@echo ""

# Setup and installation
install:
	@echo "Creating virtual environment..."
	python3 -m venv venv
	@echo "Installing dependencies..."
	./venv/bin/pip install --upgrade pip
	./venv/bin/pip install -r requirements.txt
	@echo "✓ Installation complete!"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Run 'make download-model' to download the Qwen2.5 model"
	@echo "  2. Run 'make dev' to start the service in development mode"

download-model:
	@echo "Downloading Qwen2.5 model..."
	bash scripts/download_models.sh
	@echo "✓ Model download complete!"

# Development
dev:
	@echo "Starting service in development mode..."
	./venv/bin/python src/app.py

run:
	@echo "Starting service..."
	./venv/bin/uvicorn src.app:app --host 0.0.0.0 --port 8000

test:
	@echo "Running tests..."
	./venv/bin/pytest tests/ -v

lint:
	@echo "Checking code quality..."
	./venv/bin/flake8 src/ tests/ --max-line-length=120 || true
	@echo "✓ Lint check complete"

format:
	@echo "Formatting code with black..."
	./venv/bin/black src/ tests/
	@echo "✓ Code formatted"

# Cleanup
clean:
	@echo "Cleaning cache files..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.log" -delete
	find . -type f -name "*.pid" -delete
	@echo "✓ Cleanup complete"

clean-npu:
	@echo "⚠️  Force cleaning NPU device (requires sudo)..."
	@bash scripts/cleanup_npu.sh
	@echo "✓ NPU cleanup complete"
	@echo "You can now restart the service with: make dev"

clean-all: clean
	@echo "Removing virtual environment..."
	rm -rf venv
	@echo "Removing downloaded models..."
	rm -rf models
	@echo "✓ Full cleanup complete"

# Production (systemd)
install-service:
	@echo "Installing systemd service..."
	sudo cp systemd/qwen-chat.service /etc/systemd/system/
	sudo systemctl daemon-reload
	@echo "✓ Service installed"
	@echo ""
	@echo "Edit /etc/systemd/system/qwen-chat.service to adjust paths if needed"
	@echo "Then run: make enable && make start"

enable:
	sudo systemctl enable qwen-chat
	@echo "✓ Service enabled (will start on boot)"

disable:
	sudo systemctl disable qwen-chat
	@echo "✓ Service disabled"

start:
	sudo systemctl start qwen-chat
	@echo "✓ Service started"
	@echo "Check status with: make status"

stop:
	sudo systemctl stop qwen-chat
	@echo "✓ Service stopped"

restart:
	sudo systemctl restart qwen-chat
	@echo "✓ Service restarted"

status:
	sudo systemctl status qwen-chat

logs:
	sudo journalctl -u qwen-chat -f

# Quick test
test-api:
	@echo "Testing health endpoint..."
	curl -s http://localhost:8000/health | python3 -m json.tool
	@echo ""
	@echo "Testing chat completion..."
	curl -s -X POST http://localhost:8000/v1/chat/completions \
		-H "Content-Type: application/json" \
		-d '{"model":"Qwen2.5-1.5B-Instruct","messages":[{"role":"user","content":"Hello!"}]}' \
		| python3 -m json.tool
