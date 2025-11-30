"""
YouTube Context Service

Provides access to YouTube video transcripts for educational content.
Part of the "Ask an Expert" feature for technical research.

Uses youtube-transcript-api for transcript extraction (no API key needed).
Optionally uses YouTube Data API v3 for video search (requires API key).
"""

import html
import logging
import re
from typing import Dict, List, Optional, Any
from urllib.parse import quote, urlparse, parse_qs

import requests

logger = logging.getLogger(__name__)

# Import cache
try:
    from ..utils.cache import get_cache
    CACHE_AVAILABLE = True
except ImportError:
    CACHE_AVAILABLE = False
    logger.warning("Cache not available, YouTube requests will not be cached")

# Import transcript API (v1.x uses instance-based API)
try:
    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api._errors import (
        TranscriptsDisabled,
        NoTranscriptFound,
        VideoUnavailable,
    )
    TRANSCRIPT_API_AVAILABLE = True
    # Create singleton API instance (v1.x uses instance methods)
    _transcript_api = YouTubeTranscriptApi()
except ImportError:
    TRANSCRIPT_API_AVAILABLE = False
    _transcript_api = None
    logger.warning("youtube-transcript-api not available")


def sanitize_html(text: str) -> str:
    """
    Sanitize HTML content to prevent XSS attacks.
    Removes all HTML tags and escapes special characters.
    """
    if not text:
        return ""
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    # Escape HTML entities
    text = html.escape(text)
    return text


def sanitize_url(url: str) -> str:
    """
    Validate and sanitize URL to prevent injection.
    Only allows YouTube domains.
    """
    if not url:
        return ""
    # Only allow YouTube domains
    if not re.match(r'^https?://(www\.)?(youtube\.com|youtu\.be)/', url):
        return ""
    # Remove any script injection attempts
    if re.search(r'javascript:|data:|vbscript:', url, re.IGNORECASE):
        return ""
    return url


def extract_video_id(url_or_id: str) -> Optional[str]:
    """
    Extract video ID from various YouTube URL formats or return ID if already an ID.
    
    Supported formats:
    - https://www.youtube.com/watch?v=VIDEO_ID
    - https://youtu.be/VIDEO_ID
    - https://www.youtube.com/embed/VIDEO_ID
    - VIDEO_ID (11 character string)
    """
    if not url_or_id:
        return None
    
    # If it's already a video ID (11 characters, alphanumeric + - _)
    if re.match(r'^[a-zA-Z0-9_-]{11}$', url_or_id):
        return url_or_id
    
    try:
        parsed = urlparse(url_or_id)
        
        # youtube.com/watch?v=ID
        if parsed.hostname in ('www.youtube.com', 'youtube.com'):
            if parsed.path == '/watch':
                query = parse_qs(parsed.query)
                if 'v' in query:
                    return query['v'][0]
            # youtube.com/embed/ID
            elif parsed.path.startswith('/embed/'):
                return parsed.path.split('/')[2]
        
        # youtu.be/ID
        elif parsed.hostname == 'youtu.be':
            return parsed.path[1:]  # Remove leading /
        
    except Exception:
        pass
    
    return None


class YouTubeService:
    """
    YouTube context service for educational video content.
    
    Features:
    - Search videos (via web scraping or API if key provided)
    - Get transcripts for videos
    - Extract relevant segments from transcripts
    """
    
    # YouTube web search URL (no API key needed)
    SEARCH_URL = "https://www.youtube.com/results"
    
    # YouTube Data API v3 (requires API key)
    API_URL = "https://www.googleapis.com/youtube/v3"
    
    # Preferred languages for transcripts
    PREFERRED_LANGUAGES = ['en', 'en-US', 'en-GB', 'de', 'fr', 'es', 'zh']
    
    USER_AGENT = "TrendRadar/1.0 (Ask an Expert feature; news aggregation tool)"
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize YouTube service.
        
        Args:
            api_key: Optional YouTube Data API v3 key for search
        """
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.USER_AGENT,
            "Accept-Language": "en-US,en;q=0.9",
        })
    
    def search(
        self,
        query: str,
        limit: int = 5,
        content_type: str = "video"
    ) -> Dict[str, Any]:
        """
        Search YouTube for videos matching a query.
        
        Args:
            query: Search query (e.g., "RAG tutorial", "transformer explained")
            limit: Maximum number of results (default: 5, max: 20)
            content_type: Type of content - "video", "channel", "playlist"
            
        Returns:
            Dict with video results including title, channel, URL
        """
        if not query or not query.strip():
            return {
                "success": False,
                "error": "Query is required",
                "query": ""
            }
        
        query = query.strip()
        
        # Check cache first (1 hour TTL for YouTube)
        if CACHE_AVAILABLE:
            cache = get_cache("youtube", ttl=3600)
            cache_key = cache.make_key(
                "youtube_search",
                query=query,
                limit=limit,
                content_type=content_type
            )
            cached = cache.get(cache_key)
            if cached is not None:
                logger.debug(f"Cache hit for YouTube query: {query}")
                cached["from_cache"] = True
                return cached
        
        # Use API if key available, otherwise use web search
        if self.api_key:
            result = self._search_with_api(query, limit, content_type)
        else:
            result = self._search_web(query, limit)
        
        # Cache successful results
        if CACHE_AVAILABLE and result.get("success"):
            cache.set(cache_key, result)
            logger.debug(f"Cached YouTube results for: {query}")
        
        return result
    
    def _search_with_api(
        self,
        query: str,
        limit: int,
        content_type: str
    ) -> Dict[str, Any]:
        """Search using YouTube Data API v3."""
        try:
            params = {
                "part": "snippet",
                "q": query,
                "type": content_type,
                "maxResults": min(limit, 20),
                "key": self.api_key,
                "relevanceLanguage": "en",
            }
            
            response = self.session.get(
                f"{self.API_URL}/search",
                params=params,
                timeout=15
            )
            
            if response.status_code == 403:
                logger.warning("YouTube API quota exceeded or invalid key")
                return {
                    "success": False,
                    "error": "API quota exceeded or invalid key",
                    "query": query
                }
            
            if response.status_code != 200:
                return {
                    "success": False,
                    "error": f"API returned status {response.status_code}",
                    "query": query
                }
            
            data = response.json()
            videos = []
            
            for item in data.get("items", []):
                snippet = item.get("snippet", {})
                video_id = item.get("id", {}).get("videoId", "")
                
                if not video_id:
                    continue
                
                videos.append({
                    "video_id": video_id,
                    "title": sanitize_html(snippet.get("title", "")),
                    "description": sanitize_html(snippet.get("description", ""))[:300],
                    "channel": sanitize_html(snippet.get("channelTitle", "")),
                    "published_at": snippet.get("publishedAt", ""),
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                    "thumbnail": snippet.get("thumbnails", {}).get("medium", {}).get("url", ""),
                })
            
            return {
                "success": True,
                "query": query,
                "count": len(videos),
                "videos": videos,
                "source": "youtube_api"
            }
            
        except requests.Timeout:
            logger.error("YouTube API timeout")
            return {
                "success": False,
                "error": "Request timed out",
                "query": query
            }
        except Exception as e:
            logger.error(f"YouTube API error: {e}")
            return {
                "success": False,
                "error": str(e),
                "query": query
            }
    
    def _search_web(self, query: str, limit: int) -> Dict[str, Any]:
        """
        Search YouTube via web scraping (no API key needed).
        This is a fallback method with limited functionality.
        """
        try:
            # Use YouTube's search URL
            params = {"search_query": query}
            response = self.session.get(
                self.SEARCH_URL,
                params=params,
                timeout=15
            )
            
            if response.status_code != 200:
                return {
                    "success": False,
                    "error": f"Search returned status {response.status_code}",
                    "query": query
                }
            
            # Extract video IDs from the page
            # YouTube embeds video data in ytInitialData JSON
            video_pattern = r'"videoId":"([a-zA-Z0-9_-]{11})"'
            title_pattern = r'"title":\{"runs":\[\{"text":"([^"]+)"\}\]'
            
            video_ids = re.findall(video_pattern, response.text)
            
            # Get unique video IDs (preserve order)
            seen = set()
            unique_ids = []
            for vid in video_ids:
                if vid not in seen:
                    seen.add(vid)
                    unique_ids.append(vid)
                    if len(unique_ids) >= limit:
                        break
            
            videos = []
            for video_id in unique_ids:
                videos.append({
                    "video_id": video_id,
                    "title": "",  # Can't reliably extract from web search
                    "description": "",
                    "channel": "",
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                    "note": "Limited metadata - use get_transcript for content"
                })
            
            return {
                "success": True,
                "query": query,
                "count": len(videos),
                "videos": videos,
                "source": "youtube_web",
                "note": "Web search has limited metadata. Consider using API key for full results."
            }
            
        except Exception as e:
            logger.error(f"YouTube web search error: {e}")
            return {
                "success": False,
                "error": str(e),
                "query": query
            }
    
    def get_transcript(
        self,
        video_id_or_url: str,
        languages: Optional[List[str]] = None,
        max_length: int = 10000
    ) -> Dict[str, Any]:
        """
        Get transcript/captions for a YouTube video.
        
        Args:
            video_id_or_url: YouTube video ID or URL
            languages: Preferred languages (default: ['en', 'en-US', 'de'])
            max_length: Maximum transcript length in characters
            
        Returns:
            Dict with transcript text and metadata
        """
        if not TRANSCRIPT_API_AVAILABLE:
            return {
                "success": False,
                "error": "youtube-transcript-api not installed",
                "video_id": video_id_or_url
            }
        
        video_id = extract_video_id(video_id_or_url)
        if not video_id:
            return {
                "success": False,
                "error": "Invalid video ID or URL",
                "video_id": video_id_or_url
            }
        
        # Check cache first (transcripts cached for 24 hours)
        if CACHE_AVAILABLE:
            cache = get_cache("youtube_transcripts", ttl=86400)
            cache_key = cache.make_key(
                "transcript",
                video_id=video_id
            )
            cached = cache.get(cache_key)
            if cached is not None:
                logger.debug(f"Cache hit for transcript: {video_id}")
                cached["from_cache"] = True
                return cached
        
        languages = languages or self.PREFERRED_LANGUAGES
        
        try:
            # Use instance-based API (v1.x)
            transcript_list = _transcript_api.list(video_id)
            
            transcript = None
            language_used = None
            is_generated = False
            
            # First try manually created transcripts
            for lang in languages:
                try:
                    transcript = transcript_list.find_manually_created_transcript([lang])
                    language_used = lang
                    is_generated = False
                    break
                except NoTranscriptFound:
                    continue
            
            # Fall back to auto-generated if no manual transcript
            if transcript is None:
                for lang in languages:
                    try:
                        transcript = transcript_list.find_generated_transcript([lang])
                        language_used = lang
                        is_generated = True
                        break
                    except NoTranscriptFound:
                        continue
            
            # Last resort: get any available transcript
            if transcript is None:
                try:
                    # Get first available transcript
                    for t in transcript_list:
                        transcript = t
                        language_used = t.language_code
                        is_generated = t.is_generated
                        break
                except Exception:
                    pass
            
            if transcript is None:
                return {
                    "success": False,
                    "error": "No transcript available for this video",
                    "video_id": video_id
                }
            
            # Fetch the transcript segments
            segments = transcript.fetch()
            
            # Combine into full text (v1.x returns FetchedTranscriptSnippet objects)
            full_text = " ".join([
                sanitize_html(getattr(seg, 'text', '') if hasattr(seg, 'text') else seg.get("text", ""))
                for seg in segments
            ])
            
            # Truncate if too long
            if len(full_text) > max_length:
                full_text = full_text[:max_length] + "... [truncated]"
            
            # Create segment list with timestamps (v1.x uses attributes)
            timed_segments = []
            for seg in segments[:100]:  # Limit segments to avoid huge responses
                if hasattr(seg, 'text'):
                    # v1.x FetchedTranscriptSnippet
                    timed_segments.append({
                        "start": round(getattr(seg, 'start', 0), 1),
                        "duration": round(getattr(seg, 'duration', 0), 1),
                        "text": sanitize_html(getattr(seg, 'text', ''))
                    })
                else:
                    # v0.x dict format
                    timed_segments.append({
                        "start": round(seg.get("start", 0), 1),
                        "duration": round(seg.get("duration", 0), 1),
                        "text": sanitize_html(seg.get("text", ""))
                    })
            
            result = {
                "success": True,
                "video_id": video_id,
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "language": language_used,
                "is_auto_generated": is_generated,
                "transcript": full_text,
                "segments": timed_segments,
                "segment_count": len(segments),
                "character_count": len(full_text),
                "source": "youtube_transcript"
            }
            
            # Cache the result
            if CACHE_AVAILABLE:
                cache.set(cache_key, result)
                logger.debug(f"Cached transcript for: {video_id}")
            
            return result
            
        except TranscriptsDisabled:
            return {
                "success": False,
                "error": "Transcripts are disabled for this video",
                "video_id": video_id
            }
        except VideoUnavailable:
            return {
                "success": False,
                "error": "Video is unavailable",
                "video_id": video_id
            }
        except Exception as e:
            logger.error(f"Transcript error for {video_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "video_id": video_id
            }
    
    def search_with_transcripts(
        self,
        query: str,
        limit: int = 3,
        max_transcript_length: int = 5000
    ) -> Dict[str, Any]:
        """
        Search YouTube and get transcripts for top results.
        Useful for getting educational content context.
        
        Args:
            query: Search query
            limit: Number of videos to get transcripts for
            max_transcript_length: Max chars per transcript
            
        Returns:
            Dict with videos and their transcripts
        """
        # Search for videos
        search_result = self.search(query, limit=limit)
        
        if not search_result.get("success"):
            return search_result
        
        videos_with_transcripts = []
        
        for video in search_result.get("videos", [])[:limit]:
            video_id = video.get("video_id")
            if not video_id:
                continue
            
            # Get transcript
            transcript_result = self.get_transcript(
                video_id,
                max_length=max_transcript_length
            )
            
            videos_with_transcripts.append({
                **video,
                "transcript_available": transcript_result.get("success", False),
                "transcript": transcript_result.get("transcript", "") if transcript_result.get("success") else None,
                "transcript_language": transcript_result.get("language"),
                "is_auto_generated": transcript_result.get("is_auto_generated"),
                "transcript_error": transcript_result.get("error") if not transcript_result.get("success") else None,
            })
        
        return {
            "success": True,
            "query": query,
            "count": len(videos_with_transcripts),
            "videos": videos_with_transcripts,
            "source": "youtube"
        }


# Singleton instance
_youtube_service: Optional[YouTubeService] = None


def get_youtube_service(api_key: Optional[str] = None) -> YouTubeService:
    """Get or create the YouTube service singleton."""
    global _youtube_service
    if _youtube_service is None:
        _youtube_service = YouTubeService(api_key=api_key)
    return _youtube_service
