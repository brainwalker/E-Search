"""
Scraper Manager - orchestrates all site scrapers.

Provides a unified interface for running scrapers, either individually
or all at once. Handles parallel execution and result aggregation.
"""

import asyncio
from typing import Dict, List, Optional, Type
from datetime import datetime, timezone
import logging

from .base import BaseScraper, ScrapeResult, ScraperType
from .config import SITES, get_site_config, get_enabled_sites

# Import all implemented scrapers
from .sites.sft import SFTScraper
from .sites.dd import DDScraper

logger = logging.getLogger(__name__)


# Registry of implemented scrapers
# Add new scrapers here as they are implemented
SCRAPER_REGISTRY: Dict[str, Type[BaseScraper]] = {
    'sft': SFTScraper,
    'discreet': DDScraper,
    # 'secret': SecretScraper,
    # 'select': SelectScraper,
    # ... add more as implemented
}


class ScraperManager:
    """
    Manages and orchestrates all site scrapers.

    Usage:
        manager = ScraperManager(db_session)

        # Run single scraper
        result = await manager.scrape_site('sft')

        # Run all enabled scrapers
        results = await manager.scrape_all()

        # Check status
        status = manager.list_scrapers()
    """

    def __init__(self, db_session=None):
        """
        Initialize the scraper manager.

        Args:
            db_session: SQLAlchemy database session
        """
        self.db = db_session
        self.results: Dict[str, ScrapeResult] = {}

    def get_scraper(self, site_key: str) -> Optional[BaseScraper]:
        """
        Get a scraper instance for a site.

        Args:
            site_key: Site identifier (e.g., 'sft')

        Returns:
            Scraper instance or None if not implemented
        """
        if site_key not in SCRAPER_REGISTRY:
            logger.warning(f"Scraper not implemented for site: {site_key}")
            return None

        scraper_class = SCRAPER_REGISTRY[site_key]
        return scraper_class(self.db)

    async def scrape_site(self, site_key: str) -> ScrapeResult:
        """
        Run scraper for a single site.

        Args:
            site_key: Site identifier

        Returns:
            ScrapeResult with statistics
        """
        config = get_site_config(site_key)
        logger.info(f"Starting scrape for {config.name} ({site_key})")

        scraper = self.get_scraper(site_key)
        if not scraper:
            return ScrapeResult(
                source=site_key,
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
                errors=1,
                error_details=[{'error': f'Scraper not implemented for {site_key}'}]
            )

        try:
            result = await scraper.run()
            self.results[site_key] = result
            return result

        except Exception as e:
            logger.error(f"Scraper failed for {site_key}: {e}")
            result = ScrapeResult(
                source=site_key,
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
                errors=1,
                error_details=[{'error': str(e)}]
            )
            self.results[site_key] = result
            return result

    async def scrape_all(
        self,
        site_keys: List[str] = None,
        parallel: bool = False
    ) -> Dict[str, ScrapeResult]:
        """
        Run scrapers for multiple sites.

        Args:
            site_keys: List of site keys to scrape (defaults to all enabled)
            parallel: Whether to run scrapers in parallel

        Returns:
            Dictionary mapping site_key to ScrapeResult
        """
        if site_keys is None:
            # Get all enabled sites that are implemented
            enabled = get_enabled_sites()
            site_keys = [k for k in enabled.keys() if k in SCRAPER_REGISTRY]

        logger.info(f"Starting scrape for {len(site_keys)} sites: {site_keys}")

        if parallel:
            # Run all scrapers concurrently
            tasks = [self.scrape_site(key) for key in site_keys]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for key, result in zip(site_keys, results):
                if isinstance(result, Exception):
                    self.results[key] = ScrapeResult(
                        source=key,
                        started_at=datetime.now(timezone.utc),
                        completed_at=datetime.now(timezone.utc),
                        errors=1,
                        error_details=[{'error': str(result)}]
                    )
                else:
                    self.results[key] = result
        else:
            # Run scrapers sequentially
            for key in site_keys:
                await self.scrape_site(key)

        return self.results

    def list_scrapers(self) -> List[Dict]:
        """
        List all configured sites and their implementation status.

        Returns:
            List of site info dictionaries
        """
        scrapers = []
        for key, config in SITES.items():
            scrapers.append({
                'key': key,
                'name': config.name,
                'short_name': config.short_name,
                'type': config.scraper_type.value,
                'enabled': config.enabled,
                'implemented': key in SCRAPER_REGISTRY,
                'url': config.schedule_url,
            })
        return scrapers

    def get_implemented_scrapers(self) -> List[str]:
        """Get list of implemented scraper keys."""
        return list(SCRAPER_REGISTRY.keys())

    def get_results_summary(self) -> Dict:
        """
        Get summary of all scrape results.

        Returns:
            Summary dictionary with totals
        """
        if not self.results:
            return {
                'total_sites': 0,
                'successful': 0,
                'failed': 0,
                'total_listings': 0,
                'new_listings': 0,
                'updated_listings': 0,
            }

        successful = sum(1 for r in self.results.values() if r.success)
        failed = len(self.results) - successful

        return {
            'total_sites': len(self.results),
            'successful': successful,
            'failed': failed,
            'total_listings': sum(r.total for r in self.results.values()),
            'new_listings': sum(r.new for r in self.results.values()),
            'updated_listings': sum(r.updated for r in self.results.values()),
            'sites': {k: v.to_dict() for k, v in self.results.items()},
        }


# Convenience functions for standalone usage

async def scrape_site(site_key: str, db_session=None) -> ScrapeResult:
    """
    Scrape a single site.

    Args:
        site_key: Site identifier
        db_session: Optional database session

    Returns:
        ScrapeResult
    """
    manager = ScraperManager(db_session)
    return await manager.scrape_site(site_key)


async def scrape_all(db_session=None) -> Dict[str, ScrapeResult]:
    """
    Scrape all enabled sites.

    Args:
        db_session: Optional database session

    Returns:
        Dictionary of results
    """
    manager = ScraperManager(db_session)
    return await manager.scrape_all()
