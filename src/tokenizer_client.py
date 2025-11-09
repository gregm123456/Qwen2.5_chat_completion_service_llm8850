"""
Tokenizer client for Qwen2.5 Chat Completion Service.
Communicates with the tokenizer HTTP server for encoding, decoding, and chat template application.
"""

import logging
import requests
from typing import List, Dict, Any, Optional
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import get_config

logger = logging.getLogger(__name__)


class TokenizerError(Exception):
    """Exception raised for tokenizer-related errors."""
    pass


class TokenizerClient:
    """Client for interacting with the Qwen2.5 tokenizer HTTP server."""
    
    def __init__(self, base_url: Optional[str] = None, timeout: int = 10):
        """Initialize tokenizer client.
        
        Args:
            base_url: Base URL of tokenizer server. If None, uses config.
            timeout: Request timeout in seconds.
        """
        config = get_config()
        self.base_url = base_url or config.tokenizer_url
        self.timeout = timeout
        
        # Create session with retries
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET", "POST"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        logger.info(f"TokenizerClient initialized with base_url={self.base_url}")
    
    def health_check(self) -> bool:
        """Check if tokenizer server is healthy.
        
        Returns:
            True if server is healthy, False otherwise.
        """
        try:
            response = self.session.get(
                f"{self.base_url}/health",
                timeout=self.timeout
            )
            return response.status_code == 200
        except requests.RequestException as e:
            logger.warning(f"Tokenizer health check failed: {e}")
            return False
    
    def encode(self, text: str) -> List[int]:
        """Encode text to token IDs.
        
        Args:
            text: Text to encode.
            
        Returns:
            List of token IDs.
            
        Raises:
            TokenizerError: If encoding fails.
        """
        try:
            response = self.session.post(
                f"{self.base_url}/encode",
                json={"text": text},
                timeout=self.timeout
            )
            response.raise_for_status()

            try:
                data = response.json()
            except ValueError:
                # Non-JSON reply (legacy tokenizer) - log and raise
                logger.error("Tokenizer encode returned non-JSON response")
                raise TokenizerError("Tokenizer returned non-JSON response for encode")

            # Accept either 'tokens' or legacy 'token_ids'
            return data.get("tokens") or data.get("token_ids") or []

        except requests.RequestException as e:
            logger.error(f"Tokenizer encode failed: {e}")
            raise TokenizerError(f"Failed to encode text: {e}")
    
    def decode(self, tokens: List[int]) -> str:
        """Decode token IDs to text.
        
        Args:
            tokens: List of token IDs.
            
        Returns:
            Decoded text.
            
        Raises:
            TokenizerError: If decoding fails.
        """
        try:
            response = self.session.post(
                f"{self.base_url}/decode",
                json={"tokens": tokens},
                timeout=self.timeout
            )
            response.raise_for_status()

            try:
                data = response.json()
            except ValueError:
                logger.error("Tokenizer decode returned non-JSON response")
                raise TokenizerError("Tokenizer returned non-JSON response for decode")

            # Accept either 'text' or legacy field
            return data.get("text") or data.get("decoded", "")

        except requests.RequestException as e:
            logger.error(f"Tokenizer decode failed: {e}")
            raise TokenizerError(f"Failed to decode tokens: {e}")
    
    def apply_chat_template(
        self,
        messages: List[Dict[str, str]],
        add_generation_prompt: bool = True
    ) -> str:
        """Apply Qwen2.5 chat template to messages.
        
        Args:
            messages: List of chat messages in OpenAI format.
                     Each message: {"role": "system"|"user"|"assistant", "content": "..."}
            add_generation_prompt: Whether to add the generation prompt (<|im_start|>assistant\n).
            
        Returns:
            Formatted prompt string ready for model input.
            
        Raises:
            TokenizerError: If template application fails.
        """
        try:
            response = self.session.post(
                f"{self.base_url}/chat_template",
                json={
                    "messages": messages,
                    "add_generation_prompt": add_generation_prompt
                },
                timeout=self.timeout
            )
            response.raise_for_status()

            try:
                data = response.json()
            except ValueError:
                # Non-JSON or empty response from tokenizer; raise a TokenizerError so caller can fall back
                logger.error("Tokenizer chat_template returned non-JSON response")
                raise TokenizerError("Tokenizer returned non-JSON response for chat_template")

            return data.get("prompt", "")

        except requests.RequestException as e:
            logger.error(f"Tokenizer chat template application failed: {e}")
            raise TokenizerError(f"Failed to apply chat template: {e}")
    
    def count_tokens(self, text: str) -> int:
        """Count tokens in text.
        
        Args:
            text: Text to count tokens for.
            
        Returns:
            Number of tokens.
        """
        try:
            tokens = self.encode(text)
            return len(tokens)
        except TokenizerError:
            # Fallback: rough estimate (4 chars per token)
            return len(text) // 4
    
    def close(self):
        """Close the session."""
        self.session.close()


# Global tokenizer client instance
_tokenizer_client: Optional[TokenizerClient] = None


def get_tokenizer_client() -> TokenizerClient:
    """Get or create global tokenizer client instance."""
    global _tokenizer_client
    if _tokenizer_client is None:
        _tokenizer_client = TokenizerClient()
    return _tokenizer_client
