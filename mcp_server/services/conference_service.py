"""
Tech Conference Search Service

Searches for tech conferences using the confs.tech API.
Free, no API key required.
"""

import html
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

# Import cache
try:
    from ..utils.cache import get_cache
    CACHE_AVAILABLE = True
except ImportError:
    CACHE_AVAILABLE = False
    logger.warning("Cache not available for Conference service")


def sanitize_text(text: str) -> str:
    """Sanitize text to prevent XSS attacks."""
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    text = html.escape(text)
    return text


class ConferenceService:
    """
    Tech conference search service using confs.tech.
    
    Features:
    - Search conferences by topic/technology
    - Filter by location, date range
    - Get conference details (dates, location, CFP deadlines)
    """
    
    # confs.tech GitHub raw data URLs
    BASE_URL = "https://raw.githubusercontent.com/tech-conferences/conference-data/main/conferences"
    
    # Supported topics/categories
    TOPICS = [
        "android", "clojure", "cpp", "css", "data", "devops", "dotnet",
        "elixir", "general", "golang", "graphql", "ios", "java",
        "javascript", "kotlin", "kubernetes", "leadership", "ml", "networking",
        "php", "product", "python", "ruby", "rust", "scala", "security",
        "tech-comm", "typescript", "ux"
    ]
    
    def __init__(self):
        """Initialize Conference service."""
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "TrendRadar/1.0 Conference Search",
            "Accept": "application/json",
        })
        
        if CACHE_AVAILABLE:
            self.cache = get_cache("conferences", ttl=3600)  # 1 hour cache
        else:
            self.cache = None
    
    def search_conferences(
        self,
        topic: Optional[str] = None,
        year: Optional[int] = None,
        country: Optional[str] = None,
        city: Optional[str] = None,
        limit: int = 20,
        include_past: bool = False
    ) -> Dict[str, Any]:
        """
        Search for tech conferences.
        
        Args:
            topic: Technology/topic (e.g., python, javascript, ml, devops)
            year: Conference year (default: current year)
            country: Filter by country
            city: Filter by city
            limit: Maximum results
            include_past: Include past conferences
            
        Returns:
            Dict with conferences and metadata
        """
        if year is None:
            year = datetime.now().year
        
        # Normalize topic
        if topic:
            topic = topic.lower().strip()
            # Map common aliases
            topic_aliases = {
                "machine learning": "ml",
                "ai": "ml",
                "artificial intelligence": "ml",
                "k8s": "kubernetes",
                "js": "javascript",
                "ts": "typescript",
                "py": "python",
                "go": "golang",
                "c++": "cpp",
                ".net": "dotnet",
                "react": "javascript",
                "node": "javascript",
                "vue": "javascript",
                "angular": "javascript",
            }
            topic = topic_aliases.get(topic, topic)
        
        # Check cache
        if self.cache:
            cache_key = self.cache.make_key(
                "search",
                topic=topic,
                year=year,
                country=country,
                city=city,
                limit=limit
            )
            cached = self.cache.get(cache_key)
            if cached is not None:
                logger.debug(f"Cache hit for conference search")
                cached["from_cache"] = True
                return cached
        
        try:
            conferences = []
            
            # If topic specified, search that topic
            if topic and topic in self.TOPICS:
                topics_to_search = [topic]
            elif topic:
                # Search general + try to match
                topics_to_search = ["general"]
                for t in self.TOPICS:
                    if topic in t or t in topic:
                        topics_to_search.append(t)
            else:
                # Search popular topics
                topics_to_search = ["general", "javascript", "python", "devops", "ml"]
            
            for t in topics_to_search[:3]:  # Limit API calls
                try:
                    confs = self._fetch_conferences(t, year)
                    conferences.extend(confs)
                except Exception as e:
                    logger.debug(f"Error fetching {t} conferences: {e}")
            
            # Apply filters
            filtered = []
            today = datetime.now().date()
            
            for conf in conferences:
                # Date filter (exclude past unless requested)
                if not include_past:
                    try:
                        end_date = conf.get("endDate") or conf.get("startDate")
                        if end_date:
                            conf_date = datetime.strptime(end_date, "%Y-%m-%d").date()
                            if conf_date < today:
                                continue
                    except (ValueError, TypeError):
                        pass
                
                # Country filter
                if country:
                    conf_country = conf.get("country", "").lower()
                    if country.lower() not in conf_country:
                        continue
                
                # City filter
                if city:
                    conf_city = conf.get("city", "").lower()
                    if city.lower() not in conf_city:
                        continue
                
                filtered.append(conf)
            
            # Sort by start date
            filtered.sort(key=lambda x: x.get("startDate", "9999-99-99"))
            
            # Limit results
            filtered = filtered[:limit]
            
            result = {
                "success": True,
                "count": len(filtered),
                "conferences": filtered,
                "filters": {
                    "topic": topic,
                    "year": year,
                    "country": country,
                    "city": city
                },
                "available_topics": self.TOPICS,
                "source": "confs.tech"
            }
            
            # Cache result
            if self.cache and filtered:
                self.cache.set(cache_key, result)
            
            return result
            
        except Exception as e:
            logger.error(f"Conference search error: {e}")
            return {
                "success": False,
                "error": str(e),
                "conferences": []
            }
    
    def _fetch_conferences(self, topic: str, year: int) -> List[Dict[str, Any]]:
        """Fetch conferences for a specific topic and year."""
        url = f"{self.BASE_URL}/{year}/{topic}.json"
        
        response = self.session.get(url, timeout=10)
        
        if response.status_code == 404:
            return []
        
        response.raise_for_status()
        data = response.json()
        
        # Normalize conference data
        conferences = []
        for conf in data:
            conferences.append({
                "name": sanitize_text(conf.get("name", "")),
                "url": conf.get("url", ""),
                "startDate": conf.get("startDate", ""),
                "endDate": conf.get("endDate", ""),
                "city": sanitize_text(conf.get("city", "")),
                "country": sanitize_text(conf.get("country", "")),
                "cfpUrl": conf.get("cfpUrl", ""),
                "cfpEndDate": conf.get("cfpEndDate", ""),
                "twitter": conf.get("twitter", ""),
                "topic": topic,
                "online": conf.get("online", False),
            })
        
        return conferences


# Singleton instance
_conference_service: Optional[ConferenceService] = None


def get_conference_service() -> ConferenceService:
    """Get singleton ConferenceService instance."""
    global _conference_service
    if _conference_service is None:
        _conference_service = ConferenceService()
    return _conference_service
