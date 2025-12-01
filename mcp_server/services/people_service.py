"""
People Search Service

Provides person lookup with support for German politicians via Wikipedia and Bundestag.de.
Combines multiple sources for comprehensive person information.
"""

import html
import logging
import re
from typing import Dict, List, Optional, Any
from urllib.parse import quote, urljoin

import requests

logger = logging.getLogger(__name__)


def sanitize_text(text: str) -> str:
    """Sanitize text to prevent XSS attacks."""
    if not text:
        return ""
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Escape special characters
    text = html.escape(text)
    return text.strip()


def sanitize_url(url: str) -> str:
    """Validate and sanitize URL."""
    if not url:
        return ""
    # Only allow specific domains
    allowed_domains = [
        'wikipedia.org',
        'bundestag.de',
        'abgeordnetenwatch.de',
    ]
    if not any(domain in url for domain in allowed_domains):
        return ""
    # Block script injection
    if re.search(r'javascript:|data:|vbscript:', url, re.IGNORECASE):
        return ""
    return url


class PeopleService:
    """
    Service for searching and retrieving information about people.
    
    Primary focus on German politicians with fallback sources:
    1. Wikipedia (German & English)
    2. Bundestag.de (German parliament)
    """
    
    # Wikipedia API endpoints
    WIKIPEDIA_API = {
        "de": "https://de.wikipedia.org/w/api.php",
        "en": "https://en.wikipedia.org/w/api.php",
    }
    
    WIKIPEDIA_REST = {
        "de": "https://de.wikipedia.org/api/rest_v1",
        "en": "https://en.wikipedia.org/api/rest_v1",
    }
    
    # Bundestag API
    BUNDESTAG_SEARCH_URL = "https://www.bundestag.de/ajax/filterlist/de/abgeordnete/525246-525246"
    BUNDESTAG_BASE_URL = "https://www.bundestag.de"
    
    USER_AGENT = "TrendRadar/1.0 (News aggregation tool)"
    
    def __init__(self):
        """Initialize the people search service."""
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.USER_AGENT,
            "Accept": "application/json, text/html",
        })
        
        # Try to use cache if available
        try:
            from ..utils.cache import get_cache
            self.cache = get_cache("people", ttl=3600)  # 1 hour cache
        except ImportError:
            self.cache = None
    
    def search_person(
        self,
        name: str,
        person_type: Optional[str] = None,
        language: str = "de"
    ) -> Dict[str, Any]:
        """
        Search for a person across multiple sources.
        
        Args:
            name: Person's name to search
            person_type: Type hint (e.g., "politician", "bundestag")
            language: Primary language for search ("de", "en")
            
        Returns:
            Dict with person information from available sources
        """
        if not name or not name.strip():
            return {
                "success": False,
                "error": "Name is required",
                "results": []
            }
        
        name = name.strip()[:200]  # Limit length
        
        # Check cache
        if self.cache:
            cache_key = self.cache.make_key("person", name=name, type=person_type, lang=language)
            cached = self.cache.get(cache_key)
            if cached is not None:
                cached["from_cache"] = True
                return cached
        
        results = []
        sources_checked = []
        
        # For German politicians, try Bundestag first
        if person_type in ("politician", "bundestag", "mdb") or language == "de":
            bundestag_result = self._search_bundestag(name)
            sources_checked.append("bundestag.de")
            if bundestag_result:
                results.extend(bundestag_result)
        
        # Search Wikipedia (German first, then English)
        wiki_langs = ["de", "en"] if language == "de" else ["en", "de"]
        for lang in wiki_langs:
            wiki_results = self._search_wikipedia(name, lang, person_type)
            sources_checked.append(f"wikipedia.org/{lang}")
            if wiki_results:
                # Merge with existing results or add new ones
                for wiki_person in wiki_results:
                    # Check if we already have this person
                    existing = next(
                        (r for r in results if self._same_person(r, wiki_person)),
                        None
                    )
                    if existing:
                        # Enrich existing entry
                        self._merge_person_data(existing, wiki_person)
                    else:
                        results.append(wiki_person)
        
        result = {
            "success": True,
            "query": name,
            "person_type": person_type,
            "count": len(results),
            "results": results[:10],  # Limit results
            "sources_checked": sources_checked
        }
        
        # Cache result
        if self.cache and results:
            self.cache.set(cache_key, result)
        
        return result
    
    def search_politician(
        self,
        name: str,
        party: Optional[str] = None,
        country: str = "de"
    ) -> Dict[str, Any]:
        """
        Search specifically for politicians.
        
        Args:
            name: Politician's name
            party: Optional party filter (e.g., "SPD", "CDU")
            country: Country code ("de" for Germany)
            
        Returns:
            Dict with politician information
        """
        if country == "de":
            return self.search_german_politician(name, party)
        else:
            # Fallback to general search with politician type hint
            return self.search_person(name, person_type="politician", language="en")
    
    def search_german_politician(
        self,
        name: str,
        party: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Search for German politicians via Bundestag and Wikipedia.
        
        Args:
            name: Politician's name
            party: Optional party filter
            
        Returns:
            Dict with politician information including party, role, etc.
        """
        if not name or not name.strip():
            return {
                "success": False,
                "error": "Name is required",
                "results": []
            }
        
        name = name.strip()[:200]
        
        # Check cache
        if self.cache:
            cache_key = self.cache.make_key("german_politician", name=name, party=party)
            cached = self.cache.get(cache_key)
            if cached is not None:
                cached["from_cache"] = True
                return cached
        
        results = []
        
        # Search Bundestag first (most authoritative for current MdB)
        bundestag_results = self._search_bundestag(name)
        if bundestag_results:
            # Filter by party if specified
            if party:
                party_lower = party.lower()
                bundestag_results = [
                    r for r in bundestag_results
                    if party_lower in r.get("party", "").lower()
                ]
            results.extend(bundestag_results)
        
        # Enrich with Wikipedia
        for person in results[:5]:
            wiki_data = self._get_wikipedia_summary(person["name"], "de")
            if wiki_data:
                self._merge_person_data(person, wiki_data)
        
        # If no Bundestag results, search Wikipedia directly
        if not results:
            wiki_results = self._search_wikipedia(name, "de", "politician")
            if wiki_results:
                # Filter for politicians
                for wiki_person in wiki_results:
                    if self._is_politician(wiki_person):
                        if party:
                            if party.lower() in wiki_person.get("description", "").lower():
                                results.append(wiki_person)
                        else:
                            results.append(wiki_person)
        
        result = {
            "success": True,
            "query": name,
            "party_filter": party,
            "count": len(results),
            "results": results[:10],
            "sources": ["bundestag.de", "wikipedia.org/de"]
        }
        
        # Cache
        if self.cache and results:
            self.cache.set(cache_key, result)
        
        return result
    
    def _search_bundestag(self, name: str) -> List[Dict[str, Any]]:
        """
        Search the German Bundestag website for members of parliament.
        
        Args:
            name: Name to search
            
        Returns:
            List of matching politicians
        """
        try:
            # Bundestag search URL with name filter
            params = {
                "limit": "10",
                "noFilterSet": "true",
                "view": "BTBiographyList",
            }
            
            # Try direct search via the main page
            search_url = f"https://www.bundestag.de/services/suche?suchbegriff={quote(name)}&view=json"
            
            response = self.session.get(
                search_url,
                params=params,
                timeout=15
            )
            
            politicians = []
            
            if response.status_code == 200:
                # Parse HTML response for politician entries
                html_content = response.text
                
                # Look for politician cards/entries
                # Pattern for MdB entries on bundestag.de
                name_pattern = r'<a[^>]*href="(/abgeordnete/biografien/[^"]+)"[^>]*>([^<]+)</a>'
                party_pattern = r'<span[^>]*class="[^"]*bt-person[^"]*"[^>]*>([^<]*)</span>'
                
                # Find all matching entries
                matches = re.findall(name_pattern, html_content)
                
                for url_path, found_name in matches[:10]:
                    found_name = sanitize_text(found_name)
                    if name.lower() in found_name.lower():
                        politician = {
                            "name": found_name,
                            "source": "bundestag.de",
                            "url": sanitize_url(f"{self.BUNDESTAG_BASE_URL}{url_path}"),
                            "role": "Mitglied des Bundestages (MdB)",
                            "country": "Germany",
                            "type": "politician"
                        }
                        
                        # Try to get more details
                        detail = self._get_bundestag_detail(url_path)
                        if detail:
                            politician.update(detail)
                        
                        politicians.append(politician)
            
            # Alternative: Search the Abgeordnete list
            if not politicians:
                politicians = self._search_bundestag_list(name)
            
            return politicians
            
        except requests.Timeout:
            logger.warning(f"Bundestag search timed out for: {name}")
            return []
        except Exception as e:
            logger.error(f"Bundestag search error: {e}")
            return []
    
    def _search_bundestag_list(self, name: str) -> List[Dict[str, Any]]:
        """
        Search the Bundestag member list directly.
        """
        try:
            # Try the abgeordnete listing page
            list_url = "https://www.bundestag.de/abgeordnete"
            response = self.session.get(list_url, timeout=15)
            
            if response.status_code != 200:
                return []
            
            politicians = []
            html_content = response.text
            
            # Find politician links
            pattern = r'href="(/abgeordnete/biografien/[A-Z]/[^"]+)"[^>]*>([^<]+)</a>'
            matches = re.findall(pattern, html_content)
            
            name_lower = name.lower()
            for url_path, found_name in matches:
                found_name = sanitize_text(found_name)
                if name_lower in found_name.lower():
                    politicians.append({
                        "name": found_name,
                        "source": "bundestag.de",
                        "url": sanitize_url(f"{self.BUNDESTAG_BASE_URL}{url_path}"),
                        "role": "Mitglied des Bundestages (MdB)",
                        "country": "Germany",
                        "type": "politician"
                    })
            
            return politicians[:10]
            
        except Exception as e:
            logger.debug(f"Bundestag list search error: {e}")
            return []
    
    def _get_bundestag_detail(self, url_path: str) -> Optional[Dict[str, Any]]:
        """
        Fetch detailed information from a Bundestag politician page.
        """
        try:
            url = f"{self.BUNDESTAG_BASE_URL}{url_path}"
            response = self.session.get(url, timeout=10)
            
            if response.status_code != 200:
                return None
            
            html_content = response.text
            detail = {}
            
            # Extract party
            party_match = re.search(
                r'<span[^>]*class="[^"]*bt-biografie-name[^"]*"[^>]*>[^<]*\(([^)]+)\)',
                html_content
            )
            if party_match:
                detail["party"] = sanitize_text(party_match.group(1))
            
            # Extract birth date
            birth_match = re.search(
                r'geboren am (\d{1,2}\.\s*\w+\s*\d{4})',
                html_content
            )
            if birth_match:
                detail["birth_date"] = sanitize_text(birth_match.group(1))
            
            # Extract electoral district
            district_match = re.search(
                r'Wahlkreis[^:]*:\s*([^<]+)',
                html_content
            )
            if district_match:
                detail["electoral_district"] = sanitize_text(district_match.group(1))
            
            # Extract photo
            photo_match = re.search(
                r'<img[^>]*class="[^"]*bt-bild-portrait[^"]*"[^>]*src="([^"]+)"',
                html_content
            )
            if photo_match:
                photo_url = photo_match.group(1)
                if photo_url.startswith('/'):
                    photo_url = f"{self.BUNDESTAG_BASE_URL}{photo_url}"
                detail["photo"] = sanitize_url(photo_url) if 'bundestag.de' in photo_url else ""
            
            return detail if detail else None
            
        except Exception as e:
            logger.debug(f"Error fetching Bundestag detail: {e}")
            return None
    
    def _search_wikipedia(
        self,
        name: str,
        language: str,
        person_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search Wikipedia for a person.
        
        Args:
            name: Name to search
            language: Wikipedia language code
            person_type: Type hint for filtering
            
        Returns:
            List of matching people
        """
        try:
            api_url = self.WIKIPEDIA_API.get(language, self.WIKIPEDIA_API["en"])
            
            # Use opensearch for quick results
            params = {
                "action": "query",
                "list": "search",
                "srsearch": name,
                "srlimit": "10",
                "format": "json",
                "srprop": "snippet|size|wordcount",
            }
            
            response = self.session.get(api_url, params=params, timeout=10)
            
            if response.status_code != 200:
                return []
            
            data = response.json()
            search_results = data.get("query", {}).get("search", [])
            
            people = []
            for result in search_results:
                title = result.get("title", "")
                snippet = sanitize_text(result.get("snippet", ""))
                
                # Basic person detection from snippet
                if self._looks_like_person(title, snippet):
                    person = {
                        "name": sanitize_text(title),
                        "source": f"wikipedia.org/{language}",
                        "url": f"https://{language}.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}",
                        "description": snippet[:300],
                        "type": "person"
                    }
                    
                    # Get summary for more detail
                    summary = self._get_wikipedia_summary(title, language)
                    if summary:
                        person.update(summary)
                    
                    people.append(person)
            
            return people
            
        except Exception as e:
            logger.error(f"Wikipedia search error: {e}")
            return []
    
    def _get_wikipedia_summary(self, title: str, language: str) -> Optional[Dict[str, Any]]:
        """
        Get Wikipedia summary for a person.
        """
        try:
            rest_url = self.WIKIPEDIA_REST.get(language, self.WIKIPEDIA_REST["en"])
            url = f"{rest_url}/page/summary/{quote(title.replace(' ', '_'))}"
            
            response = self.session.get(url, timeout=10)
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            
            result = {
                "wikipedia_title": sanitize_text(data.get("title", "")),
                "wikipedia_url": sanitize_url(data.get("content_urls", {}).get("desktop", {}).get("page", "")),
                "description": sanitize_text(data.get("description", "")),
                "extract": sanitize_text(data.get("extract", ""))[:500],
            }
            
            # Extract thumbnail
            if "thumbnail" in data:
                result["photo"] = sanitize_url(data["thumbnail"].get("source", ""))
            
            return result
            
        except Exception as e:
            logger.debug(f"Wikipedia summary error: {e}")
            return None
    
    def _looks_like_person(self, title: str, snippet: str) -> bool:
        """Check if a Wikipedia result looks like a person."""
        # Common patterns for people
        person_indicators = [
            r'\bborn\b', r'\bdied\b', r'\bgeboren\b', r'\bgestorben\b',
            r'\bpolitician\b', r'\bPolitiker\b', r'\bactor\b', r'\bauthor\b',
            r'\b\d{4}\s*[-–]\s*\d{4}\b',  # Birth-death years
            r'\b\d{4}\s*[-–]\s*\)',  # Birth year with dash
            r'\(\*\s*\d{4}\)',  # German birth year format
        ]
        
        combined = f"{title} {snippet}".lower()
        return any(re.search(pattern, combined, re.IGNORECASE) for pattern in person_indicators)
    
    def _is_politician(self, person: Dict[str, Any]) -> bool:
        """Check if a person result is a politician."""
        politician_keywords = [
            'politiker', 'politician', 'minister', 'chancellor', 'kanzler',
            'bundestag', 'parliament', 'abgeordnete', 'mdb', 'senator',
            'präsident', 'president', 'bürgermeister', 'mayor',
            'spd', 'cdu', 'csu', 'grüne', 'fdp', 'linke', 'afd',
        ]
        
        text = f"{person.get('description', '')} {person.get('extract', '')}".lower()
        return any(kw in text for kw in politician_keywords)
    
    def _same_person(self, person1: Dict[str, Any], person2: Dict[str, Any]) -> bool:
        """Check if two results refer to the same person."""
        name1 = person1.get("name", "").lower()
        name2 = person2.get("name", "").lower()
        
        # Exact match
        if name1 == name2:
            return True
        
        # One name contains the other
        if name1 in name2 or name2 in name1:
            return True
        
        return False
    
    def _merge_person_data(self, target: Dict[str, Any], source: Dict[str, Any]) -> None:
        """Merge person data from source into target, preserving existing values."""
        for key, value in source.items():
            if key not in target or not target[key]:
                target[key] = value
            elif key == "sources":
                # Combine sources
                if isinstance(target[key], list):
                    target[key].extend(source.get(key, []))
                else:
                    target[key] = [target[key], source.get(key)]


# Singleton instance
_people_service: Optional[PeopleService] = None


def get_people_service() -> PeopleService:
    """Get or create the singleton PeopleService instance."""
    global _people_service
    if _people_service is None:
        _people_service = PeopleService()
    return _people_service
