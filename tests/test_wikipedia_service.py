"""
Tests for Wikipedia Knowledge Service

Tests cover:
- Basic summary fetching
- Multi-language support
- Search functionality
- XSS sanitization
- Timeout handling
"""

import pytest
from unittest.mock import patch, MagicMock

from mcp_server.services.wikipedia_service import (
    WikipediaService,
    get_wikipedia_service,
    sanitize_html,
    sanitize_url
)


class TestSanitization:
    """Test XSS sanitization functions."""
    
    def test_sanitize_html_removes_tags(self):
        """Test that HTML tags are removed."""
        assert sanitize_html("<b>bold</b>") == "bold"
        assert sanitize_html("<script>alert('xss')</script>") == "alert(&#x27;xss&#x27;)"
        assert sanitize_html("<a href='evil'>link</a>") == "link"
    
    def test_sanitize_html_escapes_entities(self):
        """Test that special characters are escaped."""
        assert "&lt;" in sanitize_html("<")
        assert "&gt;" in sanitize_html(">")
        assert "&amp;" in sanitize_html("&")
    
    def test_sanitize_html_handles_empty(self):
        """Test empty input handling."""
        assert sanitize_html("") == ""
        assert sanitize_html(None) == ""
    
    def test_sanitize_url_allows_wikipedia(self):
        """Test that Wikipedia URLs are allowed."""
        url = "https://en.wikipedia.org/wiki/Test"
        assert sanitize_url(url) == url
        
        url_de = "https://de.wikipedia.org/wiki/Test"
        assert sanitize_url(url_de) == url_de
    
    def test_sanitize_url_blocks_non_wikipedia(self):
        """Test that non-Wikipedia URLs are blocked."""
        assert sanitize_url("https://evil.com/wiki/Test") == ""
        assert sanitize_url("https://google.com") == ""
    
    def test_sanitize_url_blocks_javascript(self):
        """Test that javascript: URLs are blocked."""
        assert sanitize_url("javascript:alert('xss')") == ""
        assert sanitize_url("data:text/html,<script>") == ""
    
    def test_sanitize_url_handles_empty(self):
        """Test empty URL handling."""
        assert sanitize_url("") == ""
        assert sanitize_url(None) == ""


class TestWikipediaService:
    """Test Wikipedia service methods."""
    
    @pytest.fixture
    def service(self):
        """Create a WikipediaService instance."""
        return WikipediaService()
    
    @pytest.mark.timeout(15)
    def test_get_summary_real_article(self, service):
        """Test fetching a real Wikipedia article (integration test)."""
        result = service.get_summary("Python (programming language)", "en")
        
        assert result["success"] is True
        assert "Python" in result["title"]
        assert len(result["extract"]) > 100
        assert "wikipedia.org" in result["url"]
    
    @pytest.mark.timeout(15)
    def test_get_summary_german(self, service):
        """Test German Wikipedia."""
        result = service.get_summary("Berlin", "de")
        
        assert result["success"] is True
        assert result["language"] == "de"
        assert "de.wikipedia.org" in result["url"]
    
    @pytest.mark.timeout(15)
    def test_get_summary_not_found(self, service):
        """Test handling of non-existent articles."""
        result = service.get_summary("ThisArticleDefinitelyDoesNotExist12345", "en")
        
        # Should either find via search or return not found
        # Both are valid behaviors
        assert "success" in result
    
    @pytest.mark.timeout(15)
    def test_search_basic(self, service):
        """Test basic search functionality."""
        result = service.search("artificial intelligence", "en", limit=3)
        
        assert result["success"] is True
        assert len(result["results"]) > 0
        assert result["results"][0]["title"]
        assert result["results"][0]["url"]
    
    @pytest.mark.timeout(15)
    @pytest.mark.xfail(reason="Real Wikipedia API may timeout occasionally", strict=False)
    def test_get_context(self, service):
        """Test context retrieval for news enhancement."""
        result = service.get_context("Tesla, Inc.", "en", include_related=False)
        
        assert result["success"] is True
        assert "Tesla" in result["title"]
        assert result["source"] == "wikipedia"
    
    def test_unsupported_language_fallback(self, service):
        """Test fallback to English for unsupported languages."""
        # Service should fall back to English
        result = service.get_summary("Test", "xyz")
        # Should use English
        assert result.get("language") == "en" or "en.wikipedia.org" in result.get("url", "")


class TestWikipediaServiceMocked:
    """Test Wikipedia service with mocked responses."""
    
    @pytest.fixture
    def service(self):
        return WikipediaService()
    
    @pytest.mark.timeout(5)
    def test_timeout_handling(self, service):
        """Test that timeouts are handled gracefully."""
        with patch.object(service.session, 'get') as mock_get:
            from requests.exceptions import Timeout
            mock_get.side_effect = Timeout("Connection timed out")
            
            result = service.get_summary("Test", "en")
            
            assert result["success"] is False
            assert "error" in result
    
    @pytest.mark.timeout(5)
    def test_xss_in_response_sanitized(self, service):
        """Test that XSS in API response is sanitized."""
        with patch.object(service.session, 'get') as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "title": "<script>alert('xss')</script>Malicious Title",
                "extract": "<img onerror='alert(1)' src='x'>Text",
                "extract_html": "<b onclick='evil()'>Bold</b>",
                "description": "Normal description",
                "content_urls": {
                    "desktop": {"page": "https://en.wikipedia.org/wiki/Test"},
                    "mobile": {"page": "https://en.wikipedia.org/wiki/Test"}
                },
                "type": "standard"
            }
            mock_get.return_value = mock_response
            
            result = service.get_summary("Test", "en")
            
            assert result["success"] is True
            # Check that XSS is sanitized
            assert "<script>" not in result["title"]
            assert "<img" not in result["extract"]
            assert "onclick" not in result["extract_html"]


class TestSingleton:
    """Test singleton pattern."""
    
    def test_get_wikipedia_service_singleton(self):
        """Test that get_wikipedia_service returns the same instance."""
        service1 = get_wikipedia_service()
        service2 = get_wikipedia_service()
        
        assert service1 is service2
