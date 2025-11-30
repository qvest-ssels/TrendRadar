"""
Tests for GitHub Service

Tests sanitization, API calls, rate limiting, and repo search.
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock

from mcp_server.services.github_service import (
    GitHubService,
    get_github_service,
    sanitize_html,
    sanitize_url,
)


# =============================================================================
# Sanitization Tests
# =============================================================================

class TestSanitizeHtml:
    """Test HTML sanitization for XSS prevention."""
    
    def test_removes_script_tags(self):
        """Script tags should be removed."""
        dangerous = '<script>alert("xss")</script>Hello'
        result = sanitize_html(dangerous)
        assert "<script>" not in result
        assert "Hello" in result
    
    def test_removes_html_tags(self):
        """All HTML tags should be removed."""
        html = '<p>Hello</p> <b>World</b>'
        result = sanitize_html(html)
        assert "<p>" not in result
        assert "<b>" not in result
        assert "Hello" in result
        assert "World" in result
    
    def test_escapes_special_chars(self):
        """Special characters should be escaped."""
        text = 'Hello < World & "quoted"'
        result = sanitize_html(text)
        assert "&lt;" in result
        assert "&amp;" in result
        assert "&quot;" in result
    
    def test_normalizes_whitespace(self):
        """Multiple whitespace should be normalized."""
        text = "Hello    World\n\nTest"
        result = sanitize_html(text)
        assert "    " not in result
        assert "\n" not in result
    
    def test_handles_empty_input(self):
        """Empty or None input should return empty string."""
        assert sanitize_html("") == ""
        assert sanitize_html(None) == ""


class TestSanitizeUrl:
    """Test URL sanitization for security."""
    
    def test_allows_github_urls(self):
        """Valid GitHub URLs should pass through."""
        url = "https://github.com/microsoft/vscode"
        assert sanitize_url(url) == url
    
    def test_allows_api_github_urls(self):
        """API GitHub URLs should pass through."""
        url = "https://api.github.com/repos/microsoft/vscode"
        assert sanitize_url(url) == url
    
    def test_allows_raw_githubusercontent_urls(self):
        """Raw GitHub content URLs should pass through."""
        url = "https://raw.githubusercontent.com/microsoft/vscode/main/README.md"
        assert sanitize_url(url) == url
    
    def test_blocks_javascript_urls(self):
        """JavaScript URLs should be blocked."""
        url = "javascript:alert('xss')"
        assert sanitize_url(url) == ""
    
    def test_blocks_data_urls(self):
        """Data URLs should be blocked."""
        url = "data:text/html,<script>alert('xss')</script>"
        assert sanitize_url(url) == ""
    
    def test_blocks_non_github_domains(self):
        """Non-GitHub domains should be blocked."""
        assert sanitize_url("https://example.com/repo") == ""
        assert sanitize_url("https://malicious.com/github.com") == ""
    
    def test_handles_empty_input(self):
        """Empty or None input should return empty string."""
        assert sanitize_url("") == ""
        assert sanitize_url(None) == ""


# =============================================================================
# GitHub Service Tests
# =============================================================================

class TestGitHubServiceInit:
    """Test GitHub service initialization."""
    
    def test_creates_session(self):
        """Service should create a requests session."""
        service = GitHubService()
        assert service.session is not None
    
    def test_has_user_agent(self):
        """Session should have a user agent header."""
        service = GitHubService()
        assert "TrendRadar" in service.session.headers.get("User-Agent", "")
    
    def test_has_languages(self):
        """Service should have predefined languages."""
        service = GitHubService()
        assert "python" in service.LANGUAGES
        assert "javascript" in service.LANGUAGES
        assert "rust" in service.LANGUAGES
    
    def test_has_sort_options(self):
        """Service should have sort options."""
        service = GitHubService()
        assert "stars" in service.SORT_OPTIONS
        assert "forks" in service.SORT_OPTIONS
    
    def test_token_increases_rate_limit(self):
        """Token should increase rate limit."""
        service = GitHubService(token="test-token")
        assert service.RATE_LIMIT_REQUESTS == 30
        assert "Authorization" in service.session.headers


class TestGitHubSearch:
    """Test GitHub search functionality."""
    
    @pytest.fixture
    def service(self):
        """Create a fresh service instance."""
        return GitHubService()
    
    @pytest.fixture
    def sample_api_response(self):
        """Sample GitHub API response."""
        return {
            "total_count": 1,
            "incomplete_results": False,
            "items": [
                {
                    "name": "scrapy",
                    "full_name": "scrapy/scrapy",
                    "description": "Scrapy, a fast high-level web crawling & scraping framework for Python.",
                    "html_url": "https://github.com/scrapy/scrapy",
                    "homepage": "https://scrapy.org",
                    "stargazers_count": 50000,
                    "forks_count": 10000,
                    "open_issues_count": 100,
                    "watchers_count": 50000,
                    "language": "Python",
                    "topics": ["web-scraping", "python", "crawler"],
                    "license": {"name": "BSD-3-Clause"},
                    "created_at": "2010-02-22T02:00:00Z",
                    "updated_at": "2023-12-01T00:00:00Z",
                    "pushed_at": "2023-12-01T00:00:00Z",
                    "owner": {
                        "login": "scrapy",
                        "html_url": "https://github.com/scrapy",
                        "avatar_url": "https://github.com/scrapy.png"
                    },
                    "fork": False,
                    "archived": False,
                    "default_branch": "master"
                }
            ]
        }
    
    def test_search_returns_dict(self, service):
        """Search should return a dictionary."""
        with patch.object(service.session, 'get') as mock_get:
            mock_get.return_value = Mock(status_code=200, json=lambda: {"items": []})
            result = service.search_repos("web scraping")
            assert isinstance(result, dict)
    
    def test_search_includes_query(self, service):
        """Search result should include the original query."""
        with patch.object(service.session, 'get') as mock_get:
            mock_get.return_value = Mock(status_code=200, json=lambda: {"items": []})
            result = service.search_repos("web scraping")
            assert result.get("query") == "web scraping"
    
    def test_search_parses_repos(self, service, sample_api_response):
        """Search should parse repos from API response."""
        with patch.object(service.session, 'get') as mock_get:
            mock_get.return_value = Mock(status_code=200, json=lambda: sample_api_response)
            result = service.search_repos("web scraping")
            
            assert result.get("success") is True
            assert result.get("count") == 1
            repos = result.get("repos", [])
            assert len(repos) == 1
            assert repos[0]["name"] == "scrapy"
    
    def test_search_extracts_stars(self, service, sample_api_response):
        """Search should extract star count."""
        with patch.object(service.session, 'get') as mock_get:
            mock_get.return_value = Mock(status_code=200, json=lambda: sample_api_response)
            result = service.search_repos("web scraping")
            
            repos = result.get("repos", [])
            assert repos[0]["stars"] == 50000
    
    def test_search_extracts_language(self, service, sample_api_response):
        """Search should extract programming language."""
        with patch.object(service.session, 'get') as mock_get:
            mock_get.return_value = Mock(status_code=200, json=lambda: sample_api_response)
            result = service.search_repos("web scraping")
            
            repos = result.get("repos", [])
            assert repos[0]["language"] == "Python"
    
    def test_search_with_language_filter(self, service, sample_api_response):
        """Search should include language in query."""
        with patch.object(service.session, 'get') as mock_get:
            mock_get.return_value = Mock(status_code=200, json=lambda: sample_api_response)
            result = service.search_repos("web scraping", language="python")
            
            # Check that language was added to query
            call_args = mock_get.call_args
            params = call_args[1]["params"]
            assert "language:python" in params["q"]
    
    def test_search_with_min_stars(self, service, sample_api_response):
        """Search should filter by minimum stars."""
        with patch.object(service.session, 'get') as mock_get:
            mock_get.return_value = Mock(status_code=200, json=lambda: sample_api_response)
            service.search_repos("web scraping", min_stars=1000)
            
            call_args = mock_get.call_args
            params = call_args[1]["params"]
            assert "stars:>=1000" in params["q"]
    
    def test_search_handles_timeout(self, service):
        """Search should handle timeout gracefully."""
        import requests
        with patch.object(service.session, 'get') as mock_get:
            mock_get.side_effect = requests.Timeout()
            result = service.search_repos("web scraping")
            
            assert result.get("success") is False
            assert "timed out" in result.get("error", "").lower()
    
    def test_search_handles_api_error(self, service):
        """Search should handle API errors gracefully."""
        with patch.object(service.session, 'get') as mock_get:
            mock_get.return_value = Mock(status_code=500)
            result = service.search_repos("web scraping")
            
            assert result.get("success") is False
            assert "500" in result.get("error", "")
    
    def test_search_handles_rate_limit(self, service):
        """Search should handle rate limit response."""
        with patch.object(service.session, 'get') as mock_get:
            mock_get.return_value = Mock(status_code=403)
            result = service.search_repos("web scraping")
            
            assert result.get("success") is False
            assert "rate limit" in result.get("error", "").lower()
    
    def test_search_limits_results(self, service, sample_api_response):
        """Search should respect limit parameter."""
        with patch.object(service.session, 'get') as mock_get:
            mock_get.return_value = Mock(status_code=200, json=lambda: sample_api_response)
            service.search_repos("web scraping", limit=5)
            
            call_args = mock_get.call_args
            params = call_args[1]["params"]
            assert params["per_page"] == 5
    
    def test_search_caps_limit_at_30(self, service, sample_api_response):
        """Search should cap limit at 30."""
        with patch.object(service.session, 'get') as mock_get:
            mock_get.return_value = Mock(status_code=200, json=lambda: sample_api_response)
            service.search_repos("web scraping", limit=100)
            
            call_args = mock_get.call_args
            params = call_args[1]["params"]
            assert params["per_page"] == 30
    
    def test_empty_query_returns_error(self, service):
        """Empty query should return error."""
        result = service.search_repos("")
        assert result.get("success") is False
        assert "required" in result.get("error", "").lower()


class TestGitHubRateLimiting:
    """Test rate limiting functionality."""
    
    @pytest.fixture
    def service(self):
        """Create a fresh service instance."""
        service = GitHubService()
        # Use smaller window for testing
        service.RATE_LIMIT_REQUESTS = 3
        service.RATE_LIMIT_WINDOW = 1  # 1 second
        return service
    
    def test_allows_requests_under_limit(self, service):
        """Should allow requests under rate limit."""
        assert service._check_rate_limit() is True
        assert service._check_rate_limit() is True
    
    def test_blocks_requests_over_limit(self, service):
        """Should block requests over rate limit."""
        # Make max requests
        for _ in range(service.RATE_LIMIT_REQUESTS):
            service._check_rate_limit()
        
        # Next request should be blocked
        assert service._check_rate_limit() is False
    
    def test_resets_after_window(self, service):
        """Should reset after rate limit window."""
        # Make max requests
        for _ in range(service.RATE_LIMIT_REQUESTS):
            service._check_rate_limit()
        
        # Wait for window to expire
        time.sleep(service.RATE_LIMIT_WINDOW + 0.1)
        
        # Should be allowed again
        assert service._check_rate_limit() is True
    
    def test_get_rate_limit_wait(self, service):
        """Should return time to wait for reset."""
        service._check_rate_limit()
        wait = service._get_rate_limit_wait()
        
        # Should be close to the window time
        assert 0 <= wait <= service.RATE_LIMIT_WINDOW


class TestGitHubGetReadme:
    """Test README fetching."""
    
    @pytest.fixture
    def service(self):
        return GitHubService()
    
    def test_get_readme_success(self, service):
        """Should fetch README content."""
        with patch.object(service.session, 'get') as mock_get:
            mock_get.return_value = Mock(
                status_code=200,
                text="# Project Name\n\nThis is the README."
            )
            result = service.get_readme("owner", "repo")
            
            assert result.get("success") is True
            assert "Project Name" in result.get("content", "")
    
    def test_get_readme_truncates_long_content(self, service):
        """Should truncate very long README content."""
        long_content = "A" * 5000
        with patch.object(service.session, 'get') as mock_get:
            mock_get.return_value = Mock(status_code=200, text=long_content)
            result = service.get_readme("owner", "repo", max_length=100)
            
            assert result.get("truncated") is True
            assert len(result.get("content", "")) <= 150  # 100 + "... (truncated)"
    
    def test_get_readme_not_found(self, service):
        """Should handle README not found."""
        with patch.object(service.session, 'get') as mock_get:
            mock_get.return_value = Mock(status_code=404)
            result = service.get_readme("owner", "repo")
            
            assert result.get("success") is False
            assert "not found" in result.get("error", "").lower()
    
    def test_get_readme_removes_scripts(self, service):
        """Should remove script tags from README."""
        content = "<script>alert('xss')</script>Safe content"
        with patch.object(service.session, 'get') as mock_get:
            mock_get.return_value = Mock(status_code=200, text=content)
            result = service.get_readme("owner", "repo")
            
            assert "<script>" not in result.get("content", "")
            assert "Safe content" in result.get("content", "")


class TestGitHubHelpers:
    """Test helper methods."""
    
    def test_get_languages(self):
        """Should return language list."""
        service = GitHubService()
        result = service.get_languages()
        
        assert result.get("success") is True
        assert "python" in result.get("languages", [])
        assert "javascript" in result.get("languages", [])
    
    def test_get_sort_options(self):
        """Should return sort options."""
        service = GitHubService()
        result = service.get_sort_options()
        
        assert result.get("success") is True
        assert "stars" in result.get("sort_options", {})


# =============================================================================
# Singleton Tests
# =============================================================================

class TestGitHubSingleton:
    """Test singleton pattern."""
    
    def test_get_github_service_returns_same_instance(self):
        """get_github_service should return the same instance."""
        # Reset singleton
        import mcp_server.services.github_service as module
        module._github_service = None
        
        service1 = get_github_service()
        service2 = get_github_service()
        
        assert service1 is service2
    
    def test_singleton_is_github_service(self):
        """Singleton should be a GitHubService instance."""
        import mcp_server.services.github_service as module
        module._github_service = None
        
        service = get_github_service()
        assert isinstance(service, GitHubService)


# =============================================================================
# Security Tests
# =============================================================================

class TestGitHubSecurity:
    """Test security measures in GitHub service."""
    
    def test_xss_in_description_sanitized(self):
        """XSS in repo description should be sanitized."""
        service = GitHubService()
        response = {
            "total_count": 1,
            "items": [{
                "name": "test",
                "full_name": "test/test",
                "description": "<script>alert('xss')</script>Safe desc",
                "html_url": "https://github.com/test/test",
                "stargazers_count": 100,
                "forks_count": 10,
                "language": "Python",
                "topics": [],
                "owner": {"login": "test", "html_url": "https://github.com/test"},
            }]
        }
        
        with patch.object(service.session, 'get') as mock_get:
            mock_get.return_value = Mock(status_code=200, json=lambda: response)
            result = service.search_repos("test")
            
            repo = result["repos"][0]
            assert "<script>" not in repo["description"]
    
    def test_malicious_url_blocked(self):
        """Malicious URLs should be blocked."""
        service = GitHubService()
        response = {
            "total_count": 1,
            "items": [{
                "name": "test",
                "full_name": "test/test",
                "description": "Test",
                "html_url": "javascript:alert('xss')",
                "stargazers_count": 100,
                "forks_count": 10,
                "language": "Python",
                "topics": [],
                "owner": {"login": "test", "html_url": "https://github.com/test"},
            }]
        }
        
        with patch.object(service.session, 'get') as mock_get:
            mock_get.return_value = Mock(status_code=200, json=lambda: response)
            result = service.search_repos("test")
            
            repo = result["repos"][0]
            assert "javascript:" not in repo["url"]
            assert repo["url"] == ""  # Should be blocked
