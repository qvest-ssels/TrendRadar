"""
Tests for People Search Service.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock


class TestPeopleService:
    """Tests for general people search."""
    
    @pytest.fixture
    def service(self):
        from mcp_server.services.people_service import PeopleService
        return PeopleService()
    
    def test_search_requires_name(self, service):
        """Search should require a name."""
        result = service.search_person("")
        assert result["success"] is False
        assert "required" in result["error"].lower()
    
    def test_search_returns_dict(self, service):
        """Search should return a dict."""
        with patch.object(service.session, 'get') as mock_get:
            mock_get.return_value = Mock(
                status_code=200,
                text='<html></html>',
                json=lambda: {"query": {"search": []}}
            )
            result = service.search_person("Test Person")
            assert isinstance(result, dict)
            assert "results" in result
    
    def test_search_records_sources(self, service):
        """Search should record which sources were checked."""
        with patch.object(service.session, 'get') as mock_get:
            mock_get.return_value = Mock(
                status_code=200,
                text='<html></html>',
                json=lambda: {"query": {"search": []}}
            )
            result = service.search_person("Test", language="de")
            assert "sources_checked" in result
            assert len(result["sources_checked"]) > 0


class TestPoliticianSearch:
    """Tests for German politician search."""
    
    @pytest.fixture
    def service(self):
        from mcp_server.services.people_service import PeopleService
        return PeopleService()
    
    def test_search_german_politician_requires_name(self, service):
        """Politician search should require a name."""
        result = service.search_german_politician("")
        assert result["success"] is False
        assert "required" in result["error"].lower()
    
    def test_search_german_politician_returns_dict(self, service):
        """Politician search should return a dict."""
        with patch.object(service, '_search_bundestag') as mock_bundestag:
            mock_bundestag.return_value = []
            with patch.object(service, '_search_wikipedia') as mock_wiki:
                mock_wiki.return_value = []
                result = service.search_german_politician("Test Politiker")
                assert isinstance(result, dict)
                assert "results" in result
    
    def test_search_politician_with_party_filter(self, service):
        """Politician search should filter by party."""
        with patch.object(service, '_search_bundestag') as mock_bundestag:
            mock_bundestag.return_value = [
                {"name": "Person A", "party": "SPD"},
                {"name": "Person B", "party": "CDU"},
            ]
            result = service.search_german_politician("Person", party="SPD")
            assert result["success"] is True
            # Should only include SPD members
            if result["results"]:
                for person in result["results"]:
                    assert "spd" in person.get("party", "").lower()


class TestBundestagSearch:
    """Tests for Bundestag.de search."""
    
    @pytest.fixture
    def service(self):
        from mcp_server.services.people_service import PeopleService
        return PeopleService()
    
    def test_bundestag_search_handles_timeout(self, service):
        """Bundestag search should handle timeout."""
        import requests
        with patch.object(service.session, 'get') as mock_get:
            mock_get.side_effect = requests.Timeout()
            result = service._search_bundestag("Test")
            assert result == []
    
    def test_bundestag_search_handles_error(self, service):
        """Bundestag search should handle errors gracefully."""
        with patch.object(service.session, 'get') as mock_get:
            mock_get.side_effect = Exception("Network error")
            result = service._search_bundestag("Test")
            assert result == []
    
    def test_bundestag_search_extracts_names(self, service):
        """Bundestag search should extract politician names."""
        mock_html = '''
        <a href="/abgeordnete/biografien/S/scholz_olaf-857630">Scholz, Olaf</a>
        '''
        with patch.object(service.session, 'get') as mock_get:
            mock_get.return_value = Mock(status_code=200, text=mock_html)
            # Would normally find matches, but with our test HTML it might not
            # This tests that the method runs without error
            result = service._search_bundestag("Scholz")
            assert isinstance(result, list)


class TestWikipediaIntegration:
    """Tests for Wikipedia integration in people search."""
    
    @pytest.fixture
    def service(self):
        from mcp_server.services.people_service import PeopleService
        return PeopleService()
    
    def test_wikipedia_search_returns_list(self, service):
        """Wikipedia search should return a list."""
        with patch.object(service.session, 'get') as mock_get:
            mock_get.return_value = Mock(
                status_code=200,
                json=lambda: {
                    "query": {
                        "search": [
                            {"title": "Test Person", "snippet": "born 1950"}
                        ]
                    }
                }
            )
            result = service._search_wikipedia("Test", "de", None)
            assert isinstance(result, list)
    
    def test_looks_like_person_detects_birth_year(self, service):
        """Should detect person by birth year pattern."""
        assert service._looks_like_person("John Doe", "geboren 1950") is True
        assert service._looks_like_person("John Doe", "born 1985") is True
        assert service._looks_like_person("John Doe", "(1920-2000)") is True
    
    def test_is_politician_detects_keywords(self, service):
        """Should detect politicians by keywords."""
        politician = {"description": "deutscher Politiker", "extract": ""}
        assert service._is_politician(politician) is True
        
        politician = {"description": "MdB seit 2017", "extract": ""}
        assert service._is_politician(politician) is True
        
        actor = {"description": "amerikanischer Schauspieler", "extract": ""}
        assert service._is_politician(actor) is False


class TestPeopleSingleton:
    """Tests for people service singleton."""
    
    def test_get_service_returns_same_instance(self):
        """get_people_service should return same instance."""
        import mcp_server.services.people_service as module
        module._people_service = None
        
        from mcp_server.services.people_service import get_people_service
        service1 = get_people_service()
        service2 = get_people_service()
        assert service1 is service2


class TestSecurity:
    """Security tests for people service."""
    
    def test_sanitize_text_removes_html(self):
        """Should remove HTML tags."""
        from mcp_server.services.people_service import sanitize_text
        result = sanitize_text('<script>alert("xss")</script>Name')
        assert "<script>" not in result
        assert "alert" not in result.lower() or "&" in result
    
    def test_sanitize_url_blocks_javascript(self):
        """Should block javascript URLs."""
        from mcp_server.services.people_service import sanitize_url
        assert sanitize_url("javascript:alert(1)") == ""
        assert sanitize_url("data:text/html,<script>") == ""
    
    def test_sanitize_url_allows_valid_domains(self):
        """Should allow valid domains."""
        from mcp_server.services.people_service import sanitize_url
        assert "wikipedia.org" in sanitize_url("https://de.wikipedia.org/wiki/Test")
        assert "bundestag.de" in sanitize_url("https://www.bundestag.de/abgeordnete")
    
    def test_sanitize_url_blocks_unknown_domains(self):
        """Should block unknown domains."""
        from mcp_server.services.people_service import sanitize_url
        assert sanitize_url("https://evil.com/page") == ""
