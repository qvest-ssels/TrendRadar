"""
Service Layer Module

Provides core services including data access, caching, parsing, search, etc.
"""

from .data_service import DataService
from .cache_service import CacheService
from .parser_service import ParserService
from .search_service import SiteSearchService, DeepSearchService, RateLimiter
from .browser_service import BrowserService, browser_search, cleanup_browser, PLAYWRIGHT_AVAILABLE

__all__ = [
    'DataService',
    'CacheService',
    'ParserService',
    'SiteSearchService',
    'DeepSearchService',
    'RateLimiter',
    'BrowserService',
    'browser_search',
    'cleanup_browser',
    'PLAYWRIGHT_AVAILABLE',
]
