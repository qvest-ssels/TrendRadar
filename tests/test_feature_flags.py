"""
Tests for the Feature Flags system

Tests feature flag loading from:
- Environment variables
- Config file
- URL parameters
- Cookies
"""

import os
import pytest
from pathlib import Path


class TestFeatureFlags:
    """Tests for FeatureFlags class."""
    
    @pytest.fixture(autouse=True)
    def reset_flags(self):
        """Reset flags before each test."""
        from mcp_server.utils.feature_flags import reset_flags
        reset_flags()
        yield
        reset_flags()
    
    def test_get_flags_singleton(self):
        """Test that get_flags returns a singleton."""
        from mcp_server.utils.feature_flags import get_flags
        
        flags1 = get_flags()
        flags2 = get_flags()
        assert flags1 is flags2
    
    def test_flag_default_disabled(self):
        """Test that flags are disabled by default."""
        from mcp_server.utils.feature_flags import get_flags
        
        flags = get_flags()
        assert not flags.is_enabled("paywall_bypass")
        assert not flags.is_enabled("nonexistent_flag")
    
    def test_enable_disable_flag(self):
        """Test manual enable/disable."""
        from mcp_server.utils.feature_flags import get_flags
        
        flags = get_flags()
        
        flags.enable("test_flag", source="test")
        assert flags.is_enabled("test_flag")
        assert flags.get_source("test_flag") == "test"
        
        flags.disable("test_flag")
        assert not flags.is_enabled("test_flag")
        assert flags.get_source("test_flag") is None
    
    def test_enable_from_url_params(self):
        """Test enabling flags from URL parameters."""
        from mcp_server.utils.feature_flags import get_flags
        
        flags = get_flags()
        
        params = {
            "feature_paywall_bypass": "1",
            "feature_debug_mode": "true",
            "other_param": "value",
        }
        flags.enable_from_url_params(params)
        
        assert flags.is_enabled("paywall_bypass")
        assert flags.is_enabled("debug_mode")
        assert flags.get_source("paywall_bypass") == "url_param"
    
    def test_enable_from_cookies(self):
        """Test enabling flags from cookies."""
        from mcp_server.utils.feature_flags import get_flags
        
        flags = get_flags()
        
        cookies = {
            "feature_premium_sources": "yes",
            "feature_advanced_search": "on",
            "session_id": "abc123",
        }
        flags.enable_from_cookies(cookies)
        
        assert flags.is_enabled("premium_sources")
        assert flags.is_enabled("advanced_search")
        assert flags.get_source("premium_sources") == "cookie"
    
    def test_url_params_override_cookies(self):
        """Test that URL params take priority over cookies."""
        from mcp_server.utils.feature_flags import get_flags
        
        flags = get_flags()
        
        # Enable via cookie first
        cookies = {"feature_test_flag": "1"}
        flags.enable_from_cookies(cookies)
        assert flags.get_source("test_flag") == "cookie"
        
        # URL param should override the source
        params = {"feature_test_flag": "1"}
        flags.enable_from_url_params(params)
        assert flags.get_source("test_flag") == "url_param"
    
    def test_get_enabled_flags(self):
        """Test getting all enabled flags."""
        from mcp_server.utils.feature_flags import get_flags
        
        flags = get_flags()
        
        flags.enable("flag1")
        flags.enable("flag2")
        
        enabled = flags.get_enabled_flags()
        assert "flag1" in enabled
        assert "flag2" in enabled
    
    def test_init_flags_from_request(self):
        """Test initializing flags from a request context."""
        from mcp_server.utils.feature_flags import init_flags_from_request
        
        params = {"feature_paywall_bypass": "1"}
        cookies = {"feature_debug_mode": "1"}
        
        flags = init_flags_from_request(params, cookies)
        
        assert flags.is_enabled("paywall_bypass")
        assert flags.is_enabled("debug_mode")


class TestArchiveUrls:
    """Tests for archive.is URL generation."""
    
    def test_get_archive_url(self):
        """Test basic archive URL generation."""
        from mcp_server.utils.feature_flags import FeatureFlags
        
        url = "https://www.spiegel.de/article/test"
        archive_url = FeatureFlags.get_archive_url(url)
        
        assert archive_url == f"https://archive.is/{url}"
    
    def test_get_archive_newest_url(self):
        """Test newest archive URL generation."""
        from mcp_server.utils.feature_flags import FeatureFlags
        
        url = "https://www.spiegel.de/article/test"
        newest_url = FeatureFlags.get_archive_newest_url(url)
        
        assert newest_url == f"https://archive.is/newest/{url}"
    
    def test_get_archive_search_url(self):
        """Test archive search URL generation."""
        from mcp_server.utils.feature_flags import FeatureFlags
        
        url = "https://www.spiegel.de/article/test"
        search_url = FeatureFlags.get_archive_search_url(url)
        
        assert "archive.is/search" in search_url
        assert "spiegel" in search_url


class TestPlatformMetadata:
    """Tests for platform metadata utilities."""
    
    def test_has_paywall_true(self):
        """Test detecting paywall for known paywalled platform."""
        from mcp_server.utils.platform_metadata import has_paywall
        
        # spiegel should have paywall
        assert has_paywall("spiegel") is True
    
    def test_has_paywall_false(self):
        """Test detecting no paywall for free platform."""
        from mcp_server.utils.platform_metadata import has_paywall
        
        # heise should not have paywall
        assert has_paywall("heise") is False
        # Unknown platform should return False
        assert has_paywall("unknown_platform") is False
    
    def test_get_paywall_type(self):
        """Test getting paywall type."""
        from mcp_server.utils.platform_metadata import get_paywall_type
        
        # spiegel has metered paywall
        assert get_paywall_type("spiegel") == "metered"
        # heise has no paywall
        assert get_paywall_type("heise") is None
    
    def test_get_paywalled_platforms(self):
        """Test getting all paywalled platforms."""
        from mcp_server.utils.platform_metadata import get_paywalled_platforms
        
        paywalled = get_paywalled_platforms()
        
        # Should include spiegel
        assert "spiegel" in paywalled
        # Should not include heise
        assert "heise" not in paywalled
    
    def test_get_platform_metadata(self):
        """Test getting full platform metadata."""
        from mcp_server.utils.platform_metadata import get_platform_metadata
        
        spiegel = get_platform_metadata("spiegel")
        assert spiegel is not None
        assert spiegel["homepage"] == "https://www.spiegel.de"
        assert spiegel["country"] == "DE"
        assert spiegel["paywall"] is True


class TestEnvironmentFlags:
    """Tests for environment variable flag loading."""
    
    @pytest.fixture(autouse=True)
    def reset_env(self):
        """Clean up environment after tests."""
        from mcp_server.utils.feature_flags import reset_flags
        original_env = os.environ.copy()
        reset_flags()
        yield
        # Restore original environment
        for key in list(os.environ.keys()):
            if key.startswith("TRENDRADAR_FEATURE_"):
                del os.environ[key]
        os.environ.update(original_env)
        reset_flags()
    
    def test_load_from_environment(self):
        """Test loading flags from environment variables."""
        from mcp_server.utils.feature_flags import reset_flags, get_flags
        
        # Set environment variable
        os.environ["TRENDRADAR_FEATURE_TEST_ENV_FLAG"] = "1"
        
        # Reset to reload
        reset_flags()
        
        flags = get_flags()
        assert flags.is_enabled("test_env_flag")
        assert flags.get_source("test_env_flag") == "environment"
    
    def test_environment_flag_values(self):
        """Test various truthy values for environment flags."""
        from mcp_server.utils.feature_flags import reset_flags, FeatureFlags
        
        # Test various truthy values
        for value in ["1", "true", "True", "TRUE", "yes", "Yes", "on", "ON"]:
            os.environ["TRENDRADAR_FEATURE_TEST_FLAG"] = value
            reset_flags()
            flags = FeatureFlags()
            assert flags.is_enabled("test_flag"), f"Value '{value}' should enable flag"
        
        # Test falsy values
        for value in ["0", "false", "no", "off", ""]:
            os.environ["TRENDRADAR_FEATURE_TEST_FLAG"] = value
            reset_flags()
            flags = FeatureFlags()
            assert not flags.is_enabled("test_flag"), f"Value '{value}' should not enable flag"
