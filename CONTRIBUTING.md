# Contributing to Qwen2.5 Chat Completion Service

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Help others learn and grow

## How to Contribute

### Reporting Bugs

If you find a bug, please create an issue with:
- Clear description of the problem
- Steps to reproduce
- Expected vs actual behavior
- Environment details (OS, Python version, LLM-8850 driver version)
- Relevant logs or error messages

### Suggesting Features

For feature requests, create an issue describing:
- The problem you're trying to solve
- Your proposed solution
- Alternative approaches considered
- Examples of how it would be used

### Pull Requests

1. **Fork the repository**
   ```bash
   git clone https://github.com/gregm123456/Qwen2.5_chat_completion_service_llm8850.git
   cd Qwen2.5_chat_completion_service_llm8850
   ```

2. **Create a feature branch**
   ```bash
   git checkout -b feature/my-new-feature
   ```

3. **Make your changes**
   - Follow the coding standards (see below)
   - Add tests for new functionality
   - Update documentation as needed

4. **Test your changes**
   ```bash
   make test
   make lint
   ```

5. **Commit with clear messages**
   ```bash
   git commit -m "Add feature: description of what you added"
   ```

6. **Push and create PR**
   ```bash
   git push origin feature/my-new-feature
   ```

## Development Setup

```bash
# Clone the repo
git clone https://github.com/gregm123456/Qwen2.5_chat_completion_service_llm8850.git
cd Qwen2.5_chat_completion_service_llm8850

# Install dependencies
make install

# Download model
make download-model

# Run in development mode
make dev
```

## Coding Standards

### Python Style
- Follow PEP 8
- Use meaningful variable and function names
- Maximum line length: 120 characters
- Use type hints where appropriate

### Code Formatting
```bash
# Format code with black
make format

# Check linting
make lint
```

### Docstrings
Use docstrings for all public functions and classes:

```python
def my_function(param1: str, param2: int) -> bool:
    """
    Brief description of what the function does.
    
    Args:
        param1: Description of param1
        param2: Description of param2
        
    Returns:
        Description of return value
        
    Raises:
        ValueError: When param1 is empty
    """
    pass
```

### Testing

- Write tests for all new functionality
- Maintain or improve test coverage
- Tests should be fast and isolated
- Use pytest fixtures for setup

```python
def test_my_feature():
    """Test description"""
    # Arrange
    service = MyService()
    
    # Act
    result = service.do_something()
    
    # Assert
    assert result == expected_value
```

## Project Structure

```
src/
├── app.py              # FastAPI application (HTTP endpoints)
├── chat_completion.py  # Chat template and completion logic
├── config.py           # Configuration management
├── model_manager.py    # Model process lifecycle
├── tokenizer_client.py # HTTP client for tokenizer
└── tokenizer_manager.py # Tokenizer process lifecycle

tests/
├── test_chat_completion.py  # Chat logic tests
└── test_*.py                # Additional test files
```

## Areas for Contribution

### High Priority
- [ ] Streaming response support (Server-Sent Events)
- [ ] Integration tests with actual model
- [ ] Performance benchmarking
- [ ] Prometheus metrics endpoint
- [ ] API authentication/authorization

### Medium Priority
- [ ] Docker/container support
- [ ] Load balancing multiple model instances
- [ ] Request queuing and rate limiting
- [ ] Advanced logging (structured JSON logs)
- [ ] Model warm-up strategies

### Documentation
- [ ] API usage examples in different languages
- [ ] Deployment guides for different environments
- [ ] Troubleshooting common issues
- [ ] Performance tuning guide

### Testing
- [ ] Integration tests
- [ ] Load testing scripts
- [ ] CI/CD pipeline
- [ ] Automated deployment tests

## Testing Checklist

Before submitting a PR, ensure:
- [ ] Code passes `make lint`
- [ ] Code is formatted with `make format`
- [ ] All tests pass with `make test`
- [ ] New functionality has tests
- [ ] Documentation is updated
- [ ] CHANGELOG.md is updated (if applicable)

## Questions?

- Check the [README.md](README.md) for general documentation
- Check the [QUICKSTART.md](QUICKSTART.md) for setup help
- Review existing issues and PRs
- Create a new issue for questions

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
