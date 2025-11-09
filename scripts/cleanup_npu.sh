#!/bin/bash
# NPU cleanup script for Qwen2.5 Chat Completion Service
# This script forcefully releases the NPU device when it gets stuck

set -e

echo "=== NPU Device Cleanup ==="

# Kill any running service instances
echo "Stopping service processes..."
pkill -f "python src/app.py" 2>/dev/null || true
sleep 1

# Kill any model processes
echo "Stopping model processes..."
sudo pkill -9 -f "main_axcl" 2>/dev/null || true
sleep 1

# Kill any stuck axcl-smi processes
echo "Clearing stuck axcl-smi..."
sudo pkill -9 axcl-smi 2>/dev/null || true
sleep 2

# Clean up runtime files
echo "Cleaning up runtime files..."
rm -f logs/*.log run/*.pid run/*.sock 2>/dev/null || true

# Verify NPU is free
echo "Verifying NPU status..."
timeout 5 axcl-smi 2>&1 | grep -q "Processes:" && echo "✓ NPU device is accessible" || echo "⚠ Warning: NPU may still be locked"

echo "=== Cleanup complete ==="
echo "If NPU is still locked, you may need to reboot the system."
