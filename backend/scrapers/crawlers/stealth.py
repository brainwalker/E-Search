"""
Stealth crawler for sites with bot detection.

Uses Playwright with enhanced stealth features to bypass bot detection.
This includes realistic browser fingerprints, proper headers, and human-like behavior.
"""

import asyncio
import random
from typing import Optional, Dict
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
import logging

logger = logging.getLogger(__name__)


class StealthCrawler:
    """
    Stealth crawler using Playwright with anti-bot bypass features.
    
    Features:
    - Realistic browser fingerprints
    - Proper headers and cookies
    - Human-like delays and interactions
    - JavaScript rendering
    """

    def __init__(
        self,
        rate_limit: float = 3.0,
        timeout: float = 30.0,
        headless: bool = True,
        max_retries: int = 3
    ):
        """
        Initialize the stealth crawler.

        Args:
            rate_limit: Seconds to wait between requests
            timeout: Request timeout in seconds
            headless: Run browser in headless mode
            max_retries: Number of retries on failure
        """
        self.rate_limit = rate_limit
        self.timeout = timeout
        self.headless = headless
        self.max_retries = max_retries
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._playwright = None
        self._last_request_time = 0

    async def _wait_for_rate_limit(self):
        """Wait to respect rate limit with some randomization."""
        import time
        now = time.time()
        elapsed = now - self._last_request_time
        # Add small random delay to appear more human-like
        wait_time = self.rate_limit - elapsed + random.uniform(0, 0.5)
        if wait_time > 0:
            await asyncio.sleep(wait_time)
        self._last_request_time = time.time()

    async def _init_browser(self):
        """Initialize browser and context if not already done."""
        if self._browser is None:
            self._playwright = await async_playwright().start()
            
            # Launch browser with stealth settings
            self._browser = await self._playwright.chromium.launch(
                headless=self.headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-web-security',
                    '--disable-features=IsolateOrigins,site-per-process',
                ]
            )
            
            # Create context with realistic viewport and user agent
            self._context = await self._browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                locale='en-US',
                timezone_id='America/Toronto',
                extra_http_headers={
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
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
                }
            )
            
            # Add script to hide automation indicators
            await self._context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                
                // Override plugins
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                
                // Override languages
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en']
                });
                
                // Override permissions
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );
            """)

    async def _cleanup(self):
        """Clean up browser resources."""
        if self._context:
            await self._context.close()
            self._context = None
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    async def fetch(
        self,
        url: str,
        wait_selector: Optional[str] = None,
        wait_time: float = 2.0,
        cookies: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Fetch a URL with stealth browser.

        Args:
            url: URL to fetch
            wait_selector: Optional CSS selector to wait for
            wait_time: Time to wait after page load (for JS execution)
            cookies: Optional cookies to set

        Returns:
            HTML content as string

        Raises:
            Exception: On request failure after retries
        """
        await self._wait_for_rate_limit()
        await self._init_browser()

        last_error = None
        for attempt in range(self.max_retries):
            page: Optional[Page] = None
            try:
                page = await self._context.new_page()
                
                # Set cookies if provided
                if cookies:
                    await self._context.add_cookies([
                        {'name': k, 'value': v, 'url': url, 'domain': url.split('/')[2]}
                        for k, v in cookies.items()
                    ])
                
                # Navigate to page
                response = await page.goto(
                    url,
                    wait_until='domcontentloaded',
                    timeout=int(self.timeout * 1000)
                )
                
                if response and response.status >= 400:
                    raise Exception(f"HTTP {response.status} for {url}")
                
                # Wait for selector if specified
                if wait_selector:
                    try:
                        await page.wait_for_selector(wait_selector, timeout=10000)
                    except Exception as e:
                        logger.warning(f"Selector {wait_selector} not found: {e}")
                
                # Wait a bit for JavaScript to execute
                await asyncio.sleep(wait_time)
                
                # Simulate human-like behavior (scroll)
                await page.evaluate("""
                    window.scrollTo(0, document.body.scrollHeight / 3);
                """)
                await asyncio.sleep(0.5)
                await page.evaluate("""
                    window.scrollTo(0, document.body.scrollHeight);
                """)
                await asyncio.sleep(0.3)
                
                # Get page content
                content = await page.content()
                await page.close()
                return content

            except Exception as e:
                last_error = e
                if page:
                    try:
                        await page.close()
                    except:
                        pass
                logger.warning(f"Attempt {attempt + 1}/{self.max_retries} failed for {url}: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff

        raise last_error or Exception(f"Failed to fetch {url} after {self.max_retries} attempts")

    async def fetch_soup(
        self,
        url: str,
        wait_selector: Optional[str] = None,
        wait_time: float = 2.0,
        cookies: Optional[Dict[str, str]] = None
    ) -> BeautifulSoup:
        """
        Fetch a URL and return parsed BeautifulSoup.

        Args:
            url: URL to fetch
            wait_selector: Optional CSS selector to wait for
            wait_time: Time to wait after page load
            cookies: Optional cookies to set

        Returns:
            BeautifulSoup object
        """
        html = await self.fetch(url, wait_selector, wait_time, cookies)
        return BeautifulSoup(html, 'html.parser')

    async def close(self):
        """Close the browser and cleanup resources."""
        await self._cleanup()

    async def __aenter__(self):
        """Async context manager entry."""
        await self._init_browser()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self._cleanup()
