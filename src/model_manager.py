"""
Model manager for Qwen2.5 Chat Completion Service.
Manages the lifecycle of the model process and handles generation requests.
"""

import json
import logging
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional, Dict, Any

from config import get_config

logger = logging.getLogger(__name__)


class ModelError(Exception):
    """Exception raised for model-related errors."""
    pass


class ModelManager:
    """Manages the model process lifecycle and generation requests."""
    
    def __init__(self):
        """Initialize model manager."""
        self.config = get_config()
        self.process: Optional[subprocess.Popen] = None
        self._is_running = False
        self._is_ready = False
        
        logger.info("ModelManager initialized")
    
    def start(self) -> bool:
        """Start the model process.
        
        Returns:
            True if started successfully, False otherwise.
        """
        if self._is_running:
            logger.warning("Model process already running")
            return True
        
        # Check if model runner script exists
        script_path = self.config.model_runner_script_path
        if not script_path.exists():
            logger.error(f"Model runner script not found: {script_path}")
            logger.error("Please run scripts/download_models.sh first")
            return False
        
        # Ensure log directory exists
        log_file = self.config.model_log_file
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Ensure PID directory exists
        pid_file = self.config.model_pid_file
        pid_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Ensure socket directory exists if using Unix socket
        if self.config.model_ipc_type == "socket":
            socket_path = self.config.model_socket_path
            socket_path.parent.mkdir(parents=True, exist_ok=True)
            # Remove stale socket file if exists
            if socket_path.exists():
                socket_path.unlink()
        
        # Build command to run model
        cmd = ["bash", str(script_path)]
        
        logger.info(f"Starting model process: {' '.join(cmd)}")
        logger.warning("Note: The model runner script may need to be modified to expose an RPC interface")
        logger.warning("Currently assuming the script will be enhanced with socket/TCP listener capability")
        
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
            
            logger.info(f"Model process started with PID {self.process.pid}")
            
            # Wait for model to be ready
            if self._wait_for_ready():
                self._is_running = True
                self._is_ready = True
                logger.info("Model is ready")
                return True
            else:
                logger.error("Model failed to start")
                self.stop()
                return False
        
        except Exception as e:
            logger.error(f"Failed to start model process: {e}")
            return False
    
    def _wait_for_ready(self) -> bool:
        """Wait for model to be ready.
        
        This monitors the log file for success indicators or attempts to connect
        to the model's RPC interface.
        
        Returns:
            True if model becomes ready, False if timeout.
        """
        timeout = self.config.model_startup_timeout
        start_time = time.time()
        
        logger.info(f"Waiting for model to be ready (timeout: {timeout}s)")
        
        # Success indicators to look for in logs
        success_patterns = [
            "LLM init ok",
            "Model loaded successfully",
            "Ready to accept requests",
            "Server listening"
        ]
        
        log_file = self.config.model_log_file
        
        while time.time() - start_time < timeout:
            # Check if process died
            if self.process and self.process.poll() is not None:
                logger.error(f"Model process died with code {self.process.returncode}")
                return False
            
            # Check log file for success patterns
            if log_file.exists():
                try:
                    with open(log_file, 'r') as f:
                        log_content = f.read()
                        for pattern in success_patterns:
                            if pattern in log_content:
                                logger.info(f"Found success pattern in log: {pattern}")
                                # Additional check: try to connect to socket/port
                                if self._can_connect():
                                    return True
                except Exception as e:
                    logger.debug(f"Error reading log: {e}")
            
            # Try to connect to the RPC interface
            if self._can_connect():
                return True
            
            time.sleep(2)
        
        logger.error("Model startup timeout")
        return False
    
    def _can_connect(self) -> bool:
        """Check if we can connect to the model's RPC interface.
        
        Returns:
            True if connection succeeds, False otherwise.
        """
        try:
            if self.config.model_ipc_type == "socket":
                socket_path = self.config.model_socket_path
                if not socket_path.exists():
                    return False
                
                sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                sock.settimeout(2)
                sock.connect(str(socket_path))
                sock.close()
                return True
            
            else:  # TCP
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                sock.connect((self.config.model_tcp_host, self.config.model_tcp_port))
                sock.close()
                return True
        
        except Exception as e:
            logger.debug(f"Cannot connect to model RPC: {e}")
            return False
    
    def stop(self):
        """Stop the model process."""
        if not self.process:
            logger.warning("No model process to stop")
            return
        
        logger.info(f"Stopping model process (PID {self.process.pid})")
        
        try:
            # Send SIGTERM for graceful shutdown
            self.process.terminate()
            
            # Wait up to 15 seconds for process to exit
            try:
                self.process.wait(timeout=15)
                logger.info("Model process stopped gracefully")
            except subprocess.TimeoutExpired:
                logger.warning("Model process did not stop gracefully, killing")
                self.process.kill()
                self.process.wait()
        
        except Exception as e:
            logger.error(f"Error stopping model process: {e}")
        
        finally:
            self._is_running = False
            self._is_ready = False
            self.process = None
            
            # Remove PID file
            pid_file = self.config.model_pid_file
            if pid_file.exists():
                pid_file.unlink()
            
            # Clean up socket file if exists
            if self.config.model_ipc_type == "socket":
                socket_path = self.config.model_socket_path
                if socket_path.exists():
                    socket_path.unlink()
    
    def generate(
        self,
        prompt: str,
        temperature: Optional[float] = None,
        top_k: Optional[int] = None,
        top_p: Optional[float] = None,
        max_tokens: Optional[int] = None,
        repeat_penalty: Optional[float] = None
    ) -> str:
        """Generate text from prompt using the model.
        
        Args:
            prompt: Input prompt text.
            temperature: Sampling temperature (default from config).
            top_k: Top-k sampling (default from config).
            top_p: Top-p (nucleus) sampling (default from config).
            max_tokens: Maximum tokens to generate (default from config).
            repeat_penalty: Repetition penalty (default from config).
            
        Returns:
            Generated text.
            
        Raises:
            ModelError: If generation fails.
        """
        if not self._is_ready:
            raise ModelError("Model is not ready")
        
        # Use defaults from config if not specified
        params = {
            "temperature": temperature or self.config.default_temperature,
            "top_k": top_k or self.config.default_top_k,
            "top_p": top_p or self.config.default_top_p,
            "max_tokens": max_tokens or self.config.default_max_tokens,
            "repeat_penalty": repeat_penalty or self.config.default_repeat_penalty
        }
        
        # Build request
        request = {
            "prompt": prompt,
            "params": params
        }
        
        logger.debug(f"Sending generation request: {request}")
        
        try:
            # Send request to model via RPC
            response = self._send_request(request)
            
            # Extract generated text from response
            generated_text = response.get("text", "")
            logger.debug(f"Received generation response: {len(generated_text)} chars")
            
            return generated_text
        
        except Exception as e:
            logger.error(f"Generation failed: {e}")
            raise ModelError(f"Generation failed: {e}")
    
    def _send_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Send request to model via RPC interface.
        
        Args:
            request: Request dictionary.
            
        Returns:
            Response dictionary.
            
        Raises:
            ModelError: If request fails.
        """
        try:
            # Create socket connection
            if self.config.model_ipc_type == "socket":
                sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                sock.connect(str(self.config.model_socket_path))
            else:  # TCP
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect((self.config.model_tcp_host, self.config.model_tcp_port))
            
            sock.settimeout(self.config.model_request_timeout)
            
            # Send request as JSON with newline delimiter
            request_json = json.dumps(request) + "\n"
            sock.sendall(request_json.encode('utf-8'))
            
            # Receive response (read until newline)
            response_data = b""
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                response_data += chunk
                if b"\n" in response_data:
                    break
            
            sock.close()
            
            # Parse response
            response_str = response_data.decode('utf-8').strip()
            response = json.loads(response_str)
            
            return response
        
        except socket.timeout:
            raise ModelError("Model request timeout")
        except Exception as e:
            raise ModelError(f"Model request failed: {e}")
    
    def is_healthy(self) -> bool:
        """Check if model process is healthy.
        
        Returns:
            True if healthy, False otherwise.
        """
        if not self._is_running:
            return False
        
        # Check process is alive
        if self.process and self.process.poll() is not None:
            logger.warning("Model process died")
            self._is_running = False
            self._is_ready = False
            return False
        
        # Check RPC connection
        return self._can_connect()
    
    def get_status(self) -> dict:
        """Get model status information.
        
        Returns:
            Dictionary with status information.
        """
        status = {
            "running": self._is_running,
            "ready": self._is_ready,
            "healthy": False,
            "pid": None
        }
        
        if self.process:
            status["pid"] = self.process.pid
            status["healthy"] = self.is_healthy()
        
        return status


# Global model manager instance
_model_manager: Optional[ModelManager] = None


def get_model_manager() -> ModelManager:
    """Get or create global model manager instance."""
    global _model_manager
    if _model_manager is None:
        _model_manager = ModelManager()
    return _model_manager
