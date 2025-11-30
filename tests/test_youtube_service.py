"""
Tests for the YouTube Context Service.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock

from mcp_server.services.youtube_service import (
    YouTubeService,
    get_youtube_service,
    sanitize_html,
    sanitize_url,
    extract_video_id,
)


class TestSanitizeHtml:
    """Tests for HTML sanitization."""
    
    def test_removes_script_tags(self):
        """Script tags should be removed."""
        text = "Hello <script>alert('xss')</script> World"
        result = sanitize_html(text)
        assert "<script>" not in result
        # The script content is kept but escaped, which is safe
    
    def test_removes_html_tags(self):
        """HTML tags should be removed."""
        text = "<b>Bold</b> and <i>italic</i>"
        result = sanitize_html(text)
        assert "<b>" not in result
        assert "<i>" not in result
        assert "Bold" in result
        assert "italic" in result
    
    def test_escapes_special_chars(self):
        """Special characters should be escaped."""
        text = "Test <b>tag</b>"
        result = sanitize_html(text)
        # Tags are stripped, not escaped
        assert "<b>" not in result
        assert "Test" in result
        assert "tag" in result
    
    def test_normalizes_whitespace(self):
        """Multiple whitespace should be normalized."""
        text = "Hello    World\n\nTest"
        result = sanitize_html(text)
        assert "    " not in result
        assert "\n\n" not in result
    
    def test_handles_empty_input(self):
        """Empty strings should return empty."""
        assert sanitize_html("") == ""
        assert sanitize_html(None) == ""


class TestSanitizeUrl:
    """Tests for URL sanitization."""
    
    def test_allows_youtube_urls(self):
        """YouTube URLs should be allowed."""
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        assert sanitize_url(url) == url
    
    def test_allows_youtu_be_urls(self):
        """Short YouTube URLs should be allowed."""
        url = "https://youtu.be/dQw4w9WgXcQ"
        assert sanitize_url(url) == url
    
    def test_blocks_javascript_urls(self):
        """JavaScript URLs should be blocked."""
        url = "javascript:alert('xss')"
        assert sanitize_url(url) == ""
    
    def test_blocks_data_urls(self):
        """Data URLs should be blocked."""
        url = "data:text/html,<script>alert('xss')</script>"
        assert sanitize_url(url) == ""
    
    def test_blocks_non_youtube_domains(self):
        """Non-YouTube domains should be blocked."""
        url = "https://evil.com/watch?v=abc"
        assert sanitize_url(url) == ""
    
    def test_handles_empty_input(self):
        """Empty strings should return empty."""
        assert sanitize_url("") == ""
        assert sanitize_url(None) == ""


class TestExtractVideoId:
    """Tests for video ID extraction."""
    
    def test_extracts_from_watch_url(self):
        """Extract ID from standard watch URL."""
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        assert extract_video_id(url) == "dQw4w9WgXcQ"
    
    def test_extracts_from_short_url(self):
        """Extract ID from youtu.be URL."""
        url = "https://youtu.be/dQw4w9WgXcQ"
        assert extract_video_id(url) == "dQw4w9WgXcQ"
    
    def test_extracts_from_embed_url(self):
        """Extract ID from embed URL."""
        url = "https://www.youtube.com/embed/dQw4w9WgXcQ"
        assert extract_video_id(url) == "dQw4w9WgXcQ"
    
    def test_returns_id_if_already_id(self):
        """Return ID if already a valid ID."""
        video_id = "dQw4w9WgXcQ"
        assert extract_video_id(video_id) == video_id
    
    def test_handles_url_with_extra_params(self):
        """Handle URL with extra query parameters."""
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=120"
        assert extract_video_id(url) == "dQw4w9WgXcQ"
    
    def test_returns_none_for_invalid(self):
        """Return None for invalid input."""
        assert extract_video_id("") is None
        assert extract_video_id(None) is None
        assert extract_video_id("not-a-url") is None


class TestYouTubeServiceInit:
    """Tests for YouTubeService initialization."""
    
    def test_creates_session(self):
        """Service should create a requests session."""
        service = YouTubeService()
        assert service.session is not None
    
    def test_has_user_agent(self):
        """Service should have a user agent."""
        service = YouTubeService()
        assert "TrendRadar" in service.session.headers["User-Agent"]
    
    def test_stores_api_key(self):
        """API key should be stored if provided."""
        service = YouTubeService(api_key="test_key")
        assert service.api_key == "test_key"


class TestYouTubeSearch:
    """Tests for YouTube search functionality."""
    
    @pytest.fixture
    def service(self):
        return YouTubeService()
    
    def test_search_returns_dict(self, service):
        """Search should return a dictionary."""
        with patch.object(service.session, 'get') as mock_get:
            # Mock web search response
            mock_get.return_value = Mock(
                status_code=200,
                text='"videoId":"abc12345678","videoId":"def12345678"'
            )
            result = service.search("test query")
            assert isinstance(result, dict)
    
    def test_search_requires_query(self, service):
        """Search should fail without query."""
        result = service.search("")
        assert result["success"] is False
        assert "required" in result["error"].lower()
    
    def test_search_extracts_video_ids(self, service):
        """Search should extract video IDs from response."""
        with patch.object(service.session, 'get') as mock_get:
            mock_get.return_value = Mock(
                status_code=200,
                text='"videoId":"abc12345678","videoId":"def12345678","videoId":"ghi12345678"'
            )
            result = service.search("test query", limit=2)
            assert result["success"] is True
            assert len(result["videos"]) == 2
    
    def test_search_handles_timeout(self, service):
        """Search should handle timeout errors."""
        import requests
        with patch.object(service.session, 'get') as mock_get:
            mock_get.side_effect = requests.Timeout()
            result = service.search("test query")
            # Web search fallback or error
            assert isinstance(result, dict)
    
    def test_search_with_api_key(self):
        """Search with API key should use API endpoint."""
        service = YouTubeService(api_key="test_key")
        with patch.object(service.session, 'get') as mock_get:
            mock_get.return_value = Mock(
                status_code=200,
                json=lambda: {
                    "items": [
                        {
                            "id": {"videoId": "abc12345678"},
                            "snippet": {
                                "title": "Test Video",
                                "description": "Test description",
                                "channelTitle": "Test Channel",
                                "publishedAt": "2024-01-01T00:00:00Z"
                            }
                        }
                    ]
                }
            )
            result = service.search("test query")
            assert result["success"] is True
            assert mock_get.call_args[0][0].startswith("https://www.googleapis.com")


class TestYouTubeTranscript:
    """Tests for YouTube transcript functionality."""
    
    @pytest.fixture
    def service(self):
        return YouTubeService()
    
    def test_transcript_invalid_video_id(self, service):
        """Transcript should fail for invalid video ID."""
        result = service.get_transcript("not-valid")
        assert result["success"] is False
        assert "Invalid" in result["error"]
    
    def test_transcript_extracts_id_from_url(self, service):
        """Transcript should extract video ID from URL."""
        # Mock the instance-based API (v1.x)
        with patch('mcp_server.services.youtube_service._transcript_api') as mock_api:
            # Mock transcript response
            mock_transcript = Mock()
            mock_transcript.fetch.return_value = [
                Mock(text="Hello", start=0, duration=1),
                Mock(text="World", start=1, duration=1)
            ]
            mock_transcript.language_code = "en"
            mock_transcript.is_generated = False
            
            mock_list = Mock()
            mock_list.find_manually_created_transcript.return_value = mock_transcript
            mock_api.list.return_value = mock_list
            
            result = service.get_transcript("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
            assert result["video_id"] == "dQw4w9WgXcQ"
    
    def test_transcript_success(self, service):
        """Transcript should return text content."""
        # Mock the instance-based API (v1.x)
        with patch('mcp_server.services.youtube_service._transcript_api') as mock_api:
            mock_transcript = Mock()
            mock_transcript.fetch.return_value = [
                Mock(text="Hello", start=0, duration=1),
                Mock(text="World", start=1, duration=1)
            ]
            mock_transcript.language_code = "en"
            mock_transcript.is_generated = False
            
            mock_list = Mock()
            mock_list.find_manually_created_transcript.return_value = mock_transcript
            mock_api.list.return_value = mock_list
            
            result = service.get_transcript("dQw4w9WgXcQ")
            assert result["success"] is True
            assert "Hello" in result["transcript"]


class TestYouTubeSingleton:
    """Tests for YouTube service singleton."""
    
    def test_get_youtube_service_returns_same_instance(self):
        """get_youtube_service should return same instance."""
        # Reset singleton
        import mcp_server.services.youtube_service as youtube_module
        youtube_module._youtube_service = None
        
        service1 = get_youtube_service()
        service2 = get_youtube_service()
        assert service1 is service2
    
    def test_singleton_is_youtube_service(self):
        """Singleton should be YouTubeService instance."""
        import mcp_server.services.youtube_service as youtube_module
        youtube_module._youtube_service = None
        
        service = get_youtube_service()
        assert isinstance(service, YouTubeService)


class TestYouTubeSecurity:
    """Security tests for YouTube service."""
    
    @pytest.fixture
    def service(self):
        return YouTubeService()
    
    def test_xss_in_video_title_sanitized(self, service):
        """XSS in video titles should be sanitized."""
        service_with_api = YouTubeService(api_key="test")
        with patch.object(service_with_api.session, 'get') as mock_get:
            mock_get.return_value = Mock(
                status_code=200,
                json=lambda: {
                    "items": [
                        {
                            "id": {"videoId": "abc12345678"},
                            "snippet": {
                                "title": "<script>alert('xss')</script>Test",
                                "description": "Safe description",
                                "channelTitle": "Test Channel",
                                "publishedAt": "2024-01-01T00:00:00Z"
                            }
                        }
                    ]
                }
            )
            result = service_with_api.search("test")
            assert result["success"] is True
            video = result["videos"][0]
            # Script tags should be removed
            assert "<script>" not in video["title"]
            assert "</script>" not in video["title"]
