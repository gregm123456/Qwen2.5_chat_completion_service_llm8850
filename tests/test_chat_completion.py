"""
Unit tests for chat completion logic
"""
import pytest
from src.chat_completion import ChatCompletionService


def test_apply_chat_template_simple():
    """Test chat template with simple user message"""
    messages = [
        {"role": "user", "content": "Hello!"}
    ]
    
    service = ChatCompletionService(None, None, None)
    prompt = service.apply_chat_template(messages)
    
    assert "<|im_start|>user" in prompt
    assert "Hello!" in prompt
    assert "<|im_end|>" in prompt


def test_apply_chat_template_with_system():
    """Test chat template with system message"""
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hi there"}
    ]
    
    service = ChatCompletionService(None, None, None)
    prompt = service.apply_chat_template(messages)
    
    assert "<|im_start|>system" in prompt
    assert "You are a helpful assistant." in prompt
    assert "<|im_start|>user" in prompt
    assert "Hi there" in prompt


def test_apply_chat_template_multi_turn():
    """Test chat template with multi-turn conversation"""
    messages = [
        {"role": "user", "content": "What's 2+2?"},
        {"role": "assistant", "content": "4"},
        {"role": "user", "content": "What's 3+3?"}
    ]
    
    service = ChatCompletionService(None, None, None)
    prompt = service.apply_chat_template(messages)
    
    # Should have all turns
    assert prompt.count("<|im_start|>user") == 2
    assert prompt.count("<|im_start|>assistant") == 2  # One from history, one to prime
    assert "What's 2+2?" in prompt
    assert "What's 3+3?" in prompt
    assert prompt.endswith("<|im_start|>assistant\n")


# TODO: Add integration tests that require actual model/tokenizer processes
# TODO: Add API endpoint tests
