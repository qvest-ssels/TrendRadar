"""
Tests for URL utilities - normalization, deduplication, and tracking parameter removal.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from mcp_server.utils.url_utils import (
    is_tracking_param,
    normalize_url,
    url_hash,
    extract_domain,
    extract_base_url,
    urls_match,
    get_url_signature,
    URLRegistry,
    get_url_registry,
)


class TestIsTrackingParam:
    """Tests for tracking parameter detection."""
    
    def test_utm_params(self):
        """UTM parameters should be detected as tracking."""
        utm_params = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content']
        for param in utm_params:
            assert is_tracking_param(param), f"{param} should be tracking"
    
    def test_facebook_params(self):
        """Facebook tracking params should be detected."""
        fb_params = ['fbclid', 'fb_action_ids', 'fbc', 'fbp']
        for param in fb_params:
            assert is_tracking_param(param), f"{param} should be tracking"
    
    def test_google_params(self):
        """Google tracking params should be detected."""
        google_params = ['gclid', 'gclsrc', 'dclid', '_ga', '_gl']
        for param in google_params:
            assert is_tracking_param(param), f"{param} should be tracking"
    
    def test_session_params(self):
        """Session parameters should be detected."""
        session_params = ['sessionid', 'session_id', 'sid', 'jsessionid', 'phpsessid']
        for param in session_params:
            assert is_tracking_param(param), f"{param} should be tracking"
    
    def test_non_tracking_params(self):
        """Legitimate params should NOT be detected as tracking."""
        legit_params = ['page', 'q', 'search', 'id', 'article', 'category', 'sort', 'filter']
        for param in legit_params:
            assert not is_tracking_param(param), f"{param} should NOT be tracking"
    
    def test_case_insensitive(self):
        """Detection should be case-insensitive."""
        assert is_tracking_param('UTM_SOURCE')
        assert is_tracking_param('Utm_Medium')
        assert is_tracking_param('FBCLID')


class TestNormalizeUrl:
    """Tests for URL normalization."""
    
    def test_lowercase_scheme_and_host(self):
        """Scheme and host should be lowercased."""
        url = "HTTPS://EXAMPLE.COM/Page"
        normalized = normalize_url(url)
        assert normalized.startswith("https://example.com")
    
    def test_remove_default_ports(self):
        """Default ports should be removed."""
        assert "example.com/" in normalize_url("http://example.com:80/page")
        assert "example.com/" in normalize_url("https://example.com:443/page")
    
    def test_keep_non_default_ports(self):
        """Non-default ports should be kept."""
        assert ":8080" in normalize_url("http://example.com:8080/page")
    
    def test_remove_trailing_slash(self):
        """Trailing slashes should be removed (except root)."""
        assert normalize_url("https://example.com/page/").endswith("/page")
        assert normalize_url("https://example.com/").endswith(".com/")
    
    def test_strip_utm_params(self):
        """UTM parameters should be stripped."""
        url = "https://example.com/article?id=123&utm_source=twitter&utm_medium=social"
        normalized = normalize_url(url)
        assert "utm_source" not in normalized
        assert "utm_medium" not in normalized
        assert "id=123" in normalized
    
    def test_strip_fbclid(self):
        """Facebook click ID should be stripped."""
        url = "https://example.com/page?fbclid=IwAR1234567890"
        normalized = normalize_url(url)
        assert "fbclid" not in normalized
    
    def test_strip_session_ids(self):
        """Session IDs should be stripped."""
        url = "https://example.com/page?sessionid=abc123&content=news"
        normalized = normalize_url(url)
        assert "sessionid" not in normalized
        assert "content=news" in normalized
    
    def test_preserve_important_params(self):
        """Important parameters should be preserved."""
        url = "https://example.com/search?q=test&page=2&utm_source=google"
        normalized = normalize_url(url)
        assert "q=test" in normalized
        assert "page=2" in normalized
        assert "utm_source" not in normalized
    
    def test_sort_params(self):
        """Parameters should be sorted alphabetically."""
        url = "https://example.com/page?z=1&a=2&m=3"
        normalized = normalize_url(url)
        # Should be a=2&m=3&z=1
        assert normalized.index("a=2") < normalized.index("m=3")
        assert normalized.index("m=3") < normalized.index("z=1")
    
    def test_strip_fragment(self):
        """URL fragments should be stripped by default."""
        url = "https://example.com/page#section"
        normalized = normalize_url(url)
        assert "#" not in normalized
    
    def test_keep_fragment_when_requested(self):
        """Fragments can be preserved if requested."""
        url = "https://example.com/page#section"
        normalized = normalize_url(url, strip_fragment=False)
        assert "#section" in normalized
    
    def test_empty_url(self):
        """Empty URL should return empty string."""
        assert normalize_url("") == ""
        assert normalize_url(None) == ""


class TestUrlHash:
    """Tests for URL hashing."""
    
    def test_hash_length(self):
        """Hash should be 16 characters."""
        h = url_hash("https://example.com/page")
        assert len(h) == 16
    
    def test_same_url_same_hash(self):
        """Same URL should produce same hash."""
        url = "https://example.com/page"
        assert url_hash(url) == url_hash(url)
    
    def test_normalized_urls_same_hash(self):
        """URLs that normalize to the same should have same hash."""
        url1 = "https://example.com/page?utm_source=twitter"
        url2 = "https://example.com/page?utm_source=facebook"
        assert url_hash(url1) == url_hash(url2)
    
    def test_different_urls_different_hash(self):
        """Different URLs should have different hashes."""
        url1 = "https://example.com/page1"
        url2 = "https://example.com/page2"
        assert url_hash(url1) != url_hash(url2)
    
    def test_tracking_params_dont_affect_hash(self):
        """Different tracking params should produce same hash."""
        url1 = "https://example.com/article?id=123&fbclid=abc"
        url2 = "https://example.com/article?id=123&gclid=xyz"
        assert url_hash(url1) == url_hash(url2)


class TestExtractDomain:
    """Tests for domain extraction."""
    
    def test_simple_domain(self):
        """Should extract simple domain."""
        assert extract_domain("https://example.com/page") == "example.com"
    
    def test_subdomain(self):
        """Should include subdomains."""
        assert extract_domain("https://www.example.com/page") == "www.example.com"
    
    def test_with_port(self):
        """Should include port if present."""
        assert extract_domain("https://example.com:8080/page") == "example.com:8080"
    
    def test_lowercase(self):
        """Should return lowercase domain."""
        assert extract_domain("https://EXAMPLE.COM/page") == "example.com"


class TestUrlsMatch:
    """Tests for URL matching."""
    
    def test_exact_match(self):
        """Exact URLs should match."""
        url = "https://example.com/page"
        assert urls_match(url, url)
    
    def test_tracking_params_match(self):
        """URLs with different tracking params should match."""
        url1 = "https://example.com/article?utm_source=twitter"
        url2 = "https://example.com/article?utm_source=facebook"
        assert urls_match(url1, url2)
    
    def test_different_content_no_match(self):
        """URLs with different content should not match."""
        url1 = "https://example.com/page1"
        url2 = "https://example.com/page2"
        assert not urls_match(url1, url2)
    
    def test_different_params_no_match(self):
        """URLs with different important params should not match."""
        url1 = "https://example.com/search?q=foo"
        url2 = "https://example.com/search?q=bar"
        assert not urls_match(url1, url2)


class TestURLRegistry:
    """Tests for URL registry."""
    
    def test_register_new_url(self):
        """Should register new URLs."""
        registry = URLRegistry()
        hash_key, is_new = registry.register("https://example.com/page", source="test")
        assert is_new
        assert len(hash_key) == 16
    
    def test_register_duplicate_url(self):
        """Should recognize duplicate URLs."""
        registry = URLRegistry()
        registry.register("https://example.com/page", source="first")
        hash_key, is_new = registry.register("https://example.com/page", source="second")
        assert not is_new
    
    def test_register_same_url_different_tracking(self):
        """URLs with different tracking should be deduplicated."""
        registry = URLRegistry()
        h1, new1 = registry.register("https://example.com/page?utm_source=a", source="first")
        h2, new2 = registry.register("https://example.com/page?utm_source=b", source="second")
        assert h1 == h2
        assert new1 and not new2
    
    def test_lookup_existing(self):
        """Should find registered URLs."""
        registry = URLRegistry()
        registry.register("https://example.com/page", source="test")
        entry = registry.lookup("https://example.com/page")
        assert entry is not None
        assert "test" in entry['sources']
    
    def test_lookup_missing(self):
        """Should return None for unregistered URLs."""
        registry = URLRegistry()
        entry = registry.lookup("https://example.com/notregistered")
        assert entry is None
    
    def test_find_cached_version(self):
        """Should find cached versions of URLs."""
        registry = URLRegistry()
        registry.register("https://example.com/article?id=123", source="cached")
        
        cached = registry.find_cached_version("https://example.com/article?id=123&fbclid=abc")
        assert cached is not None
    
    def test_get_all_for_domain(self):
        """Should get all URLs for a domain."""
        registry = URLRegistry()
        registry.register("https://example.com/page1", source="test")
        registry.register("https://example.com/page2", source="test")
        registry.register("https://other.com/page", source="test")
        
        entries = registry.get_all_for_domain("example.com")
        assert len(entries) == 2
    
    def test_stats(self):
        """Should return accurate statistics."""
        registry = URLRegistry()
        registry.register("https://a.com/1", source="cached")
        registry.register("https://b.com/1", source="live")
        registry.register("https://b.com/2", source="live")
        
        stats = registry.stats()
        assert stats['total_urls'] == 3
        assert stats['total_domains'] == 2


class TestIntegration:
    """Integration tests for URL utilities."""
    
    def test_full_workflow(self):
        """Test complete URL deduplication workflow."""
        registry = URLRegistry()
        
        # Simulate cached URLs
        cached_urls = [
            "https://spiegel.de/article/123",
            "https://theguardian.com/news/456",
        ]
        for url in cached_urls:
            registry.register(url, source="cached")
        
        # Simulate live crawl with tracking params
        live_url = "https://spiegel.de/article/123?utm_source=twitter&fbclid=abc123"
        
        # Check if we have a cached version
        cached = registry.find_cached_version(live_url)
        assert cached is not None
        assert "spiegel.de/article/123" in cached
        assert "utm_source" not in cached
    
    def test_complex_url_normalization(self):
        """Test complex real-world URL normalization."""
        # Complex URL with multiple tracking parameters
        messy_url = (
            "https://www.example.com:443/news/article/"
            "?id=12345"
            "&utm_source=newsletter"
            "&utm_medium=email"
            "&utm_campaign=weekly"
            "&fbclid=IwAR1234567890"
            "&gclid=CjwKCAjw"
            "&mc_eid=abc123"
            "&sessionid=sess_xyz"
            "#comments"
        )
        
        normalized = normalize_url(messy_url)
        
        # Should have cleaned domain
        assert "www.example.com/" in normalized
        assert ":443" not in normalized
        
        # Should preserve important params
        assert "id=12345" in normalized
        
        # Should strip all tracking
        assert "utm_" not in normalized
        assert "fbclid" not in normalized
        assert "gclid" not in normalized
        assert "mc_eid" not in normalized
        assert "sessionid" not in normalized
        
        # Should strip fragment
        assert "#" not in normalized


# Timeout for all tests
pytestmark = pytest.mark.timeout(5)
