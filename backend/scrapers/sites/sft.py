"""
SexyFriendsToronto (SFT) scraper.

This is the first site implemented with the new Crawlee-based system.
It serves as a reference implementation for other static HTML scrapers.
"""

import re
import json
from typing import List, Dict, Any
from bs4 import BeautifulSoup

from ..base import BaseScraper, ScheduleItem, ScrapedListing
from ..config import get_site_config
from ..crawlers.static import StaticCrawler
from ..utils.normalizers import (
    normalize_name,
    normalize_tier,
    normalize_weight,
    normalize_height,
    normalize_measurements,
    normalize_bust_size,
)
from ..utils.extractors import (
    extract_tier,
    extract_time_range,
    extract_age,
    extract_nationality,
    extract_ethnicity,
    extract_height,
    extract_weight,
    extract_hair_color,
    extract_eye_color,
    extract_bust,
    extract_service_type,
    extract_images,
    extract_tags,
)


class SFTScraper(BaseScraper):
    """
    Scraper for SexyFriendsToronto.

    Site structure:
    - Schedule page: h5 headers for locations, h6 for days, <a> for listings
    - Profile pages: Standard text-based format with regex extraction
    """

    def __init__(self, db_session=None):
        config = get_site_config('sft')
        super().__init__(config, db_session)
        self.crawler = StaticCrawler(rate_limit=config.rate_limit_seconds)

    async def scrape_schedule(self) -> List[ScheduleItem]:
        """
        Scrape the schedule page.

        Returns list of ScheduleItem objects with basic info.
        """
        self.logger.info(f"Fetching schedule from {self.config.schedule_url}")
        soup = await self.crawler.fetch_soup(self.config.schedule_url)
        return self._parse_schedule(soup)

    def _parse_schedule(self, soup: BeautifulSoup) -> List[ScheduleItem]:
        """Parse the schedule page HTML."""
        items = []

        # Find content container
        content = soup.find('div', class_='content') or soup.find('body') or soup

        current_location = None
        current_day = None

        for element in content.find_all(['h5', 'h6', 'a']):
            text = element.get_text(strip=True)

            # Location headers (h5)
            if element.name == 'h5':
                current_location = text.replace('INCALL', '').strip()

            # Day headers (h6)
            elif element.name == 'h6':
                current_day = text

            # Listings (anchor tags)
            elif element.name == 'a' and current_day and current_location:
                profile_slug = element.get('href', '').strip().strip('/')

                if not profile_slug or profile_slug.startswith('http'):
                    continue

                full_text = element.get_text(strip=True)

                # Skip non-listing links
                skip_patterns = ['P100.ca', 'Design', 'Website', 'Contact', 'About']
                if any(pattern.lower() in full_text.lower() for pattern in skip_patterns):
                    continue

                # Extract tier
                tier = extract_tier(full_text)

                # Parse name and time
                name, start_time, end_time = self._parse_listing_text(full_text)

                if len(name) < 2:
                    continue

                items.append(ScheduleItem(
                    name=normalize_name(name),
                    profile_url=profile_slug,
                    day_of_week=current_day,
                    location=current_location,
                    start_time=start_time,
                    end_time=end_time,
                    tier=normalize_tier(tier) if tier else None,
                ))

        self.logger.info(f"Found {len(items)} schedule items")
        return items

    def _parse_listing_text(self, text: str) -> tuple:
        """
        Extract name and time from listing text.

        Returns:
            Tuple of (name, start_time, end_time)
        """
        # Remove tier markers
        clean_text = text
        for t in ['*PLATINUM VIP*', '*ULTRA VIP*', '*ELITE*', '*VIP*']:
            clean_text = clean_text.replace(t, '').strip()

        # Extract time
        start_time, end_time = extract_time_range(clean_text)

        # Remove time from text to get name
        if start_time or end_time:
            # Remove time patterns from text
            time_patterns = [
                r'\d{1,2}(?::\d{2})?\s*(?:AM|PM)\s*-\s*\d{1,2}(?::\d{2})?\s*(?:AM|PM)',
                r'\d{1,2}\s*P\s*-\s*\d{1,2}(?::\d{2})?\s*(?:AM|PM)',
                r'\d{1,2}(?::\d{2})?\s*(?:AM|PM)\s*-\s*LATE',
                r'\d{1,2}:\d{2}\s*(?:AM|PM)',
                r'\d{1,2}\s*(?:AM|PM)\s*$',
            ]
            for pattern in time_patterns:
                clean_text = re.sub(pattern, '', clean_text, flags=re.IGNORECASE)

        # Clean up name
        name = re.sub(r'[;,\s]+$', '', clean_text).strip()
        name = re.sub(r'[\d\-]+$', '', name).strip()

        return name, start_time, end_time

    async def scrape_profile(self, profile_url: str) -> Dict[str, Any]:
        """
        Scrape an individual profile page.

        Args:
            profile_url: Profile slug (not full URL)

        Returns:
            Dictionary of profile data
        """
        full_url = f"{self.config.base_url}{profile_url}"
        self.logger.debug(f"Fetching profile: {full_url}")

        soup = await self.crawler.fetch_soup(full_url)
        return self._parse_profile(soup)

    def _parse_profile(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Parse profile page HTML."""
        content = soup.find('div', class_='content') or soup.find('body') or soup
        text = content.get_text()

        profile = {}

        # Age
        age = extract_age(text)
        if age:
            profile['age'] = age

        # Nationality
        nationality = extract_nationality(text)
        if nationality:
            profile['nationality'] = nationality

        # Ethnicity
        ethnicity = extract_ethnicity(text)
        if ethnicity:
            profile['ethnicity'] = ethnicity

        # Height
        height = extract_height(text)
        if height:
            profile['height'] = normalize_height(height)

        # Weight
        weight = extract_weight(text)
        if weight:
            profile['weight'] = normalize_weight(weight)

        # Bust, bust_type, and measurements
        bust, bust_type, measurements = extract_bust(text)
        if bust:
            profile['bust'] = normalize_bust_size(bust)
        if bust_type:
            profile['bust_type'] = bust_type
        if measurements:
            profile['measurements'] = normalize_measurements(measurements)

        # Infer bust type from text if not explicitly stated
        if 'bust' in profile and 'bust_type' not in profile:
            if 'enhanced' in text.lower() or 'Enhanced: Yes' in text:
                profile['bust_type'] = 'Enhanced'
            elif 'natural' in text.lower() or 'Enhanced: No' in text or 'Enhancements: none' in text.lower():
                profile['bust_type'] = 'Natural'

        # Hair color
        hair = extract_hair_color(text)
        if hair:
            profile['hair_color'] = hair.title()

        # Eye color
        eyes = extract_eye_color(text)
        if eyes:
            profile['eye_color'] = eyes.title()

        # Service type
        service = extract_service_type(text)
        if service:
            profile['service_type'] = service

        # Tier from profile (fallback if not in schedule)
        tier_match = re.search(r'INCALL RATES\s+(PLATINUM VIP|ULTRA VIP|VIP|ELITE)\s+\d+mins?', text, re.IGNORECASE)
        if tier_match:
            profile['tier'] = normalize_tier(tier_match.group(1).strip())
        else:
            # Check header format
            header_match = re.search(r'\*\s*(PLATINUM VIP|ULTRA VIP|VIP|ELITE)\s*\*', text, re.IGNORECASE)
            if header_match:
                profile['tier'] = normalize_tier(header_match.group(1).strip())

        # Images
        images = extract_images(soup, class_name='p_gallery_img')
        if images:
            profile['images'] = images

        # Tags
        tags = extract_tags(text)
        if tags:
            profile['tags'] = tags

        return profile

    def normalize_listing(self, schedule_item: ScheduleItem, profile_data: Dict) -> ScrapedListing:
        """
        Create ScrapedListing from schedule item and profile data.

        Uses schedule tier if available, falls back to profile tier.
        """
        # Prefer schedule tier over profile tier
        tier = schedule_item.tier or profile_data.get('tier')

        return ScrapedListing(
            name=schedule_item.name,
            profile_url=schedule_item.profile_url,
            source=self.config.short_name,
            tier=tier,
            age=profile_data.get('age'),
            nationality=profile_data.get('nationality'),
            ethnicity=profile_data.get('ethnicity'),
            height=profile_data.get('height'),
            weight=profile_data.get('weight'),
            bust=profile_data.get('bust'),
            bust_type=profile_data.get('bust_type'),
            measurements=profile_data.get('measurements'),
            hair_color=profile_data.get('hair_color'),
            eye_color=profile_data.get('eye_color'),
            service_type=profile_data.get('service_type'),
            images=profile_data.get('images', []),
            tags=profile_data.get('tags', []),
            schedules=[{
                'day_of_week': schedule_item.day_of_week,
                'location': schedule_item.location,
                'start_time': schedule_item.start_time,
                'end_time': schedule_item.end_time,
            }],
            raw_data=profile_data,
        )
