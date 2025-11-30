"""
Simple in-memory cache with TTL for API responses.

Used to reduce API calls to rate-limited services like GitHub.
"""

import hashlib
import logging
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class TTLCache:
    """
    Simple in-memory cache with time-to-live (TTL).
    
    Thread-safe for basic operations.
    Automatically cleans up expired entries on access.
    """
    
    def __init__(self, default_ttl: int = 3600, max_size: int = 1000):
        """
        Initialize cache.
        
        Args:
            default_ttl: Default time-to-live in seconds (default: 1 hour)
            max_size: Maximum number of entries to store
        """
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._default_ttl = default_ttl
        self._max_size = max_size
        self._hits = 0
        self._misses = 0
    
    def _make_key(self, prefix: str, **kwargs) -> str:
        """Create a cache key from prefix and arguments."""
        # Sort kwargs for consistent key generation
        sorted_items = sorted(kwargs.items())
        key_str = f"{prefix}:{sorted_items}"
        # Use hash for shorter keys
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def make_key(self, prefix: str, **kwargs) -> str:
        """
        Create a cache key from prefix and keyword arguments.
        
        Args:
            prefix: Key prefix (e.g., "github_search", "arxiv_search")
            **kwargs: Arguments to include in key
            
        Returns:
            Hashed cache key
        """
        return self._make_key(prefix, **kwargs)
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache if it exists and hasn't expired.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found/expired
        """
        entry = self._cache.get(key)
        
        if entry is None:
            self._misses += 1
            return None
        
        # Check if expired
        if time.time() > entry["expires_at"]:
            del self._cache[key]
            self._misses += 1
            return None
        
        self._hits += 1
        return entry["value"]
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        Set value in cache with TTL.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (uses default if not specified)
        """
        # Evict old entries if at max size
        if len(self._cache) >= self._max_size:
            self._evict_expired()
            # If still at max, evict oldest
            if len(self._cache) >= self._max_size:
                self._evict_oldest()
        
        ttl = ttl if ttl is not None else self._default_ttl
        self._cache[key] = {
            "value": value,
            "expires_at": time.time() + ttl,
            "created_at": time.time()
        }
    
    def _evict_expired(self) -> int:
        """Remove all expired entries. Returns count of evicted entries."""
        now = time.time()
        expired_keys = [
            k for k, v in self._cache.items() 
            if now > v["expires_at"]
        ]
        for key in expired_keys:
            del self._cache[key]
        return len(expired_keys)
    
    def _evict_oldest(self) -> None:
        """Remove the oldest entry."""
        if not self._cache:
            return
        oldest_key = min(
            self._cache.keys(),
            key=lambda k: self._cache[k]["created_at"]
        )
        del self._cache[oldest_key]
    
    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0
    
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = self._hits + self._misses
        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self._hits / total if total > 0 else 0,
            "default_ttl": self._default_ttl
        }


# Global cache instances for different services
_caches: Dict[str, TTLCache] = {}


def get_cache(name: str, ttl: int = 3600, max_size: int = 500) -> TTLCache:
    """
    Get or create a named cache instance.
    
    Args:
        name: Cache name (e.g., "github", "arxiv")
        ttl: Default TTL in seconds
        max_size: Maximum entries
        
    Returns:
        TTLCache instance
    """
    if name not in _caches:
        _caches[name] = TTLCache(default_ttl=ttl, max_size=max_size)
    return _caches[name]


def get_all_cache_stats() -> Dict[str, Dict[str, Any]]:
    """Get stats for all caches."""
    return {name: cache.stats() for name, cache in _caches.items()}


def clear_all_caches() -> None:
    """Clear all caches."""
    for cache in _caches.values():
        cache.clear()
