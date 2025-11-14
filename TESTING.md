# Testing Guide

This document provides comprehensive instructions for testing the Task Management API system.

## Table of Contents

- [Test Overview](#test-overview)
- [Prerequisites](#prerequisites)
- [Running Tests](#running-tests)
- [Test Coverage](#test-coverage)
- [Test Structure](#test-structure)
- [Writing Tests](#writing-tests)
- [Continuous Integration](#continuous-integration)

## Test Overview

The project includes three types of tests:

1. **Unit Tests**: Test individual functions and components in isolation
2. **Integration Tests**: Test end-to-end flows with mocked AWS services
3. **Type Checking**: Validate type hints with pyright

### Test Statistics

- **Total Tests**: X
- **Test Coverage**: 93%
- **Test Duration**: ~2.5 seconds
- **Mocking Framework**: moto (AWS service mocks)

## Prerequisites

### Install Dependencies

```bash
# Activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install test dependencies
pip install -r requirements-dev.txt
```

### Verify Installation

```bash
pytest --version
# pytest 7.4.0

pyright --version
# pyright 1.1.340
```

## Running Tests

### Run All Tests

```bash
pytest
```

Expected output:
```
======================== test session starts ========================
collected X items

tests/unit/test_api_handler.py::TestValidateTask::test_valid_task_with_all_fields PASSED [ 1%]
tests/unit/test_api_handler.py::TestValidateTask::test_valid_task_without_due_date PASSED [ 3%]
...
tests/integration/test_end_to_end.py::TestEndToEndFlow::test_task_with_all_priorities PASSED [100%]

======================== X passed in 2.34s =========================
```

### Run Specific Test Categories

```bash
# Unit tests only
pytest -m unit

# Integration tests only
pytest -m integration

# Run tests in specific file
pytest tests/unit/test_api_handler.py

# Run specific test class
pytest tests/unit/test_api_handler.py::TestValidateTask

# Run specific test
pytest tests/unit/test_api_handler.py::TestValidateTask::test_valid_task_with_all_fields
```

### Verbose Output

```bash
# Verbose mode (-v)
pytest -v

# Very verbose mode (-vv)
pytest -vv

# Show print statements (-s)
pytest -s

# Show local variables on failure (--tb=long)
pytest --tb=long
```

### Fast Fail

```bash
# Stop on first failure
pytest -x

# Stop after N failures
pytest --maxfail=3
```

## Test Coverage

### Generate Coverage Report

```bash
# Run tests with coverage
pytest --cov=src --cov-report=term-missing

# Generate HTML report
pytest --cov=src --cov-report=html

# Open HTML report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows
```

### Coverage Report Example

```
Name                                  Stmts   Miss  Cover   Missing
-------------------------------------------------------------------
src/__init__.py                           X      X   100%
src/api/__init__.py                       X      X   100%
src/api/handler.py                      X      X    93%   45-47, 67
src/queue_processor/__init__.py           X      X   100%
src/queue_processor/handler.py           X      X    94%   89-91
-------------------------------------------------------------------
TOTAL                                   X     X    93%
```

## Test Structure

### Directory Layout

```
tests/
├── conftest.py              # Shared fixtures
├── unit/                    # Unit tests
│   ├── test_api_handler.py
│   └── test_queue_processor_handler.py
└── integration/             # Integration tests
    └── test_end_to_end.py
```

### Test Naming Conventions

- **Files**: `test_<module>.py`
- **Classes**: `Test<Feature>`
- **Methods**: `test_<scenario>`

Example:
```python
class TestValidateTask:
    def test_valid_task_with_all_fields(self):
        # Test passes for valid input
        pass
    
    def test_missing_title(self):
        # Test fails appropriately when title missing
        pass
```

## Writing Tests

### Unit Test Example

```python
import pytest
from src.api import handler

def test_validate_task_success():
    """Test successful validation."""
    task_data = {
        "title": "Test Task",
        "description": "Description",
        "priority": "high"
    }
    is_valid, error = handler.validate_task(task_data)
    assert is_valid is True
    assert error is None

def test_validate_task_missing_field():
    """Test validation fails for missing field."""
    task_data = {"title": "Test Task"}  # Missing description
    is_valid, error = handler.validate_task(task_data)
    assert is_valid is False
    assert "description" in error.lower()
```

### Integration Test with Moto

```python
import boto3
import pytest
from moto import mock_aws

@mock_aws
def test_end_to_end_flow():
    """Test complete task flow."""
    # Set up mock SQS
    sqs = boto3.client("sqs", region_name="us-east-1")
    queue = sqs.create_queue(
        QueueName="test-queue.fifo",
        Attributes={"FifoQueue": "true"}
    )
    
    # Test API handler
    from src.api import handler as api_handler
    response = api_handler.lambda_handler(event, context)
    
    # Verify message in queue
    messages = sqs.receive_message(QueueUrl=queue["QueueUrl"])
    assert "Messages" in messages
```

### Using Fixtures

```python
@pytest.fixture
def valid_task_data():
    """Reusable test data."""
    return {
        "title": "Test Task",
        "description": "Test description",
        "priority": "high"
    }

def test_with_fixture(valid_task_data):
    """Test using fixture."""
    result = process_task(valid_task_data)
    assert result["status"] == "success"
```

### Parametrized Tests

```python
@pytest.mark.parametrize("priority,expected", [
    ("low", True),
    ("medium", True),
    ("high", True),
    ("urgent", False),
])
def test_priority_validation(priority, expected):
    """Test multiple priority values."""
    task = {"title": "Task", "description": "Desc", "priority": priority}
    is_valid, _ = validate_task(task)
    assert is_valid == expected
```

## Type Checking

### Run Pyright

```bash
# Check all code
pyright

# Check specific files
pyright src/api/handler.py

# Check with specific Python version
pyright --pythonversion 3.12
```

### Common Type Errors

**Error**: `Argument of type "str | None" cannot be assigned to parameter of type "str"`

**Solution**: Use type guards or assertions
```python
def process(value: str | None) -> str:
    if value is None:
        raise ValueError("Value required")
    return value.upper()  # Now type checker knows value is str
```

## Code Quality Checks

### Format Code

```bash
# Format with Black
black src tests

# Check formatting without changes
black --check src tests
```

### Lint Code

```bash
# Lint with Ruff
ruff check src tests

# Auto-fix issues
ruff check --fix src tests
```

### Complete Quality Check

```bash
# Run all quality checks
black --check src tests && \
ruff check src tests && \
pyright src tests && \
pytest --cov=src --cov-fail-under=90
```

## Continuous Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      
      - name: Install dependencies
        run: |
          pip install -r requirements-dev.txt
      
      - name: Run tests
        run: |
          pytest --cov=src --cov-fail-under=90
      
      - name: Type checking
        run: |
          pyright src tests
      
      - name: Linting
        run: |
          ruff check src tests
```

## Troubleshooting

### Tests Fail with Import Errors

**Problem**: `ModuleNotFoundError: No module named 'src'`

**Solution**: Install package in editable mode
```bash
pip install -e .
```

### Moto Not Mocking AWS Calls

**Problem**: Tests making real AWS calls

**Solution**: Ensure `@mock_aws` decorator is applied
```python
from moto import mock_aws

@mock_aws
def test_with_mock():
    # AWS calls will be mocked
    pass
```

### Type Checker False Positives

**Problem**: Pyright reports errors for valid code

**Solution**: Use type: ignore comments sparingly
```python
result = some_function()  # type: ignore[some-error]
```

### Coverage Not Counting Lines

**Problem**: Coverage reports lower than expected

**Solution**: Check .coveragerc or pyproject.toml excludes
```toml
[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
]
```

## Best Practices

### 1. Test One Thing

```python
# Good
def test_validate_title_required():
    """Test title is required."""
    task = {"description": "Test", "priority": "high"}
    is_valid, error = validate_task(task)
    assert is_valid is False
    assert "title" in error.lower()

# Bad - testing multiple things
def test_validation():
    """Test validation."""
    # Tests title, description, priority...
    pass
```

### 2. Use Descriptive Names

```python
# Good
def test_api_returns_400_for_missing_required_field():
    pass

# Bad
def test_api():
    pass
```

### 3. Arrange-Act-Assert

```python
def test_task_creation():
    # Arrange
    task_data = {"title": "Test", "description": "Desc", "priority": "high"}
    
    # Act
    result = create_task(task_data)
    
    # Assert
    assert result["status"] == "created"
```

### 4. Mock External Dependencies

```python
@mock_aws
def test_send_to_queue():
    # Mock SQS instead of using real service
    sqs = boto3.client("sqs")
    queue = sqs.create_queue(QueueName="test-queue.fifo")
    # Test with mock
```

### 5. Test Edge Cases

```python
def test_empty_title():
    """Test validation fails for empty title."""
    pass

def test_title_max_length():
    """Test validation fails for title > 200 chars."""
    pass

def test_title_only_whitespace():
    """Test validation fails for whitespace-only title."""
    pass
```

## Performance Testing

### Run Tests with Profiling

```bash
# Profile test execution
pytest --profile

# Profile with pstats
pytest --profile --profile-svg
```

### Benchmark Tests

```python
import time

def test_performance():
    """Test function completes in reasonable time."""
    start = time.time()
    
    # Run operation
    result = expensive_operation()
    
    duration = time.time() - start
    assert duration < 1.0  # Should complete in < 1 second
```

## Additional Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [Moto Documentation](http://docs.getmoto.org/)
- [Pyright Documentation](https://microsoft.github.io/pyright/)
- [AWS Lambda Testing](https://docs.aws.amazon.com/lambda/latest/dg/testing-functions.html)
