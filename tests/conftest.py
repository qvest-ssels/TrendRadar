"""
Pytest configuration and fixtures for TrendRadar tests.
"""
import pytest
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture(autouse=True)
def clear_api_caches():
    """Clear all API caches before each test to ensure isolation."""
    try:
        from mcp_server.utils.cache import clear_all_caches
        clear_all_caches()
    except ImportError:
        pass  # Cache module not available
    yield
    # Also clear after test
    try:
        from mcp_server.utils.cache import clear_all_caches
        clear_all_caches()
    except ImportError:
        pass