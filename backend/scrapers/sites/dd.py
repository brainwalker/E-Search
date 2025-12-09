"""
DiscreetDolls (DD) scraper.

This site uses a unique data structure where escort data is embedded in
the schedule page via `data-doll-info` JSON attributes.

Site structure:
- Schedule page: `a.card` elements with `data-doll-info` JSON attribute
- Profile pages: `.doll-table-info` for stats, `.rightside` for images
"""

import re
import json
import html
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from bs4 import BeautifulSoup

from ..base import BaseScraper, ScheduleItem, ScrapedListing
from ..config import get_site_config
from ..crawlers.static import StaticCrawler
from ..utils.normalizers import (
    normalize_name,
    normalize_weight,
    normalize_height,
    normalize_measurements,
    normalize_bust_size,
)


# DD location mapping: known location suffixes and their town prefixes
DD_LOCATION_PATTERNS = {
    'Richmond-Peter': 'Downtown',
    'Front-Spadina': 'Downtown',
    'Bay-College': 'Downtown',
    'HWY427-Bloor': 'Etobicoke',
    'HWY10-Eglinton': 'Mississauga',
    'Square One': 'Mississauga',
}

# DD tier normalization map
DD_TIER_MAP = {
    'doll': 'Doll',
    'diamond doll': 'Diamond Doll',
    'platinum dolls': 'Platinum Dolls',
    'platinum doll': 'Platinum Dolls',
    'sapphire dolls': 'Sapphire Dolls',
    'sapphire doll': 'Sapphire Dolls',
}


def normalize_dd_tier(tier: str) -> Optional[str]:
    """Normalize DD tier names to consistent format."""
    if not tier:
        return None
    tier_lower = tier.strip().lower()
    return DD_TIER_MAP.get(tier_lower, tier.strip().title())


def parse_dd_location(location_str: str) -> Tuple[str, str]:
    """
    Parse DD location string into town and location.

    Examples:
        "Downtown Richmond-Peter" -> ("Downtown", "Richmond-Peter")
        "Etobicoke HWY427-Bloor" -> ("Etobicoke", "HWY427-Bloor")
        "North York" -> ("North York", "unknown")

    Returns:
        Tuple of (town, location)
    """
    if not location_str:
        return ("unknown", "unknown")

    location_str = location_str.strip()

    # Check for known location patterns
    for loc_suffix, expected_town in DD_LOCATION_PATTERNS.items():
        if loc_suffix in location_str:
            # Extract town from the string (everything before the suffix)
            parts = location_str.split(loc_suffix)
            town = parts[0].strip() if parts[0].strip() else expected_town
            return (town, loc_suffix)

    # Try splitting on common delimiters
    if ' ' in location_str:
        parts = location_str.rsplit(' ', 1)
        # Check if second part looks like a location code
        if '-' in parts[1] or parts[1].upper() == parts[1]:
            return (parts[0].strip(), parts[1].strip())
        # Otherwise treat whole string as town
        return (location_str, "unknown")

    return (location_str, "unknown")


def parse_dd_date(date_str: str) -> Optional[str]:
    """
    Parse DD date string to get day of week.

    Examples:
        "Mon, Dec 08" -> "Monday"
        "Fri, Dec 12" -> "Friday"

    Returns:
        Full day name or None
    """
    if not date_str:
        return None

    day_map = {
        'mon': 'Monday',
        'tue': 'Tuesday',
        'wed': 'Wednesday',
        'thu': 'Thursday',
        'fri': 'Friday',
        'sat': 'Saturday',
        'sun': 'Sunday',
    }

    date_str = date_str.strip().lower()
    for abbrev, full in day_map.items():
        if date_str.startswith(abbrev):
            return full

    return None


def parse_dd_time(time_str: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Parse DD time string into start and end times.

    Examples:
        "5:30 pm - 12 am" -> ("5:30 PM", "12 AM")
        "4:30 pm - 11 pm" -> ("4:30 PM", "11 PM")

    Returns:
        Tuple of (start_time, end_time)
    """
    if not time_str:
        return (None, None)

    # Match time range pattern
    match = re.search(
        r'(\d{1,2}(?::\d{2})?\s*(?:am|pm))\s*-\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm))',
        time_str,
        re.IGNORECASE
    )
    if match:
        start = match.group(1).strip().upper()
        end = match.group(2).strip().upper()
        return (start, end)

    return (None, None)


class DDScraper(BaseScraper):
    """
    Scraper for DiscreetDolls.

    Site structure:
    - Schedule page: `a.card` elements with `data-doll-info` JSON attribute
    - data-doll-info contains: age, breast, figure, tier, ethnicity, date_location
    - date_location is an array of [location_string, date_string] pairs
    - Profile pages: `.doll-table-info` for stats, `.rightside` for images
    """

    def __init__(self, db_session=None):
        config = get_site_config('discreet')
        super().__init__(config, db_session)
        self.crawler = StaticCrawler(rate_limit=config.rate_limit_seconds)

    async def scrape_schedule(self) -> List[ScheduleItem]:
        """
        Scrape the schedule page.

        Returns list of ScheduleItem objects with basic info from data-doll-info.
        """
        self.logger.info(f"Fetching schedule from {self.config.schedule_url}")
        soup = await self.crawler.fetch_soup(self.config.schedule_url)
        return self._parse_schedule(soup)

    def _parse_schedule(self, soup: BeautifulSoup) -> List[ScheduleItem]:
        """Parse the schedule page HTML with data-doll-info JSON."""
        items = []

        # Find all card elements with data-doll-info
        cards = soup.find_all('a', class_='card', attrs={'data-doll-info': True})

        self.logger.info(f"Found {len(cards)} escort cards")

        for card in cards:
            try:
                # Get profile URL from href
                href = card.get('href', '')
                if not href:
                    continue

                # Extract profile slug from URL
                profile_slug = href.rstrip('/').split('/')[-1]
                if not profile_slug or profile_slug == 'daily-schedule':
                    continue

                # Parse data-doll-info JSON
                doll_info_str = card.get('data-doll-info', '{}')
                # Decode HTML entities
                doll_info_str = html.unescape(doll_info_str)

                try:
                    doll_info = json.loads(doll_info_str)
                except json.JSONDecodeError as e:
                    self.logger.warning(f"Failed to parse doll_info for {profile_slug}: {e}")
                    continue

                # Extract name from card
                name_elem = card.find('div', class_='title')
                name = name_elem.get_text(strip=True) if name_elem else profile_slug.title()

                # Extract tier from data-doll-info
                tier_list = doll_info.get('tier', [])
                tier = normalize_dd_tier(tier_list[0]) if tier_list else None

                # Extract date_location pairs
                date_locations = doll_info.get('date_location', [])

                if not date_locations:
                    # Fallback: try to parse from bline elements
                    bline = card.find('div', class_='bline')
                    if bline:
                        schedules = bline.find_all('p', attrs={'data-date': True})
                        for sched in schedules:
                            date_str = sched.get('data-date', '')
                            loc_str = sched.get('data-location', '[]')

                            # Parse location from data-location attribute
                            try:
                                loc_list = eval(loc_str) if loc_str else []
                                location_str = loc_list[0] if loc_list else ''
                            except:
                                location_str = ''

                            # Parse time from span.hours
                            hours_elem = sched.find('span', class_='hours')
                            hours_str = hours_elem.get_text(strip=True) if hours_elem else ''
                            start_time, end_time = parse_dd_time(hours_str)

                            day_of_week = parse_dd_date(date_str)
                            town, location = parse_dd_location(location_str)

                            if day_of_week:
                                items.append(ScheduleItem(
                                    name=normalize_name(name),
                                    profile_url=profile_slug,
                                    day_of_week=day_of_week,
                                    location=f"{town}, {location}",
                                    start_time=start_time,
                                    end_time=end_time,
                                    tier=tier,
                                ))
                else:
                    # Use date_location from JSON
                    for date_loc in date_locations:
                        if len(date_loc) >= 2:
                            location_str = date_loc[0]
                            date_str = date_loc[1]

                            day_of_week = parse_dd_date(date_str)
                            town, location = parse_dd_location(location_str)

                            # Try to get time from bline
                            start_time, end_time = None, None
                            bline = card.find('div', class_='bline')
                            if bline:
                                # Find matching schedule entry
                                for sched in bline.find_all('p', attrs={'data-date': True}):
                                    sched_date = sched.get('data-date', '')
                                    if date_str in sched_date or sched_date in date_str:
                                        hours_elem = sched.find('span', class_='hours')
                                        if hours_elem:
                                            hours_str = hours_elem.get_text(strip=True)
                                            start_time, end_time = parse_dd_time(hours_str)
                                        break

                            if day_of_week:
                                items.append(ScheduleItem(
                                    name=normalize_name(name),
                                    profile_url=profile_slug,
                                    day_of_week=day_of_week,
                                    location=f"{town}, {location}",
                                    start_time=start_time,
                                    end_time=end_time,
                                    tier=tier,
                                ))

                # Store additional data from doll_info for profile scraping
                # This will be used in scrape_profile to avoid redundant extraction

            except Exception as e:
                self.logger.error(f"Error parsing card: {e}")
                continue

        self.logger.info(f"Parsed {len(items)} schedule items")
        return items

    async def scrape_profile(self, profile_url: str) -> Dict[str, Any]:
        """
        Scrape an individual profile page.

        Args:
            profile_url: Profile slug (not full URL)

        Returns:
            Dictionary of profile data
        """
        full_url = f"{self.config.base_url}{profile_url}/"
        self.logger.debug(f"Fetching profile: {full_url}")

        soup = await self.crawler.fetch_soup(full_url)
        return self._parse_profile(soup)

    def _parse_profile(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Parse profile page HTML."""
        profile = {}

        # Find stats table
        stats_table = soup.find('div', class_='doll-table-info')

        if stats_table:
            # Extract stats from table rows
            text = stats_table.get_text()

            # Age
            age_match = re.search(r'Age[:\s]+(\d+)', text, re.IGNORECASE)
            if age_match:
                profile['age'] = int(age_match.group(1))

            # Height - handle various formats
            height_match = re.search(
                r'Height[:\s]+(\d+[\'\u2019\u2032]?\s*\d+[\"\u2033]?|\d+\s*cm)',
                text, re.IGNORECASE
            )
            if height_match:
                profile['height'] = normalize_height(height_match.group(1))

            # Weight
            weight_match = re.search(r'Weight[:\s]+(\d+\s*(?:lbs?|kg)?)', text, re.IGNORECASE)
            if weight_match:
                profile['weight'] = normalize_weight(weight_match.group(1))

            # Bust
            bust_match = re.search(r'Bust[:\s]+(\d+\s*[A-Z]+)', text, re.IGNORECASE)
            if bust_match:
                profile['bust'] = normalize_bust_size(bust_match.group(1))

            # Measurements
            meas_match = re.search(
                r'Measurements?[:\s]+(\d+[A-Z]*\s*[-/]\s*\d+\s*[-/]\s*\d+)',
                text, re.IGNORECASE
            )
            if meas_match:
                profile['measurements'] = normalize_measurements(meas_match.group(1))

            # Ethnicity
            eth_match = re.search(r'Ethnicity[:\s]+([A-Za-z\s/]+?)(?:\n|$|[A-Z][a-z]+:)', text)
            if eth_match:
                profile['ethnicity'] = eth_match.group(1).strip()

            # Hair color
            hair_match = re.search(r'Hair[:\s]+([A-Za-z\s/]+?)(?:\n|$|[A-Z][a-z]+:)', text)
            if hair_match:
                profile['hair_color'] = hair_match.group(1).strip().title()

            # Eye color
            eye_match = re.search(r'Eyes?[:\s]+([A-Za-z\s/]+?)(?:\n|$|[A-Z][a-z]+:)', text)
            if eye_match:
                profile['eye_color'] = eye_match.group(1).strip().title()

            # Breast type (Natural/Enhanced)
            if 'natural' in text.lower():
                profile['bust_type'] = 'Natural'
            elif 'enhanced' in text.lower():
                profile['bust_type'] = 'Enhanced'

        # Extract images from rightside
        images = []
        rightside = soup.find('div', class_='rightside')
        if rightside:
            for img in rightside.find_all('img'):
                src = img.get('src', '')
                if src and 'wp-content/uploads' in src:
                    # Extract filename from URL
                    filename = src.split('/')[-1]
                    images.append(filename)

        # Also check for gallery images
        gallery = soup.find_all('img', class_='skip-lazy')
        for img in gallery:
            src = img.get('src', '')
            if src and 'wp-content/uploads' in src:
                filename = src.split('/')[-1]
                if filename not in images:
                    images.append(filename)

        if images:
            profile['images'] = images

        # Extract tags from page content
        tags = []
        full_text = soup.get_text().lower()
        tag_keywords = ['NEW', 'BLONDE', 'BRUNETTE', 'BUSTY', 'PETITE', 'ASIAN', 'EUROPEAN', 'LATINA', 'GFE', 'PSE']
        for keyword in tag_keywords:
            if keyword.lower() in full_text:
                tags.append(keyword)

        if tags:
            profile['tags'] = tags

        return profile

    def normalize_listing(self, schedule_item: ScheduleItem, profile_data: Dict) -> ScrapedListing:
        """
        Create ScrapedListing from schedule item and profile data.

        Uses schedule tier if available, falls back to profile tier.
        """
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
