"""
North Data Service for Company Lookups

Provides search and lookup capabilities for European companies via the North Data API.
Covers 22 European countries with company data, financials, and ownership information.

Security: All content is sanitized to prevent XSS attacks.

Data Sources:
1. API (preferred): Requires NORTHDATA_API_KEY - full data access
2. Web scraping (fallback): When no API key - basic data via website search

API Documentation: https://northdata.github.io/doc/api/
"""

import hashlib
import html
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote, urlencode, urlparse, unquote

import requests

# Try cloudscraper for anti-bot bypass
try:
    import cloudscraper
    CLOUDSCRAPER_AVAILABLE = True
except ImportError:
    CLOUDSCRAPER_AVAILABLE = False

logger = logging.getLogger(__name__)

# Import cache
try:
    from ..utils.cache import get_cache
    CACHE_AVAILABLE = True
except ImportError:
    CACHE_AVAILABLE = False
    logger.warning("Cache not available, North Data requests will not be cached")


# =============================================================================
# Constants
# =============================================================================

NORTHDATA_BASE_URL = "https://www.northdata.de/_api"
NORTHDATA_WEB_URL = "https://www.northdata.de"
CACHE_TTL_SEARCH = 3600  # 1 hour for search results
CACHE_TTL_COMPANY = 86400  # 24 hours for company details
REQUEST_TIMEOUT = 30
MAX_RETRIES = 2
RETRY_DELAY = 1.0

# European country codes supported by North Data
SUPPORTED_COUNTRIES = [
    "DE",  # Germany
    "AT",  # Austria
    "CH",  # Switzerland
    "GB",  # United Kingdom
    "FR",  # France
    "NL",  # Netherlands
    "BE",  # Belgium
    "PL",  # Poland
    "CZ",  # Czech Republic
    "ES",  # Spain
    "PT",  # Portugal
    "IT",  # Italy (limited)
    "IE",  # Ireland
    "DK",  # Denmark
    "SE",  # Sweden
    "NO",  # Norway
    "FI",  # Finland
    "LU",  # Luxembourg
    "LI",  # Liechtenstein
    "MT",  # Malta
    "CY",  # Cyprus
    "GR",  # Greece
]


# =============================================================================
# Security: Sanitization functions
# =============================================================================

def sanitize_html(text: Optional[str]) -> str:
    """
    Sanitize HTML content to prevent XSS attacks.
    """
    if not text:
        return ""
    
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', str(text))
    
    # Escape HTML entities
    text = html.escape(text, quote=True)
    
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text


def sanitize_url(url: Optional[str]) -> str:
    """
    Sanitize and validate URLs for North Data.
    """
    if not url:
        return ""
    
    url = str(url).strip()
    
    # Block dangerous schemes
    dangerous_schemes = ['javascript:', 'data:', 'vbscript:', 'file:']
    url_lower = url.lower()
    for scheme in dangerous_schemes:
        if url_lower.startswith(scheme):
            return ""
    
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            return ""
        
        # Allow North Data URLs and generic company websites
        return url
    except Exception:
        return ""


def sanitize_money(value: Any) -> Optional[float]:
    """Safely convert money values to float."""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


# =============================================================================
# Web Scraping Helpers
# =============================================================================

def _parse_search_results_html(html_content: str) -> List[Dict[str, Any]]:
    """
    Parse company search results from North Data website HTML.
    
    Returns list of companies with basic info extracted from search results.
    """
    companies = []
    seen_urls = set()
    
    # Find company links - pattern: href="/CompanyName,Location/RegisterInfo"
    # The comma and slashes may be URL-encoded
    company_link_pattern = re.compile(
        r'href="(/[^"]+%2C[^"]+/[^"]+)"',  # URL-encoded comma
        re.IGNORECASE
    )
    
    # Also match non-encoded commas
    company_link_pattern2 = re.compile(
        r'href="(/[^"]+,[^"]+/[^"]+)"',  # Plain comma
        re.IGNORECASE
    )
    
    for pattern in [company_link_pattern, company_link_pattern2]:
        for match in pattern.finditer(html_content):
            url_path = match.group(1)
            
            # Skip pagination, login, and external links
            if '?' in url_path or '_login' in url_path or 'offset' in url_path.lower():
                continue
            
            # Normalize URL for deduplication
            normalized = url_path.replace('%20', ' ').lower()
            if normalized in seen_urls:
                continue
            seen_urls.add(normalized)
            
            try:
                # Parse URL: /CompanyName,Location/RegisterInfo
                decoded = unquote(url_path)
                parts = decoded.strip('/').split('/')
                
                if len(parts) >= 1:
                    name_location = parts[0]
                    register_info = parts[1] if len(parts) > 1 else ""
                    
                    # Split name and location (last comma)
                    if ',' in name_location:
                        name_parts = name_location.rsplit(',', 1)
                        name = name_parts[0].strip()
                        location = name_parts[1].strip() if len(name_parts) > 1 else ""
                    else:
                        name = name_location.strip()
                        location = ""
                    
                    if name and len(name) > 2:
                        companies.append({
                            "id": "",
                            "name": sanitize_html(name),
                            "legal_form": _extract_legal_form(name),
                            "address": {
                                "street": "",
                                "postal_code": "",
                                "city": sanitize_html(location),
                                "country": _guess_country_from_location(location) or _guess_country_from_register(register_info)
                            },
                            "register": {
                                "id": sanitize_html(register_info),
                                "city": "",
                                "country": ""
                            },
                            "status": "unknown",
                            "northdata_url": f"{NORTHDATA_WEB_URL}{url_path}"
                        })
            except Exception as e:
                logger.debug(f"Error parsing company link {url_path}: {e}")
                continue
    
    # Deduplicate by name+location combination
    unique_companies = {}
    for company in companies:
        key = f"{company['name'].lower()}|{company['address']['city'].lower()}"
        if key not in unique_companies:
            unique_companies[key] = company
    
    return list(unique_companies.values())[:20]  # Limit results


def _extract_legal_form(name: str) -> str:
    """Extract legal form from company name."""
    legal_forms = [
        'GmbH & Co. KG', 'GmbH & Co. OHG', 'GmbH & Co. KGaA',
        'AG & Co. KG', 'GmbH', 'AG', 'KGaA', 'KG', 'OHG', 'GbR',
        'e.V.', 'e.G.', 'SE', 'UG', 'Ltd.', 'Inc.', 'S.A.', 'S.L.',
        'B.V.', 'N.V.', 'A/S', 'AS', 'ApS', 'AB'
    ]
    for form in legal_forms:
        if name.endswith(form) or f' {form}' in name:
            return form
    return ""


def _guess_country_from_register(register_info: str) -> str:
    """Guess country from register info."""
    if not register_info:
        return ""
    
    register_lower = register_info.lower()
    
    # German registers
    if 'amtsgericht' in register_lower or 'hrb' in register_lower or 'hra' in register_lower:
        return "DE"
    # Norwegian
    if register_lower.startswith('br '):
        return "NO"
    # Danish
    if register_lower.startswith('cvr'):
        return "DK"
    # Austrian
    if register_lower.endswith('m') and register_lower[:-1].isdigit():
        return "AT"
    # Maltese
    if register_lower.startswith('mt '):
        return "MT"
    
    return ""


def _parse_company_details_html(html_content: str, url: str) -> Dict[str, Any]:
    """
    Parse company details from a North Data company page.
    
    Extracts:
    - Company name and legal form
    - Address
    - Register information
    - Business purpose (Gegenstand)
    - Executives (Personen)
    """
    result = {
        "id": "",
        "name": "",
        "legal_form": "",
        "address": {
            "street": "",
            "postal_code": "",
            "city": "",
            "country": ""
        },
        "register": {
            "id": "",
            "city": "",
            "country": ""
        },
        "status": "unknown",
        "northdata_url": sanitize_url(url),
        "subject": "",
        "related_persons": [],
        "source": "web_scraping"
    }
    
    # Parse company name from URL (most reliable source)
    url_path = urlparse(url).path
    decoded_path = unquote(url_path).strip('/')
    if '/' in decoded_path:
        name_location_part = decoded_path.split('/')[0]
        register_part = decoded_path.split('/')[1] if len(decoded_path.split('/')) > 1 else ""
        
        if ',' in name_location_part:
            parts = name_location_part.rsplit(',', 1)
            result["name"] = sanitize_html(parts[0].strip())
            result["address"]["city"] = sanitize_html(parts[1].strip())
        else:
            result["name"] = sanitize_html(name_location_part)
        
        if register_part:
            result["register"]["id"] = sanitize_html(register_part)
            result["address"]["country"] = _guess_country_from_register(register_part)
    
    # Also try title tag as fallback for name
    if not result["name"]:
        title_match = re.search(r'<title>([^<|–]+)', html_content, re.IGNORECASE)
        if title_match:
            result["name"] = sanitize_html(title_match.group(1).strip())
    
    # Extract legal form
    result["legal_form"] = _extract_legal_form(result["name"])
    
    # Try to find address in structured content (look for common German address patterns)
    # Pattern: Street + Number, D-12345 City
    address_match = re.search(
        r'([A-Za-zäöüßÄÖÜ\-\.\s]+(?:straße|str\.|weg|platz|allee|ring|damm)\s*\d+[a-zA-Z]?)\s*[,\s]+([A-Z]?-?\d{4,5})\s+([A-Za-zäöüßÄÖÜ\-\s]+)',
        html_content,
        re.IGNORECASE
    )
    if address_match:
        result["address"]["street"] = sanitize_html(address_match.group(1).strip())
        result["address"]["postal_code"] = address_match.group(2).strip()
        city_text = address_match.group(3).strip()
        # Clean up city text (stop at first special char)
        city_clean = re.split(r'[<\n\t]', city_text)[0].strip()
        if city_clean:
            result["address"]["city"] = sanitize_html(city_clean)
    
    # Look for GEGENSTAND (business purpose)
    # It's often in a specific section
    subject_patterns = [
        r'(?:GEGENSTAND|Gegenstand der Gesellschaft)[:\s]*</h[23]>\s*<p[^>]*>([^<]+)',
        r'Gegenstand[:\s]+"([^"]{50,})"',
        r'Gegenstand des Unternehmens[:\s]+([^<]{50,}?(?:\.|</p>))',
    ]
    for pattern in subject_patterns:
        match = re.search(pattern, html_content, re.IGNORECASE | re.DOTALL)
        if match:
            subject = match.group(1)
            # Clean up
            subject = re.sub(r'<[^>]+>', ' ', subject)
            subject = re.sub(r'\s+', ' ', subject).strip()
            if len(subject) > 20:
                result["subject"] = sanitize_html(subject[:1500])
                break
    
    # Parse executives/directors from the PERSONEN section
    # Look for patterns like "DD.MM.YYYY Role FirstName LastName"
    person_patterns = [
        # Pattern: date + role + name
        r'(\d{2}\.\d{2}\.\d{4})\s*(Vorstand(?:svorsitzender)?|Geschäftsführer(?:in)?|Prokurist(?:in)?|Aufsichtsrat(?:svorsitzender)?|Managing Director|Director|CEO|CFO)\s+([A-Za-zäöüßÄÖÜ\.\-\s]{3,40}?)(?=[<\d]|$)',
        # Pattern: role + name (no date)
        r'(?:Vorstand|Geschäftsführer)(?:svorsitzender)?:\s*([A-Za-zäöüßÄÖÜ\.\-\s]{5,40}?)(?=[<,]|$)',
    ]
    
    seen_persons = set()
    for pattern in person_patterns:
        for match in re.finditer(pattern, html_content, re.IGNORECASE):
            if len(match.groups()) >= 3:
                date = match.group(1)
                role = match.group(2).strip()
                name = match.group(3).strip()
            else:
                date = ""
                role = "Vorstand"
                name = match.group(1).strip()
            
            # Clean up name
            name = re.sub(r'<[^>]*>', '', name).strip()
            name = re.sub(r'\s+', ' ', name)
            
            # Skip invalid names
            if not name or len(name) < 3 or len(name) > 50:
                continue
            if any(x in name.lower() for x in ['gmbh', 'gesellschaft', 'unternehmen', 'firma']):
                continue
            
            # Deduplicate
            name_key = name.lower()
            if name_key in seen_persons:
                continue
            seen_persons.add(name_key)
            
            # Split name into first and last
            name_parts = name.split()
            if len(name_parts) >= 2:
                first_name = " ".join(name_parts[:-1])
                last_name = name_parts[-1]
            else:
                first_name = ""
                last_name = name
            
            result["related_persons"].append({
                "first_name": sanitize_html(first_name),
                "last_name": sanitize_html(last_name),
                "roles": [{
                    "type": role.lower().replace('ä', 'ae').replace('ö', 'oe').replace('ü', 'ue'),
                    "name": sanitize_html(role),
                    "date": date
                }]
            })
    
    # Limit persons
    result["related_persons"] = result["related_persons"][:20]
    
    # Determine status from page content
    status_indicators = {
        "terminated": ['gelöscht', 'aufgelöst', 'liquidation', 'abwicklung', 'erloschen'],
        "active": ['aktiv', 'eingetragen', 'bestehend']
    }
    
    content_lower = html_content.lower()
    for status, keywords in status_indicators.items():
        if any(kw in content_lower for kw in keywords):
            result["status"] = status
            break
    
    return result


def _guess_country_from_location(location: str) -> str:
    """Guess country code from location string."""
    location_lower = location.lower()
    
    country_keywords = {
        "DE": ["deutschland", "germany", "berlin", "münchen", "hamburg", "frankfurt", "köln", "düsseldorf"],
        "AT": ["österreich", "austria", "wien", "vienna", "graz", "salzburg"],
        "CH": ["schweiz", "switzerland", "zürich", "zurich", "genf", "geneva", "bern"],
        "GB": ["uk", "united kingdom", "england", "london", "manchester", "birmingham"],
        "FR": ["france", "frankreich", "paris", "lyon", "marseille"],
        "NL": ["niederlande", "netherlands", "amsterdam", "rotterdam"],
        "BE": ["belgien", "belgium", "brüssel", "brussels"],
        "PL": ["polen", "poland", "warschau", "warsaw"],
        "NO": ["norwegen", "norway", "oslo"],
    }
    
    for country_code, keywords in country_keywords.items():
        for keyword in keywords:
            if keyword in location_lower:
                return country_code
    
    return ""


# =============================================================================
# North Data Service Class
# =============================================================================

class NorthDataService:
    """
    Service for interacting with the North Data API.
    
    Provides:
    - Company search (universal and power search)
    - Company details lookup
    - Person search
    - Financial data
    
    Data Sources (in priority order):
    1. API: Full data access with API key
    2. Web Scraping: Basic data when no API key (free fallback)
    
    API Key Priority:
    1. Constructor argument
    2. Config file: api_keys.northdata in config.yaml
    3. Environment variable: NORTHDATA_API_KEY
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize North Data service.
        
        Args:
            api_key: North Data API key. If not provided, reads from config or env var.
        """
        self.api_key = api_key or self._load_api_key()
        
        # API session (regular requests)
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "TrendRadar/1.0 (https://github.com/qvest-ssels/TrendRadar)"
        })
        
        # Scraping session (cloudscraper for anti-bot bypass)
        if CLOUDSCRAPER_AVAILABLE:
            self.scrape_session = cloudscraper.create_scraper(
                browser={
                    'browser': 'chrome',
                    'platform': 'darwin',
                    'desktop': True
                }
            )
        else:
            self.scrape_session = requests.Session()
            self.scrape_session.headers.update({
                "Accept": "text/html,application/xhtml+xml",
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept-Language": "de-DE,de;q=0.9,en;q=0.8"
            })
        
        if not self.api_key:
            logger.info("NORTHDATA_API_KEY not set - using web scraping fallback")
    
    def _load_api_key(self) -> Optional[str]:
        """Load API key from config file or environment variable."""
        # Try config file first
        try:
            from pathlib import Path
            import yaml
            
            config_paths = [
                Path(__file__).parent.parent.parent / "config" / "config.yaml",
                Path("config/config.yaml"),
            ]
            
            for config_path in config_paths:
                if config_path.exists():
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config = yaml.safe_load(f)
                        api_keys = config.get('api_keys', {})
                        if api_keys.get('northdata'):
                            logger.debug("Loaded NORTHDATA API key from config.yaml")
                            return api_keys['northdata']
                    break
        except Exception as e:
            logger.debug(f"Could not load config: {e}")
        
        # Fall back to environment variable
        return os.environ.get("NORTHDATA_API_KEY")
    
    def _get_cache_key(self, prefix: str, **kwargs) -> str:
        """Generate a cache key from prefix and parameters."""
        key_data = f"{prefix}:{sorted(kwargs.items())}"
        return f"northdata:{hashlib.md5(key_data.encode()).hexdigest()}"
    
    def _make_request(
        self,
        endpoint: str,
        params: Dict[str, Any],
        cache_ttl: int = CACHE_TTL_SEARCH
    ) -> Dict[str, Any]:
        """
        Make an authenticated request to the North Data API.
        
        Args:
            endpoint: API endpoint path
            params: Query parameters
            cache_ttl: Cache TTL in seconds
            
        Returns:
            API response as dictionary
        """
        if not self.api_key:
            return {
                "success": False,
                "error": {
                    "code": "NO_API_KEY",
                    "message": "NORTHDATA_API_KEY environment variable not set. Get an API key at https://www.northdata.de/_data"
                }
            }
        
        # Add API key to params
        params["api_key"] = self.api_key
        
        # Check cache
        cache_key = self._get_cache_key(endpoint, **{k: v for k, v in params.items() if k != "api_key"})
        
        if CACHE_AVAILABLE:
            cache = get_cache()
            cached = cache.get(cache_key)
            if cached:
                logger.debug(f"Cache hit for {endpoint}")
                return cached
        
        url = f"{NORTHDATA_BASE_URL}{endpoint}"
        
        for attempt in range(MAX_RETRIES):
            try:
                response = self.session.get(
                    url,
                    params=params,
                    timeout=REQUEST_TIMEOUT
                )
                
                if response.status_code == 200:
                    result = response.json()
                    
                    # Cache successful response
                    if CACHE_AVAILABLE:
                        cache.set(cache_key, result, ttl=cache_ttl)
                    
                    return result
                
                elif response.status_code == 401:
                    return {
                        "success": False,
                        "error": {
                            "code": "UNAUTHORIZED",
                            "message": "Invalid North Data API key"
                        }
                    }
                
                elif response.status_code == 403:
                    return {
                        "success": False,
                        "error": {
                            "code": "FORBIDDEN",
                            "message": "API key does not have access to this feature. Check your subscription level."
                        }
                    }
                
                elif response.status_code == 404:
                    return {
                        "success": False,
                        "error": {
                            "code": "NOT_FOUND",
                            "message": "Company or person not found"
                        }
                    }
                
                elif response.status_code == 429:
                    wait_time = RETRY_DELAY * (attempt + 1)
                    logger.warning(f"Rate limited, waiting {wait_time}s")
                    time.sleep(wait_time)
                    continue
                
                else:
                    return {
                        "success": False,
                        "error": {
                            "code": f"HTTP_{response.status_code}",
                            "message": f"API request failed with status {response.status_code}"
                        }
                    }
                    
            except requests.exceptions.Timeout:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY)
                    continue
                return {
                    "success": False,
                    "error": {
                        "code": "TIMEOUT",
                        "message": "Request timed out"
                    }
                }
            except requests.exceptions.RequestException as e:
                logger.error(f"Request error: {e}")
                return {
                    "success": False,
                    "error": {
                        "code": "REQUEST_ERROR",
                        "message": str(e)
                    }
                }
        
        return {
            "success": False,
            "error": {
                "code": "MAX_RETRIES",
                "message": "Maximum retry attempts exceeded"
            }
        }
    
    # =========================================================================
    # Web Scraping Methods (fallback when no API key)
    # =========================================================================
    
    def _scrape_search(
        self,
        query: str,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Search for companies by scraping the North Data website.
        
        Args:
            query: Search query
            limit: Maximum number of results
            
        Returns:
            Dict with search results
        """
        cache_key = self._get_cache_key("scrape_search", query=query, limit=limit)
        
        if CACHE_AVAILABLE:
            cache = get_cache("northdata_scrape", ttl=CACHE_TTL_SEARCH)
            cached = cache.get(cache_key)
            if cached:
                logger.debug(f"Cache hit for scrape search: {query}")
                return cached
        
        # URL encode the query
        search_url = f"{NORTHDATA_WEB_URL}/{quote(query, safe='')}"
        
        for attempt in range(MAX_RETRIES):
            try:
                response = self.scrape_session.get(
                    search_url,
                    timeout=REQUEST_TIMEOUT,
                    allow_redirects=True
                )
                
                if response.status_code == 200:
                    companies = _parse_search_results_html(response.text)
                    
                    result = {
                        "success": True,
                        "companies": companies[:limit],
                        "total": len(companies),
                        "query": query,
                        "source": "web_scraping",
                        "note": "Limited data - for full access, configure an API key"
                    }
                    
                    if CACHE_AVAILABLE:
                        cache.set(cache_key, result, ttl=CACHE_TTL_SEARCH)
                    
                    return result
                
                elif response.status_code == 404:
                    return {
                        "success": True,
                        "companies": [],
                        "total": 0,
                        "query": query,
                        "source": "web_scraping"
                    }
                
                else:
                    logger.warning(f"Scrape search got status {response.status_code}")
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(RETRY_DELAY)
                        continue
                    return {
                        "success": False,
                        "error": {
                            "code": f"HTTP_{response.status_code}",
                            "message": f"Website returned status {response.status_code}"
                        }
                    }
                    
            except requests.exceptions.Timeout:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY)
                    continue
                return {
                    "success": False,
                    "error": {
                        "code": "TIMEOUT",
                        "message": "Request timed out"
                    }
                }
            except requests.exceptions.RequestException as e:
                logger.error(f"Scrape request error: {e}")
                return {
                    "success": False,
                    "error": {
                        "code": "REQUEST_ERROR",
                        "message": str(e)
                    }
                }
        
        return {
            "success": False,
            "error": {
                "code": "MAX_RETRIES",
                "message": "Maximum retry attempts exceeded"
            }
        }
    
    def _scrape_company_details(
        self,
        url: str
    ) -> Dict[str, Any]:
        """
        Get company details by scraping the North Data website.
        
        Args:
            url: Full North Data URL for the company
            
        Returns:
            Dict with company details
        """
        cache_key = self._get_cache_key("scrape_company", url=url)
        
        if CACHE_AVAILABLE:
            cache = get_cache("northdata_scrape", ttl=CACHE_TTL_COMPANY)
            cached = cache.get(cache_key)
            if cached:
                logger.debug(f"Cache hit for scrape company: {url}")
                return cached
        
        for attempt in range(MAX_RETRIES):
            try:
                response = self.scrape_session.get(
                    url,
                    timeout=REQUEST_TIMEOUT,
                    allow_redirects=True
                )
                
                if response.status_code == 200:
                    company = _parse_company_details_html(response.text, url)
                    
                    result = {
                        "success": True,
                        "company": company,
                        "note": "Limited data via web scraping - for full access, configure an API key"
                    }
                    
                    if CACHE_AVAILABLE:
                        cache.set(cache_key, result, ttl=CACHE_TTL_COMPANY)
                    
                    return result
                
                elif response.status_code == 404:
                    return {
                        "success": False,
                        "error": {
                            "code": "NOT_FOUND",
                            "message": "Company not found"
                        }
                    }
                
                else:
                    logger.warning(f"Scrape company got status {response.status_code}")
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(RETRY_DELAY)
                        continue
                    return {
                        "success": False,
                        "error": {
                            "code": f"HTTP_{response.status_code}",
                            "message": f"Website returned status {response.status_code}"
                        }
                    }
                    
            except requests.exceptions.Timeout:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY)
                    continue
                return {
                    "success": False,
                    "error": {
                        "code": "TIMEOUT",
                        "message": "Request timed out"
                    }
                }
            except requests.exceptions.RequestException as e:
                logger.error(f"Scrape request error: {e}")
                return {
                    "success": False,
                    "error": {
                        "code": "REQUEST_ERROR",
                        "message": str(e)
                    }
                }
        
        return {
            "success": False,
            "error": {
                "code": "MAX_RETRIES",
                "message": "Maximum retry attempts exceeded"
            }
        }
    
    def _search_and_get_first(
        self,
        name: str,
        address: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Search for a company and return details of the best match (via scraping).
        
        Args:
            name: Company name
            address: Optional city/address to narrow search
            
        Returns:
            Dict with company details
        """
        # Build search query
        query = name
        if address:
            query = f"{name} {address}"
        
        # Search first
        search_result = self._scrape_search(query, limit=10)
        
        if not search_result.get("success"):
            return search_result
        
        companies = search_result.get("companies", [])
        if not companies:
            return {
                "success": False,
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"No company found for: {query}"
                }
            }
        
        # Find best matching company
        name_lower = name.lower().strip()
        address_lower = (address or "").lower().strip()
        
        best_match = None
        best_score = -1
        
        for company in companies:
            score = 0
            company_name = company.get("name", "").lower()
            company_city = company.get("address", {}).get("city", "").lower()
            company_country = company.get("address", {}).get("country", "").upper()
            
            # Exact name match gets highest score
            if company_name == name_lower:
                score += 100
            # Name starts with search term
            elif company_name.startswith(name_lower):
                score += 50
            # Search term is contained in name
            elif name_lower in company_name:
                score += 25
            
            # City match bonus
            if address_lower and address_lower in company_city:
                score += 30
            
            # Country preference - German companies get bonus (most common use case)
            if company_country == "DE":
                score += 20
            elif company_country in ("AT", "CH"):
                score += 10
            
            # Penalty for names that are much longer (likely different entity)
            len_diff = len(company_name) - len(name_lower)
            if len_diff > 20:
                score -= 20
            elif len_diff > 10:
                score -= 10
            
            # Prefer stock corporations (AG) over associations (e.V.)
            if ' ag' in company_name or company_name.endswith(' ag'):
                score += 10
            if 'e.v.' in company_name or 'e. v.' in company_name:
                score -= 15
            
            # Penalty for branches/subsidiaries
            if 'zweigniederlassung' in company_name:
                score -= 10
            
            if score > best_score:
                best_score = score
                best_match = company
        
        if not best_match:
            best_match = companies[0]
        
        # Get details of the best match
        company_url = best_match.get("northdata_url")
        
        if not company_url:
            # Return basic search result if no URL
            return {
                "success": True,
                "company": best_match,
                "note": "Limited data via web scraping - for full access, configure an API key"
            }
        
        return self._scrape_company_details(company_url)
    
    def search_companies(
        self,
        query: str,
        countries: Optional[List[str]] = None,
        limit: int = 10,
        include_financials: bool = False,
        status: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Search for companies by name or keyword.
        
        Uses API if key is configured, otherwise falls back to web scraping.
        
        Args:
            query: Search query (company name, keyword, or partial match)
            countries: List of ISO country codes to restrict search (e.g., ["DE", "AT"])
            limit: Maximum number of results (default: 10, max: 50)
            include_financials: Include financial data in results (API only)
            status: Filter by status: "active", "terminated", or "liquidation" (API only)
            
        Returns:
            Dict with:
            - success: bool
            - companies: List of company results
            - total: Total number of matches
            - query: Original query
        """
        if not query or len(query.strip()) < 2:
            return {
                "success": False,
                "error": {
                    "code": "INVALID_QUERY",
                    "message": "Query must be at least 2 characters"
                }
            }
        
        # Use web scraping if no API key
        if not self.api_key:
            logger.debug(f"Using web scraping for search: {query}")
            return self._scrape_search(query, limit=limit)
        
        # Use API
        params = {
            "query": query.strip(),
            "domain": "company",
            "limit": min(limit, 50),
            "output": "json"
        }
        
        if countries:
            # Validate country codes
            valid_countries = [c.upper() for c in countries if c.upper() in SUPPORTED_COUNTRIES]
            if valid_countries:
                params["countries"] = ",".join(valid_countries)
        
        if include_financials:
            params["financials"] = "true"
        
        if status and status in ("active", "terminated", "liquidation"):
            params["status"] = status
        
        response = self._make_request("/search/v1/universal", params)
        
        if "error" in response:
            return {"success": False, **response}
        
        # Process results
        companies = []
        for result in response.get("results", []):
            company = result.get("company", {})
            if company:
                companies.append(self._format_company_result(company))
        
        return {
            "success": True,
            "companies": companies,
            "total": response.get("total", len(companies)),
            "query": query,
            "countries_searched": params.get("countries", "all"),
            "source": "api"
        }
    
    def get_company_details(
        self,
        name: Optional[str] = None,
        address: Optional[str] = None,
        register_id: Optional[str] = None,
        register_city: Optional[str] = None,
        include_financials: bool = True,
        include_relations: bool = True,
        include_events: bool = False,
        northdata_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get detailed information about a specific company.
        
        Uses API if key is configured, otherwise falls back to web scraping.
        
        Args:
            name: Company name
            address: City or full address
            register_id: German register ID (e.g., "HRB 12345")
            register_city: Court city (e.g., "Hamburg")
            include_financials: Include financial performance data (API only)
            include_relations: Include related companies/persons (API only)
            include_events: Include company events (API only)
            northdata_url: Direct North Data URL (for web scraping)
            
        Returns:
            Dict with detailed company information
        """
        if not name and not register_id and not northdata_url:
            return {
                "success": False,
                "error": {
                    "code": "MISSING_PARAMS",
                    "message": "Either name, register_id, or northdata_url is required"
                }
            }
        
        # Use web scraping if no API key
        if not self.api_key:
            logger.debug(f"Using web scraping for company details: {name or northdata_url}")
            
            # If we have a direct URL, use it
            if northdata_url and northdata_url.startswith(NORTHDATA_WEB_URL):
                return self._scrape_company_details(northdata_url)
            
            # Otherwise search and get the first result
            if name:
                return self._search_and_get_first(name, address)
            
            return {
                "success": False,
                "error": {
                    "code": "INVALID_PARAMS",
                    "message": "Company name required for web scraping (no API key configured)"
                }
            }
        
        # Use API
        params = {
            "output": "json",
            "fuzzyMatch": "true"
        }
        
        if name:
            params["name"] = name.strip()
        if address:
            params["address"] = address.strip()
        if register_id:
            params["registerId"] = register_id.strip()
        if register_city:
            params["registerCity"] = register_city.strip()
        
        if include_financials:
            params["financials"] = "true"
        if include_relations:
            params["relations"] = "true"
        if include_events:
            params["events"] = "true"
            params["maxEvents"] = "20"
        
        response = self._make_request("/company/v1/company", params, cache_ttl=CACHE_TTL_COMPANY)
        
        if "error" in response:
            return {"success": False, **response}
        
        result = self._format_company_details(response)
        result["source"] = "api"
        
        return {
            "success": True,
            "company": result
        }
    
    def search_persons(
        self,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        address: Optional[str] = None,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Search for persons (executives, directors, shareholders).
        
        Requires API key - person search is not available via web scraping.
        
        Args:
            first_name: First name(s)
            last_name: Last name (required)
            address: City
            limit: Maximum results
            
        Returns:
            Dict with person results and their company relations
        """
        if not last_name:
            return {
                "success": False,
                "error": {
                    "code": "MISSING_LASTNAME",
                    "message": "Last name is required for person search"
                }
            }
        
        # Person search requires API key
        if not self.api_key:
            return {
                "success": False,
                "error": {
                    "code": "API_KEY_REQUIRED",
                    "message": "Person search requires an API key. Get one at https://www.northdata.de/_data. For company lookups without API key, use search_company or get_company_details."
                }
            }
        
        # Build query string
        query_parts = []
        if first_name:
            query_parts.append(first_name.strip())
        query_parts.append(last_name.strip())
        if address:
            query_parts.append(address.strip())
        
        params = {
            "query": " ".join(query_parts),
            "domain": "person",
            "limit": min(limit, 50),
            "output": "json"
        }
        
        response = self._make_request("/search/v1/universal", params)
        
        if "error" in response:
            return {"success": False, **response}
        
        persons = []
        for result in response.get("results", []):
            person = result.get("person", {})
            if person:
                persons.append(self._format_person_result(person))
        
        return {
            "success": True,
            "persons": persons,
            "total": response.get("total", len(persons)),
            "query": " ".join(query_parts),
            "source": "api"
        }
    
    def _format_company_result(self, company: Dict[str, Any]) -> Dict[str, Any]:
        """Format a company result for output."""
        name_data = company.get("name", {})
        address_data = company.get("address", {})
        register_data = company.get("register", {})
        
        result = {
            "id": company.get("id", ""),
            "name": sanitize_html(name_data.get("name", "")),
            "legal_form": sanitize_html(name_data.get("legalForm", "")),
            "address": {
                "street": sanitize_html(address_data.get("street", "")),
                "postal_code": sanitize_html(address_data.get("postalCode", "")),
                "city": sanitize_html(address_data.get("city", "")),
                "country": sanitize_html(address_data.get("country", "")),
            },
            "register": {
                "id": sanitize_html(register_data.get("id", "")),
                "city": sanitize_html(register_data.get("city", "")),
                "country": sanitize_html(register_data.get("country", ""))
            },
            "status": company.get("status", "unknown"),
            "northdata_url": sanitize_url(company.get("northDataUrl", ""))
        }
        
        # Add subject/purpose if available
        if company.get("subject"):
            result["subject"] = sanitize_html(company["subject"][:500])
        
        return result
    
    def _format_company_details(self, company: Dict[str, Any]) -> Dict[str, Any]:
        """Format detailed company information."""
        result = self._format_company_result(company)
        
        # Add LEI if available
        if company.get("lei"):
            result["lei"] = sanitize_html(company["lei"])
        
        # Add full subject
        if company.get("subject"):
            result["subject"] = sanitize_html(company["subject"])
        
        # Add segment codes (industry classification)
        if company.get("segmentCodes"):
            result["industry_codes"] = company["segmentCodes"]
        
        # Add financials
        if company.get("financials"):
            financials = company["financials"]
            result["financials"] = {
                "date": financials.get("formattedDate", ""),
                "consolidated": financials.get("consolidated", False),
                "indicators": {}
            }
            
            for item in financials.get("items", []):
                indicator_id = item.get("id", "")
                if indicator_id:
                    result["financials"]["indicators"][indicator_id] = {
                        "name": sanitize_html(item.get("name", "")),
                        "value": sanitize_money(item.get("value")),
                        "formatted": sanitize_html(item.get("formattedValue", "")),
                        "unit": item.get("unit", "")
                    }
        
        # Add related persons (directors, executives)
        if company.get("relatedPersons", {}).get("items"):
            result["related_persons"] = []
            for relation in company["relatedPersons"]["items"][:20]:
                person = relation.get("person", {})
                person_name = person.get("name", {})
                
                roles = []
                for role in relation.get("roles", []):
                    if not role.get("demotion"):
                        roles.append({
                            "type": role.get("type", ""),
                            "name": sanitize_html(role.get("name", "")),
                            "date": role.get("date", "")
                        })
                
                if roles:
                    result["related_persons"].append({
                        "first_name": sanitize_html(person_name.get("firstName", "")),
                        "last_name": sanitize_html(person_name.get("lastName", "")),
                        "roles": roles
                    })
        
        # Add related companies
        if company.get("relatedCompanies", {}).get("items"):
            result["related_companies"] = []
            for relation in company["relatedCompanies"]["items"][:20]:
                related = relation.get("company", {})
                related_name = related.get("name", {})
                
                roles = []
                for role in relation.get("roles", []):
                    roles.append({
                        "type": role.get("type", ""),
                        "name": sanitize_html(role.get("name", "")),
                        "shares_percent": role.get("sharesPercent")
                    })
                
                result["related_companies"].append({
                    "name": sanitize_html(related_name.get("name", "")),
                    "legal_form": sanitize_html(related_name.get("legalForm", "")),
                    "roles": roles,
                    "northdata_url": sanitize_url(related.get("northDataUrl", ""))
                })
        
        # Add events
        if company.get("events", {}).get("items"):
            result["events"] = []
            for event in company["events"]["items"][:20]:
                result["events"].append({
                    "type": event.get("type", ""),
                    "date": event.get("date", ""),
                    "description": sanitize_html(event.get("description", ""))
                })
        
        return result
    
    def _format_person_result(self, person: Dict[str, Any]) -> Dict[str, Any]:
        """Format a person result for output."""
        name_data = person.get("name", {})
        address_data = person.get("address", {})
        
        result = {
            "id": person.get("id", ""),
            "first_name": sanitize_html(name_data.get("firstName", "")),
            "last_name": sanitize_html(name_data.get("lastName", "")),
            "title": sanitize_html(name_data.get("title", "")),
            "birth_year": person.get("birthYear"),
            "address": {
                "city": sanitize_html(address_data.get("city", "")),
                "country": sanitize_html(address_data.get("country", ""))
            },
            "northdata_url": sanitize_url(person.get("northDataUrl", ""))
        }
        
        # Add company relations
        if person.get("relatedCompanies", {}).get("items"):
            result["companies"] = []
            for relation in person["relatedCompanies"]["items"][:10]:
                company = relation.get("company", {})
                company_name = company.get("name", {})
                
                roles = []
                for role in relation.get("roles", []):
                    if not role.get("demotion"):
                        roles.append({
                            "type": role.get("type", ""),
                            "name": sanitize_html(role.get("name", ""))
                        })
                
                if roles:
                    result["companies"].append({
                        "name": sanitize_html(company_name.get("name", "")),
                        "legal_form": sanitize_html(company_name.get("legalForm", "")),
                        "roles": roles
                    })
        
        return result


# =============================================================================
# Singleton instance
# =============================================================================

_service_instance: Optional[NorthDataService] = None


def get_northdata_service() -> NorthDataService:
    """Get or create the North Data service singleton."""
    global _service_instance
    if _service_instance is None:
        _service_instance = NorthDataService()
    return _service_instance
