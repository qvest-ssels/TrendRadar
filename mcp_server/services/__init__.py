"""
Service Layer Module

Provides core services including data access, caching, parsing, search, etc.
"""

from .data_service import DataService
from .cache_service import CacheService
from .parser_service import ParserService
from .search_service import SiteSearchService, DeepSearchService, RateLimiter
from .browser_service import BrowserService, browser_search, cleanup_browser, PLAYWRIGHT_AVAILABLE
from .wikipedia_service import WikipediaService, get_wikipedia_service
from .huggingface_service import HuggingFaceService, get_huggingface_service
from .arxiv_service import ArxivService, get_arxiv_service
from .github_service import GitHubService, get_github_service
from .youtube_service import YouTubeService, get_youtube_service
from .udemy_service import UdemyService, get_udemy_service
from .conference_service import ConferenceService, get_conference_service
from .newsletter_service import NewsletterService, get_newsletter_service
from .imdb_service import IMDBService, get_imdb_service
from .people_service import PeopleService, get_people_service

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
    'WikipediaService',
    'get_wikipedia_service',
    'HuggingFaceService',
    'get_huggingface_service',
    'ArxivService',
    'get_arxiv_service',
    'GitHubService',
    'get_github_service',
    'YouTubeService',
    'get_youtube_service',
    'UdemyService',
    'get_udemy_service',
    'ConferenceService',
    'get_conference_service',
    'NewsletterService',
    'get_newsletter_service',
    'IMDBService',
    'get_imdb_service',
    'PeopleService',
    'get_people_service',
]
