"""
Playwright-based crawler for sites with anti-bot protection.

Uses Playwright with stealth settings to bypass Cloudflare and similar protections.
"""

import asyncio
from typing import Optional, Dict
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)


class PlaywrightCrawler:
    """
    Crawler using Playwright for JavaScript-rendered and anti-bot protected sites.
    """

    def __init__(
        self,
        rate_limit: float = 2.0,
        timeout: float = 30000,
        headless: bool = True
    ):
        """
        Initialize the Playwright crawler.

        Args:
            rate_limit: Seconds to wait between requests
            timeout: Page load timeout in milliseconds
            headless: Run browser in headless mode
        """
        self.rate_limit = rate_limit
        self.timeout = timeout
        self.headless = headless
        self._browser = None
        self._context = None
        self._last_request_time = 0

    async def _ensure_browser(self):
        """Ensure browser is initialized."""
        if self._browser is None:
            from playwright.async_api import async_playwright

            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=self.headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                ]
            )
            self._context = await self._browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                locale='en-US',
            )
            # Add stealth scripts
            await self._context.add_init_script("""
                // Override webdriver property
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
            """)

    async def _wait_for_rate_limit(self):
        """Wait to respect rate limit."""
        import time
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self.rate_limit:
            await asyncio.sleep(self.rate_limit - elapsed)
        self._last_request_time = time.time()

    async def fetch(self, url: str) -> str:
        """
        Fetch a URL and return HTML content.

        Args:
            url: URL to fetch

        Returns:
            HTML content as string
        """
        await self._ensure_browser()
        await self._wait_for_rate_limit()

        page = await self._context.new_page()
        try:
            logger.info(f"Fetching with Playwright: {url}")
            await page.goto(url, timeout=self.timeout, wait_until='networkidle')

            # Wait a bit for any dynamic content
            await asyncio.sleep(2)

            html = await page.content()
            return html

        except Exception as e:
            logger.error(f"Playwright fetch failed for {url}: {e}")
            raise
        finally:
            await page.close()

    async def fetch_soup(self, url: str) -> BeautifulSoup:
        """
        Fetch a URL and return parsed BeautifulSoup.

        Args:
            url: URL to fetch

        Returns:
            BeautifulSoup object
        """
        html = await self.fetch(url)
        return BeautifulSoup(html, 'html.parser')

    async def close(self):
        """Close browser and clean up resources."""
        if self._context:
            await self._context.close()
            self._context = None
        if self._browser:
            await self._browser.close()
            self._browser = None
        if hasattr(self, '_playwright') and self._playwright:
            await self._playwright.stop()
            self._playwright = None

    async def __aenter__(self):
        await self._ensure_browser()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
