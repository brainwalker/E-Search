"""
Crawlee-based scraper system for E-Search.

This module provides a unified scraping framework supporting:
- Static HTML sites (BeautifulSoupCrawler)
- JavaScript-rendered sites (PlaywrightCrawler)
- Anti-bot protected sites (Camoufox - future)
"""

from .base import BaseScraper, ScraperType, SiteConfig, ScrapedListing
from .config import SITES, get_site_config, get_enabled_sites
from .manager import ScraperManager

__all__ = [
    'BaseScraper',
    'ScraperType',
    'SiteConfig',
    'ScrapedListing',
    'SITES',
    'get_site_config',
    'get_enabled_sites',
    'ScraperManager',
]
