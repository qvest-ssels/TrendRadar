"""
URL utilities for normalization, deduplication, and tracking parameter removal.

Provides tools for:
- Stripping tracking/analytics parameters (UTM, session IDs, etc.)
- Normalizing URLs for consistent comparison
- Generating hashes for efficient deduplication
- Linking live crawled content to cached versions
"""

import hashlib
import re
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)

# Parameters to always strip (tracking, analytics, session management)
TRACKING_PARAMS = {
    # UTM parameters (Google Analytics / Urchin)
    'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
    'utm_id', 'utm_source_platform', 'utm_creative_format', 'utm_marketing_tactic',
    
    # Facebook/Meta
    'fbclid', 'fb_action_ids', 'fb_action_types', 'fb_source', 'fb_ref',
    'fbc', 'fbp', '_fb_noscript',
    
    # Google Ads/Analytics
    'gclid', 'gclsrc', 'dclid', 'gbraid', 'wbraid', 'gad_source',
    '_ga', '_gl', '_gid', 'ga_source', 'ga_medium', 'ga_term', 'ga_content', 'ga_campaign',
    
    # Microsoft/Bing
    'msclkid', 'mkt_tok',
    
    # Twitter/X
    'twclid', 'twsrc', 'twcamp', 'twterm', 'twcon', 'twgr',
    
    # LinkedIn
    'li_fat_id', 'li_medium', 'li_source', 'trk',
    
    # TikTok
    'ttclid', '_ttp',
    
    # Pinterest
    'epik',
    
    # Email marketing
    'mc_eid', 'mc_cid', 'ml_subscriber', 'ml_subscriber_hash',
    'oly_enc_id', 'oly_anon_id', 'vero_id', 'vero_conv',
    'spm', 'scm', 'algo_pvid',  # Alibaba/AliExpress
    
    # Affiliate/referral
    'ref', 'ref_', 'referrer', 'affiliate', 'partner', 'source',
    'aff_id', 'aff_sub', 'aff_sub2', 'aff_sub3', 'aff_sub4', 'aff_sub5',
    'clickid', 'click_id', 'irclickid',
    
    # Session/user tracking
    'sessionid', 'session_id', 'sid', 'ssid', 'jsessionid', 'phpsessid',
    'aspsessionid', 'asp_session', 'cfid', 'cftoken',
    'visitor_id', 'visitorid', '__hstc', '__hssc', '__hsfp', 'hubspotutk',
    '_hsmi', '_hsenc',
    
    # Cache busters / timestamps
    'timestamp', 'ts', 'cb', 'cachebuster', 'nocache', 'nc', 'rand', 'random',
    '_t', '_ts', 't', 'time', 'v', 'ver', 'version',
    
    # Miscellaneous tracking
    'cid', 'eid', 'uid', 'userid', 'user_id', 'mid', 'aid', 'nid',
    'tracking', 'track', 'tracker', 'trk_contact', 'trk_msg', 'trk_module', 'trk_sid',
    'igshid', 'share_id', 'share', 's',  # Instagram/general sharing
    'pk_campaign', 'pk_kwd', 'pk_source', 'pk_medium',  # Piwik/Matomo
    'mtm_campaign', 'mtm_kwd', 'mtm_source', 'mtm_medium',  # Matomo
    'hsa_acc', 'hsa_cam', 'hsa_grp', 'hsa_ad', 'hsa_src', 'hsa_net', 'hsa_tgt', 'hsa_kw', 'hsa_mt', 'hsa_ver',  # HubSpot
    'zanpid', 'awc', 'ef_id',  # Various ad networks
    'nr_email_referer', 'email', 'e', 'em',  # Email tracking (but not actual email addresses)
    'sc_campaign', 'sc_channel', 'sc_content', 'sc_medium', 'sc_outcome', 'sc_geo', 'sc_country',  # SiteCatalyst
}

# Patterns for dynamic tracking params (regex patterns)
TRACKING_PARAM_PATTERNS = [
    r'^utm_',           # Any UTM variant
    r'^_ga',            # Google Analytics cookies
    r'^_gl',            # Google cross-domain linker
    r'^fb[_-]',         # Facebook variants
    r'^mc[_-]',         # Mailchimp variants
    r'^hs[_-]',         # HubSpot variants
    r'^trk[_-]',        # Tracking variants
    r'^__',             # Double underscore (often tracking cookies)
    r'session',         # Session-related
    r'token$',          # Token suffixes (but not the word 'token' alone)
    r'^click',          # Click tracking
    r'track(er|ing)?$', # Tracking suffixes
]

# Compiled patterns for performance
_compiled_patterns = [re.compile(p, re.IGNORECASE) for p in TRACKING_PARAM_PATTERNS]


def is_tracking_param(param_name: str) -> bool:
    """
    Check if a URL parameter is a tracking/analytics parameter.
    
    Args:
        param_name: The parameter name to check
        
    Returns:
        True if this is a tracking parameter that should be stripped
    """
    param_lower = param_name.lower()
    
    # Check against known tracking params
    if param_lower in TRACKING_PARAMS:
        return True
    
    # Check against patterns
    for pattern in _compiled_patterns:
        if pattern.search(param_lower):
            return True
    
    return False


def normalize_url(url: str, strip_tracking: bool = True, strip_fragment: bool = True) -> str:
    """
    Normalize a URL for consistent comparison and deduplication.
    
    Normalizations applied:
    - Convert scheme and host to lowercase
    - Remove default ports (80 for http, 443 for https)
    - Remove trailing slashes (except for root path)
    - Sort query parameters alphabetically
    - Remove tracking/analytics parameters (optional)
    - Remove fragment/anchor (optional)
    - Decode percent-encoded characters where safe
    
    Args:
        url: The URL to normalize
        strip_tracking: Whether to remove tracking parameters (default: True)
        strip_fragment: Whether to remove URL fragments (default: True)
        
    Returns:
        Normalized URL string
    """
    if not url:
        return ""
    
    try:
        parsed = urlparse(url)
    except Exception as e:
        logger.warning(f"Failed to parse URL: {url[:100]} - {e}")
        return url
    
    # Lowercase scheme and host
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    
    # Remove default ports
    if ':' in netloc:
        host, port = netloc.rsplit(':', 1)
        if (scheme == 'http' and port == '80') or (scheme == 'https' and port == '443'):
            netloc = host
    
    # Normalize path
    path = parsed.path
    # Remove trailing slash except for root
    if path != '/' and path.endswith('/'):
        path = path.rstrip('/')
    # Ensure at least root path
    if not path:
        path = '/'
    
    # Process query parameters
    query_params = parse_qs(parsed.query, keep_blank_values=True)
    
    if strip_tracking:
        # Remove tracking parameters
        query_params = {
            k: v for k, v in query_params.items()
            if not is_tracking_param(k)
        }
    
    # Sort parameters and rebuild query string
    if query_params:
        # Flatten single-value lists
        flat_params = []
        for k in sorted(query_params.keys()):
            for v in query_params[k]:
                flat_params.append((k, v))
        query = urlencode(flat_params)
    else:
        query = ''
    
    # Handle fragment
    fragment = '' if strip_fragment else parsed.fragment
    
    # Reconstruct URL
    normalized = urlunparse((scheme, netloc, path, '', query, fragment))
    
    return normalized


def url_hash(url: str, normalize: bool = True) -> str:
    """
    Generate a hash for a URL for efficient deduplication.
    
    Args:
        url: The URL to hash
        normalize: Whether to normalize the URL first (default: True)
        
    Returns:
        SHA-256 hash of the (normalized) URL (first 16 chars for brevity)
    """
    if normalize:
        url = normalize_url(url)
    
    hash_obj = hashlib.sha256(url.encode('utf-8'))
    return hash_obj.hexdigest()[:16]


def extract_domain(url: str) -> str:
    """
    Extract the domain from a URL.
    
    Args:
        url: The URL to extract domain from
        
    Returns:
        Domain string (e.g., 'example.com')
    """
    try:
        parsed = urlparse(url)
        return parsed.netloc.lower()
    except Exception:
        return ""


def extract_base_url(url: str) -> str:
    """
    Extract the base URL (scheme + domain) from a URL.
    
    Args:
        url: The full URL
        
    Returns:
        Base URL (e.g., 'https://example.com')
    """
    try:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"
    except Exception:
        return ""


def urls_match(url1: str, url2: str, ignore_tracking: bool = True) -> bool:
    """
    Check if two URLs point to the same content (ignoring tracking params).
    
    Args:
        url1: First URL
        url2: Second URL
        ignore_tracking: Whether to ignore tracking parameters (default: True)
        
    Returns:
        True if URLs match after normalization
    """
    norm1 = normalize_url(url1, strip_tracking=ignore_tracking)
    norm2 = normalize_url(url2, strip_tracking=ignore_tracking)
    return norm1 == norm2


def get_url_signature(url: str) -> Tuple[str, str, str]:
    """
    Get a signature tuple for a URL for matching against cache.
    
    Returns:
        Tuple of (domain, path_hash, normalized_url)
    """
    normalized = normalize_url(url)
    domain = extract_domain(normalized)
    path_hash = url_hash(normalized)
    
    return (domain, path_hash, normalized)


class URLRegistry:
    """
    Registry for tracking unique URLs and linking live/cached content.
    
    Supports both in-memory operation and SQLite persistence.
    When a DataStore is provided, operations are persisted to the database.
    """
    
    def __init__(self, use_db: bool = False):
        """
        Initialize URL registry.
        
        Args:
            use_db: If True, use SQLite persistence via DataStore
        """
        self._use_db = use_db
        self._store = None
        
        # In-memory fallback
        self._registry: dict[str, dict] = {}
        self._domain_index: dict[str, set] = {}
    
    def _get_store(self):
        """Lazy-load DataStore to avoid circular imports."""
        if self._store is None and self._use_db:
            try:
                from ..data.store import get_data_store
                self._store = get_data_store()
            except ImportError:
                logger.warning("DataStore not available, using in-memory registry")
                self._use_db = False
        return self._store
    
    def register(self, url: str, source: str = "unknown") -> Tuple[str, bool]:
        """
        Register a URL in the registry.
        
        Args:
            url: The URL to register
            source: Source identifier (e.g., 'live_crawl', 'cached', 'woodchuck')
            
        Returns:
            Tuple of (url_hash, is_new) where is_new indicates if this is first time seeing this URL
        """
        store = self._get_store()
        
        if store:
            # Use persistent storage
            url_id, hash_key, is_new = store.register_url(url, source)
            return hash_key, is_new
        
        # Fall back to in-memory
        normalized = normalize_url(url)
        hash_key = url_hash(normalized, normalize=False)
        domain = extract_domain(normalized)
        
        is_new = hash_key not in self._registry
        
        if is_new:
            self._registry[hash_key] = {
                'normalized_url': normalized,
                'original_urls': [url],
                'first_seen': None,
                'sources': {source},
            }
            if domain not in self._domain_index:
                self._domain_index[domain] = set()
            self._domain_index[domain].add(hash_key)
        else:
            entry = self._registry[hash_key]
            entry['sources'].add(source)
            if url not in entry['original_urls']:
                entry['original_urls'].append(url)
        
        return hash_key, is_new
    
    def lookup(self, url: str) -> Optional[dict]:
        """
        Look up a URL in the registry.
        
        Args:
            url: The URL to look up
            
        Returns:
            Registry entry if found, None otherwise
        """
        store = self._get_store()
        
        if store:
            return store.lookup_url(url)
        
        # Fall back to in-memory
        normalized = normalize_url(url)
        hash_key = url_hash(normalized, normalize=False)
        return self._registry.get(hash_key)
    
    def find_cached_version(self, url: str) -> Optional[str]:
        """
        Find a cached version of a URL if it exists.
        
        Args:
            url: The live URL to find a cached version for
            
        Returns:
            Normalized URL if found in cache, None otherwise
        """
        store = self._get_store()
        
        if store:
            return store.find_cached_url(url)
        
        # Fall back to in-memory
        entry = self.lookup(url)
        if entry and 'cached' in entry.get('sources', set()):
            return entry['normalized_url']
        return None
    
    def get_all_for_domain(self, domain: str) -> list[dict]:
        """
        Get all registered URLs for a domain.
        
        Args:
            domain: The domain to get URLs for
            
        Returns:
            List of registry entries for the domain
        """
        store = self._get_store()
        
        if store:
            return store.get_urls_by_domain(domain)
        
        # Fall back to in-memory
        domain = domain.lower()
        if domain not in self._domain_index:
            return []
        
        return [
            self._registry[hash_key]
            for hash_key in self._domain_index[domain]
            if hash_key in self._registry
        ]
    
    def stats(self) -> dict:
        """Get registry statistics."""
        store = self._get_store()
        
        if store:
            db_stats = store.db.stats()
            return {
                'total_urls': db_stats.get('urls_count', 0),
                'total_domains': len(db_stats.get('top_domains', [])),
                'top_domains': db_stats.get('top_domains', []),
                'persistent': True,
            }
        
        # Fall back to in-memory stats
        return {
            'total_urls': len(self._registry),
            'total_domains': len(self._domain_index),
            'sources': self._get_source_counts(),
            'persistent': False,
        }
    
    def _get_source_counts(self) -> dict[str, int]:
        """Count URLs by source (in-memory only)."""
        counts: dict[str, int] = {}
        for entry in self._registry.values():
            for source in entry.get('sources', []):
                counts[source] = counts.get(source, 0) + 1
        return counts


# Global registry instance
_url_registry: Optional[URLRegistry] = None


def get_url_registry(use_db: bool = False) -> URLRegistry:
    """
    Get the global URL registry instance.
    
    Args:
        use_db: If True, use SQLite persistence
        
    Returns:
        URLRegistry instance
    """
    global _url_registry
    if _url_registry is None:
        _url_registry = URLRegistry(use_db=use_db)
    return _url_registry


def reset_url_registry():
    """Reset the global URL registry (for testing)."""
    global _url_registry
    _url_registry = None
