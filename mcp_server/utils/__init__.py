"""
Utility Classes Module

Provides auxiliary functions such as parameter validation, error handling,
and URL utilities for normalization and deduplication.
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
)

__all__ = [
    "is_tracking_param",
    "normalize_url",
    "url_hash",
    "extract_domain",
    "extract_base_url",
    "urls_match",
    "get_url_signature",
    "URLRegistry",
    "get_url_registry",
]
