"""
Platform Metadata Utilities

Provides functions to load and query platform metadata including paywall information.
"""

import logging
from pathlib import Path
from typing import Optional, Dict, Any
from functools import lru_cache

import yaml

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _load_platform_metadata() -> Dict[str, Any]:
    """Load platform metadata from config file (cached)."""
    config_paths = [
        Path("config/platform_metadata.yaml"),
        Path("../config/platform_metadata.yaml"),
        Path(__file__).parent.parent.parent / "config" / "platform_metadata.yaml",
    ]
    
    for config_path in config_paths:
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    return data.get("platforms", {})
            except Exception as e:
                logger.warning(f"Could not load platform metadata from {config_path}: {e}")
    
    logger.warning("Platform metadata file not found")
    return {}


def get_platform_metadata(platform_id: str) -> Optional[Dict[str, Any]]:
    """
    Get metadata for a specific platform.
    
    Args:
        platform_id: The platform identifier (e.g., 'spiegel', 'guardian')
        
    Returns:
        Platform metadata dict or None if not found
    """
    platforms = _load_platform_metadata()
    return platforms.get(platform_id)


def has_paywall(platform_id: str) -> bool:
    """
    Check if a platform has a paywall.
    
    Args:
        platform_id: The platform identifier
        
    Returns:
        True if the platform has a paywall, False otherwise
    """
    metadata = get_platform_metadata(platform_id)
    if metadata is None:
        return False
    return metadata.get("paywall", False)


def get_paywall_type(platform_id: str) -> Optional[str]:
    """
    Get the paywall type for a platform.
    
    Args:
        platform_id: The platform identifier
        
    Returns:
        Paywall type ('metered', 'hard', 'soft') or None if no paywall
    """
    metadata = get_platform_metadata(platform_id)
    if metadata is None or not metadata.get("paywall", False):
        return None
    return metadata.get("paywall_type")


def get_paywalled_platforms() -> Dict[str, Dict[str, Any]]:
    """
    Get all platforms with paywalls.
    
    Returns:
        Dict of platform_id -> metadata for all paywalled platforms
    """
    platforms = _load_platform_metadata()
    return {
        pid: meta
        for pid, meta in platforms.items()
        if meta.get("paywall", False)
    }


def get_homepage(platform_id: str) -> Optional[str]:
    """Get the homepage URL for a platform."""
    metadata = get_platform_metadata(platform_id)
    if metadata is None:
        return None
    return metadata.get("homepage")


def clear_metadata_cache():
    """Clear the metadata cache (for testing or config reloading)."""
    _load_platform_metadata.cache_clear()
