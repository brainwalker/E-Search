#!/usr/bin/env python3
"""
Test script for the new Crawlee-based scraper system.

Usage:
    cd backend
    python -m scrapers.test_scraper [site_key]

Examples:
    python -m scrapers.test_scraper sft      # Test SFT scraper
    python -m scrapers.test_scraper --list   # List all scrapers
    python -m scrapers.test_scraper --schedule sft  # Test schedule only
"""

import asyncio
import argparse
import logging
import json
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from scrapers.manager import ScraperManager
from scrapers.config import get_site_config, list_sites, get_site_summary
from scrapers.sites.sft import SFTScraper


async def test_schedule_only(site_key: str):
    """Test just the schedule scraping (no profiles)."""
    print(f"\n{'='*60}")
    print(f"Testing SCHEDULE ONLY for: {site_key}")
    print(f"{'='*60}\n")

    config = get_site_config(site_key)
    print(f"Site: {config.name}")
    print(f"URL: {config.schedule_url}")
    print(f"Type: {config.scraper_type.value}")
    print()

    if site_key == 'sft':
        scraper = SFTScraper()
        items = await scraper.scrape_schedule()

        print(f"Found {len(items)} schedule items\n")

        # Show first 10 items
        for i, item in enumerate(items[:10]):
            print(f"{i+1}. {item.name}")
            print(f"   Day: {item.day_of_week}")
            print(f"   Location: {item.location}")
            print(f"   Time: {item.start_time} - {item.end_time}")
            print(f"   Tier: {item.tier}")
            print(f"   URL: {item.profile_url}")
            print()

        if len(items) > 10:
            print(f"... and {len(items) - 10} more items")
    else:
        print(f"Schedule test not implemented for {site_key}")


async def test_profile(site_key: str, profile_url: str):
    """Test profile scraping for a specific URL."""
    print(f"\n{'='*60}")
    print(f"Testing PROFILE scraping for: {site_key}")
    print(f"Profile: {profile_url}")
    print(f"{'='*60}\n")

    if site_key == 'sft':
        scraper = SFTScraper()
        profile = await scraper.scrape_profile(profile_url)

        print("Extracted data:")
        print(json.dumps(profile, indent=2, default=str))
    else:
        print(f"Profile test not implemented for {site_key}")


async def test_full_scrape(site_key: str, limit: int = 3):
    """Test full scrape (schedule + profiles) with limit."""
    print(f"\n{'='*60}")
    print(f"Testing FULL SCRAPE for: {site_key} (limit: {limit} profiles)")
    print(f"{'='*60}\n")

    config = get_site_config(site_key)
    print(f"Site: {config.name}")
    print(f"URL: {config.schedule_url}")
    print()

    if site_key == 'sft':
        scraper = SFTScraper()

        # Get schedule
        items = await scraper.scrape_schedule()
        print(f"Found {len(items)} schedule items")

        # Scrape first N profiles
        for i, item in enumerate(items[:limit]):
            print(f"\n--- Profile {i+1}/{limit}: {item.name} ---")

            try:
                profile = await scraper.scrape_profile(item.profile_url)
                listing = scraper.normalize_listing(item, profile)

                print(f"  Age: {listing.age}")
                print(f"  Height: {listing.height}")
                print(f"  Weight: {listing.weight}")
                print(f"  Bust: {listing.bust} ({listing.bust_type})")
                print(f"  Hair: {listing.hair_color}")
                print(f"  Eyes: {listing.eye_color}")
                print(f"  Tier: {listing.tier}")
                print(f"  Service: {listing.service_type}")
                print(f"  Images: {len(listing.images)} found")
                print(f"  Tags: {listing.tags}")

            except Exception as e:
                print(f"  ERROR: {e}")

        print(f"\n✓ Tested {min(limit, len(items))} profiles successfully")
    else:
        print(f"Full scrape test not implemented for {site_key}")


def list_scrapers():
    """List all configured scrapers."""
    print(f"\n{'='*60}")
    print("Available Scrapers")
    print(f"{'='*60}\n")

    summary = get_site_summary()

    for site in summary:
        status = "✅" if site['enabled'] else "⏳"
        impl = "IMPL" if site['key'] in ['sft'] else "TODO"
        print(f"{status} [{impl}] {site['key']:12} - {site['name']}")
        print(f"              Type: {site['type']}")
        print()


async def main():
    parser = argparse.ArgumentParser(description='Test the scraper system')
    parser.add_argument('site_key', nargs='?', help='Site key to test (e.g., sft)')
    parser.add_argument('--list', action='store_true', help='List all scrapers')
    parser.add_argument('--schedule', action='store_true', help='Test schedule only')
    parser.add_argument('--profile', type=str, help='Test specific profile URL')
    parser.add_argument('--limit', type=int, default=3, help='Limit profiles to test')

    args = parser.parse_args()

    if args.list:
        list_scrapers()
        return

    if not args.site_key:
        parser.print_help()
        print("\nExample: python -m scrapers.test_scraper sft")
        return

    site_key = args.site_key.lower()

    if args.schedule:
        await test_schedule_only(site_key)
    elif args.profile:
        await test_profile(site_key, args.profile)
    else:
        await test_full_scrape(site_key, args.limit)


if __name__ == '__main__':
    asyncio.run(main())
