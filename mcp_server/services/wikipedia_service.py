"""
Wikipedia Knowledge Service

Provides access to Wikipedia for background information and context.
Supports multiple languages for language-aware knowledge retrieval.
"""

import html
import logging
import re
from typing import Dict, List, Optional, Any
from urllib.parse import quote

import requests

logger = logging.getLogger(__name__)


def sanitize_html(text: str) -> str:
    """
    Sanitize HTML content to prevent XSS attacks.
    Removes all HTML tags and escapes special characters.
    
    Args:
        text: Raw HTML text from Wikipedia
        
    Returns:
        Sanitized plain text
    """
    if not text:
        return ""
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Escape HTML entities
    text = html.escape(text)
    return text


def sanitize_url(url: str) -> str:
    """
    Validate and sanitize URL to prevent injection.
    Only allows Wikipedia URLs.
    
    Args:
        url: URL to sanitize
        
    Returns:
        Sanitized URL or empty string if invalid
    """
    if not url:
        return ""
    # Only allow Wikipedia domains
    if not re.match(r'^https?://[a-z]{2,3}\.wikipedia\.org/', url):
        return ""
    # Remove any script injection attempts
    if re.search(r'javascript:|data:|vbscript:', url, re.IGNORECASE):
        return ""
    return url


class WikipediaService:
    """
    Service for fetching Wikipedia information.
    
    Supports:
    - Summary/extract retrieval
    - Multi-language queries
    - Search suggestions
    - Related topics
    """
    
    # Wikipedia API endpoints by language
    API_ENDPOINTS = {
        "en": "https://en.wikipedia.org/api/rest_v1",
        "de": "https://de.wikipedia.org/api/rest_v1",
        "fr": "https://fr.wikipedia.org/api/rest_v1",
        "es": "https://es.wikipedia.org/api/rest_v1",
        "zh": "https://zh.wikipedia.org/api/rest_v1",
        "ja": "https://ja.wikipedia.org/api/rest_v1",
        "ru": "https://ru.wikipedia.org/api/rest_v1",
        "pt": "https://pt.wikipedia.org/api/rest_v1",
        "ar": "https://ar.wikipedia.org/api/rest_v1",
        "ko": "https://ko.wikipedia.org/api/rest_v1",
    }
    
    # MediaWiki API for search
    SEARCH_ENDPOINTS = {
        "en": "https://en.wikipedia.org/w/api.php",
        "de": "https://de.wikipedia.org/w/api.php",
        "fr": "https://fr.wikipedia.org/w/api.php",
        "es": "https://es.wikipedia.org/w/api.php",
        "zh": "https://zh.wikipedia.org/w/api.php",
        "ja": "https://ja.wikipedia.org/w/api.php",
        "ru": "https://ru.wikipedia.org/w/api.php",
        "pt": "https://pt.wikipedia.org/w/api.php",
        "ar": "https://ar.wikipedia.org/w/api.php",
        "ko": "https://ko.wikipedia.org/w/api.php",
    }
    
    USER_AGENT = "TrendRadar/1.0 (News aggregation tool; contact@example.com)"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.USER_AGENT,
            "Accept": "application/json"
        })
    
    def get_summary(
        self,
        title: str,
        language: str = "en"
    ) -> Dict[str, Any]:
        """
        Get Wikipedia summary/extract for a topic.
        
        Args:
            title: Topic/article title to look up
            language: Wikipedia language code (en, de, fr, etc.)
            
        Returns:
            Dict with title, extract, url (article link), thumbnail_image_url, etc.
        """
        lang = language.lower()
        if lang not in self.API_ENDPOINTS:
            lang = "en"
        
        api_url = self.API_ENDPOINTS[lang]
        encoded_title = quote(title.replace(" ", "_"), safe="")
        
        try:
            # Try REST API summary endpoint
            url = f"{api_url}/page/summary/{encoded_title}"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                # Sanitize all text content to prevent XSS
                raw_url = data.get("content_urls", {}).get("desktop", {}).get("page", "")
                raw_mobile_url = data.get("content_urls", {}).get("mobile", {}).get("page", "")
                
                return {
                    "success": True,
                    "title": sanitize_html(data.get("title", title)),
                    "extract": sanitize_html(data.get("extract", "")),
                    "extract_html": sanitize_html(data.get("extract_html", "")),  # Strip HTML for safety
                    "description": sanitize_html(data.get("description", "")),
                    "url": sanitize_url(raw_url),  # Main article URL - use this for links!
                    "mobile_url": sanitize_url(raw_mobile_url),
                    "thumbnail_image_url": data.get("thumbnail", {}).get("source", ""),  # Image only, NOT article link
                    "language": lang,
                    "type": data.get("type", "standard"),
                    "source": "wikipedia"
                }
            elif response.status_code == 404:
                # Article not found, try search
                return self._search_and_get_best(title, lang)
            else:
                logger.warning(f"Wikipedia API returned {response.status_code} for {title}")
                return {
                    "success": False,
                    "error": f"Wikipedia returned status {response.status_code}",
                    "title": title,
                    "language": lang
                }
                
        except Exception as e:
            logger.error(f"Wikipedia fetch error: {e}")
            return {
                "success": False,
                "error": str(e),
                "title": title,
                "language": lang
            }
    
    def search(
        self,
        query: str,
        language: str = "en",
        limit: int = 5
    ) -> Dict[str, Any]:
        """
        Search Wikipedia for articles matching a query.
        
        Args:
            query: Search query
            language: Wikipedia language code
            limit: Maximum number of results
            
        Returns:
            Dict with search results
        """
        lang = language.lower()
        if lang not in self.SEARCH_ENDPOINTS:
            lang = "en"
        
        api_url = self.SEARCH_ENDPOINTS[lang]
        
        try:
            params = {
                "action": "query",
                "list": "search",
                "srsearch": query,
                "srlimit": limit,
                "format": "json",
                "srprop": "snippet|titlesnippet|size|wordcount"
            }
            
            response = self.session.get(api_url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                results = []
                
                for item in data.get("query", {}).get("search", []):
                    # Sanitize snippet and title
                    snippet = sanitize_html(item.get("snippet", ""))
                    title = sanitize_html(item.get("title", ""))
                    
                    # Build and validate URL
                    wiki_url = f"https://{lang}.wikipedia.org/wiki/{quote(item.get('title', '').replace(' ', '_'))}"
                    
                    results.append({
                        "title": title,
                        "snippet": snippet,
                        "url": sanitize_url(wiki_url),
                        "word_count": item.get("wordcount", 0),
                        "size": item.get("size", 0)
                    })
                
                return {
                    "success": True,
                    "query": query,
                    "language": lang,
                    "total_hits": data.get("query", {}).get("searchinfo", {}).get("totalhits", 0),
                    "results": results,
                    "source": "wikipedia"
                }
            else:
                return {
                    "success": False,
                    "error": f"Search returned status {response.status_code}",
                    "query": query,
                    "language": lang
                }
                
        except Exception as e:
            logger.error(f"Wikipedia search error: {e}")
            return {
                "success": False,
                "error": str(e),
                "query": query,
                "language": lang
            }
    
    def _search_and_get_best(
        self,
        title: str,
        language: str
    ) -> Dict[str, Any]:
        """
        Search for a topic and return the best matching article summary.
        """
        search_result = self.search(title, language, limit=1)
        
        if search_result.get("success") and search_result.get("results"):
            best_match = search_result["results"][0]
            # Recursively get summary for best match
            return self.get_summary(best_match["title"], language)
        
        return {
            "success": False,
            "error": "No Wikipedia article found",
            "title": title,
            "language": language,
            "suggestion": "Try a different search term or language"
        }
    
    def get_context(
        self,
        topic: str,
        language: str = "en",
        include_related: bool = False
    ) -> Dict[str, Any]:
        """
        Get context information about a topic for news enhancement.
        
        This is the main method for enriching news with background info.
        
        Args:
            topic: Topic to get context for (person, company, event, etc.)
            language: Preferred language
            include_related: Whether to include related articles
            
        Returns:
            Context information including summary, links, and optionally related topics
        """
        result = self.get_summary(topic, language)
        
        if result.get("success") and include_related:
            # Get related topics via search
            search = self.search(topic, language, limit=3)
            if search.get("success"):
                related = [
                    r for r in search.get("results", [])
                    if r.get("title", "").lower() != result.get("title", "").lower()
                ]
                result["related_topics"] = related[:3]
        
        return result
    
    def get_multi_language(
        self,
        topic: str,
        languages: List[str] = None
    ) -> Dict[str, Any]:
        """
        Get Wikipedia info in multiple languages for comparison.
        
        Useful for understanding how different cultures/regions cover a topic.
        
        Args:
            topic: Topic to look up
            languages: List of language codes (default: en, de, zh)
            
        Returns:
            Dict with results per language
        """
        if languages is None:
            languages = ["en", "de", "zh"]
        
        results = {}
        for lang in languages:
            results[lang] = self.get_summary(topic, lang)
        
        return {
            "topic": topic,
            "languages": languages,
            "results": results,
            "source": "wikipedia"
        }


# Singleton instance
_wikipedia_service = None


def get_wikipedia_service() -> WikipediaService:
    """Get or create Wikipedia service singleton."""
    global _wikipedia_service
    if _wikipedia_service is None:
        _wikipedia_service = WikipediaService()
    return _wikipedia_service
