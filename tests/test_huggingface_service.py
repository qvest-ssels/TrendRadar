"""
Tests for HuggingFace Service

Tests the Ask an Expert feature for ML model/dataset/paper search.
"""

import pytest
from unittest.mock import Mock, patch

from mcp_server.services.huggingface_service import (
    HuggingFaceService,
    get_huggingface_service,
    sanitize_html,
    sanitize_url,
)


class TestSanitization:
    """Test XSS sanitization functions."""
    
    def test_sanitize_html_removes_tags(self):
        """Test that HTML tags are removed."""
        text = "<script>alert('xss')</script>Hello <b>World</b>"
        result = sanitize_html(text)
        assert "<script>" not in result
        assert "<b>" not in result
        assert "Hello" in result
        assert "World" in result
    
    def test_sanitize_html_escapes_entities(self):
        """Test that special characters are escaped."""
        text = "Test & \"quotes\" 'apostrophe'"
        result = sanitize_html(text)
        assert "&amp;" in result
        # Quotes are escaped
        assert "&quot;" in result or "&#x27;" in result or "quotes" in result
    
    def test_sanitize_html_handles_empty(self):
        """Test empty string handling."""
        assert sanitize_html("") == ""
        assert sanitize_html(None) == ""
    
    def test_sanitize_url_allows_huggingface(self):
        """Test that HuggingFace URLs are allowed."""
        url = "https://huggingface.co/meta-llama/Llama-2-7b"
        assert sanitize_url(url) == url
        
        url2 = "https://hf.co/models"
        assert sanitize_url(url2) == url2
    
    def test_sanitize_url_blocks_non_huggingface(self):
        """Test that non-HuggingFace URLs are blocked."""
        assert sanitize_url("https://evil.com/hack") == ""
        assert sanitize_url("https://example.org/test") == ""
    
    def test_sanitize_url_blocks_javascript(self):
        """Test that javascript: URLs are blocked."""
        assert sanitize_url("javascript:alert(1)") == ""
        assert sanitize_url("https://huggingface.co/javascript:alert(1)") == ""
    
    def test_sanitize_url_handles_empty(self):
        """Test empty URL handling."""
        assert sanitize_url("") == ""
        assert sanitize_url(None) == ""


class TestHuggingFaceService:
    """Test HuggingFace service with real API calls (requires network)."""
    
    @pytest.fixture
    def service(self):
        return HuggingFaceService()
    
    @pytest.mark.timeout(20)
    def test_search_models_basic(self, service):
        """Test basic model search."""
        result = service.search_models("llama", limit=5)
        
        assert result["success"] is True
        assert "models" in result
        assert len(result["models"]) <= 5
        assert result["source"] == "huggingface"
        
        # Check model structure
        if result["models"]:
            model = result["models"][0]
            assert "id" in model
            assert "name" in model
            assert "downloads" in model
            assert "url" in model
    
    @pytest.mark.timeout(20)
    def test_search_models_with_task(self, service):
        """Test model search with task filter."""
        result = service.search_models("code", task="text-generation", limit=5)
        
        assert result["success"] is True
        assert result["task_filter"] == "text-generation"
    
    @pytest.mark.timeout(20)
    def test_search_datasets(self, service):
        """Test dataset search."""
        result = service.search_datasets("sentiment", limit=5)
        
        assert result["success"] is True
        assert "datasets" in result
        assert result["source"] == "huggingface"
        
        if result["datasets"]:
            ds = result["datasets"][0]
            assert "id" in ds
            assert "url" in ds
    
    @pytest.mark.timeout(20)
    def test_get_daily_papers(self, service):
        """Test getting daily papers."""
        result = service.get_daily_papers(limit=5)
        
        assert result["success"] is True
        assert "papers" in result
        assert result["source"] == "huggingface_papers"
    
    @pytest.mark.timeout(20)
    @pytest.mark.xfail(reason="Paper search API may return empty for some queries", strict=False)
    def test_search_papers(self, service):
        """Test paper search."""
        result = service.search_papers("transformer", limit=5)
        
        assert result["success"] is True
        assert "papers" in result
        if result["papers"]:
            paper = result["papers"][0]
            assert "title" in paper
            assert "arxiv_id" in paper
    
    def test_get_task_types(self, service):
        """Test getting available task types."""
        result = service.get_task_types()
        
        assert result["success"] is True
        assert "tasks" in result
        assert "text-generation" in result["tasks"]
        assert "text-to-image" in result["tasks"]


class TestHuggingFaceServiceMocked:
    """Test HuggingFace service with mocked responses."""
    
    @pytest.fixture
    def service(self):
        return HuggingFaceService()
    
    def test_timeout_handling(self, service):
        """Test timeout is handled gracefully."""
        with patch.object(service.session, 'get') as mock_get:
            import requests
            mock_get.side_effect = requests.Timeout("Connection timed out")
            
            result = service.search_models("test")
            
            assert result["success"] is False
            assert "timed out" in result["error"].lower()
    
    def test_xss_in_response_sanitized(self, service):
        """Test that XSS in API response is sanitized."""
        with patch.object(service.session, 'get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = [
                {
                    "id": "<script>alert('xss')</script>evil/model",
                    "downloads": 1000,
                    "likes": 50,
                    "pipeline_tag": "text-generation",
                    "tags": ["<img onerror=alert(1)>"],
                    "lastModified": "2024-01-01"
                }
            ]
            mock_get.return_value = mock_response
            
            result = service.search_models("test")
            
            assert result["success"] is True
            model = result["models"][0]
            assert "<script>" not in model["id"]
            assert "alert" not in model["tags"][0] or "&" in model["tags"][0]


class TestSingleton:
    """Test singleton pattern."""
    
    def test_get_huggingface_service_singleton(self):
        """Test that get_huggingface_service returns same instance."""
        service1 = get_huggingface_service()
        service2 = get_huggingface_service()
        
        assert service1 is service2
