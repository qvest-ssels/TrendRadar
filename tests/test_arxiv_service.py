"""
Tests for ArXiv Service

Tests sanitization, API calls, XML parsing, and university linking.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from mcp_server.services.arxiv_service import (
    ArxivService,
    get_arxiv_service,
    sanitize_html,
    sanitize_url,
)


# =============================================================================
# Sanitization Tests
# =============================================================================

class TestSanitizeHtml:
    """Test HTML sanitization for XSS prevention."""
    
    def test_removes_script_tags(self):
        """Script tags should be completely removed."""
        dangerous = '<script>alert("xss")</script>Hello'
        result = sanitize_html(dangerous)
        assert "<script>" not in result
        # Content inside script tags is kept but escaped
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
        # Should have single spaces, no newlines
        assert "    " not in result
        assert "\n" not in result
    
    def test_handles_empty_input(self):
        """Empty or None input should return empty string."""
        assert sanitize_html("") == ""
        assert sanitize_html(None) == ""
    
    def test_removes_event_handlers(self):
        """Event handler attributes should be removed."""
        dangerous = '<div onclick="alert()">Content</div>'
        result = sanitize_html(dangerous)
        assert "onclick" not in result
        assert "Content" in result


class TestSanitizeUrl:
    """Test URL sanitization for security."""
    
    def test_allows_arxiv_urls(self):
        """Valid arXiv URLs should pass through."""
        url = "https://arxiv.org/abs/2301.07041"
        assert sanitize_url(url) == url
    
    def test_allows_export_arxiv_urls(self):
        """Export arXiv URLs should pass through."""
        url = "http://export.arxiv.org/api/query"
        assert sanitize_url(url) == url
    
    def test_blocks_javascript_urls(self):
        """JavaScript URLs should be blocked."""
        url = "javascript:alert('xss')"
        assert sanitize_url(url) == ""
    
    def test_blocks_data_urls(self):
        """Data URLs should be blocked."""
        url = "data:text/html,<script>alert('xss')</script>"
        assert sanitize_url(url) == ""
    
    def test_blocks_non_arxiv_domains(self):
        """Non-arXiv domains should be blocked."""
        assert sanitize_url("https://example.com/paper") == ""
        assert sanitize_url("https://malicious.com/arxiv.org") == ""
    
    def test_handles_empty_input(self):
        """Empty or None input should return empty string."""
        assert sanitize_url("") == ""
        assert sanitize_url(None) == ""
    
    def test_blocks_vbscript(self):
        """VBScript URLs should be blocked."""
        url = "vbscript:msgbox('xss')"
        assert sanitize_url(url) == ""


# =============================================================================
# ArXiv Service Tests
# =============================================================================

class TestArxivServiceInit:
    """Test ArXiv service initialization."""
    
    def test_creates_session(self):
        """Service should create a requests session."""
        service = ArxivService()
        assert service.session is not None
    
    def test_has_user_agent(self):
        """Session should have a user agent header."""
        service = ArxivService()
        assert "TrendRadar" in service.session.headers.get("User-Agent", "")
    
    def test_has_categories(self):
        """Service should have predefined categories."""
        service = ArxivService()
        assert "cs.AI" in service.CATEGORIES
        assert "cs.LG" in service.CATEGORIES
        assert "cs.CL" in service.CATEGORIES


class TestArxivSearch:
    """Test arXiv search functionality."""
    
    @pytest.fixture
    def service(self):
        """Create a fresh service instance."""
        return ArxivService()
    
    @pytest.fixture
    def sample_atom_response(self):
        """Sample arXiv Atom XML response."""
        return '''<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2301.07041v1</id>
    <title>Attention Is All You Need</title>
    <summary>We propose a new simple network architecture, the Transformer.</summary>
    <author>
      <name>Ashish Vaswani</name>
      <arxiv:affiliation>Google Brain</arxiv:affiliation>
    </author>
    <author>
      <name>Noam Shazeer</name>
      <arxiv:affiliation>Google Brain</arxiv:affiliation>
    </author>
    <published>2023-01-17T18:58:10Z</published>
    <updated>2023-01-17T18:58:10Z</updated>
    <link title="pdf" href="http://arxiv.org/pdf/2301.07041v1"/>
    <arxiv:primary_category term="cs.CL"/>
    <category term="cs.CL"/>
    <category term="cs.LG"/>
  </entry>
</feed>'''
    
    def test_search_returns_dict(self, service):
        """Search should return a dictionary."""
        with patch.object(service.session, 'get') as mock_get:
            mock_get.return_value = Mock(status_code=200, text="<feed></feed>")
            result = service.search("transformer")
            assert isinstance(result, dict)
    
    def test_search_includes_query(self, service):
        """Search result should include the original query."""
        with patch.object(service.session, 'get') as mock_get:
            mock_get.return_value = Mock(status_code=200, text="<feed></feed>")
            result = service.search("neural networks")
            assert result.get("query") == "neural networks"
    
    def test_search_parses_papers(self, service, sample_atom_response):
        """Search should parse papers from Atom XML."""
        with patch.object(service.session, 'get') as mock_get:
            mock_get.return_value = Mock(status_code=200, text=sample_atom_response)
            # Disable university linking to avoid Wikipedia calls
            result = service.search("transformer", include_university_links=False)
            
            assert result.get("success") is True
            assert result.get("count") == 1
            papers = result.get("papers", [])
            assert len(papers) == 1
            assert "Attention" in papers[0]["title"]
    
    def test_search_extracts_authors(self, service, sample_atom_response):
        """Search should extract author names."""
        with patch.object(service.session, 'get') as mock_get:
            mock_get.return_value = Mock(status_code=200, text=sample_atom_response)
            result = service.search("transformer", include_university_links=False)
            
            papers = result.get("papers", [])
            assert len(papers[0]["authors"]) >= 1
            assert "Vaswani" in papers[0]["authors"][0]
    
    def test_search_extracts_affiliations(self, service, sample_atom_response):
        """Search should extract author affiliations."""
        with patch.object(service.session, 'get') as mock_get:
            mock_get.return_value = Mock(status_code=200, text=sample_atom_response)
            result = service.search("transformer", include_university_links=False)
            
            papers = result.get("papers", [])
            assert "Google" in str(papers[0]["affiliations"])
    
    def test_search_with_category(self, service, sample_atom_response):
        """Search should filter by category."""
        with patch.object(service.session, 'get') as mock_get:
            mock_get.return_value = Mock(status_code=200, text=sample_atom_response)
            result = service.search("transformer", category="cs.CL", include_university_links=False)
            
            assert result.get("category") == "cs.CL"
            assert "Computation and Language" in result.get("category_name", "")
    
    def test_search_handles_timeout(self, service):
        """Search should handle timeout gracefully."""
        import requests
        with patch.object(service.session, 'get') as mock_get:
            mock_get.side_effect = requests.Timeout()
            result = service.search("transformer")
            
            assert result.get("success") is False
            assert "timed out" in result.get("error", "").lower()
    
    def test_search_handles_api_error(self, service):
        """Search should handle API errors gracefully."""
        with patch.object(service.session, 'get') as mock_get:
            mock_get.return_value = Mock(status_code=500, text="Internal Server Error")
            result = service.search("transformer")
            
            assert result.get("success") is False
            assert "500" in result.get("error", "")
    
    def test_search_limits_results(self, service):
        """Search should respect max_results limit."""
        with patch.object(service.session, 'get') as mock_get:
            # The limit should be passed to the API
            mock_get.return_value = Mock(status_code=200, text="<feed></feed>")
            service.search("transformer", max_results=5)
            
            call_args = mock_get.call_args
            params = call_args[1]["params"]
            assert params["max_results"] == 5
    
    def test_search_caps_max_results_at_50(self, service):
        """Search should cap max_results at 50."""
        with patch.object(service.session, 'get') as mock_get:
            mock_get.return_value = Mock(status_code=200, text="<feed></feed>")
            service.search("transformer", max_results=100)
            
            call_args = mock_get.call_args
            params = call_args[1]["params"]
            assert params["max_results"] == 50


class TestArxivGetPaper:
    """Test getting individual paper by ID."""
    
    @pytest.fixture
    def service(self):
        return ArxivService()
    
    @pytest.fixture
    def sample_paper_response(self):
        return '''<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2301.07041v1</id>
    <title>Test Paper Title</title>
    <summary>This is a test abstract.</summary>
    <author><name>Test Author</name></author>
    <published>2023-01-17T18:58:10Z</published>
    <updated>2023-01-17T18:58:10Z</updated>
    <arxiv:primary_category term="cs.AI"/>
  </entry>
</feed>'''
    
    def test_get_paper_by_id(self, service, sample_paper_response):
        """Should retrieve paper by arXiv ID."""
        with patch.object(service.session, 'get') as mock_get:
            mock_get.return_value = Mock(status_code=200, text=sample_paper_response)
            result = service.get_paper("2301.07041")
            
            assert result.get("success") is True
            assert result.get("paper") is not None
            assert "Test Paper" in result["paper"]["title"]
    
    def test_get_paper_not_found(self, service):
        """Should handle paper not found."""
        with patch.object(service.session, 'get') as mock_get:
            # Empty feed = no paper
            mock_get.return_value = Mock(status_code=200, text="<feed></feed>")
            result = service.get_paper("nonexistent")
            
            assert result.get("success") is False
            assert "not found" in result.get("error", "").lower()


class TestArxivCategories:
    """Test category retrieval."""
    
    def test_get_categories(self):
        """Should return category dictionary."""
        service = ArxivService()
        result = service.get_categories()
        
        assert result.get("success") is True
        assert isinstance(result.get("categories"), dict)
        assert "cs.AI" in result["categories"]
        assert "Machine Learning" in str(result["categories"])


class TestArxivUniversityLinking:
    """Test university linking via Wikipedia."""
    
    @pytest.fixture
    def service(self):
        return ArxivService()
    
    def test_known_universities_mapped(self, service):
        """Known universities should be in the mapping."""
        assert "MIT" in service.KNOWN_UNIVERSITIES
        assert "Stanford" in service.KNOWN_UNIVERSITIES
        assert "OpenAI" in service.KNOWN_UNIVERSITIES
    
    def test_get_university_links_without_wikipedia(self, service):
        """Should create fallback links without Wikipedia."""
        # Set Wikipedia service to None explicitly
        service._wikipedia_service = None
        
        # Mock _get_wikipedia_service to return None
        with patch.object(service, '_get_wikipedia_service', return_value=None):
            links = service._get_university_links(["MIT research lab", "Stanford AI Lab"])
            
            # Should still return links using fallback
            assert len(links) > 0
            # Check that any link contains MIT or Stanford
            all_names = [link.get("name", "") for link in links]
            assert any("MIT" in name or "Massachusetts" in name for name in all_names) or \
                   any("Stanford" in name for name in all_names)
    
    def test_get_university_links_with_wikipedia(self, service):
        """Should enrich links with Wikipedia data."""
        mock_wiki = Mock()
        mock_wiki.get_summary.return_value = {
            "success": True,
            "url": "https://en.wikipedia.org/wiki/MIT",
            "description": "Private research university"
        }
        
        service._wikipedia_service = mock_wiki
        with patch.object(service, '_get_wikipedia_service', return_value=mock_wiki):
            links = service._get_university_links(["MIT"])
            
            # Should have Wikipedia URL
            assert len(links) > 0
            assert "wikipedia" in links[0].get("wikipedia_url", "").lower()


# =============================================================================
# Singleton Tests
# =============================================================================

class TestArxivSingleton:
    """Test singleton pattern."""
    
    def test_get_arxiv_service_returns_same_instance(self):
        """get_arxiv_service should return the same instance."""
        # Reset singleton
        import mcp_server.services.arxiv_service as module
        module._arxiv_service = None
        
        service1 = get_arxiv_service()
        service2 = get_arxiv_service()
        
        assert service1 is service2
    
    def test_singleton_is_arxiv_service(self):
        """Singleton should be an ArxivService instance."""
        import mcp_server.services.arxiv_service as module
        module._arxiv_service = None
        
        service = get_arxiv_service()
        assert isinstance(service, ArxivService)


# =============================================================================
# Integration-style Tests (mocked but realistic)
# =============================================================================

class TestArxivRealWorldScenarios:
    """Test realistic usage scenarios with mocked responses."""
    
    @pytest.fixture
    def service(self):
        return ArxivService()
    
    def test_search_nlp_papers(self, service):
        """Search for NLP papers in cs.CL category."""
        response = '''<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2005.14165v4</id>
    <title>Language Models are Few-Shot Learners</title>
    <summary>We demonstrate that scaling up language models greatly improves task-agnostic, few-shot performance.</summary>
    <author><name>Tom B. Brown</name><arxiv:affiliation>OpenAI</arxiv:affiliation></author>
    <published>2020-05-28T17:29:03Z</published>
    <updated>2020-07-22T17:58:33Z</updated>
    <arxiv:primary_category term="cs.CL"/>
    <category term="cs.CL"/>
    <arxiv:comment>40+32 pages</arxiv:comment>
  </entry>
</feed>'''
        
        with patch.object(service.session, 'get') as mock_get:
            mock_get.return_value = Mock(status_code=200, text=response)
            result = service.search("GPT-3", category="cs.CL", include_university_links=False)
            
            assert result["success"] is True
            assert result["count"] == 1
            paper = result["papers"][0]
            assert "Few-Shot" in paper["title"]
            assert "OpenAI" in str(paper["affiliations"])
            assert paper["primary_category"] == "cs.CL"
            assert "40+32 pages" in paper["comment"]
    
    def test_search_computer_vision(self, service):
        """Search for computer vision papers."""
        response = '''<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2010.11929v2</id>
    <title>An Image is Worth 16x16 Words: Transformers for Image Recognition at Scale</title>
    <summary>We apply a standard Transformer directly to images.</summary>
    <author><name>Alexey Dosovitskiy</name><arxiv:affiliation>Google Brain</arxiv:affiliation></author>
    <published>2020-10-22T17:55:40Z</published>
    <updated>2021-06-03T08:56:57Z</updated>
    <arxiv:primary_category term="cs.CV"/>
    <link title="pdf" href="http://arxiv.org/pdf/2010.11929v2"/>
  </entry>
</feed>'''
        
        with patch.object(service.session, 'get') as mock_get:
            mock_get.return_value = Mock(status_code=200, text=response)
            result = service.search("vision transformer", category="cs.CV", include_university_links=False)
            
            assert result["success"] is True
            paper = result["papers"][0]
            assert "16x16" in paper["title"]
            assert paper["primary_category"] == "cs.CV"
            assert "arxiv.org" in paper["pdf_url"]


# =============================================================================
# Security Tests
# =============================================================================

class TestArxivSecurity:
    """Test security measures in arXiv service."""
    
    def test_xss_in_title_sanitized(self):
        """XSS in paper title should be sanitized."""
        service = ArxivService()
        response = '''<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/test</id>
    <title>&lt;script&gt;alert('xss')&lt;/script&gt;Safe Title</title>
    <summary>Test</summary>
    <author><name>Author</name></author>
    <published>2023-01-01T00:00:00Z</published>
    <updated>2023-01-01T00:00:00Z</updated>
    <arxiv:primary_category term="cs.AI"/>
  </entry>
</feed>'''
        
        with patch.object(service.session, 'get') as mock_get:
            mock_get.return_value = Mock(status_code=200, text=response)
            result = service.search("test", include_university_links=False)
            
            paper = result["papers"][0]
            # Script tags should be removed (content remains but escaped)
            assert "<script>" not in paper["title"]
            assert "</script>" not in paper["title"]
            # Safe content should be present
            assert "Safe Title" in paper["title"]
    
    def test_xss_in_abstract_sanitized(self):
        """XSS in abstract should be sanitized."""
        service = ArxivService()
        response = '''<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/test</id>
    <title>Safe Title</title>
    <summary>&lt;img src=x onerror=alert(1)&gt;Safe summary</summary>
    <author><name>Author</name></author>
    <published>2023-01-01T00:00:00Z</published>
    <updated>2023-01-01T00:00:00Z</updated>
    <arxiv:primary_category term="cs.AI"/>
  </entry>
</feed>'''
        
        with patch.object(service.session, 'get') as mock_get:
            mock_get.return_value = Mock(status_code=200, text=response)
            result = service.search("test", include_university_links=False)
            
            paper = result["papers"][0]
            assert "<img" not in paper["abstract"]
            assert "onerror" not in paper["abstract"]
    
    def test_malicious_url_blocked(self):
        """Malicious URLs in PDF link should be blocked."""
        service = ArxivService()
        response = '''<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/test</id>
    <title>Test</title>
    <summary>Test</summary>
    <author><name>Author</name></author>
    <published>2023-01-01T00:00:00Z</published>
    <updated>2023-01-01T00:00:00Z</updated>
    <arxiv:primary_category term="cs.AI"/>
    <link title="pdf" href="javascript:alert('xss')"/>
  </entry>
</feed>'''
        
        with patch.object(service.session, 'get') as mock_get:
            mock_get.return_value = Mock(status_code=200, text=response)
            result = service.search("test", include_university_links=False)
            
            paper = result["papers"][0]
            # Should use fallback URL, not the malicious one
            assert "javascript:" not in paper["pdf_url"]
            assert "arxiv.org" in paper["pdf_url"]
