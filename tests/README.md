# Tests

This directory contains unit and integration tests for the Qwen2.5 Chat Completion Service.

## Running Tests

### All tests
```bash
pytest tests/
```

### Specific test file
```bash
pytest tests/test_chat_completion.py
```

### With coverage
```bash
pytest --cov=src tests/
```

## Test Structure

- `test_chat_completion.py` - Tests for chat template and completion logic
- `test_api.py` - API endpoint tests (TODO)
- `test_model_manager.py` - Model process management tests (TODO)
- `test_tokenizer_manager.py` - Tokenizer process management tests (TODO)

## Writing Tests

Use pytest fixtures for common setup:

```python
import pytest
from src.app import app

@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    return TestClient(app)

def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
```

## Integration Tests

Integration tests that require the actual model/tokenizer processes should:
1. Check if processes are available
2. Skip if not available (use `@pytest.mark.skipif`)
3. Clean up resources after tests
