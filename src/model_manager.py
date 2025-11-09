"""
Model manager for Qwen2.5 Chat Completion Service.
Manages the lifecycle of the model process using stdin/stdout communication.
"""

import logging
import re
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional
from queue import Queue, Empty

from config import get_config

logger = logging.getLogger(__name__)


class ModelError(Exception):
    """Exception raised for model-related errors."""
    pass


class ModelManager:
    """Manages the model process lifecycle using stdin/stdout pipes."""
    
    def __init__(self):
        """Initialize model manager."""
        self.config = get_config()
        self.process: Optional[subprocess.Popen] = None
        self._is_running = False
        self._is_ready = False
        self._output_queue = Queue()
        self._output_thread = None
        
        logger.info("ModelManager initialized (stdin/stdout mode)")
    
    def start(self) -> bool:
        """Start the model process with stdin/stdout pipes.
        
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
        
        # Build command - source /etc/profile for NPU environment
        cmd = ["bash", "-c", f"source /etc/profile 2>/dev/null; bash {script_path}"]
        
        logger.info(f"Starting model process (with /etc/profile sourced)")
        
        try:
            # Start process with PIPE for stdin/stdout
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=self.config.model_repo_path,
                text=True,
                bufsize=1,  # Line buffered
                start_new_session=True
            )
            
            # Write PID file
            with open(pid_file, 'w') as f:
                f.write(str(self.process.pid))
            
            logger.info(f"Model process started with PID {self.process.pid}")
            
            # Start output reader thread
            self._output_thread = threading.Thread(
                target=self._read_output,
                daemon=True
            )
            self._output_thread.start()
            
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
    
    def _read_output(self):
        """Read model stdout in a background thread."""
        try:
            log_file = self.config.model_log_file
            with open(log_file, 'a') as log_f:
                for line in self.process.stdout:
                    # Write to log file
                    log_f.write(line)
                    log_f.flush()
                    
                    # Also put in queue for analysis
                    self._output_queue.put(line)
        except Exception as e:
            logger.error(f"Error reading model output: {e}")
    
    def _wait_for_ready(self) -> bool:
        """Wait for model to be ready by looking for the >> prompt.
        
        Returns:
            True if model is ready, False if timeout.
        """
        timeout = self.config.model_startup_timeout
        start_time = time.time()
        
        logger.info(f"Waiting for model to be ready (timeout: {timeout}s)")
        
        while time.time() - start_time < timeout:
            # Check if process died
            if self.process.poll() is not None:
                logger.error(f"Model process died with code {self.process.returncode}")
                return False
            
            # Check output queue for ready signal
            try:
                line = self._output_queue.get(timeout=1)
                
                # Look for "LLM init ok" and ">>" prompt
                if "LLM init ok" in line:
                    logger.info("Model initialization complete")
                    # Give it a moment to print the prompt
                    time.sleep(0.5)
                    return True
                    
            except Empty:
                continue
        
        logger.error("Model startup timeout")
        return False
    
    def generate(self, prompt: str, temperature: float = None, max_tokens: int = None, 
                 top_p: float = None, top_k: int = None) -> Optional[str]:
        """Send a prompt to the model and get the response.
        
        Args:
            prompt: The input prompt
            temperature: Sampling temperature (ignored - model uses internal config)
            max_tokens: Maximum tokens to generate (ignored - model uses internal config)
            top_p: Top-p sampling (ignored - model uses internal config)
            top_k: Top-k sampling (ignored - model uses internal config)
            
        Returns:
            Generated text or None on error
            
        Note:
            The underlying model binary uses its own configuration for sampling parameters.
            These parameters are accepted for API compatibility but not used.
        """
        if not self._is_ready:
            raise ModelError("Model is not ready")
        
        try:
            # Clear the output queue
            while not self._output_queue.empty():
                try:
                    self._output_queue.get_nowait()
                except Empty:
                    break
            
            # Send prompt to stdin
            logger.debug(f"Sending prompt to model: {prompt[:100]}...")
            self.process.stdin.write(prompt + "\n")
            self.process.stdin.flush()
            
            # Collect response
            response_lines = []
            timeout = self.config.model_request_timeout
            start_time = time.time()
            got_response = False
            
            while time.time() - start_time < timeout:
                try:
                    line = self._output_queue.get(timeout=0.5)
                    
                    # Skip ANSI escape codes and progress bars
                    clean_line = re.sub(r'\x1b\[[0-9;]*m', '', line)
                    clean_line = clean_line.strip()
                    
                    # Check for prompt (end of response)
                    if clean_line.endswith('>>'):
                        got_response = True
                        break
                    
                    # Collect non-empty lines that look like response
                    if clean_line and not clean_line.startswith('[') and '|' not in clean_line:
                        response_lines.append(clean_line)
                        
                except Empty:
                    # If we got some response and there's a pause, consider it done
                    if response_lines and time.time() - start_time > 2:
                        got_response = True
                        break
                    continue
            
            if not got_response and not response_lines:
                logger.error("Generation timeout - no response received")
                return None
            
            response = '\n'.join(response_lines).strip()
            logger.debug(f"Model response: {response[:100]}...")
            return response
            
        except Exception as e:
            logger.error(f"Error during generation: {e}")
            raise ModelError(f"Generation failed: {e}")
    
    def stop(self):
        """Stop the model process and ensure NPU device is released."""
        if not self._is_running and not self.process:
            return
        
        logger.info(f"Stopping model process (PID {self.process.pid if self.process else 'unknown'})")
        
        try:
            if self.process:
                pid = self.process.pid
                
                # Try graceful shutdown first
                if self.process.stdin:
                    try:
                        self.process.stdin.write("q\n")
                        self.process.stdin.flush()
                        self.process.stdin.close()
                    except:
                        pass
                
                # Wait a bit for graceful shutdown
                try:
                    self.process.wait(timeout=3)
                    logger.info("Model process stopped gracefully")
                except subprocess.TimeoutExpired:
                    logger.warning("Graceful shutdown timeout, forcing termination")
                    # Force kill the entire process group to ensure child processes die
                    import os
                    import signal
                    try:
                        os.killpg(os.getpgid(pid), signal.SIGTERM)
                        self.process.wait(timeout=2)
                        logger.info("Model process group terminated")
                    except subprocess.TimeoutExpired:
                        # Last resort: SIGKILL
                        try:
                            os.killpg(os.getpgid(pid), signal.SIGKILL)
                            self.process.wait(timeout=1)
                            logger.info("Model process group killed")
                        except:
                            logger.error("Failed to kill process group, may need manual cleanup")
                    except Exception as e:
                        logger.warning(f"Process group kill failed: {e}, trying direct kill")
                        self.process.kill()
                        self.process.wait()
        
        except Exception as e:
            logger.error(f"Error stopping model process: {e}")
        
        finally:
            # Clean up PID file
            pid_file = self.config.model_pid_file
            if pid_file.exists():
                pid_file.unlink()
            
            self._is_running = False
            self._is_ready = False
            self.process = None
            
            # Give NPU time to release
            time.sleep(0.5)
    
    def get_status(self) -> dict:
        """Get the current status of the model manager.
        
        Returns:
            Dictionary with status information.
        """
        status = {
            "running": self._is_running,
            "ready": self._is_ready,
            "healthy": self.is_healthy()
        }
        
        if self.process:
            status["pid"] = self.process.pid
            status["returncode"] = self.process.poll()
        
        return status
    
    def is_healthy(self) -> bool:
        """Check if model process is healthy.
        
        Returns:
            True if healthy, False otherwise.
        """
        if not self._is_running or not self.process:
            return False
        
        # Check if process is still running
        if self.process.poll() is not None:
            logger.error(f"Model process died unexpectedly")
            self._is_running = False
            self._is_ready = False
            return False
        
        return True


# Singleton instance
_model_manager_instance: Optional[ModelManager] = None


def get_model_manager() -> ModelManager:
    """Get the singleton ModelManager instance.
    
    Returns:
        The ModelManager singleton instance.
    """
    global _model_manager_instance
    if _model_manager_instance is None:
        _model_manager_instance = ModelManager()
    return _model_manager_instance
