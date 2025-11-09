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

# Verify NPU is free (run axcl-smi without attaching its TTY to avoid leaving the terminal in
# a non-echo/raw state if the tool is killed)
echo "Verifying NPU status..."
TMP_AXCL_OUT=$(mktemp /tmp/axcl_smi.XXXXXX)
if timeout 5 axcl-smi >"$TMP_AXCL_OUT" 2>&1; then
	if grep -q "Processes:" "$TMP_AXCL_OUT"; then
		echo "✓ NPU device is accessible"
	else
		echo "⚠ Warning: NPU may still be locked"
	fi
else
	echo "⚠ axcl-smi timed out or failed"
fi

# Always restore terminal settings in case axcl-smi (or a killed process) left the tty
# in raw/no-echo mode. This avoids the invisible-keystrokes problem you observed.
stty sane 2>/dev/null || true

rm -f "$TMP_AXCL_OUT"

echo "=== Cleanup complete ==="
echo "If NPU is still locked, you may need to reboot the system."
