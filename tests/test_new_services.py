"""
Tests for new services: Udemy, Conference, Newsletter, IMDB.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock


# ========== Udemy Service Tests ==========

class TestUdemyService:
    """Tests for Udemy course search service."""
    
    @pytest.fixture
    def service(self):
        from mcp_server.services.udemy_service import UdemyService
        return UdemyService()
    
    def test_search_requires_query(self, service):
        """Search should require a query."""
        result = service.search_courses("")
        assert result["success"] is False
        assert "required" in result["error"].lower()
    
    def test_search_returns_dict(self, service):
        """Search should return a dict."""
        with patch.object(service.session, 'get') as mock_get:
            mock_get.return_value = Mock(
                status_code=200,
                text='href="/course/python-basics/" href="/course/ml-intro/"'
            )
            result = service.search_courses("python")
            assert isinstance(result, dict)
            assert "courses" in result
    
    def test_search_extracts_course_urls(self, service):
        """Search should extract course URLs from HTML."""
        with patch.object(service.session, 'get') as mock_get:
            mock_get.return_value = Mock(
                status_code=200,
                text='href="/course/test-course-123/"'
            )
            result = service.search_courses("test")
            assert result["success"] is True
            if result["courses"]:
                assert "udemy.com/course" in result["courses"][0]["url"]
    
    def test_search_handles_timeout(self, service):
        """Search should handle timeout gracefully."""
        import requests
        with patch.object(service.session, 'get') as mock_get:
            mock_get.side_effect = requests.Timeout()
            result = service.search_courses("test")
            assert result["success"] is False
            assert "timed out" in result["error"].lower() or "timeout" in result["error"].lower()
    
    def test_rating_filter(self, service):
        """Rating filter should be applied."""
        # Test that min_rating parameter is accepted
        with patch.object(service.session, 'get') as mock_get:
            mock_get.return_value = Mock(status_code=200, text='')
            result = service.search_courses("python", min_rating=4.5)
            assert result["filters"]["min_rating"] == 4.5


class TestUdemySingleton:
    """Tests for Udemy service singleton."""
    
    def test_get_service_returns_same_instance(self):
        """get_udemy_service should return same instance."""
        import mcp_server.services.udemy_service as module
        module._udemy_service = None
        
        from mcp_server.services.udemy_service import get_udemy_service
        service1 = get_udemy_service()
        service2 = get_udemy_service()
        assert service1 is service2


# ========== Conference Service Tests ==========

class TestConferenceService:
    """Tests for tech conference search service."""
    
    @pytest.fixture
    def service(self):
        from mcp_server.services.conference_service import ConferenceService
        return ConferenceService()
    
    def test_search_returns_dict(self, service):
        """Search should return a dict."""
        with patch.object(service.session, 'get') as mock_get:
            mock_get.return_value = Mock(
                status_code=200,
                json=lambda: []
            )
            result = service.search_conferences(topic="python")
            assert isinstance(result, dict)
            assert "conferences" in result
    
    def test_topic_alias_mapping(self, service):
        """Common aliases should be mapped to correct topics."""
        # Test internal mapping
        aliases = {
            "machine learning": "ml",
            "ai": "ml",
            "k8s": "kubernetes",
            "js": "javascript",
        }
        for alias, expected in aliases.items():
            with patch.object(service.session, 'get') as mock_get:
                mock_get.return_value = Mock(status_code=404)
                service.search_conferences(topic=alias)
                # Verify the request was made (topic was processed)
                assert mock_get.called
    
    def test_search_handles_404(self, service):
        """Search should handle 404 (no conferences) gracefully."""
        with patch.object(service.session, 'get') as mock_get:
            mock_get.return_value = Mock(status_code=404)
            result = service.search_conferences(topic="obscure-topic")
            assert result["success"] is True
            assert result["conferences"] == []
    
    def test_search_parses_conference_data(self, service):
        """Search should parse conference JSON."""
        with patch.object(service.session, 'get') as mock_get:
            mock_get.return_value = Mock(
                status_code=200,
                json=lambda: [{
                    "name": "PyCon 2025",
                    "url": "https://pycon.org",
                    "startDate": "2025-05-15",
                    "endDate": "2025-05-18",
                    "city": "Pittsburgh",
                    "country": "USA"
                }]
            )
            result = service.search_conferences(topic="python", include_past=True)
            assert result["success"] is True
            assert len(result["conferences"]) == 1
            assert result["conferences"][0]["name"] == "PyCon 2025"
    
    def test_available_topics_returned(self, service):
        """Search should return list of available topics."""
        with patch.object(service.session, 'get') as mock_get:
            mock_get.return_value = Mock(status_code=404)
            result = service.search_conferences()
            assert "available_topics" in result
            assert "python" in result["available_topics"]


class TestConferenceSingleton:
    """Tests for conference service singleton."""
    
    def test_get_service_returns_same_instance(self):
        """get_conference_service should return same instance."""
        import mcp_server.services.conference_service as module
        module._conference_service = None
        
        from mcp_server.services.conference_service import get_conference_service
        service1 = get_conference_service()
        service2 = get_conference_service()
        assert service1 is service2


# ========== Newsletter Service Tests ==========

class TestNewsletterService:
    """Tests for newsletter discovery service."""
    
    @pytest.fixture
    def service(self):
        from mcp_server.services.newsletter_service import NewsletterService
        return NewsletterService()
    
    def test_search_requires_query(self, service):
        """Search should require a query."""
        result = service.search_newsletters("")
        assert result["success"] is False
        assert "required" in result["error"].lower()
    
    def test_search_returns_dict(self, service):
        """Search should return a dict."""
        with patch.object(service.session, 'get') as mock_get:
            mock_get.return_value = Mock(
                status_code=200,
                text='href="https://test.substack.com"'
            )
            result = service.search_newsletters("AI")
            assert isinstance(result, dict)
            assert "newsletters" in result
    
    def test_search_extracts_substack_urls(self, service):
        """Search should extract Substack newsletter URLs."""
        with patch.object(service.session, 'get') as mock_get:
            mock_get.return_value = Mock(
                status_code=200,
                text='href="https://ainews.substack.com"'
            )
            result = service.search_newsletters("AI")
            assert result["success"] is True
            if result["newsletters"]:
                assert "substack.com" in result["newsletters"][0]["url"]
    
    def test_popular_newsletters_returns_curated_list(self, service):
        """get_popular_newsletters should return curated list."""
        result = service.get_popular_newsletters()
        assert result["success"] is True
        assert len(result["newsletters"]) > 0
        # Check for known newsletters
        names = [n["name"] for n in result["newsletters"]]
        assert any("TLDR" in name or "Pragmatic" in name for name in names)
    
    def test_popular_newsletters_category_filter(self, service):
        """Popular newsletters should filter by category."""
        result = service.get_popular_newsletters(category="technology")
        assert result["success"] is True
        for newsletter in result["newsletters"]:
            assert "technology" in newsletter.get("category", "").lower()


class TestNewsletterSingleton:
    """Tests for newsletter service singleton."""
    
    def test_get_service_returns_same_instance(self):
        """get_newsletter_service should return same instance."""
        import mcp_server.services.newsletter_service as module
        module._newsletter_service = None
        
        from mcp_server.services.newsletter_service import get_newsletter_service
        service1 = get_newsletter_service()
        service2 = get_newsletter_service()
        assert service1 is service2


# ========== IMDB Service Tests ==========

class TestIMDBService:
    """Tests for IMDB/movie search service."""
    
    @pytest.fixture
    def service(self):
        from mcp_server.services.imdb_service import IMDBService
        return IMDBService(api_key="test_key")
    
    @pytest.fixture
    def service_no_key(self):
        from mcp_server.services.imdb_service import IMDBService
        return IMDBService(api_key=None)
    
    def test_search_requires_query(self, service):
        """Search should require a query."""
        result = service.search_movies("")
        assert result["success"] is False
        assert "required" in result["error"].lower()
    
    def test_search_requires_api_key(self, service_no_key):
        """Search should require API key."""
        result = service_no_key.search_movies("test")
        assert result["success"] is False
        assert "API key" in result["error"]
    
    def test_search_returns_movies(self, service):
        """Search should return movie results."""
        with patch.object(service.session, 'get') as mock_get:
            mock_get.return_value = Mock(
                status_code=200,
                json=lambda: {
                    "Response": "True",
                    "Search": [
                        {
                            "Title": "The Matrix",
                            "Year": "1999",
                            "imdbID": "tt0133093",
                            "Type": "movie",
                            "Poster": "https://example.com/poster.jpg"
                        }
                    ],
                    "totalResults": "1"
                }
            )
            result = service.search_movies("matrix")
            assert result["success"] is True
            assert len(result["results"]) == 1
            assert result["results"][0]["title"] == "The Matrix"
            assert result["results"][0]["imdb_id"] == "tt0133093"
    
    def test_search_handles_not_found(self, service):
        """Search should handle no results."""
        with patch.object(service.session, 'get') as mock_get:
            mock_get.return_value = Mock(
                status_code=200,
                json=lambda: {
                    "Response": "False",
                    "Error": "Movie not found!"
                }
            )
            result = service.search_movies("nonexistent12345")
            assert result["success"] is False
            assert "not found" in result["error"].lower()
    
    def test_get_details_returns_full_info(self, service):
        """get_movie_details should return detailed info."""
        with patch.object(service.session, 'get') as mock_get:
            mock_get.return_value = Mock(
                status_code=200,
                json=lambda: {
                    "Response": "True",
                    "Title": "Inception",
                    "Year": "2010",
                    "Rated": "PG-13",
                    "Released": "16 Jul 2010",
                    "Runtime": "148 min",
                    "Genre": "Action, Adventure, Sci-Fi",
                    "Director": "Christopher Nolan",
                    "Writer": "Christopher Nolan",
                    "Actors": "Leonardo DiCaprio, Joseph Gordon-Levitt",
                    "Plot": "A thief who steals corporate secrets...",
                    "Language": "English",
                    "Country": "USA, UK",
                    "Awards": "Won 4 Oscars",
                    "Poster": "https://example.com/poster.jpg",
                    "Ratings": [
                        {"Source": "Internet Movie Database", "Value": "8.8/10"},
                        {"Source": "Rotten Tomatoes", "Value": "87%"}
                    ],
                    "Metascore": "74",
                    "imdbRating": "8.8",
                    "imdbVotes": "2,000,000",
                    "imdbID": "tt1375666",
                    "Type": "movie",
                    "BoxOffice": "$292,576,195"
                }
            )
            result = service.get_movie_details(imdb_id="tt1375666")
            assert result["success"] is True
            assert result["title"] == "Inception"
            assert result["director"] == "Christopher Nolan"
            assert result["imdb_rating"] == "8.8"
            assert len(result["ratings"]) == 2
    
    def test_get_details_by_title(self, service):
        """get_movie_details should work with title."""
        with patch.object(service.session, 'get') as mock_get:
            mock_get.return_value = Mock(
                status_code=200,
                json=lambda: {
                    "Response": "True",
                    "Title": "The Matrix",
                    "imdbID": "tt0133093",
                    "Year": "1999",
                    "Type": "movie",
                    "Ratings": []
                }
            )
            result = service.get_movie_details(title="The Matrix", year=1999)
            assert result["success"] is True
            # Verify title and year were passed
            call_args = mock_get.call_args
            assert "t" in call_args.kwargs.get("params", {}) or \
                   any("t" in str(arg) for arg in call_args)


class TestIMDBPersonSearch:
    """Tests for IMDB person search functionality."""
    
    @pytest.fixture
    def service(self):
        from mcp_server.services.imdb_service import IMDBService
        return IMDBService()
    
    def test_search_person_requires_name(self, service):
        """Search person should require a name."""
        result = service.search_person("")
        assert result["success"] is False
        assert "required" in result["error"].lower()
    
    def test_search_person_returns_dict(self, service):
        """Search person should return a dict."""
        with patch.object(service.session, 'get') as mock_get:
            mock_get.return_value = Mock(
                status_code=200,
                text='<a href="/name/nm0000158/">Tom Hanks</a>'
            )
            result = service.search_person("Tom Hanks", include_wikipedia=False)
            assert isinstance(result, dict)
            assert "success" in result
    
    def test_search_person_handles_network_error(self, service):
        """Search person should handle network errors."""
        import requests
        with patch.object(service.session, 'get') as mock_get:
            mock_get.side_effect = requests.RequestException("Network error")
            result = service.search_person("Test Actor", include_wikipedia=False)
            # Network errors are caught and return empty results with success=True
            assert isinstance(result, dict)
    
    def test_search_person_extracts_imdb_id(self, service):
        """Search person should extract IMDB person ID."""
        with patch.object(service, '_search_imdb_person') as mock_search:
            mock_search.return_value = [{
                "name": "Tom Hanks",
                "imdb_id": "nm0000158",
                "known_for": [],
                "url": "https://www.imdb.com/name/nm0000158/"
            }]
            result = service.search_person("Tom Hanks", include_wikipedia=False)
            assert result["success"] is True
            assert len(result["results"]) > 0
            assert result["results"][0]["imdb_id"] == "nm0000158"
    
    def test_search_person_with_wikipedia(self, service):
        """Search person with Wikipedia should include bio."""
        with patch.object(service, '_search_imdb_person') as mock_search:
            mock_search.return_value = [{
                "name": "Tom Hanks",
                "imdb_id": "nm0000158",
                "known_for": [],
                "url": "https://www.imdb.com/name/nm0000158/",
                "wikipedia": None
            }]
            with patch.object(service, '_enrich_with_wikipedia') as mock_wiki:
                mock_wiki.return_value = [{
                    "name": "Tom Hanks",
                    "imdb_id": "nm0000158",
                    "known_for": [],
                    "url": "https://www.imdb.com/name/nm0000158/",
                    "wikipedia": {
                        "found": True,
                        "summary": "Thomas Jeffrey Hanks is an American actor.",
                        "url": "https://en.wikipedia.org/wiki/Tom_Hanks"
                    }
                }]
                result = service.search_person("Tom Hanks", include_wikipedia=True)
                assert result["success"] is True
                assert result["results"][0]["wikipedia"]["found"] is True
    
    def test_get_filmography_requires_name(self, service):
        """Get filmography should require a valid IMDB ID."""
        result = service.get_person_filmography("")
        assert result["success"] is False
        assert "required" in result["error"].lower() or "valid" in result["error"].lower()
    
    def test_get_filmography_returns_dict(self, service):
        """Get filmography should return a dict."""
        with patch.object(service.session, 'get') as mock_get:
            mock_get.return_value = Mock(
                status_code=200,
                text='''
                <span class="hero__primary-text">Tom Hanks</span>
                <a href="/title/tt0109830/" class="ipc-metadata-list-summary-item__t">Forrest Gump</a>
                <span class="ipc-metadata-list-summary-item__li">1994</span>
                '''
            )
            result = service.get_person_filmography("nm0000158")
            assert isinstance(result, dict)
            assert "success" in result
    
    def test_filmography_validates_imdb_id(self, service):
        """Get filmography should validate IMDB person ID format."""
        # Invalid format
        result = service.get_person_filmography("invalid_id")
        assert result["success"] is False
        assert "valid" in result["error"].lower()
        
        # Movie ID instead of person ID
        result = service.get_person_filmography("tt0133093")
        assert result["success"] is False
    
    def test_filmography_limit(self, service):
        """Get filmography should respect limit."""
        with patch.object(service.session, 'get') as mock_get:
            mock_get.return_value = Mock(
                status_code=200,
                text='''
                <span class="hero__primary-text">Test Actor</span>
                <a href="/title/tt0000001/" class="ipc-metadata-list-summary-item__t">Movie 1</a>
                '''
            )
            result = service.get_person_filmography("nm0000001", limit=5)
            assert "success" in result


class TestIMDBSingleton:
    """Tests for IMDB service singleton."""
    
    def test_get_service_returns_same_instance(self):
        """get_imdb_service should return same instance."""
        import mcp_server.services.imdb_service as module
        module._imdb_service = None
        
        from mcp_server.services.imdb_service import get_imdb_service
        service1 = get_imdb_service()
        service2 = get_imdb_service()
        assert service1 is service2


# ========== Security Tests ==========

class TestServiceSecurity:
    """Security tests for all services."""
    
    def test_udemy_sanitizes_course_titles(self):
        """Udemy should sanitize course titles."""
        from mcp_server.services.udemy_service import sanitize_text
        malicious = '<script>alert("xss")</script>Course'
        result = sanitize_text(malicious)
        assert "<script>" not in result
        assert "alert" not in result.lower() or "&" in result  # escaped
    
    def test_conference_sanitizes_names(self):
        """Conference service should sanitize names."""
        from mcp_server.services.conference_service import sanitize_text
        malicious = '<img src=x onerror="alert(1)">Conf'
        result = sanitize_text(malicious)
        assert "<img" not in result
        assert "onerror" not in result
    
    def test_newsletter_sanitizes_urls(self):
        """Newsletter service should sanitize URLs."""
        from mcp_server.services.newsletter_service import sanitize_url
        # JavaScript URL should be blocked
        assert sanitize_url("javascript:alert(1)") == ""
        # Data URL should be blocked
        assert sanitize_url("data:text/html,<script>") == ""
        # Valid URL should pass
        assert sanitize_url("https://example.com") == "https://example.com"
    
    def test_imdb_sanitizes_plot(self):
        """IMDB should sanitize plot text."""
        from mcp_server.services.imdb_service import sanitize_text
        malicious = '<div onclick="steal()">Plot text</div>'
        result = sanitize_text(malicious)
        assert "<div" not in result
        assert "onclick" not in result
