"""
Crawlee-based stealth crawler with fingerprint rotation.

Uses Crawlee's PlaywrightCrawler with built-in:
- Browser fingerprint generation/rotation
- Anti-detection measures
- Session management
"""

import asyncio
import random
import logging
from typing import Optional, Dict, List
from bs4 import BeautifulSoup

from ..base import is_cancelled, ScrapeCancelledException

# Suppress verbose Crawlee logging
logging.getLogger('crawlee').setLevel(logging.WARNING)
logging.getLogger('crawlee.crawlers').setLevel(logging.WARNING)
logging.getLogger('crawlee._autoscaling').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


class CrawleeStealth:
    """
    Stealth crawler using Crawlee's PlaywrightCrawler.

    Features:
    - Automatic fingerprint rotation
    - Built-in anti-detection
    - Session/cookie management
    """

    def __init__(
        self,
        rate_limit: float = 2.0,
        headless: bool = True,
        max_retries: int = 3,
    ):
        self.rate_limit = rate_limit
        self.headless = headless
        self.max_retries = max_retries
        self._last_request_time = 0
        self._results: Dict[str, str] = {}
        self._crawler = None

    async def _wait_for_rate_limit(self):
        """Wait with randomization to appear human-like."""
        import time
        now = time.time()
        elapsed = now - self._last_request_time
        # Add random delay for human-like behavior
        random_delay = random.uniform(0.3, 1.0)
        wait_time = self.rate_limit - elapsed + random_delay
        if wait_time > 0:
            await asyncio.sleep(wait_time)
        self._last_request_time = time.time()

    async def fetch(self, url: str) -> str:
        """
        Fetch a single URL using Crawlee.

        Args:
            url: URL to fetch

        Returns:
            HTML content as string
        """
        from crawlee.crawlers import PlaywrightCrawler
        from crawlee.storage_clients import MemoryStorageClient

        await self._wait_for_rate_limit()

        result_html = None
        error_msg = None
        handler_called = False

        async def request_handler(context):
            nonlocal result_html, handler_called
            handler_called = True
            page = context.page
            result_html = await page.content()

        for attempt in range(self.max_retries):
            result_html = None
            handler_called = False
            try:
                # Use MemoryStorageClient to avoid file-based request deduplication
                # This prevents "Request handler was never called" on repeated scrapes
                crawler = PlaywrightCrawler(
                    headless=self.headless,
                    browser_launch_options={
                        'args': [
                            '--disable-blink-features=AutomationControlled',
                            '--disable-dev-shm-usage',
                            '--no-sandbox',
                        ]
                    },
                    max_requests_per_crawl=1,
                    storage_client=MemoryStorageClient(),
                )
                crawler.router.default_handler(request_handler)

                await crawler.run([url])

                if result_html:
                    return result_html
                elif not handler_called:
                    error_msg = "Request handler was never called - request may have been blocked"
                    logger.warning(f"Attempt {attempt + 1}/{self.max_retries}: {error_msg}")
                else:
                    error_msg = "Handler called but no HTML content retrieved"
                    logger.warning(f"Attempt {attempt + 1}/{self.max_retries}: {error_msg}")

            except Exception as e:
                error_msg = str(e)
                logger.warning(f"Attempt {attempt + 1}/{self.max_retries} failed for {url}: {e}")

            if attempt < self.max_retries - 1:
                backoff = 2 + (attempt * 2) + random.uniform(0, 1)
                await asyncio.sleep(backoff)

        raise Exception(f"Failed to fetch {url} after {self.max_retries} attempts: {error_msg}")

    async def fetch_many(self, urls: List[str]) -> Dict[str, str]:
        """
        Fetch multiple URLs efficiently using Crawlee's queue.

        Args:
            urls: List of URLs to fetch

        Returns:
            Dict mapping URL to HTML content
        """
        from crawlee.crawlers import PlaywrightCrawler
        from crawlee.storage_clients import MemoryStorageClient

        results = {}

        async def request_handler(context):
            page = context.page
            url = context.request.url
            html = await page.content()
            results[url] = html
            # Random delay between requests
            await asyncio.sleep(self.rate_limit + random.uniform(0.3, 1.0))

        try:
            crawler = PlaywrightCrawler(
                headless=self.headless,
                browser_launch_options={
                    'args': [
                        '--disable-blink-features=AutomationControlled',
                        '--disable-dev-shm-usage',
                        '--no-sandbox',
                    ]
                },
                max_requests_per_crawl=len(urls),
                max_crawl_depth=0,  # Don't follow links
                storage_client=MemoryStorageClient(),
            )
            crawler.router.default_handler(request_handler)

            await crawler.run(urls)

        except Exception as e:
            logger.error(f"Crawlee batch fetch error: {e}")

        return results

    async def fetch_soup(self, url: str) -> BeautifulSoup:
        """Fetch URL and return parsed BeautifulSoup."""
        html = await self.fetch(url)
        return BeautifulSoup(html, 'html.parser')

    async def close(self):
        """Cleanup resources."""
        pass  # Crawlee handles cleanup internally
