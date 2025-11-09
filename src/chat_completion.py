"""
Chat completion logic for Qwen2.5 Chat Completion Service.
Applies the Qwen2.5 chat template and coordinates tokenizer and model for completions.
"""

import logging
from typing import List, Dict, Optional

from tokenizer_client import get_tokenizer_client, TokenizerError
from model_manager import get_model_manager, ModelError

logger = logging.getLogger(__name__)


class ChatCompletionError(Exception):
    """Exception raised for chat completion errors."""
    pass


def apply_chat_template_local(
    messages: List[Dict[str, str]],
    add_generation_prompt: bool = True
) -> str:
    """Apply Qwen2.5 chat template locally (fallback if tokenizer doesn't support it).
    
    Qwen2.5 chat format:
    <|im_start|>system
    {system_message}<|im_end|>
    <|im_start|>user
    {user_message}<|im_end|>
    <|im_start|>assistant
    {assistant_message}<|im_end|>
    <|im_start|>assistant
    
    Args:
        messages: List of chat messages in OpenAI format.
        add_generation_prompt: Whether to add the assistant generation prompt.
        
    Returns:
        Formatted prompt string.
    """
    prompt_parts = []
    
    for message in messages:
        role = message.get("role", "")
        content = message.get("content", "")
        
        if role not in ["system", "user", "assistant"]:
            logger.warning(f"Unknown role: {role}, treating as user")
            role = "user"
        
        prompt_parts.append(f"<|im_start|>{role}\n{content}<|im_end|>")
    
    prompt = "\n".join(prompt_parts)
    
    if add_generation_prompt:
        prompt += "\n<|im_start|>assistant\n"
    
    return prompt


def apply_chat_template(
    messages: List[Dict[str, str]],
    add_generation_prompt: bool = True
) -> str:
    """Apply Qwen2.5 chat template to messages.
    
    Tries to use tokenizer server's chat template endpoint first,
    falls back to local implementation if unavailable.
    
    Args:
        messages: List of chat messages in OpenAI format.
        add_generation_prompt: Whether to add the assistant generation prompt.
        
    Returns:
        Formatted prompt string.
        
    Raises:
        ChatCompletionError: If template application fails.
    """
    try:
        # Try using tokenizer server
        tokenizer = get_tokenizer_client()
        prompt = tokenizer.apply_chat_template(messages, add_generation_prompt)
        return prompt
    
    except TokenizerError as e:
        logger.warning(f"Tokenizer chat template failed, using local fallback: {e}")
        # Fallback to local implementation
        return apply_chat_template_local(messages, add_generation_prompt)


def chat_completion(
    messages: List[Dict[str, str]],
    temperature: Optional[float] = None,
    top_k: Optional[int] = None,
    top_p: Optional[float] = None,
    max_tokens: Optional[int] = None,
    repeat_penalty: Optional[float] = None,
    model: Optional[str] = None
) -> Dict:
    """Generate a chat completion response.
    
    Args:
        messages: List of chat messages in OpenAI format.
        temperature: Sampling temperature.
        top_k: Top-k sampling.
        top_p: Top-p (nucleus) sampling.
        max_tokens: Maximum tokens to generate.
        repeat_penalty: Repetition penalty.
        model: Model identifier (for compatibility, not used).
        
    Returns:
        OpenAI-compatible response dictionary with:
            - id: Unique response ID
            - object: "chat.completion"
            - created: Unix timestamp
            - model: Model name
            - choices: List with single choice containing message
            - usage: Token usage information
        
    Raises:
        ChatCompletionError: If completion fails.
    """
    import time
    import uuid
    
    try:
        # Validate messages
        if not messages or not isinstance(messages, list):
            raise ChatCompletionError("Messages must be a non-empty list")
        
        for msg in messages:
            if not isinstance(msg, dict):
                raise ChatCompletionError("Each message must be a dictionary")
            if "role" not in msg or "content" not in msg:
                raise ChatCompletionError("Each message must have 'role' and 'content'")
        
        logger.info(f"Processing chat completion request with {len(messages)} messages")
        
        # Apply chat template
        prompt = apply_chat_template(messages, add_generation_prompt=True)
        logger.debug(f"Generated prompt: {prompt[:200]}...")
        
        # Count prompt tokens
        try:
            tokenizer = get_tokenizer_client()
            prompt_tokens = tokenizer.count_tokens(prompt)
        except Exception as e:
            logger.warning(f"Could not count prompt tokens: {e}")
            prompt_tokens = len(prompt) // 4  # Rough estimate
        
        # Generate completion using model
        model_manager = get_model_manager()
        generated_text = model_manager.generate(
            prompt=prompt,
            temperature=temperature,
            top_k=top_k,
            top_p=top_p,
            max_tokens=max_tokens,
            repeat_penalty=repeat_penalty
        )
        
        logger.info(f"Generated completion: {len(generated_text)} chars")
        
        # Count completion tokens
        try:
            completion_tokens = tokenizer.count_tokens(generated_text)
        except Exception as e:
            logger.warning(f"Could not count completion tokens: {e}")
            completion_tokens = len(generated_text) // 4  # Rough estimate
        
        # Build OpenAI-compatible response
        response = {
            "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model or "qwen2.5-1.5b-instruct",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": generated_text
                    },
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens
            }
        }
        
        return response
    
    except ModelError as e:
        logger.error(f"Model error during chat completion: {e}")
        raise ChatCompletionError(f"Model error: {e}")
    
    except Exception as e:
        logger.error(f"Unexpected error during chat completion: {e}")
        raise ChatCompletionError(f"Unexpected error: {e}")


def validate_messages(messages: List[Dict[str, str]]) -> bool:
    """Validate chat messages format.
    
    Args:
        messages: List of messages to validate.
        
    Returns:
        True if valid, False otherwise.
    """
    if not messages or not isinstance(messages, list):
        return False
    
    for msg in messages:
        if not isinstance(msg, dict):
            return False
        if "role" not in msg or "content" not in msg:
            return False
        if msg["role"] not in ["system", "user", "assistant"]:
            return False
        if not isinstance(msg["content"], str):
            return False
    
    return True
