"""
arXiv Research Papers Service

Provides access to arXiv for searching academic papers.
Part of the "Ask an Expert" feature for technical/scientific research.

Includes university linking via Wikipedia for author affiliations.
Caches results to reduce API calls.
"""

import hashlib
import html
import logging
import re
import xml.etree.ElementTree as ET
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
    logger.warning("Cache not available, arXiv requests will not be cached")


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
    Only allows arXiv URLs.
    """
    if not url:
        return ""
    # Only allow arXiv domains
    if not re.match(r'^https?://(arxiv\.org|export\.arxiv\.org)/', url):
        return ""
    # Remove any script injection attempts
    if re.search(r'javascript:|data:|vbscript:', url, re.IGNORECASE):
        return ""
    return url


class ArxivService:
    """
    Service for searching arXiv papers.
    
    Supports:
    - Paper search by query and category
    - Get paper details by ID
    - Extract author affiliations
    - Link to universities via Wikipedia
    """
    
    API_URL = "http://export.arxiv.org/api/query"
    
    # Common arXiv categories for CS/ML
    CATEGORIES = {
        "cs.AI": "Artificial Intelligence",
        "cs.CL": "Computation and Language (NLP)",
        "cs.CV": "Computer Vision",
        "cs.LG": "Machine Learning",
        "cs.NE": "Neural and Evolutionary Computing",
        "cs.IR": "Information Retrieval",
        "cs.RO": "Robotics",
        "cs.SE": "Software Engineering",
        "cs.DC": "Distributed Computing",
        "cs.CR": "Cryptography and Security",
        "stat.ML": "Machine Learning (Statistics)",
        "math.OC": "Optimization and Control",
        "eess.AS": "Audio and Speech Processing",
        "eess.IV": "Image and Video Processing",
        "q-bio.NC": "Neurons and Cognition",
    }
    
    # Known universities for quick matching (expanded on demand)
    KNOWN_UNIVERSITIES = {
        "MIT": "Massachusetts Institute of Technology",
        "Stanford": "Stanford University",
        "Berkeley": "University of California, Berkeley",
        "CMU": "Carnegie Mellon University",
        "Harvard": "Harvard University",
        "Oxford": "University of Oxford",
        "Cambridge": "University of Cambridge",
        "ETH": "ETH Zurich",
        "DeepMind": "DeepMind",
        "Google": "Google",
        "OpenAI": "OpenAI",
        "Meta": "Meta AI",
        "Microsoft": "Microsoft Research",
        "Apple": "Apple",
        "NVIDIA": "NVIDIA",
        "Anthropic": "Anthropic",
    }
    
    USER_AGENT = "TrendRadar/1.0 (Ask an Expert feature; news aggregation tool)"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.USER_AGENT,
        })
        self._wikipedia_service = None
    
    def _get_wikipedia_service(self):
        """Lazy load Wikipedia service for university linking."""
        if self._wikipedia_service is None:
            try:
                from .wikipedia_service import get_wikipedia_service
                self._wikipedia_service = get_wikipedia_service()
            except ImportError:
                logger.warning("Wikipedia service not available for university linking")
        return self._wikipedia_service
    
    def search(
        self,
        query: str,
        category: Optional[str] = None,
        max_results: int = 10,
        sort_by: str = "relevance",
        include_university_links: bool = True
    ) -> Dict[str, Any]:
        """
        Search arXiv for papers matching a query.
        
        Args:
            query: Search query (e.g., "transformer architecture", "RAG")
            category: Filter by arXiv category (e.g., "cs.LG", "cs.CL")
            max_results: Maximum number of results (default: 10, max: 50)
            sort_by: Sort order - "relevance", "lastUpdatedDate", "submittedDate"
            include_university_links: Whether to add Wikipedia links for universities
            
        Returns:
            Dict with papers including title, authors, abstract, URLs
        """
        # Check cache first (30 min TTL for arXiv)
        if CACHE_AVAILABLE:
            cache = get_cache("arxiv", ttl=1800)
            cache_key = cache.make_key(
                "arxiv_search",
                query=query,
                category=category,
                max_results=max_results,
                sort_by=sort_by
            )
            cached = cache.get(cache_key)
            if cached is not None:
                logger.debug(f"Cache hit for arXiv query: {query}")
                cached["cached"] = True
                return cached
        
        try:
            # Build search query
            search_parts = []
            
            # Add main query
            if query:
                # Search in title, abstract, and all fields
                search_parts.append(f'all:{query}')
            
            # Add category filter
            if category and category in self.CATEGORIES:
                search_parts.append(f'cat:{category}')
            
            search_query = " AND ".join(search_parts) if search_parts else "all:*"
            
            # Map sort options
            sort_map = {
                "relevance": "relevance",
                "lastUpdatedDate": "lastUpdatedDate",
                "submittedDate": "submittedDate",
                "date": "submittedDate",
            }
            sort_order = sort_map.get(sort_by, "relevance")
            
            params = {
                "search_query": search_query,
                "start": 0,
                "max_results": min(max_results, 50),
                "sortBy": sort_order,
                "sortOrder": "descending",
            }
            
            response = self.session.get(self.API_URL, params=params, timeout=15)
            
            if response.status_code != 200:
                logger.warning(f"arXiv API returned {response.status_code}")
                return {
                    "success": False,
                    "error": f"API returned status {response.status_code}",
                    "query": query
                }
            
            # Parse Atom XML response
            papers = self._parse_atom_response(response.text, include_university_links)
            
            result = {
                "success": True,
                "query": query,
                "category": category,
                "category_name": self.CATEGORIES.get(category, "") if category else "",
                "count": len(papers),
                "papers": papers,
                "source": "arxiv"
            }
            
            # Cache successful results
            if CACHE_AVAILABLE and result["success"]:
                cache.set(cache_key, result)
                logger.debug(f"Cached arXiv results for: {query}")
            
            return result
            
        except requests.Timeout:
            logger.error("arXiv API timeout")
            return {
                "success": False,
                "error": "Request timed out",
                "query": query
            }
        except Exception as e:
            logger.error(f"arXiv search error: {e}")
            return {
                "success": False,
                "error": str(e),
                "query": query
            }
    
    def _parse_atom_response(
        self,
        xml_text: str,
        include_university_links: bool = True
    ) -> List[Dict[str, Any]]:
        """Parse arXiv Atom XML response into structured data."""
        papers = []
        
        try:
            # Define namespaces
            ns = {
                'atom': 'http://www.w3.org/2005/Atom',
                'arxiv': 'http://arxiv.org/schemas/atom',
            }
            
            root = ET.fromstring(xml_text)
            
            for entry in root.findall('atom:entry', ns):
                paper = self._parse_entry(entry, ns, include_university_links)
                if paper:
                    papers.append(paper)
                    
        except ET.ParseError as e:
            logger.error(f"XML parse error: {e}")
        
        return papers
    
    def _parse_entry(
        self,
        entry: ET.Element,
        ns: Dict[str, str],
        include_university_links: bool
    ) -> Optional[Dict[str, Any]]:
        """Parse a single arXiv entry."""
        try:
            # Get arXiv ID from the id URL
            id_elem = entry.find('atom:id', ns)
            arxiv_url = id_elem.text if id_elem is not None else ""
            arxiv_id = arxiv_url.split('/')[-1] if arxiv_url else ""
            
            # Get title
            title_elem = entry.find('atom:title', ns)
            title = sanitize_html(title_elem.text) if title_elem is not None else ""
            
            # Get abstract/summary
            summary_elem = entry.find('atom:summary', ns)
            abstract = sanitize_html(summary_elem.text) if summary_elem is not None else ""
            # Truncate long abstracts
            if len(abstract) > 500:
                abstract = abstract[:497] + "..."
            
            # Get authors with affiliations
            authors = []
            affiliations = set()
            for author_elem in entry.findall('atom:author', ns):
                name_elem = author_elem.find('atom:name', ns)
                if name_elem is not None:
                    author_name = sanitize_html(name_elem.text)
                    authors.append(author_name)
                
                # Check for affiliation in arxiv namespace
                affil_elem = author_elem.find('arxiv:affiliation', ns)
                if affil_elem is not None and affil_elem.text:
                    affiliations.add(sanitize_html(affil_elem.text))
            
            # Get dates
            published_elem = entry.find('atom:published', ns)
            published = published_elem.text if published_elem is not None else ""
            
            updated_elem = entry.find('atom:updated', ns)
            updated = updated_elem.text if updated_elem is not None else ""
            
            # Get PDF link
            pdf_url = ""
            for link in entry.findall('atom:link', ns):
                if link.get('title') == 'pdf':
                    pdf_url = sanitize_url(link.get('href', ''))
                    break
            
            # Get categories
            categories = []
            primary_category = ""
            
            primary_cat_elem = entry.find('arxiv:primary_category', ns)
            if primary_cat_elem is not None:
                primary_category = primary_cat_elem.get('term', '')
            
            for cat_elem in entry.findall('atom:category', ns):
                cat_term = cat_elem.get('term', '')
                if cat_term:
                    categories.append(cat_term)
            
            # Get journal reference if available
            journal_ref_elem = entry.find('arxiv:journal_ref', ns)
            journal_ref = sanitize_html(journal_ref_elem.text) if journal_ref_elem is not None else ""
            
            # Get comment (often contains page count, conference info)
            comment_elem = entry.find('arxiv:comment', ns)
            comment = sanitize_html(comment_elem.text) if comment_elem is not None else ""
            
            # Build paper dict
            paper = {
                "arxiv_id": arxiv_id,
                "title": title,
                "abstract": abstract,
                "authors": authors[:10],  # Limit to 10 authors
                "affiliations": list(affiliations)[:5],  # Limit affiliations
                "published": published,
                "updated": updated,
                "primary_category": primary_category,
                "categories": categories[:5],
                "url": f"https://arxiv.org/abs/{arxiv_id}",
                "pdf_url": pdf_url or f"https://arxiv.org/pdf/{arxiv_id}.pdf",
                "journal_ref": journal_ref,
                "comment": comment,
            }
            
            # Add university links via Wikipedia
            if include_university_links and affiliations:
                paper["university_links"] = self._get_university_links(list(affiliations))
            
            return paper
            
        except Exception as e:
            logger.error(f"Error parsing entry: {e}")
            return None
    
    def _get_university_links(self, affiliations: List[str]) -> List[Dict[str, str]]:
        """
        Get Wikipedia links for universities/institutions in affiliations.
        
        Args:
            affiliations: List of affiliation strings
            
        Returns:
            List of dicts with name and Wikipedia URL
        """
        links = []
        wiki = self._get_wikipedia_service()
        
        for affil in affiliations[:3]:  # Limit to 3 to avoid too many API calls
            # First check known universities for quick match
            for key, full_name in self.KNOWN_UNIVERSITIES.items():
                if key.lower() in affil.lower():
                    if wiki:
                        try:
                            result = wiki.get_summary(full_name, "en")
                            if result.get("success"):
                                links.append({
                                    "name": full_name,
                                    "wikipedia_url": result.get("url", ""),
                                    "description": result.get("description", "")[:100]
                                })
                                break
                        except Exception as e:
                            logger.debug(f"Wikipedia lookup failed for {full_name}: {e}")
                    else:
                        # Fallback without Wikipedia
                        links.append({
                            "name": full_name,
                            "wikipedia_url": f"https://en.wikipedia.org/wiki/{quote(full_name.replace(' ', '_'))}",
                            "description": ""
                        })
                        break
            else:
                # If no known match, try Wikipedia search
                if wiki:
                    try:
                        # Clean up affiliation for search
                        search_term = re.sub(r'\s+', ' ', affil).strip()
                        result = wiki.search(search_term, "en", limit=1)
                        if result.get("success") and result.get("results"):
                            first = result["results"][0]
                            links.append({
                                "name": first.get("title", affil),
                                "wikipedia_url": first.get("url", ""),
                                "description": first.get("snippet", "")[:100]
                            })
                    except Exception as e:
                        logger.debug(f"Wikipedia search failed for {affil}: {e}")
        
        return links
    
    def get_paper(self, arxiv_id: str) -> Dict[str, Any]:
        """
        Get details for a specific arXiv paper by ID.
        
        Args:
            arxiv_id: arXiv paper ID (e.g., "2301.07041")
            
        Returns:
            Dict with paper details
        """
        try:
            params = {
                "id_list": arxiv_id,
                "max_results": 1,
            }
            
            response = self.session.get(self.API_URL, params=params, timeout=15)
            
            if response.status_code != 200:
                return {
                    "success": False,
                    "error": f"API returned status {response.status_code}",
                    "arxiv_id": arxiv_id
                }
            
            papers = self._parse_atom_response(response.text)
            
            if papers:
                return {
                    "success": True,
                    "paper": papers[0],
                    "source": "arxiv"
                }
            else:
                return {
                    "success": False,
                    "error": "Paper not found",
                    "arxiv_id": arxiv_id
                }
                
        except Exception as e:
            logger.error(f"arXiv get paper error: {e}")
            return {
                "success": False,
                "error": str(e),
                "arxiv_id": arxiv_id
            }
    
    def get_categories(self) -> Dict[str, Any]:
        """
        Get available arXiv categories.
        
        Returns:
            Dict with category codes and descriptions
        """
        return {
            "success": True,
            "categories": self.CATEGORIES,
            "source": "arxiv"
        }


# Singleton instance
_arxiv_service = None


def get_arxiv_service() -> ArxivService:
    """Get or create arXiv service singleton."""
    global _arxiv_service
    if _arxiv_service is None:
        _arxiv_service = ArxivService()
    return _arxiv_service
