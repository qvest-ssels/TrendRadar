"""
Feature Flags System for TrendRadar

Supports enabling features through:
1. Environment variables: TRENDRADAR_FEATURE_<FLAG_NAME>=1
2. Config file: feature_flags section in config.yaml
3. URL parameters: ?feature_<flag_name>=1
4. Cookies: feature_<flag_name>=1

Flags are evaluated in priority order:
1. URL params (highest - temporary override)
2. Cookies (session-persistent override)
3. Environment variables (deployment-level)
4. Config file (default settings)

Usage:
    from mcp_server.utils.feature_flags import FeatureFlags, get_flags

    # Check if a flag is enabled
    flags = get_flags()
    if flags.is_enabled("paywall_bypass"):
        # Premium feature logic
        url = flags.get_archive_url(original_url)
"""

import os
import logging
from dataclasses import dataclass, field
from typing import Optional, Set
from urllib.parse import quote_plus, urlparse

logger = logging.getLogger(__name__)

# Known feature flags with descriptions
KNOWN_FLAGS = {
    "paywall_bypass": "Enable archive.is bypass for paywalled content",
    "premium_sources": "Access to premium news sources",
    "advanced_search": "Enable advanced search operators",
    "debug_mode": "Enable verbose debugging output",
    "experimental_ui": "Enable experimental UI features",
}


@dataclass
class FeatureFlags:
    """
    Feature flags manager.
    
    Supports multiple sources of truth with priority:
    1. URL params (highest)
    2. Cookies
    3. Environment variables
    4. Config file (lowest)
    """
    
    # Flags explicitly enabled (from any source)
    _enabled_flags: Set[str] = field(default_factory=set)
    
    # Source of each flag for debugging
    _flag_sources: dict = field(default_factory=dict)
    
    # Config-based defaults
    _config_flags: dict = field(default_factory=dict)
    
    def __post_init__(self):
        """Initialize flags from environment and config."""
        self._load_from_environment()
        self._load_from_config()
    
    def _load_from_environment(self):
        """Load flags from environment variables."""
        for key, value in os.environ.items():
            if key.startswith("TRENDRADAR_FEATURE_"):
                flag_name = key[19:].lower()  # Remove prefix, lowercase
                if value.lower() in ("1", "true", "yes", "on"):
                    self._enabled_flags.add(flag_name)
                    self._flag_sources[flag_name] = "environment"
                    logger.debug(f"Feature flag '{flag_name}' enabled via environment")
    
    def _load_from_config(self):
        """Load flags from config.yaml if available."""
        try:
            import yaml
            from pathlib import Path
            
            # Try to find config.yaml
            config_paths = [
                Path("config/config.yaml"),
                Path("../config/config.yaml"),
                Path(__file__).parent.parent.parent / "config" / "config.yaml",
            ]
            
            for config_path in config_paths:
                if config_path.exists():
                    with open(config_path, "r", encoding="utf-8") as f:
                        config = yaml.safe_load(f)
                    
                    feature_flags = config.get("feature_flags", {})
                    self._config_flags = feature_flags
                    
                    for flag_name, enabled in feature_flags.items():
                        if enabled and flag_name not in self._enabled_flags:
                            self._enabled_flags.add(flag_name)
                            self._flag_sources[flag_name] = "config"
                            logger.debug(f"Feature flag '{flag_name}' enabled via config")
                    break
        except Exception as e:
            logger.warning(f"Could not load feature flags from config: {e}")
    
    def enable_from_url_params(self, params: dict):
        """
        Enable flags from URL query parameters.
        
        Args:
            params: Dict of query parameters (e.g., from request.args)
        """
        for key, value in params.items():
            if key.startswith("feature_"):
                flag_name = key[8:]  # Remove 'feature_' prefix
                if value.lower() in ("1", "true", "yes", "on"):
                    self._enabled_flags.add(flag_name)
                    self._flag_sources[flag_name] = "url_param"
                    logger.debug(f"Feature flag '{flag_name}' enabled via URL param")
    
    def enable_from_cookies(self, cookies: dict):
        """
        Enable flags from cookies.
        
        Args:
            cookies: Dict of cookies (e.g., from request.cookies)
        """
        for key, value in cookies.items():
            if key.startswith("feature_"):
                flag_name = key[8:]  # Remove 'feature_' prefix
                if value.lower() in ("1", "true", "yes", "on"):
                    if flag_name not in self._enabled_flags or self._flag_sources.get(flag_name) != "url_param":
                        self._enabled_flags.add(flag_name)
                        # Only update source if not already set by URL param
                        if self._flag_sources.get(flag_name) != "url_param":
                            self._flag_sources[flag_name] = "cookie"
                        logger.debug(f"Feature flag '{flag_name}' enabled via cookie")
    
    def enable(self, flag_name: str, source: str = "manual"):
        """Manually enable a flag."""
        self._enabled_flags.add(flag_name)
        self._flag_sources[flag_name] = source
        logger.info(f"Feature flag '{flag_name}' enabled ({source})")
    
    def disable(self, flag_name: str):
        """Manually disable a flag."""
        self._enabled_flags.discard(flag_name)
        self._flag_sources.pop(flag_name, None)
        logger.info(f"Feature flag '{flag_name}' disabled")
    
    def is_enabled(self, flag_name: str) -> bool:
        """Check if a feature flag is enabled."""
        return flag_name in self._enabled_flags
    
    def get_source(self, flag_name: str) -> Optional[str]:
        """Get the source that enabled this flag."""
        return self._flag_sources.get(flag_name)
    
    def get_enabled_flags(self) -> Set[str]:
        """Get all enabled flags."""
        return self._enabled_flags.copy()
    
    def get_all_flags_status(self) -> dict:
        """Get status of all known flags."""
        return {
            flag: {
                "enabled": self.is_enabled(flag),
                "source": self.get_source(flag),
                "description": KNOWN_FLAGS.get(flag, "Unknown flag"),
            }
            for flag in KNOWN_FLAGS
        }
    
    # ==================== Archive.is Integration ====================
    
    @staticmethod
    def get_archive_url(url: str) -> str:
        """
        Generate an archive.is URL for bypassing paywalls.
        
        Args:
            url: The original article URL
            
        Returns:
            archive.is URL that may have a cached version
        """
        # archive.is expects the full URL as a path component
        # Format: https://archive.is/https://example.com/article
        return f"https://archive.is/{url}"
    
    @staticmethod
    def get_archive_search_url(url: str) -> str:
        """
        Generate an archive.is search URL to find cached versions.
        
        Args:
            url: The original article URL
            
        Returns:
            archive.is search URL
        """
        encoded_url = quote_plus(url)
        return f"https://archive.is/search/?q={encoded_url}"
    
    @staticmethod
    def get_archive_newest_url(url: str) -> str:
        """
        Generate an archive.is URL for the newest cached version.
        
        Args:
            url: The original article URL
            
        Returns:
            archive.is newest version URL
        """
        return f"https://archive.is/newest/{url}"


# Global instance (singleton pattern)
_flags_instance: Optional[FeatureFlags] = None


def get_flags() -> FeatureFlags:
    """
    Get the global feature flags instance.
    
    Returns:
        FeatureFlags: The global feature flags manager
    """
    global _flags_instance
    if _flags_instance is None:
        _flags_instance = FeatureFlags()
    return _flags_instance


def reset_flags():
    """Reset the global feature flags instance (for testing)."""
    global _flags_instance
    _flags_instance = None


def init_flags_from_request(params: dict = None, cookies: dict = None) -> FeatureFlags:
    """
    Initialize feature flags from a request context.
    
    This should be called at the start of request handling to pick up
    URL params and cookies.
    
    Args:
        params: Query parameters dict
        cookies: Cookies dict
        
    Returns:
        FeatureFlags: Configured flags instance
    """
    flags = get_flags()
    if params:
        flags.enable_from_url_params(params)
    if cookies:
        flags.enable_from_cookies(cookies)
    return flags
