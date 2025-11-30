"""
Newsletter Discovery Service

Searches for newsletters via Substack and newsletter directories.
No API key required - uses web scraping.
"""

import html
import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

import requests

logger = logging.getLogger(__name__)

# Import cache
try:
    from ..utils.cache import get_cache
    CACHE_AVAILABLE = True
except ImportError:
    CACHE_AVAILABLE = False
    logger.warning("Cache not available for Newsletter service")


def sanitize_text(text: str) -> str:
    """Sanitize text to prevent XSS attacks."""
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    text = html.escape(text)
    return text


def sanitize_url(url: str) -> str:
    """Validate and sanitize URL."""
    if not url:
        return ""
    # Only allow http/https
    if not re.match(r'^https?://', url):
        return ""
    # Block script injection
    if re.search(r'javascript:|data:|vbscript:', url, re.IGNORECASE):
        return ""
    return url


class NewsletterService:
    """
    Newsletter discovery service.
    
    Features:
    - Search newsletters by topic
    - Browse popular newsletters
    - Get newsletter details (author, frequency, subscriber count)
    """
    
    # Substack search/browse
    SUBSTACK_SEARCH_URL = "https://substack.com/search"
    SUBSTACK_API_URL = "https://substack.com/api/v1"
    
    # Newsletter categories/topics
    CATEGORIES = [
        "technology", "business", "finance", "culture", "politics",
        "science", "health", "food", "sports", "music", "art",
        "crypto", "climate", "ai", "startups", "productivity"
    ]
    
    def __init__(self):
        """Initialize Newsletter service."""
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        })
        
        if CACHE_AVAILABLE:
            self.cache = get_cache("newsletters", ttl=7200)  # 2 hour cache
        else:
            self.cache = None
    
    def search_newsletters(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Search for newsletters by topic.
        
        Args:
            query: Search keywords
            category: Newsletter category
            limit: Maximum results
            
        Returns:
            Dict with newsletters and metadata
        """
        if not query or not query.strip():
            return {
                "success": False,
                "error": "Query is required",
                "newsletters": []
            }
        
        query = query.strip()[:100]  # Limit query length
        
        # Check cache
        if self.cache:
            cache_key = self.cache.make_key(
                "search",
                query=query,
                category=category,
                limit=limit
            )
            cached = self.cache.get(cache_key)
            if cached is not None:
                logger.debug(f"Cache hit for newsletter search: {query}")
                cached["from_cache"] = True
                return cached
        
        try:
            newsletters = []
            
            # Search Substack
            substack_results = self._search_substack(query, limit)
            newsletters.extend(substack_results)
            
            # Sort by subscriber count if available
            newsletters.sort(
                key=lambda x: x.get("subscribers", 0),
                reverse=True
            )
            
            # Limit results
            newsletters = newsletters[:limit]
            
            result = {
                "success": True,
                "query": query,
                "count": len(newsletters),
                "newsletters": newsletters,
                "category": category,
                "available_categories": self.CATEGORIES,
                "source": "substack"
            }
            
            # Cache result
            if self.cache and newsletters:
                self.cache.set(cache_key, result)
            
            return result
            
        except requests.Timeout:
            return {
                "success": False,
                "error": "Request timed out",
                "query": query,
                "newsletters": []
            }
        except Exception as e:
            logger.error(f"Newsletter search error: {e}")
            return {
                "success": False,
                "error": str(e),
                "query": query,
                "newsletters": []
            }
    
    def _search_substack(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """
        Search Substack for newsletters.
        """
        try:
            # Substack search page
            search_url = f"{self.SUBSTACK_SEARCH_URL}/{quote_plus(query)}"
            
            response = self.session.get(search_url, timeout=15)
            
            if response.status_code != 200:
                logger.warning(f"Substack search returned {response.status_code}")
                return []
            
            newsletters = []
            
            # Extract newsletter URLs from search results
            # Substack uses subdomain pattern: name.substack.com
            subdomain_pattern = r'href="https://([a-zA-Z0-9_-]+)\.substack\.com/?(?:"|\?)'
            matches = re.findall(subdomain_pattern, response.text)
            
            # Get unique subdomains
            seen = set()
            unique_subdomains = []
            for subdomain in matches:
                if subdomain not in seen and subdomain not in ['www', 'api', 'cdn']:
                    seen.add(subdomain)
                    unique_subdomains.append(subdomain)
                    if len(unique_subdomains) >= limit:
                        break
            
            # Extract newsletter names from page
            name_pattern = r'<a[^>]*href="https://([a-zA-Z0-9_-]+)\.substack\.com"[^>]*>([^<]+)</a>'
            name_matches = re.findall(name_pattern, response.text)
            name_map = {m[0]: sanitize_text(m[1]) for m in name_matches}
            
            for subdomain in unique_subdomains:
                name = name_map.get(subdomain, subdomain.replace('-', ' ').title())
                newsletters.append({
                    "id": subdomain,
                    "name": name,
                    "url": f"https://{subdomain}.substack.com",
                    "platform": "substack",
                    "description": "",
                    "author": "",
                    "subscribers": 0,
                    "frequency": "Unknown",
                    "note": "Visit newsletter for full details"
                })
            
            return newsletters
            
        except Exception as e:
            logger.error(f"Substack search error: {e}")
            return []
    
    def get_popular_newsletters(
        self,
        category: Optional[str] = None,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Get popular/featured newsletters.
        
        Args:
            category: Filter by category
            limit: Maximum results
            
        Returns:
            Dict with popular newsletters
        """
        # Check cache
        if self.cache:
            cache_key = self.cache.make_key(
                "popular",
                category=category,
                limit=limit
            )
            cached = self.cache.get(cache_key)
            if cached is not None:
                logger.debug("Cache hit for popular newsletters")
                cached["from_cache"] = True
                return cached
        
        try:
            # Curated list of popular tech newsletters
            popular = [
                {
                    "name": "The Pragmatic Engineer",
                    "url": "https://newsletter.pragmaticengineer.com",
                    "author": "Gergely Orosz",
                    "category": "technology",
                    "description": "Software engineering insights from Big Tech and startups",
                    "subscribers": 500000,
                },
                {
                    "name": "Lenny's Newsletter",
                    "url": "https://www.lennysnewsletter.com",
                    "author": "Lenny Rachitsky",
                    "category": "product",
                    "description": "Product management and growth advice",
                    "subscribers": 400000,
                },
                {
                    "name": "TLDR",
                    "url": "https://tldr.tech",
                    "author": "TLDR Team",
                    "category": "technology",
                    "description": "Daily byte-sized tech news",
                    "subscribers": 1000000,
                },
                {
                    "name": "Morning Brew",
                    "url": "https://www.morningbrew.com",
                    "author": "Morning Brew Team",
                    "category": "business",
                    "description": "Daily business news in a witty, informative style",
                    "subscribers": 4000000,
                },
                {
                    "name": "The Hustle",
                    "url": "https://thehustle.co",
                    "author": "HubSpot",
                    "category": "business",
                    "description": "Business and tech news",
                    "subscribers": 2000000,
                },
                {
                    "name": "Stratechery",
                    "url": "https://stratechery.com",
                    "author": "Ben Thompson",
                    "category": "technology",
                    "description": "Tech strategy and business analysis",
                    "subscribers": 100000,
                },
                {
                    "name": "The Information",
                    "url": "https://www.theinformation.com",
                    "author": "The Information Team",
                    "category": "technology",
                    "description": "Deep tech industry reporting",
                    "subscribers": 50000,
                },
                {
                    "name": "Hacker Newsletter",
                    "url": "https://hackernewsletter.com",
                    "author": "Kale Davis",
                    "category": "technology",
                    "description": "Best of Hacker News, weekly",
                    "subscribers": 60000,
                },
                {
                    "name": "AI Weekly",
                    "url": "https://aiweekly.co",
                    "author": "AI Weekly Team",
                    "category": "ai",
                    "description": "Curated AI and ML news",
                    "subscribers": 30000,
                },
                {
                    "name": "Python Weekly",
                    "url": "https://www.pythonweekly.com",
                    "author": "Rahul Chaudhary",
                    "category": "technology",
                    "description": "Python news, articles, and tutorials",
                    "subscribers": 50000,
                },
            ]
            
            # Filter by category
            if category:
                category = category.lower()
                popular = [n for n in popular if category in n.get("category", "").lower()]
            
            # Limit results
            popular = popular[:limit]
            
            result = {
                "success": True,
                "count": len(popular),
                "newsletters": popular,
                "category": category,
                "source": "curated"
            }
            
            # Cache result
            if self.cache:
                self.cache.set(cache_key, result)
            
            return result
            
        except Exception as e:
            logger.error(f"Popular newsletters error: {e}")
            return {
                "success": False,
                "error": str(e),
                "newsletters": []
            }


# Singleton instance
_newsletter_service: Optional[NewsletterService] = None


def get_newsletter_service() -> NewsletterService:
    """Get singleton NewsletterService instance."""
    global _newsletter_service
    if _newsletter_service is None:
        _newsletter_service = NewsletterService()
    return _newsletter_service
