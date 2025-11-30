"""
Tests for the API cache utility.
"""
import pytest
import time

from mcp_server.utils.cache import (
    TTLCache,
    get_cache,
    get_all_cache_stats,
    clear_all_caches,
)


class TestTTLCache:
    """Tests for TTLCache class."""
    
    def test_set_and_get(self):
        """Can store and retrieve values."""
        cache = TTLCache()
        cache.set("test_key", {"data": "value"})
        result = cache.get("test_key")
        assert result == {"data": "value"}
    
    def test_get_missing_key(self):
        """Returns None for missing keys."""
        cache = TTLCache()
        assert cache.get("nonexistent") is None
    
    def test_expiration(self):
        """Values expire after TTL."""
        cache = TTLCache(default_ttl=1)  # 1 second TTL
        cache.set("expiring", "value")
        
        # Should exist immediately
        assert cache.get("expiring") == "value"
        
        # Wait for expiration
        time.sleep(1.1)
        
        # Should be gone
        assert cache.get("expiring") is None
    
    def test_custom_ttl_per_entry(self):
        """Can set custom TTL per entry."""
        cache = TTLCache(default_ttl=60)
        cache.set("quick", "value", ttl=1)
        
        assert cache.get("quick") == "value"
        time.sleep(1.1)
        assert cache.get("quick") is None
    
    def test_make_key(self):
        """Key generation is consistent."""
        cache = TTLCache()
        key1 = cache.make_key("prefix", a=1, b="test")
        key2 = cache.make_key("prefix", b="test", a=1)  # Different order
        key3 = cache.make_key("prefix", a=1, b="other")
        
        # Same args should produce same key regardless of order
        assert key1 == key2
        
        # Different args should produce different keys
        assert key1 != key3
    
    def test_stats(self):
        """Stats track hits and misses."""
        cache = TTLCache()
        
        # Initial stats
        stats = cache.stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        
        # Miss
        cache.get("missing")
        assert cache.stats()["misses"] == 1
        
        # Set and hit
        cache.set("existing", "value")
        cache.get("existing")
        assert cache.stats()["hits"] == 1
    
    def test_clear(self):
        """Clear removes all entries and resets stats."""
        cache = TTLCache()
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.get("key1")  # Hit
        
        cache.clear()
        
        assert cache.get("key1") is None
        assert cache.get("key2") is None
        stats = cache.stats()
        assert stats["size"] == 0
        # Stats reset but gets after clear count as misses
    
    def test_max_size_eviction(self):
        """Evicts oldest entries when at max size."""
        cache = TTLCache(max_size=3)
        
        cache.set("key1", "value1")
        time.sleep(0.01)
        cache.set("key2", "value2")
        time.sleep(0.01)
        cache.set("key3", "value3")
        time.sleep(0.01)
        cache.set("key4", "value4")  # Should evict oldest (key1)
        
        assert cache.get("key1") is None  # Evicted
        assert cache.get("key2") == "value2"
        assert cache.get("key3") == "value3"
        assert cache.get("key4") == "value4"


class TestCacheModule:
    """Tests for module-level cache functions."""
    
    def test_get_cache_creates_named_cache(self):
        """get_cache creates separate named caches."""
        clear_all_caches()
        
        cache1 = get_cache("test1")
        cache2 = get_cache("test2")
        
        cache1.set("key", "value1")
        cache2.set("key", "value2")
        
        assert cache1.get("key") == "value1"
        assert cache2.get("key") == "value2"
    
    def test_get_cache_returns_same_instance(self):
        """get_cache returns same instance for same name."""
        clear_all_caches()
        
        cache1 = get_cache("same_name")
        cache2 = get_cache("same_name")
        
        assert cache1 is cache2
        
        cache1.set("key", "value")
        assert cache2.get("key") == "value"
    
    def test_get_cache_custom_ttl(self):
        """get_cache accepts custom TTL."""
        clear_all_caches()
        
        cache = get_cache("custom_ttl", ttl=1)
        cache.set("key", "value")
        
        assert cache.get("key") == "value"
        time.sleep(1.1)
        assert cache.get("key") is None
    
    def test_get_all_cache_stats(self):
        """get_all_cache_stats returns stats for all caches."""
        clear_all_caches()
        
        cache1 = get_cache("stats1")
        cache2 = get_cache("stats2")
        
        cache1.set("key", "value")
        cache1.get("key")  # Hit
        cache2.get("missing")  # Miss
        
        all_stats = get_all_cache_stats()
        
        assert "stats1" in all_stats
        assert "stats2" in all_stats
        assert all_stats["stats1"]["hits"] == 1
        assert all_stats["stats2"]["misses"] == 1
    
    def test_clear_all_caches(self):
        """clear_all_caches clears all named caches."""
        clear_all_caches()
        
        cache1 = get_cache("clear1")
        cache2 = get_cache("clear2")
        
        cache1.set("key", "value1")
        cache2.set("key", "value2")
        
        clear_all_caches()
        
        # Caches should be empty
        assert cache1.get("key") is None
        assert cache2.get("key") is None
