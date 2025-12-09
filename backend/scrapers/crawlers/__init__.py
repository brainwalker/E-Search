"""Crawler implementations for different site types."""

from .static import StaticCrawler
from .playwright_crawler import PlaywrightCrawler

__all__ = ['StaticCrawler', 'PlaywrightCrawler']
