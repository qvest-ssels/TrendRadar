"""
Browser Service - Playwright-based JavaScript rendering for site search.

This module provides headless browser support for scraping JavaScript-rendered
pages. It's designed to be optional - if Playwright is not installed, the
service gracefully degrades.

Usage:
    from mcp_server.services.browser_service import BrowserService
    
    async with BrowserService() as browser:
        html = await browser.get_page_content("https://example.com/search?q=test")
        # Parse html with BeautifulSoup
"""

import asyncio
import logging
from typing import Optional, Dict, List, Any
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

# Check if Playwright is available
PLAYWRIGHT_AVAILABLE = False
try:
    from playwright.async_api import async_playwright, Browser, Page, Playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    logger.info("Playwright not installed. JavaScript rendering disabled. Install with: pip install playwright && playwright install chromium")


class BrowserService:
    """
    Async browser service for JavaScript-rendered page scraping.
    
    Features:
    - Lazy browser initialization (only starts when needed)
    - Connection pooling (reuses browser instance)
    - Automatic cleanup
    - Graceful degradation if Playwright not installed
    """
    
    # Configuration
    DEFAULT_TIMEOUT = 15000  # 15 seconds
    DEFAULT_WAIT_FOR = "domcontentloaded"  # Faster than networkidle
    
    USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    
    def __init__(self):
        """Initialize browser service - each instance gets fresh state."""
        self._playwright = None
        self._browser = None
        self._context = None
    
    @classmethod
    def is_available(cls) -> bool:
        """Check if Playwright is available."""
        return PLAYWRIGHT_AVAILABLE
    
    async def _ensure_browser(self) -> bool:
        """Ensure browser is started. Returns True if successful."""
        if not PLAYWRIGHT_AVAILABLE:
            logger.warning("Playwright not available - cannot render JavaScript")
            return False
        
        if self._browser is None or not self._browser.is_connected():
            try:
                logger.debug("Starting Playwright browser...")
                self._playwright = await async_playwright().start()
                self._browser = await self._playwright.chromium.launch(
                    headless=True,
                    args=[
                        '--disable-gpu',
                        '--disable-dev-shm-usage',
                        '--disable-setuid-sandbox',
                        '--no-sandbox',
                        '--disable-extensions',
                    ]
                )
                logger.debug("Playwright browser started successfully")
            except Exception as e:
                logger.error(f"Failed to start browser: {e}")
                return False
        
        return True
    
    async def cleanup(self):
        """Clean up browser resources."""
        try:
            if self._browser:
                await self._browser.close()
                self._browser = None
            if self._playwright:
                await self._playwright.stop()
                self._playwright = None
        except Exception as e:
            logger.debug(f"Cleanup error (safe to ignore): {e}")
    
    async def get_page_content(
        self,
        url: str,
        wait_for: str = None,
        wait_selector: str = None,
        timeout: int = None,
        extra_headers: Dict[str, str] = None
    ) -> Optional[str]:
        """
        Fetch page content with JavaScript rendering.
        
        Args:
            url: URL to fetch
            wait_for: Wait condition - "load", "domcontentloaded", "networkidle"
            wait_selector: CSS selector to wait for before returning
            timeout: Timeout in milliseconds
            extra_headers: Additional HTTP headers
            
        Returns:
            HTML content of the rendered page, or None on failure
        """
        if not await self._ensure_browser():
            return None
        
        timeout = timeout or self.DEFAULT_TIMEOUT
        wait_for = wait_for or self.DEFAULT_WAIT_FOR
        
        page = None
        try:
            # Create new context for isolation
            context = await self._browser.new_context(
                user_agent=self.USER_AGENT,
                viewport={'width': 1920, 'height': 1080},
                extra_http_headers=extra_headers or {}
            )
            
            page = await context.new_page()
            
            # Navigate to URL
            logger.debug(f"Fetching {url} with Playwright...")
            await page.goto(url, wait_until=wait_for, timeout=timeout)
            
            # Wait for specific selector if provided
            if wait_selector:
                try:
                    await page.wait_for_selector(wait_selector, timeout=timeout)
                except Exception as e:
                    logger.warning(f"Selector {wait_selector} not found: {e}")
            
            # Small delay to let dynamic content load
            await asyncio.sleep(0.5)
            
            # Get rendered HTML
            content = await page.content()
            logger.debug(f"Successfully fetched {len(content)} bytes from {url}")
            
            return content
            
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None
        finally:
            if page:
                await page.close()
            if self._context:
                await context.close()
    
    async def search_and_extract(
        self,
        url: str,
        selectors: Dict[str, str],
        wait_selector: str = None,
        max_results: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Fetch page, render JavaScript, and extract search results.
        
        Args:
            url: Search URL
            selectors: Dict with CSS selectors for results, title, link, etc.
            wait_selector: Selector to wait for before extracting
            max_results: Maximum results to extract
            
        Returns:
            List of extracted results
        """
        from bs4 import BeautifulSoup
        
        html = await self.get_page_content(
            url,
            wait_selector=wait_selector or selectors.get("results")
        )
        
        if not html:
            return []
        
        soup = BeautifulSoup(html, 'html.parser')
        results = []
        
        # Find result containers
        result_selector = selectors.get("results", "article")
        containers = soup.select(result_selector)
        
        logger.debug(f"Found {len(containers)} result containers with selector: {result_selector}")
        
        for container in containers[:max_results * 2]:  # Get extra in case some are filtered
            result = self._extract_result(container, selectors, url)
            if result:
                results.append(result)
                if len(results) >= max_results:
                    break
        
        logger.info(f"Extracted {len(results)} results from {url}")
        return results
    
    def _extract_result(
        self,
        container,
        selectors: Dict[str, str],
        base_url: str
    ) -> Optional[Dict[str, Any]]:
        """Extract a single result from a container element."""
        from urllib.parse import urljoin
        
        result = {"source": "site_search"}
        
        # Extract title
        title_selector = selectors.get("title", "h2, h3, a")
        title_el = container.select_one(title_selector)
        if title_el:
            result["title"] = title_el.get_text(strip=True)
        
        # Extract link
        link_selector = selectors.get("link", "a")
        link_el = container.select_one(link_selector)
        if link_el and link_el.get("href"):
            href = link_el.get("href")
            result["url"] = urljoin(base_url, href) if not href.startswith("http") else href
        
        # Try to get link from title element if it's an anchor
        if not result.get("url") and title_el and title_el.name == "a":
            href = title_el.get("href")
            if href:
                result["url"] = urljoin(base_url, href) if not href.startswith("http") else href
        
        # Extract description
        desc_selector = selectors.get("description", "p")
        desc_el = container.select_one(desc_selector)
        if desc_el:
            result["description"] = desc_el.get_text(strip=True)[:300]
        
        # Extract date
        date_selector = selectors.get("date", "time")
        date_el = container.select_one(date_selector)
        if date_el:
            result["date"] = date_el.get("datetime") or date_el.get_text(strip=True)
        
        # Validate result
        if not result.get("title") or len(result.get("title", "")) < 5:
            return None
        if not result.get("url"):
            return None
        
        return result
    
    async def close(self):
        """Close browser and cleanup resources."""
        if self._browser:
            try:
                await self._browser.close()
                self._browser = None
            except Exception as e:
                logger.error(f"Error closing browser: {e}")
        
        if self._playwright:
            try:
                await self._playwright.stop()
                self._playwright = None
            except Exception as e:
                logger.error(f"Error stopping playwright: {e}")
        
        BrowserService._instance = None
        logger.info("Browser service closed")
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self._ensure_browser()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - don't close browser, keep for reuse."""
        # Don't close browser here - it's reused across requests
        pass


# Convenience function for one-off searches
async def browser_search(
    url: str,
    selectors: Dict[str, str],
    platform_id: str = "unknown",
    max_results: int = 20
) -> List[Dict[str, Any]]:
    """
    Convenience function to perform a browser-based search.
    
    Args:
        url: Search URL
        selectors: CSS selectors for extraction
        platform_id: Platform identifier for results
        max_results: Maximum results
        
    Returns:
        List of search results
    """
    if not PLAYWRIGHT_AVAILABLE:
        logger.warning(f"Playwright not available for {platform_id} search")
        return []
    
    service = await BrowserService.get_instance()
    results = await service.search_and_extract(url, selectors, max_results=max_results)
    
    # Add platform_id to results
    for result in results:
        result["platform_id"] = platform_id
    
    return results


# Cleanup function for graceful shutdown
async def cleanup_browser():
    """Cleanup browser resources. Call on application shutdown."""
    if BrowserService._instance:
        await BrowserService._instance.close()
