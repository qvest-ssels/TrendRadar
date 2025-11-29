"""
Cloudscraper Service - Cloudflare bypass proxy service.

This service uses cloudscraper to bypass Cloudflare protection on websites.
It provides an alternative to Playwright for sites that have Cloudflare WAF.
"""

import asyncio
import logging
from typing import Optional
from urllib.parse import urljoin

import cloudscraper
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class CloudscraperService:
    """
    Service for bypassing Cloudflare protection using cloudscraper.
    
    This is used as a fallback/alternative for sites protected by Cloudflare
    where Playwright with stealth mode still gets blocked.
    """
    
    def __init__(self):
        """Initialize the cloudscraper service."""
        self._scraper = None
        self._initialized = False
        
    def _get_scraper(self):
        """Get or create a cloudscraper instance with stealth settings."""
        if self._scraper is None:
            self._scraper = cloudscraper.create_scraper(
                browser={
                    'browser': 'chrome',
                    'platform': 'darwin',  # macOS
                    'mobile': False,
                    'desktop': True,
                },
                delay=2,  # Delay between requests
                interpreter='nodejs',  # Use nodejs for JS challenges
            )
            # Add realistic headers
            self._scraper.headers.update({
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Cache-Control': 'max-age=0',
            })
            self._initialized = True
            logger.info("Cloudscraper initialized with Chrome/macOS profile")
        return self._scraper
    
    async def fetch_page(self, url: str, timeout: int = 30) -> Optional[str]:
        """
        Fetch a page using cloudscraper to bypass Cloudflare.
        
        Args:
            url: The URL to fetch
            timeout: Request timeout in seconds
            
        Returns:
            HTML content or None if failed
        """
        try:
            scraper = self._get_scraper()
            logger.info(f"Fetching with cloudscraper: {url}")
            
            # Run in thread pool since cloudscraper is synchronous
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: scraper.get(url, timeout=timeout)
            )
            
            if response.status_code == 200:
                logger.info(f"Successfully fetched {url} ({len(response.text)} chars)")
                return response.text
            else:
                logger.warning(f"Failed to fetch {url}: HTTP {response.status_code}")
                return None
                
        except cloudscraper.exceptions.CloudflareChallengeError as e:
            logger.error(f"Cloudflare challenge failed for {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None
    
    async def search_site(
        self,
        search_url: str,
        query: str,
        result_selector: str,
        title_selector: str = 'a',
        link_selector: str = 'a',
        max_results: int = 10,
        timeout: int = 30
    ) -> list[dict]:
        """
        Search a Cloudflare-protected site using cloudscraper.
        
        Args:
            search_url: URL with {query} placeholder
            query: Search query
            result_selector: CSS selector for result items
            title_selector: CSS selector for title within result
            link_selector: CSS selector for link within result
            max_results: Maximum results to return
            timeout: Request timeout
            
        Returns:
            List of search results with title and url
        """
        try:
            # Format the search URL
            import urllib.parse
            encoded_query = urllib.parse.quote_plus(query)
            url = search_url.replace('{query}', encoded_query)
            
            # Fetch the page
            html = await self.fetch_page(url, timeout=timeout)
            if not html:
                return []
            
            # Parse results
            soup = BeautifulSoup(html, 'html.parser')
            results = []
            
            items = soup.select(result_selector)
            logger.info(f"Found {len(items)} result items with selector '{result_selector}'")
            
            for item in items[:max_results]:
                try:
                    # Extract title
                    title_elem = item.select_one(title_selector) if title_selector != result_selector else item
                    title = title_elem.get_text(strip=True) if title_elem else ''
                    
                    # Extract link
                    link_elem = item.select_one(link_selector) if link_selector != result_selector else item
                    link = link_elem.get('href', '') if link_elem else ''
                    
                    # Handle relative URLs
                    if link and not link.startswith('http'):
                        base_url = '/'.join(url.split('/')[:3])
                        link = urljoin(base_url, link)
                    
                    if title and link:
                        results.append({
                            'title': title,
                            'url': link
                        })
                except Exception as e:
                    logger.debug(f"Error parsing result item: {e}")
                    continue
            
            logger.info(f"Extracted {len(results)} search results from {url}")
            return results
            
        except Exception as e:
            logger.error(f"Error searching {search_url}: {e}")
            return []
    
    async def test_cloudflare_bypass(self, url: str) -> dict:
        """
        Test if we can bypass Cloudflare for a given URL.
        
        Args:
            url: URL to test
            
        Returns:
            Dict with success status and details
        """
        try:
            html = await self.fetch_page(url, timeout=30)
            
            if html:
                # Check if we got a real page or Cloudflare challenge
                if 'Checking your browser' in html or 'cf-browser-verification' in html:
                    return {
                        'success': False,
                        'blocked': True,
                        'message': 'Cloudflare challenge not bypassed',
                        'content_length': len(html)
                    }
                elif 'Access denied' in html or 'Error 1015' in html:
                    return {
                        'success': False,
                        'blocked': True,
                        'message': 'Rate limited or blocked by Cloudflare',
                        'content_length': len(html)
                    }
                else:
                    # Check for some basic content indicators
                    soup = BeautifulSoup(html, 'html.parser')
                    title = soup.title.string if soup.title else 'No title'
                    has_articles = len(soup.select('article, .article, .story, .post')) > 0
                    
                    return {
                        'success': True,
                        'blocked': False,
                        'message': 'Successfully bypassed Cloudflare',
                        'title': title,
                        'has_articles': has_articles,
                        'content_length': len(html)
                    }
            else:
                return {
                    'success': False,
                    'blocked': False,
                    'message': 'Failed to fetch page (timeout or error)',
                    'content_length': 0
                }
                
        except Exception as e:
            return {
                'success': False,
                'blocked': False,
                'message': f'Error: {str(e)}',
                'content_length': 0
            }
    
    def close(self):
        """Close the scraper session."""
        if self._scraper:
            try:
                self._scraper.close()
            except:
                pass
            self._scraper = None
            self._initialized = False
            logger.info("Cloudscraper session closed")


# Singleton instance
_cloudscraper_service: Optional[CloudscraperService] = None


def get_cloudscraper_service() -> CloudscraperService:
    """Get the singleton cloudscraper service instance."""
    global _cloudscraper_service
    if _cloudscraper_service is None:
        _cloudscraper_service = CloudscraperService()
    return _cloudscraper_service
