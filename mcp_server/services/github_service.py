"""
GitHub Search Service for Ask an Expert

Provides search capabilities for GitHub repositories.
Uses GitHub REST API with rate limiting and caching.

Security: All content is sanitized to prevent XSS attacks.
"""

import hashlib
import html
import logging
import re
import time
from typing import Any, Dict, List, Optional
from urllib.parse import quote, urlparse

import requests

logger = logging.getLogger(__name__)

# Import cache
try:
    from ..utils.cache import get_cache
    CACHE_AVAILABLE = True
except ImportError:
    CACHE_AVAILABLE = False
    logger.warning("Cache not available, GitHub requests will not be cached")


# =============================================================================
# Security: Sanitization functions
# =============================================================================

def sanitize_html(text: Optional[str]) -> str:
    """
    Sanitize HTML content to prevent XSS attacks.
    
    - Removes all HTML tags
    - Escapes special characters
    - Normalizes whitespace
    """
    if not text:
        return ""
    
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # Escape HTML entities
    text = html.escape(text, quote=True)
    
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text


def sanitize_url(url: Optional[str]) -> str:
    """
    Sanitize and validate URLs.
    
    Only allows:
    - github.com domains
    - raw.githubusercontent.com for README content
    - HTTP(S) schemes
    """
    if not url:
        return ""
    
    url = url.strip()
    
    # Block dangerous schemes
    dangerous_schemes = ['javascript:', 'data:', 'vbscript:', 'file:']
    url_lower = url.lower()
    for scheme in dangerous_schemes:
        if url_lower.startswith(scheme):
            return ""
    
    # Parse URL
    try:
        parsed = urlparse(url)
        
        # Only allow http/https
        if parsed.scheme not in ('http', 'https'):
            return ""
        
        # Only allow GitHub domains
        allowed_domains = [
            'github.com',
            'www.github.com',
            'raw.githubusercontent.com',
            'api.github.com',
        ]
        
        if not any(parsed.netloc == domain or parsed.netloc.endswith('.' + domain) 
                   for domain in allowed_domains):
            return ""
        
        return url
        
    except Exception:
        return ""


# =============================================================================
# GitHub Service
# =============================================================================

class GitHubService:
    """
    GitHub repository search service.
    
    Uses GitHub REST API v3 for searching repositories.
    Implements rate limiting to avoid API limits.
    """
    
    API_URL = "https://api.github.com"
    
    # Rate limiting: 10 requests per minute for unauthenticated
    RATE_LIMIT_REQUESTS = 10
    RATE_LIMIT_WINDOW = 60  # seconds
    
    # Common programming languages
    LANGUAGES = [
        "python", "javascript", "typescript", "java", "go", "rust",
        "c", "cpp", "csharp", "ruby", "php", "swift", "kotlin",
        "scala", "r", "julia", "shell", "dockerfile"
    ]
    
    # Sort options
    SORT_OPTIONS = {
        "stars": "Most stars",
        "forks": "Most forks",
        "updated": "Recently updated",
        "help-wanted-issues": "Most help wanted issues",
        "best-match": "Best match (default)"
    }
    
    def __init__(self, token: Optional[str] = None):
        """
        Initialize GitHub service.
        
        Args:
            token: Optional GitHub personal access token for higher rate limits
        """
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "TrendRadar/1.0 (News Research Assistant)",
        })
        
        # Add auth token if provided (increases rate limit to 30 req/min)
        if token:
            self.session.headers["Authorization"] = f"token {token}"
            self.RATE_LIMIT_REQUESTS = 30
        
        # Rate limiting state
        self._request_times: List[float] = []
    
    def _check_rate_limit(self) -> bool:
        """
        Check if we can make a request without hitting rate limits.
        
        Returns:
            True if request is allowed, False if rate limited
        """
        now = time.time()
        
        # Remove requests older than the window
        self._request_times = [
            t for t in self._request_times 
            if now - t < self.RATE_LIMIT_WINDOW
        ]
        
        if len(self._request_times) >= self.RATE_LIMIT_REQUESTS:
            return False
        
        self._request_times.append(now)
        return True
    
    def _get_rate_limit_wait(self) -> float:
        """Get seconds to wait before rate limit resets."""
        if not self._request_times:
            return 0
        oldest = min(self._request_times)
        return max(0, self.RATE_LIMIT_WINDOW - (time.time() - oldest))
    
    def search_repos(
        self,
        query: str,
        language: Optional[str] = None,
        sort: str = "stars",
        order: str = "desc",
        limit: int = 10,
        min_stars: Optional[int] = None,
        use_cache: bool = True,
    ) -> Dict[str, Any]:
        """
        Search GitHub repositories.
        
        Args:
            query: Search query (keywords, topics)
            language: Filter by programming language
            sort: Sort by: stars, forks, updated, help-wanted-issues, best-match
            order: Sort order: asc or desc
            limit: Maximum results (1-30)
            min_stars: Minimum star count filter
            use_cache: Whether to use cached results (default: True)
            
        Returns:
            Dict with search results
        """
        # Validate and sanitize inputs
        query = sanitize_html(query)
        if not query:
            return {
                "success": False,
                "error": "Query is required",
                "query": query
            }
        
        # Build search query
        search_query = query
        
        # Add language filter
        if language:
            language = sanitize_html(language.lower())
            if language in self.LANGUAGES:
                search_query += f" language:{language}"
        
        # Add minimum stars filter
        if min_stars and min_stars > 0:
            search_query += f" stars:>={min_stars}"
        
        # Validate sort option
        if sort not in self.SORT_OPTIONS and sort != "best-match":
            sort = "stars"
        
        # Validate limit
        limit = max(1, min(30, limit))
        
        # Check cache first (1 hour TTL for GitHub)
        cache_key = None
        if use_cache and CACHE_AVAILABLE:
            cache = get_cache("github", ttl=3600, max_size=500)
            cache_key = hashlib.md5(
                f"search:{search_query}:{sort}:{order}:{limit}".encode()
            ).hexdigest()
            cached = cache.get(cache_key)
            if cached:
                logger.debug(f"GitHub cache hit for: {query}")
                cached["from_cache"] = True
                return cached
        
        # Check rate limit
        if not self._check_rate_limit():
            wait_time = self._get_rate_limit_wait()
            return {
                "success": False,
                "error": f"Rate limited. Try again in {wait_time:.0f} seconds.",
                "query": query,
                "rate_limited": True,
                "retry_after": wait_time
            }
        
        try:
            params = {
                "q": search_query,
                "per_page": limit,
            }
            
            # Only add sort if not best-match (default)
            if sort != "best-match":
                params["sort"] = sort
                params["order"] = order
            
            response = self.session.get(
                f"{self.API_URL}/search/repositories",
                params=params,
                timeout=10
            )
            
            if response.status_code == 403:
                # Rate limited by GitHub
                return {
                    "success": False,
                    "error": "GitHub API rate limit exceeded",
                    "query": query,
                    "rate_limited": True
                }
            
            if response.status_code != 200:
                return {
                    "success": False,
                    "error": f"GitHub API returned status {response.status_code}",
                    "query": query
                }
            
            data = response.json()
            repos = self._parse_repos(data.get("items", []))
            
            result = {
                "success": True,
                "query": query,
                "language": language,
                "sort": sort,
                "sort_description": self.SORT_OPTIONS.get(sort, ""),
                "count": len(repos),
                "total_count": data.get("total_count", 0),
                "repos": repos,
                "source": "github"
            }
            
            # Store in cache
            if cache_key and CACHE_AVAILABLE:
                cache = get_cache("github")
                cache.set(cache_key, result)
                logger.debug(f"GitHub cached: {query}")
            
            return result
            
        except requests.Timeout:
            logger.error("GitHub API timeout")
            return {
                "success": False,
                "error": "Request timed out",
                "query": query
            }
        except Exception as e:
            logger.error(f"GitHub search error: {e}")
            return {
                "success": False,
                "error": str(e),
                "query": query
            }
    
    def _parse_repos(self, items: List[Dict]) -> List[Dict[str, Any]]:
        """Parse GitHub API response into clean repo data."""
        repos = []
        
        for item in items:
            try:
                repo = {
                    "name": sanitize_html(item.get("name", "")),
                    "full_name": sanitize_html(item.get("full_name", "")),
                    "description": sanitize_html(item.get("description", "")),
                    "url": sanitize_url(item.get("html_url", "")),
                    "homepage": sanitize_url(item.get("homepage", "")),
                    "stars": item.get("stargazers_count", 0),
                    "forks": item.get("forks_count", 0),
                    "open_issues": item.get("open_issues_count", 0),
                    "watchers": item.get("watchers_count", 0),
                    "language": sanitize_html(item.get("language", "")),
                    "topics": [sanitize_html(t) for t in item.get("topics", [])[:5]],
                    "license": sanitize_html(
                        item.get("license", {}).get("name", "") 
                        if item.get("license") else ""
                    ),
                    "created_at": item.get("created_at", ""),
                    "updated_at": item.get("updated_at", ""),
                    "pushed_at": item.get("pushed_at", ""),
                    "owner": {
                        "login": sanitize_html(item.get("owner", {}).get("login", "")),
                        "url": sanitize_url(item.get("owner", {}).get("html_url", "")),
                        "avatar_url": sanitize_url(item.get("owner", {}).get("avatar_url", "")),
                    },
                    "is_fork": item.get("fork", False),
                    "archived": item.get("archived", False),
                    "default_branch": sanitize_html(item.get("default_branch", "main")),
                }
                
                repos.append(repo)
                
            except Exception as e:
                logger.error(f"Error parsing repo: {e}")
                continue
        
        return repos
    
    def get_readme(
        self,
        owner: str,
        repo: str,
        max_length: int = 2000
    ) -> Dict[str, Any]:
        """
        Get README content for a repository.
        
        Args:
            owner: Repository owner/organization
            repo: Repository name
            max_length: Maximum content length to return
            
        Returns:
            Dict with README content
        """
        owner = sanitize_html(owner)
        repo = sanitize_html(repo)
        
        if not owner or not repo:
            return {
                "success": False,
                "error": "Owner and repo are required"
            }
        
        # Check rate limit
        if not self._check_rate_limit():
            wait_time = self._get_rate_limit_wait()
            return {
                "success": False,
                "error": f"Rate limited. Try again in {wait_time:.0f} seconds.",
                "rate_limited": True,
                "retry_after": wait_time
            }
        
        try:
            # Try to get README
            response = self.session.get(
                f"{self.API_URL}/repos/{owner}/{repo}/readme",
                headers={"Accept": "application/vnd.github.raw"},
                timeout=10
            )
            
            if response.status_code == 404:
                return {
                    "success": False,
                    "error": "README not found",
                    "owner": owner,
                    "repo": repo
                }
            
            if response.status_code != 200:
                return {
                    "success": False,
                    "error": f"GitHub API returned status {response.status_code}",
                    "owner": owner,
                    "repo": repo
                }
            
            content = response.text
            
            # Truncate if too long
            if len(content) > max_length:
                content = content[:max_length] + "\n\n... (truncated)"
            
            # Basic sanitization - keep markdown but escape HTML
            content = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL | re.IGNORECASE)
            content = re.sub(r'<style[^>]*>.*?</style>', '', content, flags=re.DOTALL | re.IGNORECASE)
            content = re.sub(r'on\w+="[^"]*"', '', content)  # Remove event handlers
            
            return {
                "success": True,
                "owner": owner,
                "repo": repo,
                "content": content,
                "length": len(content),
                "truncated": len(response.text) > max_length,
                "source": "github"
            }
            
        except requests.Timeout:
            logger.error("GitHub API timeout")
            return {
                "success": False,
                "error": "Request timed out",
                "owner": owner,
                "repo": repo
            }
        except Exception as e:
            logger.error(f"GitHub README error: {e}")
            return {
                "success": False,
                "error": str(e),
                "owner": owner,
                "repo": repo
            }
    
    def get_languages(self) -> Dict[str, Any]:
        """
        Get list of supported programming languages.
        
        Returns:
            Dict with language list
        """
        return {
            "success": True,
            "languages": self.LANGUAGES,
            "source": "github"
        }
    
    def get_sort_options(self) -> Dict[str, Any]:
        """
        Get available sort options.
        
        Returns:
            Dict with sort options
        """
        return {
            "success": True,
            "sort_options": self.SORT_OPTIONS,
            "source": "github"
        }


# Singleton instance
_github_service: Optional[GitHubService] = None


def get_github_service() -> GitHubService:
    """Get or create GitHub service singleton."""
    global _github_service
    if _github_service is None:
        # Could load token from environment here
        # token = os.environ.get("GITHUB_TOKEN")
        _github_service = GitHubService()
    return _github_service
