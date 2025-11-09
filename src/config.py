"""
Configuration management for Qwen2.5 Chat Completion Service.
Loads settings from config.yaml and provides typed access.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional


class Config:
    """Service configuration loaded from YAML."""
    
    def __init__(self, config_path: Optional[str] = None):
        """Load configuration from YAML file.
        
        Args:
            config_path: Path to config.yaml. If None, looks for config/config.yaml
                        relative to project root.
        """
        if config_path is None:
            # Find project root (parent of src/)
            project_root = Path(__file__).parent.parent
            config_path = project_root / "config" / "config.yaml"
        
        self.config_path = Path(config_path)
        self._config: Dict[str, Any] = {}
        self._load()
    
    def _load(self):
        """Load configuration from YAML file."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        
        with open(self.config_path, 'r') as f:
            self._config = yaml.safe_load(f)
    
    def _get(self, *keys, default=None):
        """Get nested configuration value."""
        value = self._config
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return default
            if value is None:
                return default
        return value
    
    # Service settings
    @property
    def service_host(self) -> str:
        return self._get('service', 'host', default='127.0.0.1')
    
    @property
    def service_port(self) -> int:
        return self._get('service', 'port', default=8080)
    
    @property
    def service_workers(self) -> int:
        return self._get('service', 'workers', default=1)
    
    # Path settings
    @property
    def install_root(self) -> Path:
        # Use env var override or config value
        root = os.getenv('QWEN_INSTALL_ROOT', 
                        self._get('paths', 'install_root', default='/opt/qwen'))
        return Path(root)
    
    @property
    def model_repo_path(self) -> Path:
        """Get absolute path to model repository."""
        # For development, use project root
        project_root = Path(__file__).parent.parent
        rel_path = self._get('paths', 'model_repo', default='models/Qwen2.5-1.5B-Instruct-GPTQ-Int4')
        return project_root / rel_path
    
    @property
    def log_dir(self) -> Path:
        log_dir = os.getenv('QWEN_LOG_DIR',
                           self._get('paths', 'log_dir', default='/var/log/qwen'))
        return Path(log_dir)
    
    @property
    def run_dir(self) -> Path:
        run_dir = os.getenv('QWEN_RUN_DIR',
                           self._get('paths', 'run_dir', default='/run/qwen'))
        return Path(run_dir)
    
    # Tokenizer settings
    @property
    def tokenizer_host(self) -> str:
        return self._get('tokenizer', 'host', default='127.0.0.1')
    
    @property
    def tokenizer_port(self) -> int:
        return self._get('tokenizer', 'port', default=12345)
    
    @property
    def tokenizer_url(self) -> str:
        return f"http://{self.tokenizer_host}:{self.tokenizer_port}"
    
    @property
    def tokenizer_script(self) -> str:
        return self._get('tokenizer', 'script', default='qwen2.5_tokenizer.py')
    
    @property
    def tokenizer_script_path(self) -> Path:
        return self.model_repo_path / self.tokenizer_script
    
    @property
    def tokenizer_pid_file(self) -> Path:
        return Path(self._get('tokenizer', 'pid_file', default='/run/qwen/tokenizer.pid'))
    
    @property
    def tokenizer_log_file(self) -> Path:
        return Path(self._get('tokenizer', 'log_file', default='/var/log/qwen/tokenizer.log'))
    
    @property
    def tokenizer_startup_timeout(self) -> int:
        return self._get('tokenizer', 'startup_timeout', default=30)
    
    @property
    def tokenizer_health_check_interval(self) -> int:
        return self._get('tokenizer', 'health_check_interval', default=10)
    
    # Model settings
    @property
    def model_name(self) -> str:
        return self._get('model', 'name', default='qwen2.5-1.5b-instruct')
    
    @property
    def model_runner_script(self) -> str:
        return self._get('model', 'runner_script', default='run_qwen2.5_1.5b_gptq_int4_axcl_aarch64.sh')
    
    @property
    def model_runner_script_path(self) -> Path:
        return self.model_repo_path / self.model_runner_script
    
    @property
    def model_ipc_type(self) -> str:
        return self._get('model', 'ipc_type', default='socket')
    
    @property
    def model_socket_path(self) -> Path:
        return Path(self._get('model', 'socket_path', default='/run/qwen/model.sock'))
    
    @property
    def model_tcp_host(self) -> str:
        return self._get('model', 'tcp_host', default='127.0.0.1')
    
    @property
    def model_tcp_port(self) -> int:
        return self._get('model', 'tcp_port', default=11411)
    
    @property
    def model_pid_file(self) -> Path:
        return Path(self._get('model', 'pid_file', default='/run/qwen/model.pid'))
    
    @property
    def model_log_file(self) -> Path:
        return Path(self._get('model', 'log_file', default='/var/log/qwen/model.log'))
    
    @property
    def model_startup_timeout(self) -> int:
        return self._get('model', 'startup_timeout', default=60)
    
    @property
    def model_request_timeout(self) -> int:
        return self._get('model', 'request_timeout', default=30)
    
    # Model generation defaults
    @property
    def default_temperature(self) -> float:
        return self._get('model', 'default_temperature', default=0.7)
    
    @property
    def default_top_k(self) -> int:
        return self._get('model', 'default_top_k', default=40)
    
    @property
    def default_top_p(self) -> float:
        return self._get('model', 'default_top_p', default=0.9)
    
    @property
    def default_max_tokens(self) -> int:
        return self._get('model', 'default_max_tokens', default=512)
    
    @property
    def default_repeat_penalty(self) -> float:
        return self._get('model', 'default_repeat_penalty', default=1.1)
    
    # Logging settings
    @property
    def log_level(self) -> str:
        return self._get('logging', 'level', default='INFO')
    
    @property
    def log_format(self) -> str:
        return self._get('logging', 'format', 
                        default='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    @property
    def log_file(self) -> Path:
        return Path(self._get('logging', 'file', default='/var/log/qwen/service.log'))
    
    # User settings
    @property
    def service_user(self) -> str:
        return self._get('user', 'name', default='qwen')
    
    @property
    def service_user_home(self) -> Path:
        return Path(self._get('user', 'home', default='/var/lib/qwen'))


# Global config instance
_config: Optional[Config] = None


def get_config(config_path: Optional[str] = None) -> Config:
    """Get or create global config instance."""
    global _config
    if _config is None:
        _config = Config(config_path)
    return _config
