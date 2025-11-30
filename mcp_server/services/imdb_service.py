"""
IMDB/Movie Database Service

Search for movies, TV shows, and people via OMDb API and IMDB web scraping.
Free tier: 1000 requests/day with API key.
Person search uses web scraping (no API key required).
"""

import html
import logging
import os
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
    logger.warning("Cache not available for IMDB service")


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
    if not re.match(r'^https?://', url):
        return ""
    if re.search(r'javascript:|data:|vbscript:', url, re.IGNORECASE):
        return ""
    return url


class IMDBService:
    """
    Movie, TV show, and person search service.
    
    Features:
    - Search movies/TV shows by title (OMDb API)
    - Get detailed movie info (ratings, cast, plot)
    - Search for people/celebrities (IMDB web scraping)
    - Cross-reference people with Wikipedia
    - Get filmography for actors/directors
    """
    
    OMDB_API_URL = "https://www.omdbapi.com/"
    IMDB_BASE_URL = "https://www.imdb.com"
    IMDB_SEARCH_URL = "https://www.imdb.com/find"
    
    # Content types
    TYPES = ["movie", "series", "episode"]
    
    # Person categories
    PERSON_CATEGORIES = ["actor", "actress", "director", "writer", "producer", "composer"]
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize IMDB service.
        
        Args:
            api_key: OMDb API key (free tier: 1000/day)
                    Get one at: https://www.omdbapi.com/apikey.aspx
        """
        self.api_key = api_key or os.environ.get("OMDB_API_KEY")
        
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        })
        
        if CACHE_AVAILABLE:
            self.cache = get_cache("imdb", ttl=86400)  # 24 hour cache
        else:
            self.cache = None
    
    def search_person(
        self,
        name: str,
        include_wikipedia: bool = True,
        limit: int = 5
    ) -> Dict[str, Any]:
        """
        Search for a person (actor, director, etc.) on IMDB.
        
        Args:
            name: Person's name to search
            include_wikipedia: Cross-reference with Wikipedia for bio
            limit: Maximum results
            
        Returns:
            Dict with person info and filmography
        """
        if not name or not name.strip():
            return {
                "success": False,
                "error": "Name is required",
                "results": []
            }
        
        name = name.strip()[:100]
        
        # Check cache
        if self.cache:
            cache_key = self.cache.make_key(
                "person_search",
                name=name,
                wiki=include_wikipedia,
                limit=limit
            )
            cached = self.cache.get(cache_key)
            if cached is not None:
                logger.debug(f"Cache hit for person search: {name}")
                cached["from_cache"] = True
                return cached
        
        try:
            # Search IMDB for person
            people = self._search_imdb_person(name, limit)
            
            # Cross-reference with Wikipedia if requested
            if include_wikipedia and people:
                people = self._enrich_with_wikipedia(people)
            
            result = {
                "success": True,
                "query": name,
                "count": len(people),
                "results": people,
                "source": "imdb"
            }
            
            # Cache result
            if self.cache and people:
                self.cache.set(cache_key, result)
            
            return result
            
        except requests.Timeout:
            return {
                "success": False,
                "error": "Request timed out",
                "query": name,
                "results": []
            }
        except Exception as e:
            logger.error(f"Person search error: {e}")
            return {
                "success": False,
                "error": str(e),
                "query": name,
                "results": []
            }
    
    def _search_imdb_person(self, name: str, limit: int) -> List[Dict[str, Any]]:
        """Search IMDB for people via web scraping."""
        try:
            # IMDB search with name category
            params = {
                "q": name,
                "s": "nm",  # nm = names (people)
                "exact": "true"
            }
            
            response = self.session.get(
                self.IMDB_SEARCH_URL,
                params=params,
                timeout=15
            )
            
            if response.status_code != 200:
                logger.warning(f"IMDB search returned {response.status_code}")
                return []
            
            people = []
            
            # Extract person IDs from search results
            # Modern IMDB uses aria-label for names: href="/name/nm0000158/..." aria-label="Tom Hanks"
            # Try new pattern first
            person_pattern = r'href="/name/(nm\d+)/[^"]*"[^>]*aria-label="([^"]+)"'
            matches = re.findall(person_pattern, response.text)
            
            # Fallback to old pattern if no matches
            if not matches:
                person_pattern = r'href="/name/(nm\d+)[^"]*"[^>]*>([^<]+)</a>'
                matches = re.findall(person_pattern, response.text)
            
            # Get unique people
            seen = set()
            for imdb_id, raw_name in matches:
                if imdb_id not in seen:
                    seen.add(imdb_id)
                    
                    # Try to extract additional info
                    person_info = {
                        "imdb_id": imdb_id,
                        "name": sanitize_text(raw_name),
                        "url": f"https://www.imdb.com/name/{imdb_id}/",
                        "known_for": [],
                        "profession": "",
                        "photo": "",
                        "wikipedia": None
                    }
                    
                    people.append(person_info)
                    
                    if len(people) >= limit:
                        break
            
            # Try to get more details for first few results
            for person in people[:3]:
                self._enrich_person_details(person)
            
            return people
            
        except requests.Timeout:
            raise
        except Exception as e:
            logger.error(f"IMDB person search error: {e}")
            return []
    
    def _enrich_person_details(self, person: Dict[str, Any]) -> None:
        """Fetch additional details from person's IMDB page."""
        try:
            response = self.session.get(
                person["url"],
                timeout=10
            )
            
            if response.status_code != 200:
                return
            
            html_content = response.text
            
            # Extract profession/known for
            profession_match = re.search(
                r'<span[^>]*class="[^"]*ipc-inline-list__item[^"]*"[^>]*>([^<]+)</span>',
                html_content
            )
            if profession_match:
                person["profession"] = sanitize_text(profession_match.group(1))
            
            # Extract known for titles
            known_for_pattern = r'data-testid="nm_flmg_c_\d+"[^>]*>.*?<a[^>]*href="/title/(tt\d+)[^"]*"[^>]*>([^<]+)</a>'
            known_for_matches = re.findall(known_for_pattern, html_content, re.DOTALL)[:5]
            person["known_for"] = [
                {
                    "title": sanitize_text(title),
                    "imdb_id": title_id,
                    "url": f"https://www.imdb.com/title/{title_id}/"
                }
                for title_id, title in known_for_matches
            ]
            
            # Extract photo URL
            photo_match = re.search(
                r'<img[^>]*class="[^"]*ipc-image[^"]*"[^>]*src="([^"]+)"',
                html_content
            )
            if photo_match:
                photo_url = photo_match.group(1)
                if photo_url.startswith("http"):
                    person["photo"] = sanitize_url(photo_url)
            
            # Extract birth info
            birth_match = re.search(
                r'Born.*?(\w+ \d+, \d{4})',
                html_content
            )
            if birth_match:
                person["birth_date"] = sanitize_text(birth_match.group(1))
            
        except Exception as e:
            logger.debug(f"Error enriching person details: {e}")
    
    def _enrich_with_wikipedia(self, people: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Cross-reference people with Wikipedia."""
        try:
            from .wikipedia_service import get_wikipedia_service
            wiki = get_wikipedia_service()
            
            for person in people[:3]:  # Limit Wikipedia lookups
                try:
                    # Search Wikipedia for the person
                    wiki_result = wiki.search(person["name"], limit=1)
                    
                    if wiki_result.get("results"):
                        top_result = wiki_result["results"][0]
                        wiki_title = top_result.get("title", "")
                        
                        # Verify it's likely the same person
                        # Check if name appears in the Wikipedia title/description
                        name_parts = person["name"].lower().split()
                        wiki_title_lower = wiki_title.lower()
                        
                        if any(part in wiki_title_lower for part in name_parts if len(part) > 2):
                            # Get summary from Wikipedia
                            summary_result = wiki.get_summary(wiki_title)
                            
                            if summary_result.get("success"):
                                person["wikipedia"] = {
                                    "title": sanitize_text(summary_result.get("title", "")),
                                    "url": sanitize_url(summary_result.get("url", "")),
                                    "summary": sanitize_text(summary_result.get("extract", ""))[:500],
                                    "thumbnail": sanitize_url(summary_result.get("thumbnail", "")),
                                }
                                
                except Exception as e:
                    logger.debug(f"Wikipedia lookup failed for {person['name']}: {e}")
                    
        except ImportError:
            logger.warning("Wikipedia service not available")
        except Exception as e:
            logger.error(f"Wikipedia enrichment error: {e}")
        
        return people
    
    def get_person_filmography(
        self,
        imdb_id: str,
        limit: int = 20
    ) -> Dict[str, Any]:
        """
        Get filmography for a person.
        
        Args:
            imdb_id: IMDB person ID (e.g., nm0000138 for Leonardo DiCaprio)
            limit: Maximum titles to return
            
        Returns:
            Dict with person info and filmography
        """
        if not imdb_id or not re.match(r'^nm\d+$', imdb_id):
            return {
                "success": False,
                "error": "Valid IMDB person ID required (e.g., nm0000138)"
            }
        
        # Check cache
        if self.cache:
            cache_key = self.cache.make_key("filmography", imdb_id=imdb_id, limit=limit)
            cached = self.cache.get(cache_key)
            if cached is not None:
                cached["from_cache"] = True
                return cached
        
        try:
            url = f"{self.IMDB_BASE_URL}/name/{imdb_id}/"
            response = self.session.get(url, timeout=15)
            
            if response.status_code != 200:
                return {
                    "success": False,
                    "error": f"Could not fetch person page (status {response.status_code})"
                }
            
            html_content = response.text
            
            # Extract name
            name_match = re.search(
                r'<span[^>]*class="[^"]*hero__primary-text[^"]*"[^>]*>([^<]+)</span>',
                html_content
            )
            name = sanitize_text(name_match.group(1)) if name_match else imdb_id
            
            # Extract filmography
            filmography = []
            seen_titles = set()
            
            # Use simpler pattern that matches title links
            title_pattern = r'href="/title/(tt\d+)/[^"]*"[^>]*>([^<]+)</a>'
            
            # Find all titles
            for match in re.finditer(title_pattern, html_content):
                title_id = match.group(1)
                raw_title = match.group(2).strip()
                
                # Skip duplicates
                if title_id in seen_titles:
                    continue
                seen_titles.add(title_id)
                
                # Extract year from title if present (e.g., "Inception (2010)")
                year_match = re.search(r'\((\d{4})\)', raw_title)
                year = year_match.group(1) if year_match else ""
                
                # Clean title (remove year suffix)
                title = re.sub(r'\s*\(\d{4}\)\s*$', '', raw_title)
                title = sanitize_text(title)
                
                if not title:
                    continue
                
                filmography.append({
                    "title": title,
                    "imdb_id": title_id,
                    "year": year,
                    "url": f"https://www.imdb.com/title/{title_id}/"
                })
                
                if len(filmography) >= limit:
                    break
            
            result = {
                "success": True,
                "imdb_id": imdb_id,
                "name": name,
                "url": url,
                "filmography_count": len(filmography),
                "filmography": filmography,
                "source": "imdb"
            }
            
            # Cache result
            if self.cache:
                self.cache.set(cache_key, result)
            
            return result
            
        except requests.Timeout:
            return {
                "success": False,
                "error": "Request timed out"
            }
        except Exception as e:
            logger.error(f"Filmography error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def search_movies(
        self,
        query: str,
        content_type: Optional[str] = None,
        year: Optional[int] = None,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Search for movies or TV shows.
        
        Args:
            query: Search title
            content_type: Filter by type (movie, series, episode)
            year: Filter by release year
            limit: Maximum results (OMDb returns max 10 per page)
            
        Returns:
            Dict with movies/shows and metadata
        """
        if not query or not query.strip():
            return {
                "success": False,
                "error": "Query is required",
                "results": []
            }
        
        if not self.api_key:
            return {
                "success": False,
                "error": "OMDb API key required. Get free key at omdbapi.com/apikey.aspx",
                "results": [],
                "hint": "Set OMDB_API_KEY environment variable"
            }
        
        query = query.strip()[:100]
        
        # Check cache
        if self.cache:
            cache_key = self.cache.make_key(
                "search",
                query=query,
                type=content_type,
                year=year,
                limit=limit
            )
            cached = self.cache.get(cache_key)
            if cached is not None:
                logger.debug(f"Cache hit for movie search: {query}")
                cached["from_cache"] = True
                return cached
        
        try:
            params = {
                "apikey": self.api_key,
                "s": query,
            }
            
            if content_type and content_type in self.TYPES:
                params["type"] = content_type
            
            if year:
                params["y"] = str(year)
            
            response = self.session.get(
                self.OMDB_API_URL,
                params=params,
                timeout=10
            )
            
            data = response.json()
            
            if data.get("Response") == "False":
                error = data.get("Error", "Unknown error")
                return {
                    "success": False,
                    "error": error,
                    "query": query,
                    "results": []
                }
            
            # Parse results
            results = []
            for item in data.get("Search", [])[:limit]:
                results.append({
                    "imdb_id": item.get("imdbID", ""),
                    "title": sanitize_text(item.get("Title", "")),
                    "year": item.get("Year", ""),
                    "type": item.get("Type", ""),
                    "poster": item.get("Poster", "N/A"),
                    "url": f"https://www.imdb.com/title/{item.get('imdbID', '')}/"
                })
            
            result = {
                "success": True,
                "query": query,
                "count": len(results),
                "total_results": int(data.get("totalResults", 0)),
                "results": results,
                "filters": {
                    "type": content_type,
                    "year": year
                },
                "source": "omdb"
            }
            
            # Cache result
            if self.cache and results:
                self.cache.set(cache_key, result)
            
            return result
            
        except requests.Timeout:
            return {
                "success": False,
                "error": "Request timed out",
                "query": query,
                "results": []
            }
        except Exception as e:
            logger.error(f"Movie search error: {e}")
            return {
                "success": False,
                "error": str(e),
                "query": query,
                "results": []
            }
    
    def get_movie_details(
        self,
        imdb_id: Optional[str] = None,
        title: Optional[str] = None,
        year: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get detailed info for a movie or TV show.
        
        Args:
            imdb_id: IMDB ID (e.g., tt1234567)
            title: Movie title (if no IMDB ID)
            year: Year to help disambiguation
            
        Returns:
            Dict with detailed movie info
        """
        if not imdb_id and not title:
            return {
                "success": False,
                "error": "Either imdb_id or title is required"
            }
        
        if not self.api_key:
            return {
                "success": False,
                "error": "OMDb API key required",
                "hint": "Set OMDB_API_KEY environment variable"
            }
        
        # Check cache
        cache_key_id = imdb_id or f"{title}_{year}"
        if self.cache:
            cache_key = self.cache.make_key("details", id=cache_key_id)
            cached = self.cache.get(cache_key)
            if cached is not None:
                logger.debug(f"Cache hit for movie details: {cache_key_id}")
                cached["from_cache"] = True
                return cached
        
        try:
            params = {
                "apikey": self.api_key,
                "plot": "full",
            }
            
            if imdb_id:
                params["i"] = imdb_id
            else:
                params["t"] = title
                if year:
                    params["y"] = str(year)
            
            response = self.session.get(
                self.OMDB_API_URL,
                params=params,
                timeout=10
            )
            
            data = response.json()
            
            if data.get("Response") == "False":
                error = data.get("Error", "Unknown error")
                return {
                    "success": False,
                    "error": error
                }
            
            # Parse ratings
            ratings = []
            for rating in data.get("Ratings", []):
                ratings.append({
                    "source": sanitize_text(rating.get("Source", "")),
                    "value": rating.get("Value", "")
                })
            
            result = {
                "success": True,
                "imdb_id": data.get("imdbID", ""),
                "title": sanitize_text(data.get("Title", "")),
                "year": data.get("Year", ""),
                "rated": data.get("Rated", ""),
                "released": data.get("Released", ""),
                "runtime": data.get("Runtime", ""),
                "genre": data.get("Genre", ""),
                "director": sanitize_text(data.get("Director", "")),
                "writer": sanitize_text(data.get("Writer", "")),
                "actors": sanitize_text(data.get("Actors", "")),
                "plot": sanitize_text(data.get("Plot", "")),
                "language": data.get("Language", ""),
                "country": data.get("Country", ""),
                "awards": sanitize_text(data.get("Awards", "")),
                "poster": data.get("Poster", "N/A"),
                "ratings": ratings,
                "imdb_rating": data.get("imdbRating", "N/A"),
                "imdb_votes": data.get("imdbVotes", "N/A"),
                "metascore": data.get("Metascore", "N/A"),
                "type": data.get("Type", ""),
                "box_office": data.get("BoxOffice", "N/A"),
                "url": f"https://www.imdb.com/title/{data.get('imdbID', '')}/",
                "source": "omdb"
            }
            
            # Cache result
            if self.cache:
                self.cache.set(cache_key, result)
            
            return result
            
        except requests.Timeout:
            return {
                "success": False,
                "error": "Request timed out"
            }
        except Exception as e:
            logger.error(f"Movie details error: {e}")
            return {
                "success": False,
                "error": str(e)
            }


# Singleton instance
_imdb_service: Optional[IMDBService] = None


def get_imdb_service(api_key: Optional[str] = None) -> IMDBService:
    """Get singleton IMDBService instance."""
    global _imdb_service
    if _imdb_service is None:
        _imdb_service = IMDBService(api_key=api_key)
    return _imdb_service
