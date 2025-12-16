"""
Static HTML crawler using Crawlee's BeautifulSoupCrawler.

This crawler is optimized for sites that don't require JavaScript rendering.
It's faster and more resource-efficient than Playwright-based crawlers.
"""

import asyncio
from typing import Optional, Dict, List, Callable, Any
from bs4 import BeautifulSoup
import httpx
import logging

logger = logging.getLogger(__name__)


class StaticCrawler:
    """
    Wrapper for fetching static HTML pages.

    Uses httpx for async HTTP requests and BeautifulSoup for parsing.
    Provides rate limiting, connection pooling, and error handling.
    """

    def __init__(
        self,
        rate_limit: float = 1.0,
        timeout: float = 30.0,
        max_retries: int = 3,
        headers: Optional[Dict[str, str]] = None
    ):
        """
        Initialize the static crawler.

        Args:
            rate_limit: Seconds to wait between requests
            timeout: Request timeout in seconds
            max_retries: Number of retries on failure
            headers: Custom HTTP headers
        """
        self.rate_limit = rate_limit
        self.timeout = timeout
        self.max_retries = max_retries
        self.headers = headers or {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate',  # Some sites have issues with brotli
        }
        self._last_request_time = 0
        # Reusable HTTP client with connection pooling
        self._client: Optional[httpx.AsyncClient] = None

    async def _wait_for_rate_limit(self):
        """Wait to respect rate limit."""
        import time
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self.rate_limit:
            await asyncio.sleep(self.rate_limit - elapsed)
        self._last_request_time = time.time()

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create reusable HTTP client with connection pooling."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                follow_redirects=True,
                timeout=self.timeout,
                headers=self.headers,
                limits=httpx.Limits(
                    max_keepalive_connections=5,
                    max_connections=10,
                    keepalive_expiry=30.0
                )
            )
        return self._client

    async def close(self):
        """Close the HTTP client and release resources."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def fetch(
        self,
        url: str,
        cookies: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Fetch a URL and return HTML content.

        Args:
            url: URL to fetch
            cookies: Optional cookies to send

        Returns:
            HTML content as string

        Raises:
            httpx.HTTPError: On request failure after retries
        """
        logger.debug(f"StaticCrawler fetching: {url}")
        await self._wait_for_rate_limit()

        last_error = None
        client = await self._get_client()

        for attempt in range(self.max_retries):
            try:
                # Set cookies for this request if provided
                response = await client.get(url, cookies=cookies)

                # Some sites return 500 but still have valid content
                # Only raise for status if response is empty or clearly an error page
                if response.status_code >= 400:
                    # Check if response has substantial content (likely valid despite status)
                    if len(response.text) > 1000 and '<html' in response.text.lower():
                        logger.warning(f"Got status {response.status_code} but response has content, proceeding")
                        return response.text
                    response.raise_for_status()

                return response.text

            except httpx.HTTPError as e:
                last_error = e
                logger.warning(f"Attempt {attempt + 1}/{self.max_retries} failed for {url}: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff

        raise last_error

    async def fetch_soup(
        self,
        url: str,
        cookies: Optional[Dict[str, str]] = None
    ) -> BeautifulSoup:
        """
        Fetch a URL and return parsed BeautifulSoup.

        Args:
            url: URL to fetch
            cookies: Optional cookies to send

        Returns:
            BeautifulSoup object
        """
        html = await self.fetch(url, cookies)
        return BeautifulSoup(html, 'html.parser')

    async def fetch_many(
        self,
        urls: List[str],
        cookies: Optional[Dict[str, str]] = None
    ) -> Dict[str, str]:
        """
        Fetch multiple URLs with rate limiting.

        Args:
            urls: List of URLs to fetch
            cookies: Optional cookies to send

        Returns:
            Dictionary mapping URL to HTML content
        """
        results = {}
        for url in urls:
            try:
                html = await self.fetch(url, cookies)
                results[url] = html
            except Exception as e:
                logger.error(f"Failed to fetch {url}: {e}")
                results[url] = None
        return results

    async def fetch_with_callback(
        self,
        url: str,
        callback: Callable[[BeautifulSoup], Any],
        cookies: Optional[Dict[str, str]] = None
    ) -> Any:
        """
        Fetch a URL and process with callback.

        Args:
            url: URL to fetch
            callback: Function to process BeautifulSoup
            cookies: Optional cookies to send

        Returns:
            Result of callback function
        """
        soup = await self.fetch_soup(url, cookies)
        return callback(soup)
