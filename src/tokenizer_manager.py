"""
Tokenizer manager for Qwen2.5 Chat Completion Service.
Manages the lifecycle of the tokenizer HTTP server subprocess.
"""

import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from config import get_config
from tokenizer_client import TokenizerClient

logger = logging.getLogger(__name__)


class TokenizerManager:
    """Manages the tokenizer server subprocess lifecycle."""
    
    def __init__(self):
        """Initialize tokenizer manager."""
        self.config = get_config()
        self.process: Optional[subprocess.Popen] = None
        self.client = TokenizerClient()
        self._is_running = False
        
        logger.info("TokenizerManager initialized")
    
    def start(self) -> bool:
        """Start the tokenizer server subprocess.
        
        Returns:
            True if started successfully, False otherwise.
        """
        if self._is_running:
            logger.warning("Tokenizer server already running")
            return True
        
        # Check if tokenizer script exists
        script_path = self.config.tokenizer_script_path
        if not script_path.exists():
            logger.error(f"Tokenizer script not found: {script_path}")
            logger.error("Please run scripts/download_models.sh first")
            return False
        
        # Ensure log directory exists
        log_file = self.config.tokenizer_log_file
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Ensure PID directory exists
        pid_file = self.config.tokenizer_pid_file
        pid_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Build command
        cmd = [
            sys.executable,  # Use same Python interpreter
            str(script_path),
            "--port", str(self.config.tokenizer_port),
            "--host", self.config.tokenizer_host
        ]
        
        logger.info(f"Starting tokenizer server: {' '.join(cmd)}")
        
        try:
            # Open log file for output
            with open(log_file, 'a') as log_f:
                self.process = subprocess.Popen(
                    cmd,
                    stdout=log_f,
                    stderr=subprocess.STDOUT,
                    cwd=self.config.model_repo_path,
                    start_new_session=True  # Detach from parent process group
                )
            
            # Write PID file
            with open(pid_file, 'w') as f:
                f.write(str(self.process.pid))
            
            logger.info(f"Tokenizer server started with PID {self.process.pid}")
            
            # Wait for server to be ready
            if self._wait_for_ready():
                self._is_running = True
                logger.info("Tokenizer server is ready")
                return True
            else:
                logger.error("Tokenizer server failed to start")
                self.stop()
                return False
        
        except Exception as e:
            logger.error(f"Failed to start tokenizer server: {e}")
            return False
    
    def _wait_for_ready(self) -> bool:
        """Wait for tokenizer server to be ready.
        
        Returns:
            True if server becomes ready, False if timeout.
        """
        timeout = self.config.tokenizer_startup_timeout
        start_time = time.time()
        
        logger.info(f"Waiting for tokenizer server to be ready (timeout: {timeout}s)")
        
        while time.time() - start_time < timeout:
            # Check if process died
            if self.process and self.process.poll() is not None:
                logger.error(f"Tokenizer process died with code {self.process.returncode}")
                return False
            
            # Check health
            if self.client.health_check():
                return True
            
            time.sleep(1)
        
        logger.error("Tokenizer server startup timeout")
        return False
    
    def stop(self):
        """Stop the tokenizer server subprocess."""
        if not self.process:
            logger.warning("No tokenizer process to stop")
            return
        
        logger.info(f"Stopping tokenizer server (PID {self.process.pid})")
        
        try:
            # Send SIGTERM for graceful shutdown
            self.process.terminate()
            
            # Wait up to 10 seconds for process to exit
            try:
                self.process.wait(timeout=10)
                logger.info("Tokenizer server stopped gracefully")
            except subprocess.TimeoutExpired:
                logger.warning("Tokenizer server did not stop gracefully, killing")
                self.process.kill()
                self.process.wait()
        
        except Exception as e:
            logger.error(f"Error stopping tokenizer server: {e}")
        
        finally:
            self._is_running = False
            self.process = None
            
            # Remove PID file
            pid_file = self.config.tokenizer_pid_file
            if pid_file.exists():
                pid_file.unlink()
    
    def restart(self) -> bool:
        """Restart the tokenizer server.
        
        Returns:
            True if restarted successfully, False otherwise.
        """
        logger.info("Restarting tokenizer server")
        self.stop()
        time.sleep(2)  # Brief pause before restart
        return self.start()
    
    def is_healthy(self) -> bool:
        """Check if tokenizer server is healthy.
        
        Returns:
            True if healthy, False otherwise.
        """
        if not self._is_running:
            return False
        
        # Check process is alive
        if self.process and self.process.poll() is not None:
            logger.warning("Tokenizer process died")
            self._is_running = False
            return False
        
        # Check health endpoint
        return self.client.health_check()
    
    def get_status(self) -> dict:
        """Get tokenizer server status information.
        
        Returns:
            Dictionary with status information.
        """
        status = {
            "running": self._is_running,
            "healthy": False,
            "pid": None
        }
        
        if self.process:
            status["pid"] = self.process.pid
            status["healthy"] = self.is_healthy()
        
        return status


# Global tokenizer manager instance
_tokenizer_manager: Optional[TokenizerManager] = None


def get_tokenizer_manager() -> TokenizerManager:
    """Get or create global tokenizer manager instance."""
    global _tokenizer_manager
    if _tokenizer_manager is None:
        _tokenizer_manager = TokenizerManager()
    return _tokenizer_manager
