# TrendRadar Tests

This directory contains the test suite for the TrendRadar project.

## Running Tests

### Prerequisites
Install development dependencies:
```bash
pip install -e ".[dev]"
```

### Run all tests
```bash
pytest
```

### Run specific test file
```bash
pytest tests/test_utils.py
```

### Run with coverage
```bash
pytest --cov=trendradar_mcp --cov-report=html
```

## Test Structure

- `test_utils.py` - Tests for utility functions (timezone, config loading)
- `test_server.py` - Tests for MCP server initialization
- `test_data_service.py` - Tests for data service functionality
- `conftest.py` - Pytest configuration and fixtures

## Test Categories

- **Unit tests**: Test individual functions and methods
- **Integration tests**: Test component interactions (marked with `@pytest.mark.integration`)

## Adding New Tests

1. Create test files in `tests/` directory with `test_*.py` naming pattern
2. Use descriptive test function names starting with `test_`
3. Use appropriate fixtures from `conftest.py`
4. Mock external dependencies to isolate unit tests