"""
Stealth crawler for sites with bot detection.

Uses Playwright with enhanced stealth features to bypass bot detection.
This includes realistic browser fingerprints, proper headers, and human-like behavior.
"""

import asyncio
import random
import os
from typing import Optional, Dict
from urllib.parse import urlparse
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
        rate_limit: float = 1.5,  # Reduced from 3.0 for faster scraping
        timeout: float = 20.0,    # Reduced from 30.0
        headless: bool = True,
        max_retries: int = 3,
        reuse_page: bool = True   # Reuse page instead of creating new ones
    ):
        """
        Initialize the stealth crawler.

        Args:
            rate_limit: Seconds to wait between requests
            timeout: Request timeout in seconds
            headless: Run browser in headless mode
            max_retries: Number of retries on failure
            reuse_page: If True, reuse the same page for multiple requests (faster)
        """
        self.rate_limit = rate_limit
        self.timeout = timeout
        self.headless = headless
        self.max_retries = max_retries
        self.reuse_page = reuse_page
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None  # Reusable page
        self._playwright = None
        self._last_request_time = 0
        self._request_count = 0  # Track requests for periodic browser refresh

    async def _wait_for_rate_limit(self):
        """Wait to respect rate limit with some randomization."""
        import time
        now = time.time()
        elapsed = now - self._last_request_time
        # Add small random delay to appear more human-like (reduced randomization)
        wait_time = self.rate_limit - elapsed + random.uniform(0, 0.3)
        if wait_time > 0:
            await asyncio.sleep(wait_time)
        self._last_request_time = time.time()

    async def _get_or_create_page(self) -> Page:
        """Get reusable page or create a new one."""
        if self.reuse_page and self._page:
            try:
                # Check if page is still usable
                _ = self._page.url
                return self._page
            except Exception:
                self._page = None

        # Create new page
        page = await asyncio.wait_for(
            self._context.new_page(),
            timeout=10.0
        )
        if self.reuse_page:
            self._page = page
        return page

    async def _maybe_refresh_browser(self):
        """Periodically refresh browser to prevent memory leaks and crashes."""
        self._request_count += 1
        # Refresh browser every 30 requests to prevent memory buildup
        if self._request_count >= 30:
            logger.info("Refreshing browser after 30 requests...")
            self._request_count = 0
            await self._cleanup()
            await asyncio.sleep(1)
            await self._init_browser()

    async def _init_browser(self):
        """Initialize browser and context if not already done."""
        if self._browser is None or not await self._check_context_valid():
            # Clean up existing resources if any
            if self._context:
                try:
                    await self._context.close()
                except Exception:
                    pass
            if self._browser:
                try:
                    await self._browser.close()
                except Exception:
                    pass
            if self._playwright:
                try:
                    await self._playwright.stop()
                except Exception:
                    pass
            
            # Small delay to let resources free up
            await asyncio.sleep(0.5)
            
            try:
                # Start Playwright
                self._playwright = await async_playwright().start()
                
                # Verify Chromium is installed
                try:
                    chromium_path = self._playwright.chromium.executable_path
                    if not chromium_path or not os.path.exists(chromium_path):
                        raise Exception("Chromium browser not found. Run: playwright install chromium")
                except Exception as e:
                    logger.error(f"Chromium check failed: {e}")
                    raise Exception(f"Chromium browser not properly installed: {e}")
                
                # Launch browser with stealth settings and increased stability options
                logger.debug("Launching Chromium browser...")
                self._browser = await self._playwright.chromium.launch(
                    headless=self.headless,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--disable-dev-shm-usage',
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-web-security',
                        '--disable-features=IsolateOrigins,site-per-process',
                        '--disable-background-timer-throttling',
                        '--disable-backgrounding-occluded-windows',
                        '--disable-renderer-backgrounding',
                        '--disable-gpu',  # Disable GPU to reduce crashes
                    ],
                    handle_sigint=False,
                    handle_sigterm=False,
                    handle_sighup=False,
                )
                
                # Verify browser started successfully
                if not self._browser.is_connected():
                    raise Exception("Browser launched but not connected")
                
                # Small delay to let browser stabilize
                await asyncio.sleep(0.3)
                
                # Create context with realistic viewport and user agent
                # Increased timeout and better connection handling
                self._context = await self._browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    locale='en-US',
                    timezone_id='America/Toronto',
                    ignore_https_errors=True,
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
                
                # Verify context was created
                if self._context is None:
                    raise Exception("Failed to create browser context")
                
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
                
                # Test context by creating and immediately closing a test page
                test_page = None
                try:
                    test_page = await self._context.new_page()
                    await test_page.close()
                    logger.debug("Browser initialization successful")
                except Exception as e:
                    logger.warning(f"Browser initialization test failed: {e}")
                    if test_page:
                        try:
                            await test_page.close()
                        except Exception:
                            pass
                    raise Exception(f"Browser context not working: {e}")
                    
            except Exception as e:
                logger.error(f"Failed to initialize browser: {e}")
                # Clean up partial initialization
                await self._cleanup()
                raise

    async def _cleanup(self):
        """Clean up browser resources with timeouts to prevent hanging."""
        cleanup_timeout = 2.0  # 2 second timeout per cleanup operation
        
        if self._page:
            try:
                await asyncio.wait_for(self._page.close(), timeout=cleanup_timeout)
            except asyncio.TimeoutError:
                logger.warning("Page close timed out, forcing cleanup")
            except Exception as e:
                logger.debug(f"Error closing page: {e}")
            self._page = None
        
        if self._context:
            try:
                await asyncio.wait_for(self._context.close(), timeout=cleanup_timeout)
            except asyncio.TimeoutError:
                logger.warning("Context close timed out, forcing cleanup")
            except Exception as e:
                logger.warning(f"Error closing context: {e}")
            self._context = None
        
        if self._browser:
            try:
                await asyncio.wait_for(self._browser.close(), timeout=cleanup_timeout)
            except asyncio.TimeoutError:
                logger.warning("Browser close timed out, forcing cleanup")
            except Exception as e:
                logger.warning(f"Error closing browser: {e}")
            self._browser = None
        
        if self._playwright:
            try:
                await asyncio.wait_for(self._playwright.stop(), timeout=cleanup_timeout)
            except asyncio.TimeoutError:
                logger.warning("Playwright stop timed out, forcing cleanup")
            except Exception as e:
                logger.warning(f"Error stopping playwright: {e}")
            self._playwright = None

    async def _check_context_valid(self) -> bool:
        """Check if browser context is still valid."""
        try:
            if self._context is None or self._browser is None:
                return False
            # Check if browser is still connected
            if not self._browser.is_connected():
                return False
            # Try to access pages - if context is closed, this will fail
            _ = self._context.pages  # Access to check if context is alive
            return True
        except Exception:
            return False

    async def _reinit_browser_if_needed(self):
        """Reinitialize browser if context is closed."""
        if not await self._check_context_valid():
            logger.warning("Browser context closed, reinitializing...")
            await self._cleanup()
            # Longer delay before reinitializing to let resources free up
            await asyncio.sleep(2)
            try:
                await self._init_browser()
            except Exception as e:
                logger.error(f"Failed to reinitialize browser: {e}")
                raise

    def _extract_domain(self, url: str) -> str:
        """
        Safely extract domain from URL.
        
        Handles URLs with or without protocol:
        - "https://example.com/path" -> "example.com"
        - "http://example.com" -> "example.com"
        - "example.com" -> "example.com"
        - "example.com/path" -> "example.com"
        
        Args:
            url: URL string (with or without protocol)
            
        Returns:
            Domain name as string
            
        Raises:
            ValueError: If URL cannot be parsed
        """
        # Add protocol if missing to make urlparse work correctly
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        try:
            parsed = urlparse(url)
            domain = parsed.netloc or parsed.path.split('/')[0]
            if not domain:
                raise ValueError(f"Could not extract domain from URL: {url}")
            # Remove port if present (e.g., "example.com:8080" -> "example.com")
            domain = domain.split(':')[0]
            return domain
        except Exception as e:
            raise ValueError(f"Failed to parse URL '{url}': {e}")

    async def fetch(
        self,
        url: str,
        wait_selector: Optional[str] = None,
        wait_time: float = 0.8,  # Reduced from 2.0 for faster scraping
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
        await self._reinit_browser_if_needed()
        await self._maybe_refresh_browser()

        last_error = None
        page_was_reused = False

        for attempt in range(self.max_retries):
            page: Optional[Page] = None
            try:
                # Check context before creating page - reinit if needed
                if not await self._check_context_valid():
                    logger.warning(f"Context invalid before attempt {attempt + 1}, reinitializing...")
                    await self._reinit_browser_if_needed()

                # Verify context is still valid after reinit
                if not await self._check_context_valid():
                    raise Exception("Failed to initialize browser context")

                # Get or create page (reuse if enabled)
                try:
                    page = await self._get_or_create_page()
                    page_was_reused = self.reuse_page and self._page is not None
                except asyncio.TimeoutError:
                    raise Exception("Timeout creating new page - browser may be unresponsive")

                # Set cookies if provided (only on first use or new page)
                if cookies and not page_was_reused:
                    try:
                        domain = self._extract_domain(url)
                        await self._context.add_cookies([
                            {'name': k, 'value': v, 'url': url, 'domain': domain}
                            for k, v in cookies.items()
                        ])
                    except Exception as e:
                        logger.warning(f"Failed to set cookies: {e}")

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
                        await page.wait_for_selector(wait_selector, timeout=8000)
                    except Exception as e:
                        logger.debug(f"Selector {wait_selector} not found: {e}")

                # Brief wait for JavaScript to execute (reduced for speed)
                await asyncio.sleep(wait_time)

                # Light scroll to trigger lazy loading (faster than before)
                try:
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
                    await asyncio.sleep(0.2)
                except Exception:
                    pass  # Scroll is optional, don't fail on it

                # Get page content
                content = await page.content()
                return content

            except Exception as e:
                last_error = e

                # If using reusable page and it failed, clear it
                if self.reuse_page:
                    self._page = None

                # Close page if we created it and it's not reusable
                if page and not page_was_reused:
                    try:
                        await page.close()
                    except Exception:
                        pass

                # Check if error is due to closed context/browser
                error_str = str(e).lower()
                if any(keyword in error_str for keyword in ['connection closed', 'context', 'browser', 'driver', 'target closed']):
                    logger.warning(f"Browser/context issue detected on attempt {attempt + 1}, will reinitialize")
                    self._page = None
                    self._context = None
                    self._browser = None

                logger.warning(f"Attempt {attempt + 1}/{self.max_retries} failed for {url}: {e}")
                if attempt < self.max_retries - 1:
                    # Reinitialize browser if context was closed
                    await self._reinit_browser_if_needed()
                    # Shorter backoff for faster recovery
                    backoff_time = min(1.5 ** attempt, 3)  # Cap at 3 seconds
                    await asyncio.sleep(backoff_time)

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
