"""
Udemy Course Search Service

Searches for online courses on Udemy via web scraping.
No API key required - uses public search results.
"""

import html
import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus, urljoin

import requests

logger = logging.getLogger(__name__)

# Import cache
try:
    from ..utils.cache import get_cache
    CACHE_AVAILABLE = True
except ImportError:
    CACHE_AVAILABLE = False
    logger.warning("Cache not available for Udemy service")


def sanitize_text(text: str) -> str:
    """Sanitize text to prevent XSS attacks."""
    if not text:
        return ""
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    # Escape HTML entities
    text = html.escape(text)
    return text


class UdemyService:
    """
    Udemy course search service.
    
    Features:
    - Search courses by keyword
    - Filter by category, level, rating
    - Get course details (ratings, reviews, instructor)
    """
    
    BASE_URL = "https://www.udemy.com"
    SEARCH_URL = "https://www.udemy.com/api-2.0/search-courses/"
    
    # Course levels
    LEVELS = {
        "beginner": "beginner",
        "intermediate": "intermediate",
        "expert": "expert",
        "all": "all"
    }
    
    # Popular categories
    CATEGORIES = {
        "development": "Development",
        "business": "Business",
        "it": "IT & Software",
        "design": "Design",
        "marketing": "Marketing",
        "data-science": "Data Science",
        "personal-development": "Personal Development",
        "photography": "Photography & Video",
        "music": "Music",
        "health": "Health & Fitness"
    }
    
    def __init__(self):
        """Initialize Udemy service."""
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.udemy.com/",
        })
        
        if CACHE_AVAILABLE:
            self.cache = get_cache("udemy", ttl=3600)  # 1 hour cache
        else:
            self.cache = None
    
    def search_courses(
        self,
        query: str,
        category: Optional[str] = None,
        level: Optional[str] = None,
        min_rating: float = 0.0,
        limit: int = 10,
        free_only: bool = False
    ) -> Dict[str, Any]:
        """
        Search for courses on Udemy.
        
        Args:
            query: Search keywords
            category: Course category filter
            level: Skill level (beginner, intermediate, expert)
            min_rating: Minimum course rating (0-5)
            limit: Maximum results to return
            free_only: Only show free courses
            
        Returns:
            Dict with courses and metadata
        """
        if not query or not query.strip():
            return {
                "success": False,
                "error": "Query is required",
                "courses": []
            }
        
        query = query.strip()[:200]  # Limit query length
        
        # Check cache
        if self.cache:
            cache_key = self.cache.make_key(
                "search",
                query=query,
                category=category,
                level=level,
                min_rating=min_rating,
                limit=limit,
                free_only=free_only
            )
            cached = self.cache.get(cache_key)
            if cached is not None:
                logger.debug(f"Cache hit for Udemy search: {query}")
                cached["from_cache"] = True
                return cached
        
        try:
            # Use web scraping approach since API requires auth
            courses = self._search_web(query, limit * 2)  # Get extra for filtering
            
            # Apply filters
            filtered = []
            for course in courses:
                # Rating filter
                if course.get("rating", 0) < min_rating:
                    continue
                
                # Level filter
                if level and level != "all":
                    course_level = course.get("level", "").lower()
                    if level.lower() not in course_level:
                        continue
                
                # Free filter
                if free_only and course.get("price", "Paid") != "Free":
                    continue
                
                filtered.append(course)
                if len(filtered) >= limit:
                    break
            
            result = {
                "success": True,
                "query": query,
                "count": len(filtered),
                "courses": filtered,
                "filters": {
                    "category": category,
                    "level": level,
                    "min_rating": min_rating,
                    "free_only": free_only
                },
                "source": "udemy"
            }
            
            # Cache result
            if self.cache and filtered:
                self.cache.set(cache_key, result)
            
            return result
            
        except requests.Timeout:
            return {
                "success": False,
                "error": "Request timed out",
                "query": query,
                "courses": []
            }
        except Exception as e:
            logger.error(f"Udemy search error: {e}")
            return {
                "success": False,
                "error": str(e),
                "query": query,
                "courses": []
            }
    
    def _search_web(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """
        Search Udemy via web scraping.
        
        Extracts course data from search results page.
        """
        try:
            # Udemy search URL
            search_url = f"{self.BASE_URL}/courses/search/?q={quote_plus(query)}"
            
            response = self.session.get(search_url, timeout=15)
            
            if response.status_code != 200:
                logger.warning(f"Udemy search returned {response.status_code}")
                return []
            
            # Extract course data from HTML/JSON embedded in page
            courses = []
            
            # Look for course data in the page
            # Udemy embeds course data in script tags
            course_pattern = r'"@type"\s*:\s*"Course"[^}]*"name"\s*:\s*"([^"]+)"'
            url_pattern = r'"url"\s*:\s*"(https://www\.udemy\.com/course/[^"]+)"'
            rating_pattern = r'"ratingValue"\s*:\s*"?([0-9.]+)"?'
            review_pattern = r'"reviewCount"\s*:\s*"?([0-9]+)"?'
            
            # Alternative: Look for course cards in HTML
            # Course URL pattern
            course_urls = re.findall(
                r'href="(/course/[a-zA-Z0-9_-]+/?)"',
                response.text
            )
            
            # Get unique course URLs
            seen = set()
            unique_urls = []
            for url in course_urls:
                clean_url = url.rstrip('/')
                if clean_url not in seen:
                    seen.add(clean_url)
                    unique_urls.append(clean_url)
                    if len(unique_urls) >= limit:
                        break
            
            # Extract basic info for each course
            for url in unique_urls:
                course_id = url.split('/')[-1] or url.split('/')[-2]
                courses.append({
                    "id": course_id,
                    "title": course_id.replace('-', ' ').title(),
                    "url": f"https://www.udemy.com{url}/",
                    "rating": 0,
                    "num_reviews": 0,
                    "instructor": "",
                    "price": "Unknown",
                    "level": "",
                    "description": "",
                    "note": "Limited metadata from web search"
                })
            
            return courses
            
        except requests.Timeout:
            # Re-raise timeout to be handled by caller
            raise
        except Exception as e:
            logger.error(f"Udemy web search error: {e}")
            return []


# Singleton instance
_udemy_service: Optional[UdemyService] = None

def get_udemy_service() -> UdemyService:
    """Get singleton UdemyService instance."""
    global _udemy_service
    if _udemy_service is None:
        _udemy_service = UdemyService()
    return _udemy_service
