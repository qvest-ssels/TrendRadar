"""
Site Search Service

Provides deep search functionality by querying news sites' search functions directly.
Supports multiple search methods: URL patterns, web scraping, and APIs.
"""

import re
import time
import logging
from typing import Dict, List, Optional, Any
from urllib.parse import quote_plus, urljoin
from datetime import datetime
from difflib import SequenceMatcher

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class RateLimiter:
    """Simple rate limiter for respecting site limits"""
    
    def __init__(self):
        self._last_request: Dict[str, float] = {}
    
    def wait_if_needed(self, domain: str, min_interval: float = 1.0):
        """Wait if we need to respect rate limits"""
        now = time.time()
        last = self._last_request.get(domain, 0)
        elapsed = now - last
        
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        
        self._last_request[domain] = time.time()


class SiteSearchService:
    """
    Service for searching news sites directly via their search functions.
    
    Supports three search types:
    - url_pattern: Construct search URL and scrape results
    - api: Use official API (requires API key)
    - scrape: Scrape search results page
    """
    
    # Default search configurations for supported platforms
    SEARCH_CONFIGS = {
        "theguardian": {
            "enabled": True,
            "type": "api",
            "base_url": "https://www.theguardian.com",
            "api_url": "https://content.guardianapis.com/search",
            "api_key": "test",  # Free tier API key
            "selectors": {},  # Not needed for API
            "rate_limit": 1.0,
            "max_pages": 3,
            "requires_js": False
        },
        "spiegel": {
            "enabled": True,
            "type": "url_pattern",
            "base_url": "https://www.spiegel.de",
            "search_url": "https://www.spiegel.de/suche/?suchbegriff={query}",
            "selectors": {
                "results": "section[data-search-results] article, article[class*='teaser'], div[data-area='article-teaser-list'] article, [data-block-el='articleTeaser']",
                "title": "h2 a, h3 a, a[data-sara-title], header a, a[title]",
                "link": "a[href*='spiegel.de']",
                "description": "section p, p[class*='leading'], span[class*='standfirst']",
                "date": "time, span[class*='date'], footer time"
            },
            "rate_limit": 2.0,
            "max_pages": 2,
            "requires_js": True,  # Spiegel search requires JavaScript
            "wait_selector": "section[data-search-results], article"
        },
        "aljazeera": {
            "enabled": True,
            "type": "url_pattern",
            "base_url": "https://www.aljazeera.com",
            "search_url": "https://www.aljazeera.com/search/{query}",
            "selectors": {
                "results": "article.gc, div.gc, article[class*='article'], .search-result-item, div[class*='result']",
                "title": "h3 a, .gc__title a, a.u-clickable-card__link, h3.gc__title, a[class*='title']",
                "link": "a[href*='aljazeera.com']",
                "description": "p.gc__excerpt, div.gc__body p, p[class*='excerpt']",
                "date": "time, span.date-simple, footer span, div[class*='date']"
            },
            "rate_limit": 2.0,
            "max_pages": 2,
            "requires_js": True,  # Al Jazeera search requires JavaScript
            "wait_selector": "article.gc, .search-result"
        }
    }
    
    # User agent for requests
    USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    
    def __init__(self, config: Dict = None):
        """
        Initialize the site search service.
        
        Args:
            config: Optional configuration override for search settings
        """
        self.config = config or {}
        self.rate_limiter = RateLimiter()
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,de;q=0.8",
        })
        
        # Load additional platform configs from YAML if not provided
        if not config:
            self._load_yaml_configs()
    
    def _load_yaml_configs(self):
        """Load search configurations from config.yaml platforms"""
        import yaml
        from pathlib import Path
        
        config_path = Path(__file__).parent.parent.parent / "config" / "config.yaml"
        if not config_path.exists():
            logger.debug(f"Config file not found: {config_path}")
            return
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                yaml_config = yaml.safe_load(f)
            
            platforms = yaml_config.get("platforms", [])
            for platform in platforms:
                platform_id = platform.get("id")
                search_config = platform.get("search", {})
                
                if not platform_id or not search_config.get("enabled"):
                    continue
                
                # Skip if already in SEARCH_CONFIGS (prefer hardcoded with selectors)
                if platform_id in self.SEARCH_CONFIGS:
                    continue
                
                # Build config from YAML
                self.config[platform_id] = {
                    "enabled": True,
                    "type": search_config.get("type", "url_pattern"),
                    "base_url": search_config.get("base_url", ""),
                    "search_url": search_config.get("search_url", ""),
                    "api_url": search_config.get("api_url", ""),
                    "api_key": search_config.get("api_key", ""),
                    "selectors": search_config.get("selectors", {
                        "results": search_config.get("result_selector", "article, .search-result, .result-item, [class*='article'], [class*='result']"),
                        "title": search_config.get("title_selector", "h1 a, h2 a, h3 a, a[class*='title'], .title a"),
                        "link": search_config.get("link_selector", "a[href]"),
                        "description": "p, .excerpt, .summary, [class*='desc']",
                        "date": "time, .date, [class*='date']"
                    }),
                    "rate_limit": search_config.get("rate_limit", 2.0),
                    "max_pages": search_config.get("max_pages", 2),
                    "requires_js": search_config.get("requires_js", False),
                    "wait_selector": search_config.get("wait_selector", "article, .result"),
                    "use_cloudscraper": search_config.get("use_cloudscraper", False),
                    # Additional YAML-specific selectors
                    "result_selector": search_config.get("result_selector"),
                    "title_selector": search_config.get("title_selector"),
                    "link_selector": search_config.get("link_selector"),
                }
                logger.debug(f"Loaded search config for {platform_id} from YAML")
        except Exception as e:
            logger.warning(f"Failed to load YAML config: {e}")
    
    def _get_platform_languages(self) -> Dict[str, str]:
        """Load platform language mappings from config.yaml"""
        import yaml
        from pathlib import Path
        
        config_path = Path(__file__).parent.parent.parent / "config" / "config.yaml"
        if not config_path.exists():
            return {}
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                yaml_config = yaml.safe_load(f)
            
            languages = {}
            for platform in yaml_config.get("platforms", []):
                platform_id = platform.get("id")
                language = platform.get("language")
                if platform_id and language:
                    languages[platform_id] = language
            return languages
        except Exception as e:
            logger.warning(f"Failed to load platform languages: {e}")
            return {}
    
    def get_platform_language(self, platform_id: str) -> Optional[str]:
        """Get the language for a specific platform"""
        languages = self._get_platform_languages()
        return languages.get(platform_id)
    
    def get_search_config(self, platform_id: str) -> Optional[Dict]:
        """Get search configuration for a platform"""
        # First check user config, then fall back to defaults
        if platform_id in self.config:
            return self.config[platform_id]
        return self.SEARCH_CONFIGS.get(platform_id)
    
    def is_search_enabled(self, platform_id: str) -> bool:
        """Check if search is enabled for a platform"""
        config = self.get_search_config(platform_id)
        return config is not None and config.get("enabled", False)
    
    def get_searchable_platforms(self, language: Optional[str] = None) -> List[str]:
        """
        Get list of platforms that support site search.
        
        Args:
            language: Optional language filter (e.g., 'en', 'de', 'zh')
                      If None, returns all searchable platforms
        
        Returns:
            List of platform IDs that support search
        """
        platforms = set()
        # Add hardcoded configs
        for platform_id in self.SEARCH_CONFIGS:
            if self.is_search_enabled(platform_id):
                platforms.add(platform_id)
        # Add YAML-loaded configs
        for platform_id in self.config:
            if self.is_search_enabled(platform_id):
                platforms.add(platform_id)
        
        # Filter by language if specified
        if language:
            languages = self._get_platform_languages()
            platforms = {p for p in platforms if languages.get(p) == language}
        
        return sorted(list(platforms))
    
    def search(
        self,
        platform_id: str,
        query: str,
        max_results: int = 20,
        max_pages: int = None
    ) -> List[Dict]:
        """
        Search a specific platform for articles matching the query.
        
        Args:
            platform_id: Platform identifier (e.g., 'theguardian')
            query: Search query string
            max_results: Maximum number of results to return
            max_pages: Maximum number of pages to fetch (overrides config)
            
        Returns:
            List of search results with title, link, description, date
        """
        config = self.get_search_config(platform_id)
        if not config or not config.get("enabled"):
            logger.warning(f"Search not enabled for platform: {platform_id}")
            return []
        
        search_type = config.get("type", "url_pattern")
        
        if search_type == "url_pattern":
            return self._search_url_pattern(platform_id, config, query, max_results, max_pages)
        elif search_type == "api":
            return self._search_api(platform_id, config, query, max_results)
        elif search_type == "scrape":
            return self._search_scrape(platform_id, config, query, max_results, max_pages)
        else:
            logger.error(f"Unknown search type: {search_type}")
            return []
    
    def _search_url_pattern(
        self,
        platform_id: str,
        config: Dict,
        query: str,
        max_results: int,
        max_pages: int = None
    ) -> List[Dict]:
        """Search using URL pattern and scraping"""
        # Check if site requires JavaScript rendering
        if config.get("requires_js", False):
            return self._search_with_browser(platform_id, config, query, max_results)
        
        # Check if site uses cloudscraper for Cloudflare bypass
        if config.get("use_cloudscraper", False):
            return self._search_with_cloudscraper(platform_id, config, query, max_results)
        
        results = []
        base_url = config.get("base_url", "")
        search_url_template = config.get("search_url", "")
        selectors = config.get("selectors", {})
        rate_limit = config.get("rate_limit", 2.0)
        pages_to_fetch = max_pages or config.get("max_pages", 3)
        
        encoded_query = quote_plus(query)
        
        for page in range(1, pages_to_fetch + 1):
            if len(results) >= max_results:
                break
            
            # Build search URL
            search_url = search_url_template.format(query=encoded_query, page=page)
            
            # Respect rate limits
            self.rate_limiter.wait_if_needed(platform_id, rate_limit)
            
            try:
                logger.debug(f"[{platform_id}] Fetching search page {page}: {search_url}")
                response = self.session.get(search_url, timeout=15)
                response.raise_for_status()
                
                # Parse results
                page_results = self._parse_search_results(
                    response.text,
                    selectors,
                    base_url,
                    platform_id
                )
                
                if not page_results:
                    logger.debug(f"[{platform_id}] No results on page {page}, stopping")
                    break
                
                results.extend(page_results)
                logger.debug(f"[{platform_id}] Found {len(page_results)} results on page {page}")
                
            except requests.RequestException as e:
                logger.error(f"[{platform_id}] Request failed for page {page}: {e}")
                break
            except Exception as e:
                logger.error(f"[{platform_id}] Error parsing page {page}: {e}")
                break
        
        # Deduplicate and limit
        seen_urls = set()
        unique_results = []
        for result in results:
            url = result.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_results.append(result)
                if len(unique_results) >= max_results:
                    break
        
        return unique_results
    
    def _search_with_browser(
        self,
        platform_id: str,
        config: Dict,
        query: str,
        max_results: int
    ) -> List[Dict]:
        """Search using Playwright browser for JavaScript-rendered pages"""
        import asyncio
        from .browser_service import BrowserService, PLAYWRIGHT_AVAILABLE
        
        if not PLAYWRIGHT_AVAILABLE:
            logger.warning(f"[{platform_id}] Playwright not available for JS-rendered search. "
                         "Install with: pip install playwright && playwright install chromium")
            return []
        
        base_url = config.get("base_url", "")
        search_url_template = config.get("search_url", "")
        selectors = config.get("selectors", {})
        wait_selector = config.get("wait_selector")
        rate_limit = config.get("rate_limit", 2.0)
        
        encoded_query = quote_plus(query)
        search_url = search_url_template.format(query=encoded_query, page=1)
        
        # Respect rate limits
        self.rate_limiter.wait_if_needed(platform_id, rate_limit)
        
        async def do_browser_search():
            service = BrowserService()  # Fresh instance for each search
            try:
                results = await service.search_and_extract(
                    url=search_url,
                    selectors=selectors,
                    wait_selector=wait_selector,
                    max_results=max_results
                )
                
                # Add platform_id to results
                for result in results:
                    result["platform_id"] = platform_id
                
                logger.info(f"[{platform_id}] Browser search found {len(results)} results for '{query}'")
                return results
                
            except Exception as e:
                logger.error(f"[{platform_id}] Browser search failed: {e}")
                return []
            finally:
                await service.cleanup()
        
        # Run async function - always use a fresh event loop to avoid conflicts
        # This is important for Playwright which doesn't handle loop reuse well
        try:
            # Create a new event loop for this operation
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(do_browser_search())
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"[{platform_id}] Async execution failed: {e}")
            return []
    
    def _search_with_cloudscraper(
        self,
        platform_id: str,
        config: Dict,
        query: str,
        max_results: int
    ) -> List[Dict]:
        """Search using cloudscraper for Cloudflare-protected sites"""
        import asyncio
        from .cloudscraper_service import get_cloudscraper_service
        
        search_url_template = config.get("search_url", "")
        rate_limit = config.get("rate_limit", 2.0)
        
        # Get selectors - support both formats
        result_selector = config.get("result_selector") or config.get("selectors", {}).get("results", "article")
        title_selector = config.get("title_selector") or config.get("selectors", {}).get("title", "a")
        link_selector = config.get("link_selector") or config.get("selectors", {}).get("link", "a")
        
        # Respect rate limits
        self.rate_limiter.wait_if_needed(platform_id, rate_limit)
        
        async def do_cloudscraper_search():
            service = get_cloudscraper_service()
            try:
                results = await service.search_site(
                    search_url=search_url_template,
                    query=query,
                    result_selector=result_selector,
                    title_selector=title_selector,
                    link_selector=link_selector,
                    max_results=max_results
                )
                
                # Format results to match expected structure
                formatted_results = []
                for r in results:
                    formatted_results.append({
                        "title": r.get("title", ""),
                        "url": r.get("url", ""),
                        "description": "",  # cloudscraper doesn't extract descriptions
                        "date": None,
                        "platform_id": platform_id
                    })
                
                logger.info(f"[{platform_id}] Cloudscraper search found {len(formatted_results)} results for '{query}'")
                return formatted_results
                
            except Exception as e:
                logger.error(f"[{platform_id}] Cloudscraper search failed: {e}")
                return []
        
        # Run async function
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(do_cloudscraper_search())
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"[{platform_id}] Cloudscraper async execution failed: {e}")
            return []
    
    def _parse_search_results(
        self,
        html: str,
        selectors: Dict,
        base_url: str,
        platform_id: str
    ) -> List[Dict]:
        """Parse HTML search results page"""
        results = []
        soup = BeautifulSoup(html, 'html.parser')
        
        # Find result containers
        result_selector = selectors.get("results", "article")
        containers = soup.select(result_selector)
        
        if not containers:
            # Try alternative: find all links that look like articles
            containers = soup.select("a[href*='/20']")
        
        for container in containers:
            try:
                result = self._extract_result(container, selectors, base_url, platform_id)
                if result and result.get("title"):
                    results.append(result)
            except Exception as e:
                logger.debug(f"[{platform_id}] Failed to parse result: {e}")
                continue
        
        return results
    
    def _extract_result(
        self,
        container,
        selectors: Dict,
        base_url: str,
        platform_id: str
    ) -> Optional[Dict]:
        """Extract a single search result from a container element"""
        result = {
            "platform_id": platform_id,
            "source": "site_search"
        }
        
        # Extract title
        title_el = container.select_one(selectors.get("title", "h3, h2, a"))
        if title_el:
            result["title"] = title_el.get_text(strip=True)
        elif container.name == "a":
            result["title"] = container.get_text(strip=True)
        
        # Extract link
        link_el = container.select_one(selectors.get("link", "a"))
        if link_el and link_el.get("href"):
            href = link_el.get("href")
            result["url"] = urljoin(base_url, href) if not href.startswith("http") else href
        elif container.name == "a" and container.get("href"):
            href = container.get("href")
            result["url"] = urljoin(base_url, href) if not href.startswith("http") else href
        
        # Extract description
        desc_el = container.select_one(selectors.get("description", "p"))
        if desc_el:
            result["description"] = desc_el.get_text(strip=True)[:300]
        
        # Extract date
        date_el = container.select_one(selectors.get("date", "time"))
        if date_el:
            date_text = date_el.get("datetime") or date_el.get_text(strip=True)
            result["date"] = date_text
        
        # Filter out empty or invalid results
        if not result.get("title") or len(result.get("title", "")) < 10:
            return None
        if not result.get("url"):
            return None
        
        return result
    
    def _search_api(
        self,
        platform_id: str,
        config: Dict,
        query: str,
        max_results: int
    ) -> List[Dict]:
        """Search using official API"""
        results = []
        
        if platform_id == "theguardian":
            results = self._search_guardian_api(config, query, max_results)
        else:
            logger.warning(f"API search not implemented for {platform_id}")
        
        return results
    
    def _search_guardian_api(
        self,
        config: Dict,
        query: str,
        max_results: int
    ) -> List[Dict]:
        """Search using The Guardian's free API"""
        results = []
        api_url = config.get("api_url", "https://content.guardianapis.com/search")
        api_key = config.get("api_key", "test")
        rate_limit = config.get("rate_limit", 1.0)
        
        try:
            # Rate limit
            self.rate_limiter.wait_if_needed("guardianapis.com", rate_limit)
            
            params = {
                "q": query,
                "api-key": api_key,
                "page-size": min(max_results, 50),  # API max is 50
                "show-fields": "headline,trailText,shortUrl",
                "order-by": "relevance"
            }
            
            response = self.session.get(api_url, params=params, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            api_results = data.get("response", {}).get("results", [])
            
            for item in api_results:
                fields = item.get("fields", {})
                result = {
                    "title": fields.get("headline") or item.get("webTitle", ""),
                    "url": item.get("webUrl", ""),
                    "description": fields.get("trailText", "")[:300] if fields.get("trailText") else "",
                    "date": item.get("webPublicationDate", ""),
                    "platform_id": "theguardian",
                    "source": "site_search"
                }
                
                if result["title"] and result["url"]:
                    results.append(result)
                    
                if len(results) >= max_results:
                    break
                    
            logger.info(f"[theguardian] API returned {len(results)} results for '{query}'")
            
        except requests.exceptions.RequestException as e:
            logger.error(f"[theguardian] API request failed: {e}")
        except (KeyError, ValueError) as e:
            logger.error(f"[theguardian] API response parsing failed: {e}")
        
        return results
    
    def _search_scrape(
        self,
        platform_id: str,
        config: Dict,
        query: str,
        max_results: int,
        max_pages: int = None
    ) -> List[Dict]:
        """Search using direct scraping (same as url_pattern for now)"""
        return self._search_url_pattern(platform_id, config, query, max_results, max_pages)


class DeepSearchService:
    """
    Hybrid search service combining RSS headline search with site-specific search.
    
    Provides comprehensive news search by:
    1. Searching cached RSS headlines (fast, from existing crawls)
    2. Querying sites' search functions directly (thorough, real-time)
    3. Deduplicating and ranking combined results
    """
    
    def __init__(self, project_root: str = None, config: Dict = None):
        """
        Initialize the deep search service.
        
        Args:
            project_root: Project root directory for data service
            config: Optional configuration for search settings
        """
        from .data_service import DataService
        
        self.data_service = DataService(project_root)
        self.site_search = SiteSearchService(config)
    
    def deep_search(
        self,
        query: str,
        platforms: Optional[List[str]] = None,
        language: Optional[str] = None,
        mode: str = "both",
        max_results: int = 50,
        date_range: Optional[Dict[str, str]] = None,
        include_url: bool = True
    ) -> Dict:
        """
        Perform comprehensive search across news platforms.
        
        Args:
            query: Search query string
            platforms: List of platform IDs to search (None = all supported)
            language: Language filter (e.g., 'en', 'de', 'zh', 'fr')
                      If specified, only searches platforms in that language
            mode: Search mode:
                - "headlines": Search cached RSS headlines only (fast)
                - "site_search": Query site search functions only (thorough)
                - "both": Combine both sources (comprehensive)
            max_results: Maximum total results to return
            date_range: Date range for headline search {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
            include_url: Whether to include URLs in results
            
        Returns:
            Dict with search results and metadata
        """
        start_time = time.time()
        
        results = {
            "query": query,
            "mode": mode,
            "language": language,
            "headlines": [],
            "site_search": [],
            "combined": [],
            "metadata": {
                "total_results": 0,
                "headline_count": 0,
                "site_search_count": 0,
                "platforms_searched": [],
                "language_filter": language,
                "search_time_seconds": 0
            }
        }
        
        # Determine which platforms to search
        if platforms is None:
            # Default to searchable platforms for site search, filtered by language
            site_search_platforms = self.site_search.get_searchable_platforms(language=language)
        else:
            # Filter provided platforms by search capability and language
            site_search_platforms = [p for p in platforms if self.site_search.is_search_enabled(p)]
            if language:
                site_search_platforms = [
                    p for p in site_search_platforms 
                    if self.site_search.get_platform_language(p) == language
                ]
        
        # Search headlines (cached RSS data)
        if mode in ("headlines", "both"):
            try:
                headline_results = self._search_headlines(
                    query=query,
                    platforms=platforms,
                    date_range=date_range,
                    limit=max_results,
                    include_url=include_url
                )
                results["headlines"] = headline_results
                results["metadata"]["headline_count"] = len(headline_results)
            except Exception as e:
                logger.error(f"Headline search failed: {e}")
                results["headlines"] = []
        
        # Search sites directly
        if mode in ("site_search", "both"):
            site_results = []
            for platform_id in site_search_platforms:
                try:
                    platform_results = self.site_search.search(
                        platform_id=platform_id,
                        query=query,
                        max_results=max_results // max(len(site_search_platforms), 1)
                    )
                    site_results.extend(platform_results)
                    results["metadata"]["platforms_searched"].append(platform_id)
                except Exception as e:
                    logger.error(f"Site search failed for {platform_id}: {e}")
            
            results["site_search"] = site_results
            results["metadata"]["site_search_count"] = len(site_results)
        
        # Combine and deduplicate
        combined = self._combine_and_rank(
            headlines=results["headlines"],
            site_results=results["site_search"],
            query=query,
            max_results=max_results
        )
        results["combined"] = combined
        results["metadata"]["total_results"] = len(combined)
        results["metadata"]["search_time_seconds"] = round(time.time() - start_time, 2)
        
        return results
    
    def _search_headlines(
        self,
        query: str,
        platforms: Optional[List[str]],
        date_range: Optional[Dict[str, str]],
        limit: int,
        include_url: bool
    ) -> List[Dict]:
        """Search cached RSS headlines using existing data service"""
        try:
            # Convert date_range dict to tuple if provided
            date_tuple = None
            if date_range:
                from datetime import datetime
                start = datetime.strptime(date_range.get("start", ""), "%Y-%m-%d") if date_range.get("start") else None
                end = datetime.strptime(date_range.get("end", ""), "%Y-%m-%d") if date_range.get("end") else None
                if start and end:
                    date_tuple = (start, end)
            
            # Use the data service's search functionality
            search_result = self.data_service.search_news_by_keyword(
                keyword=query,
                platforms=platforms,
                date_range=date_tuple,
                limit=limit
            )
            
            # Convert to standardized format
            headlines = []
            for item in search_result.get("results", []):
                headlines.append({
                    "title": item.get("title", ""),
                    "platform_id": item.get("platform", ""),
                    "platform_name": item.get("platform_name", ""),
                    "url": item.get("url", "") if include_url else None,
                    "date": item.get("date", ""),
                    "source": "headlines",
                    "relevance_score": item.get("relevance_score", 0)
                })
            
            return headlines
        except Exception as e:
            logger.error(f"Headline search error: {e}")
            return []
    
    def _combine_and_rank(
        self,
        headlines: List[Dict],
        site_results: List[Dict],
        query: str,
        max_results: int
    ) -> List[Dict]:
        """Combine results from different sources, deduplicate, and rank"""
        all_results = []
        seen_titles = set()
        seen_urls = set()
        
        # Helper to normalize titles for deduplication
        def normalize_title(title: str) -> str:
            return re.sub(r'[^\w\s]', '', title.lower())[:100]
        
        # Helper to calculate relevance score
        def calculate_score(item: Dict) -> float:
            title = item.get("title", "").lower()
            query_lower = query.lower()
            
            # Exact match bonus
            if query_lower in title:
                score = 1.0
            else:
                # Fuzzy similarity
                score = SequenceMatcher(None, query_lower, title).ratio()
            
            # Source bonus (headlines are from recent crawls)
            if item.get("source") == "headlines":
                score += 0.1
            
            return round(score, 3)
        
        # Process headlines first (they're from recent/known crawls)
        for item in headlines:
            title_norm = normalize_title(item.get("title", ""))
            url = item.get("url", "")
            
            if title_norm not in seen_titles and (not url or url not in seen_urls):
                item["relevance_score"] = calculate_score(item)
                all_results.append(item)
                seen_titles.add(title_norm)
                if url:
                    seen_urls.add(url)
        
        # Add site search results (deduplicating against headlines)
        for item in site_results:
            title_norm = normalize_title(item.get("title", ""))
            url = item.get("url", "")
            
            if title_norm not in seen_titles and (not url or url not in seen_urls):
                item["relevance_score"] = calculate_score(item)
                all_results.append(item)
                seen_titles.add(title_norm)
                if url:
                    seen_urls.add(url)
        
        # Sort by relevance score (descending)
        all_results.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
        
        return all_results[:max_results]


class MetaSearchService:
    """
    Meta Search Service - Research tool for comprehensive news event analysis.
    
    This service provides high-level research capabilities by:
    1. Running multiple parallel searches across platforms
    2. Clustering related articles by topic similarity
    3. Identifying key events, perspectives, and sources
    4. Generating a comprehensive research summary
    """
    
    def __init__(self, project_root: str = None):
        """Initialize the meta search service."""
        self.deep_search = DeepSearchService(project_root)
        
    def research_topic(
        self,
        topic: str,
        related_terms: Optional[List[str]] = None,
        languages: Optional[List[str]] = None,
        max_results_per_query: int = 30,
        cluster_threshold: float = 0.4,
        include_url: bool = True
    ) -> Dict:
        """
        Research a topic comprehensively across multiple news sources.
        
        This is a meta-search that:
        1. Searches for the main topic
        2. Searches for related terms (if provided)
        3. Clusters results by similarity to identify distinct events/stories
        4. Analyzes coverage across different platforms and languages
        
        Args:
            topic: Main topic or event to research (e.g., "AI regulation", "Tesla layoffs")
            related_terms: Additional search terms to expand coverage
                          (e.g., ["artificial intelligence", "machine learning", "OpenAI"])
            languages: Language filters (e.g., ["en", "de"]). None = all languages
            max_results_per_query: Max results per search query
            cluster_threshold: Similarity threshold for clustering (0.0-1.0)
            include_url: Whether to include URLs in results
            
        Returns:
            Dict with:
            - topic: Original search topic
            - clusters: Groups of related articles
            - platform_coverage: Coverage by platform
            - language_coverage: Coverage by language
            - key_stories: Top stories identified
            - total_articles: Total unique articles found
            - search_queries: All queries executed
        """
        start_time = time.time()
        
        # Build search queries
        queries = [topic]
        if related_terms:
            queries.extend(related_terms)
        
        # Collect all results
        all_results = []
        query_stats = {}
        
        for query in queries:
            # Search each language if specified, otherwise all
            search_languages = languages if languages else [None]
            
            for lang in search_languages:
                try:
                    search_result = self.deep_search.deep_search(
                        query=query,
                        language=lang,
                        mode="both",
                        max_results=max_results_per_query,
                        include_url=include_url
                    )
                    
                    combined = search_result.get("combined", [])
                    
                    # Tag results with the query that found them
                    for item in combined:
                        item["search_query"] = query
                        item["search_language"] = lang
                    
                    all_results.extend(combined)
                    
                    query_key = f"{query}" + (f" ({lang})" if lang else "")
                    query_stats[query_key] = len(combined)
                    
                except Exception as e:
                    logger.error(f"Search failed for query '{query}' (lang={lang}): {e}")
        
        # Deduplicate results
        unique_results = self._deduplicate_results(all_results)
        
        # Cluster results by similarity
        clusters = self._cluster_results(unique_results, cluster_threshold)
        
        # Analyze coverage
        platform_coverage = self._analyze_platform_coverage(unique_results)
        language_coverage = self._analyze_language_coverage(unique_results)
        
        # Identify key stories (top from each cluster)
        key_stories = self._extract_key_stories(clusters, max_stories=10)
        
        return {
            "success": True,
            "topic": topic,
            "related_terms": related_terms or [],
            "clusters": clusters,
            "key_stories": key_stories,
            "platform_coverage": platform_coverage,
            "language_coverage": language_coverage,
            "total_articles": len(unique_results),
            "cluster_count": len(clusters),
            "search_queries": query_stats,
            "search_time_seconds": round(time.time() - start_time, 2)
        }
    
    def _deduplicate_results(self, results: List[Dict]) -> List[Dict]:
        """Deduplicate results by title similarity and URL."""
        seen_titles = set()
        seen_urls = set()
        unique = []
        
        def normalize_title(title: str) -> str:
            return re.sub(r'[^\w\s]', '', title.lower())[:100]
        
        for item in results:
            title_norm = normalize_title(item.get("title", ""))
            url = item.get("url", "")
            
            if title_norm not in seen_titles and (not url or url not in seen_urls):
                unique.append(item)
                seen_titles.add(title_norm)
                if url:
                    seen_urls.add(url)
        
        return unique
    
    def _cluster_results(
        self, 
        results: List[Dict], 
        threshold: float = 0.4
    ) -> List[Dict]:
        """
        Cluster results by title similarity to identify related stories.
        
        Uses a simple greedy clustering approach:
        1. Sort by relevance score
        2. For each article, either add to existing cluster or create new one
        """
        if not results:
            return []
        
        # Sort by relevance
        sorted_results = sorted(
            results, 
            key=lambda x: x.get("relevance_score", 0), 
            reverse=True
        )
        
        clusters = []
        
        for item in sorted_results:
            title = item.get("title", "").lower()
            
            # Find best matching cluster
            best_cluster = None
            best_similarity = 0
            
            for cluster in clusters:
                # Compare with cluster representative (first item)
                rep_title = cluster["representative"]["title"].lower()
                similarity = SequenceMatcher(None, title, rep_title).ratio()
                
                if similarity > best_similarity and similarity >= threshold:
                    best_similarity = similarity
                    best_cluster = cluster
            
            if best_cluster:
                # Add to existing cluster
                best_cluster["articles"].append(item)
                best_cluster["size"] += 1
                # Update platforms in this cluster
                platform = item.get("platform_id", "unknown")
                if platform not in best_cluster["platforms"]:
                    best_cluster["platforms"].append(platform)
            else:
                # Create new cluster
                platform = item.get("platform_id", "unknown")
                clusters.append({
                    "id": len(clusters) + 1,
                    "representative": item,
                    "articles": [item],
                    "size": 1,
                    "platforms": [platform],
                    "theme": self._extract_theme(item.get("title", ""))
                })
        
        # Sort clusters by size (most coverage first)
        clusters.sort(key=lambda c: c["size"], reverse=True)
        
        return clusters
    
    def _extract_theme(self, title: str) -> str:
        """Extract a short theme/summary from title."""
        # Simple approach: take first 50 chars or up to first punctuation
        title = title.strip()
        for punct in [':', '-', '–', '|', '—']:
            if punct in title:
                title = title.split(punct)[0].strip()
                break
        return title[:60] + "..." if len(title) > 60 else title
    
    def _analyze_platform_coverage(self, results: List[Dict]) -> Dict:
        """Analyze how many articles come from each platform."""
        platform_counts = {}
        for item in results:
            platform = item.get("platform_id", "unknown")
            platform_name = item.get("platform_name", platform)
            if platform not in platform_counts:
                platform_counts[platform] = {
                    "name": platform_name,
                    "count": 0
                }
            platform_counts[platform]["count"] += 1
        
        # Sort by count
        sorted_platforms = sorted(
            platform_counts.items(),
            key=lambda x: x[1]["count"],
            reverse=True
        )
        
        return {k: v for k, v in sorted_platforms}
    
    def _analyze_language_coverage(self, results: List[Dict]) -> Dict:
        """Analyze coverage by language."""
        # Get platform languages from SiteSearchService
        site_search = self.deep_search.site_search
        
        language_counts = {}
        for item in results:
            platform = item.get("platform_id", "")
            lang = site_search.get_platform_language(platform) or "unknown"
            
            if lang not in language_counts:
                language_counts[lang] = 0
            language_counts[lang] += 1
        
        # Sort by count
        sorted_langs = sorted(
            language_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        return dict(sorted_langs)
    
    def _extract_key_stories(
        self, 
        clusters: List[Dict], 
        max_stories: int = 10
    ) -> List[Dict]:
        """Extract key stories from clusters."""
        key_stories = []
        
        for cluster in clusters[:max_stories]:
            rep = cluster["representative"]
            key_stories.append({
                "title": rep.get("title", ""),
                "url": rep.get("url", ""),
                "platform": rep.get("platform_id", ""),
                "coverage_count": cluster["size"],
                "platforms_covering": cluster["platforms"],
                "theme": cluster["theme"]
            })
        
        return key_stories
