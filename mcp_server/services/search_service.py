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
            "max_pages": 3
        },
        "spiegel": {
            "enabled": True,
            "type": "url_pattern",
            "base_url": "https://www.spiegel.de",
            "search_url": "https://www.spiegel.de/suche/?suchbegriff={query}&seite={page}",
            "selectors": {
                "results": "article[data-block-el='articleTeaser'], div[data-area='article-teaser'], section[data-area='article-teaser-list'] article",
                "title": "h2, .leading-tight, span[data-target-teaser-el='headline'], a[title]",
                "link": "a[href*='/20']",
                "description": "p, .leading-loose",
                "date": "time, span[data-target-teaser-el='date']"
            },
            "rate_limit": 2.0,
            "max_pages": 3
        },
        "aljazeera": {
            "enabled": True,
            "type": "url_pattern",
            "base_url": "https://www.aljazeera.com",
            "search_url": "https://www.aljazeera.com/search/{query}?page={page}",
            "selectors": {
                "results": "article, div.search-result__list article, div[class*='search-result'], .gc",
                "title": "h3, .gc__title a, a[class*='title'], .gc__header-wrap a",
                "link": "a[href*='/20'], a[href*='/news/'], a[href*='/features/']",
                "description": "p, .gc__excerpt",
                "date": "time, span.date, div[class*='date']"
            },
            "rate_limit": 2.0,
            "max_pages": 3
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
    
    def get_searchable_platforms(self) -> List[str]:
        """Get list of platforms that support site search"""
        platforms = []
        for platform_id in self.SEARCH_CONFIGS:
            if self.is_search_enabled(platform_id):
                platforms.append(platform_id)
        return platforms
    
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
            "headlines": [],
            "site_search": [],
            "combined": [],
            "metadata": {
                "total_results": 0,
                "headline_count": 0,
                "site_search_count": 0,
                "platforms_searched": [],
                "search_time_seconds": 0
            }
        }
        
        # Determine which platforms to search
        if platforms is None:
            # Default to searchable platforms for site search
            site_search_platforms = self.site_search.get_searchable_platforms()
        else:
            site_search_platforms = [p for p in platforms if self.site_search.is_search_enabled(p)]
        
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
            # Use the data service's search functionality
            search_result = self.data_service.search_news(
                keyword=query,
                platforms=platforms,
                date_range=date_range,
                limit=limit,
                include_url=include_url
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
