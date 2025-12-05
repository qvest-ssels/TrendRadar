"""
North Data Service for Company Lookups

Provides search and lookup capabilities for European companies via the North Data API.
Covers 22 European countries with company data, financials, and ownership information.

Security: All content is sanitized to prevent XSS attacks.
API Key: Required - set NORTHDATA_API_KEY environment variable

API Documentation: https://northdata.github.io/doc/api/
"""

import hashlib
import html
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional
from urllib.parse import quote, urlencode, urlparse

import requests

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
    
    Requires NORTHDATA_API_KEY environment variable.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize North Data service.
        
        Args:
            api_key: North Data API key. If not provided, reads from NORTHDATA_API_KEY env var.
        """
        self.api_key = api_key or os.environ.get("NORTHDATA_API_KEY")
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "TrendRadar/1.0 (https://github.com/qvest-ssels/TrendRadar)"
        })
        
        if not self.api_key:
            logger.warning("NORTHDATA_API_KEY not set - North Data features will be limited")
    
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
        
        Args:
            query: Search query (company name, keyword, or partial match)
            countries: List of ISO country codes to restrict search (e.g., ["DE", "AT"])
            limit: Maximum number of results (default: 10, max: 50)
            include_financials: Include financial data in results
            status: Filter by status: "active", "terminated", or "liquidation"
            
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
            "countries_searched": params.get("countries", "all")
        }
    
    def get_company_details(
        self,
        name: Optional[str] = None,
        address: Optional[str] = None,
        register_id: Optional[str] = None,
        register_city: Optional[str] = None,
        include_financials: bool = True,
        include_relations: bool = True,
        include_events: bool = False
    ) -> Dict[str, Any]:
        """
        Get detailed information about a specific company.
        
        Args:
            name: Company name
            address: City or full address
            register_id: German register ID (e.g., "HRB 12345")
            register_city: Court city (e.g., "Hamburg")
            include_financials: Include financial performance data
            include_relations: Include related companies/persons
            include_events: Include company events (incorporation, changes, etc.)
            
        Returns:
            Dict with detailed company information
        """
        if not name and not register_id:
            return {
                "success": False,
                "error": {
                    "code": "MISSING_PARAMS",
                    "message": "Either name or register_id is required"
                }
            }
        
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
        
        return {
            "success": True,
            "company": self._format_company_details(response)
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
            "query": " ".join(query_parts)
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
