"""
Utility Classes Module

Provides auxiliary functions such as parameter validation, error handling,
URL utilities for normalization and deduplication, and feature flags.
"""

from .url_utils import (
    is_tracking_param,
    normalize_url,
    url_hash,
    extract_domain,
    extract_base_url,
    urls_match,
    get_url_signature,
    URLRegistry,
    get_url_registry,
    reset_url_registry,
)

from .feature_flags import (
    FeatureFlags,
    get_flags,
    reset_flags,
    init_flags_from_request,
    KNOWN_FLAGS,
)

__all__ = [
    # URL utilities
    "is_tracking_param",
    "normalize_url",
    "url_hash",
    "extract_domain",
    "extract_base_url",
    "urls_match",
    "get_url_signature",
    "URLRegistry",
    "get_url_registry",
    "reset_url_registry",
    # Feature flags
    "FeatureFlags",
    "get_flags",
    "reset_flags",
    "init_flags_from_request",
    "KNOWN_FLAGS",
]
