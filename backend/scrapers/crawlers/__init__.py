"""Crawler implementations for different site types."""

from .static import StaticCrawler
from .stealth import StealthCrawler

__all__ = ['StaticCrawler', 'StealthCrawler']
