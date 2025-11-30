"""
HuggingFace Hub Service

Provides access to HuggingFace Hub for searching models, datasets, and papers.
Part of the "Ask an Expert" feature for technical/ML research.
Caches results to reduce API calls.
"""

import html
import logging
import re
from typing import Dict, List, Optional, Any
from urllib.parse import quote

import requests

logger = logging.getLogger(__name__)

# Import cache
try:
    from ..utils.cache import get_cache
    CACHE_AVAILABLE = True
except ImportError:
    CACHE_AVAILABLE = False
    logger.warning("Cache not available, HuggingFace requests will not be cached")


def sanitize_html(text: str) -> str:
    """
    Sanitize HTML content to prevent XSS attacks.
    Removes all HTML tags and escapes special characters.
    
    Args:
        text: Raw HTML text
        
    Returns:
        Sanitized plain text
    """
    if not text:
        return ""
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Escape HTML entities
    text = html.escape(text)
    return text


def sanitize_url(url: str) -> str:
    """
    Validate and sanitize URL to prevent injection.
    Only allows HuggingFace URLs.
    
    Args:
        url: URL to sanitize
        
    Returns:
        Sanitized URL or empty string if invalid
    """
    if not url:
        return ""
    # Only allow HuggingFace domains
    if not re.match(r'^https?://(huggingface\.co|hf\.co)/', url):
        return ""
    # Remove any script injection attempts
    if re.search(r'javascript:|data:|vbscript:', url, re.IGNORECASE):
        return ""
    return url


class HuggingFaceService:
    """
    Service for searching HuggingFace Hub.
    
    Supports:
    - Model search by task, query, downloads
    - Dataset search
    - Paper search (daily papers, arXiv)
    - Model/dataset details
    """
    
    BASE_URL = "https://huggingface.co/api"
    WEB_URL = "https://huggingface.co"
    
    # Common task types for filtering
    TASK_TYPES = {
        "text-generation": "Text Generation (LLMs)",
        "text-classification": "Text Classification",
        "token-classification": "Named Entity Recognition",
        "question-answering": "Question Answering",
        "translation": "Translation",
        "summarization": "Summarization",
        "conversational": "Conversational/Chat",
        "fill-mask": "Fill Mask (BERT-style)",
        "text2text-generation": "Text-to-Text",
        "image-classification": "Image Classification",
        "object-detection": "Object Detection",
        "image-segmentation": "Image Segmentation",
        "text-to-image": "Text to Image",
        "image-to-text": "Image to Text",
        "audio-classification": "Audio Classification",
        "automatic-speech-recognition": "Speech Recognition",
        "text-to-speech": "Text to Speech",
        "feature-extraction": "Feature Extraction/Embeddings",
        "sentence-similarity": "Sentence Similarity",
        "zero-shot-classification": "Zero-Shot Classification",
        "reinforcement-learning": "Reinforcement Learning",
    }
    
    USER_AGENT = "TrendRadar/1.0 (Ask an Expert feature; news aggregation tool)"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.USER_AGENT,
            "Accept": "application/json"
        })
    
    def search_models(
        self,
        query: str,
        task: Optional[str] = None,
        sort: str = "downloads",
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Search for models on HuggingFace Hub.
        
        Args:
            query: Search query (e.g., "code generation", "llama")
            task: Filter by task type (e.g., "text-generation")
            sort: Sort by "downloads", "likes", "created", "modified"
            limit: Maximum results (max 100)
            
        Returns:
            Dict with models and metadata
        """
        # Check cache first (1 hour TTL for HuggingFace)
        if CACHE_AVAILABLE:
            cache = get_cache("huggingface", ttl=3600)
            cache_key = cache.make_key(
                "hf_models",
                query=query,
                task=task,
                sort=sort,
                limit=limit
            )
            cached = cache.get(cache_key)
            if cached is not None:
                logger.debug(f"Cache hit for HF models: {query}")
                cached["cached"] = True
                return cached
        
        try:
            params = {
                "search": query,
                "sort": sort,
                "direction": "-1",  # Descending
                "limit": min(limit, 100),
            }
            
            if task and task in self.TASK_TYPES:
                params["filter"] = task
            
            url = f"{self.BASE_URL}/models"
            response = self.session.get(url, params=params, timeout=15)
            
            if response.status_code == 200:
                models = response.json()
                
                results = []
                for model in models[:limit]:
                    model_id = model.get("id", "")
                    results.append({
                        "id": sanitize_html(model_id),
                        "name": sanitize_html(model_id.split("/")[-1] if "/" in model_id else model_id),
                        "author": sanitize_html(model_id.split("/")[0] if "/" in model_id else "unknown"),
                        "downloads": model.get("downloads", 0),
                        "likes": model.get("likes", 0),
                        "task": model.get("pipeline_tag", ""),
                        "tags": [sanitize_html(t) for t in model.get("tags", [])[:10]],
                        "url": f"{self.WEB_URL}/{model_id}",
                        "last_modified": model.get("lastModified", ""),
                    })
                
                result = {
                    "success": True,
                    "query": query,
                    "task_filter": task,
                    "sort": sort,
                    "count": len(results),
                    "models": results,
                    "source": "huggingface"
                }
                
                # Cache successful results
                if CACHE_AVAILABLE:
                    cache.set(cache_key, result)
                    logger.debug(f"Cached HF models for: {query}")
                
                return result
            else:
                logger.warning(f"HuggingFace API returned {response.status_code}")
                return {
                    "success": False,
                    "error": f"API returned status {response.status_code}",
                    "query": query
                }
                
        except requests.Timeout:
            logger.error("HuggingFace API timeout")
            return {
                "success": False,
                "error": "Request timed out",
                "query": query
            }
        except Exception as e:
            logger.error(f"HuggingFace search error: {e}")
            return {
                "success": False,
                "error": str(e),
                "query": query
            }
    
    def search_datasets(
        self,
        query: str,
        sort: str = "downloads",
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Search for datasets on HuggingFace Hub.
        
        Args:
            query: Search query
            sort: Sort by "downloads", "likes", "created", "modified"
            limit: Maximum results
            
        Returns:
            Dict with datasets and metadata
        """
        # Check cache first (1 hour TTL for HuggingFace)
        if CACHE_AVAILABLE:
            cache = get_cache("huggingface", ttl=3600)
            cache_key = cache.make_key(
                "hf_datasets",
                query=query,
                sort=sort,
                limit=limit
            )
            cached = cache.get(cache_key)
            if cached is not None:
                logger.debug(f"Cache hit for HF datasets: {query}")
                cached["cached"] = True
                return cached
        
        try:
            params = {
                "search": query,
                "sort": sort,
                "direction": "-1",
                "limit": min(limit, 100),
            }
            
            url = f"{self.BASE_URL}/datasets"
            response = self.session.get(url, params=params, timeout=15)
            
            if response.status_code == 200:
                datasets = response.json()
                
                results = []
                for ds in datasets[:limit]:
                    ds_id = ds.get("id", "")
                    results.append({
                        "id": sanitize_html(ds_id),
                        "name": sanitize_html(ds_id.split("/")[-1] if "/" in ds_id else ds_id),
                        "author": sanitize_html(ds_id.split("/")[0] if "/" in ds_id else "unknown"),
                        "downloads": ds.get("downloads", 0),
                        "likes": ds.get("likes", 0),
                        "tags": [sanitize_html(t) for t in ds.get("tags", [])[:10]],
                        "url": f"{self.WEB_URL}/datasets/{ds_id}",
                        "last_modified": ds.get("lastModified", ""),
                    })
                
                result = {
                    "success": True,
                    "query": query,
                    "sort": sort,
                    "count": len(results),
                    "datasets": results,
                    "source": "huggingface"
                }
                
                # Cache successful results
                if CACHE_AVAILABLE:
                    cache.set(cache_key, result)
                    logger.debug(f"Cached HF datasets for: {query}")
                
                return result
            else:
                return {
                    "success": False,
                    "error": f"API returned status {response.status_code}",
                    "query": query
                }
                
        except Exception as e:
            logger.error(f"HuggingFace dataset search error: {e}")
            return {
                "success": False,
                "error": str(e),
                "query": query
            }
    
    def get_model_info(
        self,
        model_id: str
    ) -> Dict[str, Any]:
        """
        Get detailed information about a specific model.
        
        Args:
            model_id: Model ID (e.g., "meta-llama/Llama-2-7b")
            
        Returns:
            Dict with model details
        """
        try:
            url = f"{self.BASE_URL}/models/{model_id}"
            response = self.session.get(url, timeout=15)
            
            if response.status_code == 200:
                model = response.json()
                
                return {
                    "success": True,
                    "id": sanitize_html(model.get("id", "")),
                    "author": sanitize_html(model.get("author", "")),
                    "downloads": model.get("downloads", 0),
                    "likes": model.get("likes", 0),
                    "task": model.get("pipeline_tag", ""),
                    "tags": [sanitize_html(t) for t in model.get("tags", [])],
                    "library": model.get("library_name", ""),
                    "license": sanitize_html(model.get("license", "")),
                    "created": model.get("createdAt", ""),
                    "modified": model.get("lastModified", ""),
                    "url": f"{self.WEB_URL}/{model_id}",
                    "source": "huggingface"
                }
            elif response.status_code == 404:
                return {
                    "success": False,
                    "error": "Model not found",
                    "model_id": model_id
                }
            else:
                return {
                    "success": False,
                    "error": f"API returned status {response.status_code}",
                    "model_id": model_id
                }
                
        except Exception as e:
            logger.error(f"HuggingFace model info error: {e}")
            return {
                "success": False,
                "error": str(e),
                "model_id": model_id
            }
    
    def get_daily_papers(
        self,
        limit: int = 10,
        date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get daily papers curated on HuggingFace.
        
        Args:
            limit: Maximum number of papers
            date: Specific date (YYYY-MM-DD) or None for latest
            
        Returns:
            Dict with papers
        """
        try:
            params = {"limit": min(limit, 50)}
            if date:
                params["date"] = date
            
            url = f"{self.BASE_URL}/daily_papers"
            response = self.session.get(url, params=params, timeout=15)
            
            if response.status_code == 200:
                papers = response.json()
                
                results = []
                for paper in papers[:limit]:
                    paper_data = paper.get("paper", {})
                    arxiv_id = paper_data.get("id", "")
                    
                    results.append({
                        "arxiv_id": sanitize_html(arxiv_id),
                        "title": sanitize_html(paper_data.get("title", "")),
                        "summary": sanitize_html(paper_data.get("summary", ""))[:500],  # Truncate
                        "authors": [sanitize_html(a.get("name", "")) for a in paper_data.get("authors", [])[:5]],
                        "published": paper_data.get("publishedAt", ""),
                        "upvotes": paper.get("paper", {}).get("upvotes", 0),
                        "url": f"{self.WEB_URL}/papers/{arxiv_id}" if arxiv_id else "",
                        "arxiv_url": f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else "",
                    })
                
                return {
                    "success": True,
                    "date": date or "latest",
                    "count": len(results),
                    "papers": results,
                    "source": "huggingface_papers"
                }
            else:
                return {
                    "success": False,
                    "error": f"API returned status {response.status_code}"
                }
                
        except Exception as e:
            logger.error(f"HuggingFace papers error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def search_papers(
        self,
        query: str,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Search papers on HuggingFace by keyword.
        
        Args:
            query: Search query
            limit: Maximum results
            
        Returns:
            Dict with matching papers
        """
        try:
            params = {
                "q": query,
                "limit": min(limit, 50)
            }
            
            url = f"{self.BASE_URL}/papers/search"
            response = self.session.get(url, params=params, timeout=15)
            
            if response.status_code == 200:
                papers = response.json()
                
                results = []
                for paper in papers[:limit]:
                    arxiv_id = paper.get("id", "")
                    
                    results.append({
                        "arxiv_id": sanitize_html(arxiv_id),
                        "title": sanitize_html(paper.get("title", "")),
                        "summary": sanitize_html(paper.get("summary", ""))[:500],
                        "authors": [sanitize_html(a.get("name", "")) for a in paper.get("authors", [])[:5]],
                        "published": paper.get("publishedAt", ""),
                        "url": f"{self.WEB_URL}/papers/{arxiv_id}" if arxiv_id else "",
                        "arxiv_url": f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else "",
                    })
                
                return {
                    "success": True,
                    "query": query,
                    "count": len(results),
                    "papers": results,
                    "source": "huggingface_papers"
                }
            else:
                return {
                    "success": False,
                    "error": f"API returned status {response.status_code}",
                    "query": query
                }
                
        except Exception as e:
            logger.error(f"HuggingFace paper search error: {e}")
            return {
                "success": False,
                "error": str(e),
                "query": query
            }
    
    def get_task_types(self) -> Dict[str, Any]:
        """
        Get available task types for model filtering.
        
        Returns:
            Dict with task types and descriptions
        """
        return {
            "success": True,
            "tasks": self.TASK_TYPES,
            "source": "huggingface"
        }


# Singleton instance
_huggingface_service = None


def get_huggingface_service() -> HuggingFaceService:
    """Get or create HuggingFace service singleton."""
    global _huggingface_service
    if _huggingface_service is None:
        _huggingface_service = HuggingFaceService()
    return _huggingface_service
