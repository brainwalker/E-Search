"""
TopDrawerLadies (TDL) scraper.

Site structure:
- Schedule page: li.items elements with CSS classes encoding day/time/location/body type
- Profile pages: Stats in <p> tags, images from CDN

CSS class encoding on schedule page:
- Days: monday, tuesday, wednesday, thursday, friday, saturday, sunday
- Times: mon-morning, mon-afternoon, mon-evening (pattern for each day)
- Locations: dixie, leslie, north-york, yonge-sheppard, dixon
- Body types: athletic, slim, curvy, busty

Time periods:
- morning: 10am-12pm
- afternoon: 12pm-8pm
- evening: 8pm-midnight
"""

import re
from typing import List, Dict, Any, Optional
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


# Map day abbreviations in CSS classes to full names
DAY_MAP = {
    'monday': 'Monday',
    'tuesday': 'Tuesday',
    'wednesday': 'Wednesday',
    'thursday': 'Thursday',
    'friday': 'Friday',
    'saturday': 'Saturday',
    'sunday': 'Sunday',
}

# Day abbreviations used in time classes
DAY_ABBREVS = {
    'mon': 'Monday',
    'tue': 'Tuesday',
    'wed': 'Wednesday',
    'thu': 'Thursday',
    'fri': 'Friday',
    'sat': 'Saturday',
    'sun': 'Sunday',
}

# Map CSS location classes to our location format (town, location)
LOCATION_MAP = {
    'dixie': ('Mississauga', 'Dixie & Hwy 401'),
    'leslie': ('Richmond Hill', 'Leslie & Hwy 7'),
    'north-york': ('North York', 'North York'),
    'yonge-sheppard': ('North York', 'Yonge & Sheppard'),
    'dixon': ('Etobicoke', 'Dixon & Hwy 27'),
}

# Map time periods to actual times
TIME_PERIODS = {
    'morning': ('10:00 AM', '12:00 PM'),
    'afternoon': ('12:00 PM', '8:00 PM'),
    'evening': ('8:00 PM', '12:00 AM'),
}


def parse_tdl_classes(class_list: List[str]) -> Dict[str, Any]:
    """
    Parse CSS classes from a schedule item to extract schedule data.

    Args:
        class_list: List of CSS classes on the li.items element

    Returns:
        Dictionary with days, times, locations, and body_types
    """
    result = {
        'days': set(),
        'time_slots': [],  # List of (day, period) tuples
        'locations': set(),
        'body_types': set(),
    }

    for cls in class_list:
        cls_lower = cls.lower()

        # Check for day classes
        if cls_lower in DAY_MAP:
            result['days'].add(DAY_MAP[cls_lower])

        # Check for time slot classes (e.g., mon-morning, tue-afternoon)
        for abbrev, day_name in DAY_ABBREVS.items():
            for period in TIME_PERIODS.keys():
                if cls_lower == f'{abbrev}-{period}':
                    result['time_slots'].append((day_name, period))

        # Check for location classes
        if cls_lower in LOCATION_MAP:
            result['locations'].add(cls_lower)

        # Check for body type classes
        if cls_lower in ('athletic', 'slim', 'curvy', 'busty'):
            result['body_types'].add(cls_lower.title())

    return result


class TDLScraper(BaseScraper):
    """
    Scraper for TopDrawerLadies.

    Site structure:
    - Schedule page: CSS classes encode day/time/location availability
    - Profile pages: Stats like Age, Height, Weight, Measurements in <p> tags
    """

    # Fields available on TDL profiles
    expected_fields = [
        'age', 'height', 'weight', 'measurements', 'bust',
        'hair_color', 'eye_color', 'tier', 'images', 'schedules'
    ]

    def __init__(self, db_session=None):
        config = get_site_config('topdrawer')
        super().__init__(config, db_session)
        self.crawler = StaticCrawler(rate_limit=config.rate_limit_seconds)

    async def scrape_schedule(self) -> List[ScheduleItem]:
        """
        Scrape the schedule page to get list of escorts with their schedules.

        Each li.items element has CSS classes indicating:
        - Which days they work (monday, tuesday, etc.)
        - Which time slots (mon-morning, tue-afternoon, etc.)
        - Which locations (dixie, leslie, etc.)

        Returns list of ScheduleItem with schedule info.
        """
        self.logger.info(f"Fetching schedule from {self.config.schedule_url}")
        soup = await self.crawler.fetch_soup(self.config.schedule_url)
        return self._parse_schedule(soup)

    def _parse_schedule(self, soup: BeautifulSoup) -> List[ScheduleItem]:
        """Parse the schedule page HTML to extract escorts and their schedules."""
        items = []

        # Find all li.items elements
        for li in soup.find_all('li', class_='items'):
            # Get profile link
            link = li.find('a', href=True)
            if not link:
                continue

            href = link.get('href', '')
            # Extract profile slug from URL like /collections/all/products/alexis
            match = re.search(r'/products/([^/]+)/?$', href)
            if not match:
                continue

            profile_slug = match.group(1)

            # Get name from image alt attribute (most reliable) or link text
            img = link.find('img')
            if img:
                name = img.get('alt', '')
                # Clean up name - remove site suffixes
                if name:
                    name = re.sub(r'\s*[-,]\s*Top Drawer.*$', '', name, flags=re.IGNORECASE)
                    name = re.sub(r'\s*[-,]\s*Escort.*$', '', name, flags=re.IGNORECASE)
                    name = re.sub(r'^Elite Companion\s*', '', name, flags=re.IGNORECASE)

            if not name:
                name = link.get_text(strip=True)
                # Clean up name from text too
                name = re.sub(r'\s*[-,]\s*Top Drawer.*$', '', name, flags=re.IGNORECASE)

            if not name or len(name) < 2:
                name = profile_slug.replace('-', ' ').title()

            # Parse CSS classes for schedule data
            classes = li.get('class', [])
            parsed = parse_tdl_classes(classes)

            # Create schedule items from time slots
            if parsed['time_slots']:
                for day_name, period in parsed['time_slots']:
                    start_time, end_time = TIME_PERIODS.get(period, (None, None))

                    # If we have specific locations, create entry for each
                    if parsed['locations']:
                        for loc_key in parsed['locations']:
                            town, location = LOCATION_MAP.get(loc_key, ('Unknown', loc_key))
                            items.append(ScheduleItem(
                                name=normalize_name(name),
                                profile_url=profile_slug,
                                day_of_week=day_name,
                                location=f"{town}, {location}",
                                start_time=start_time,
                                end_time=end_time,
                                tier=None,  # TDL doesn't show tiers on schedule
                            ))
                    else:
                        # No specific location, create entry with unknown location
                        items.append(ScheduleItem(
                            name=normalize_name(name),
                            profile_url=profile_slug,
                            day_of_week=day_name,
                            location='Unknown, Unknown',
                            start_time=start_time,
                            end_time=end_time,
                            tier=None,
                        ))
            elif parsed['days']:
                # Have days but no specific time slots
                for day_name in parsed['days']:
                    if parsed['locations']:
                        for loc_key in parsed['locations']:
                            town, location = LOCATION_MAP.get(loc_key, ('Unknown', loc_key))
                            items.append(ScheduleItem(
                                name=normalize_name(name),
                                profile_url=profile_slug,
                                day_of_week=day_name,
                                location=f"{town}, {location}",
                                start_time=None,
                                end_time=None,
                                tier=None,
                            ))
                    else:
                        items.append(ScheduleItem(
                            name=normalize_name(name),
                            profile_url=profile_slug,
                            day_of_week=day_name,
                            location='Unknown, Unknown',
                            start_time=None,
                            end_time=None,
                            tier=None,
                        ))

        self.logger.info(f"Found {len(items)} schedule entries from schedule page")
        return items

    async def scrape_profile(self, profile_url: str) -> Dict[str, Any]:
        """
        Scrape an individual profile page.

        Args:
            profile_url: Profile slug (e.g., "alexis")

        Returns:
            Dictionary of profile data including stats and images
        """
        # base_url already includes /collections/all/products/
        full_url = f"{self.config.base_url}{profile_url}"
        self.logger.debug(f"Fetching profile: {full_url}")

        soup = await self.crawler.fetch_soup(full_url)
        return self._parse_profile(soup, profile_url)

    def _parse_profile(self, soup: BeautifulSoup, profile_slug: str = "") -> Dict[str, Any]:
        """Parse profile page HTML."""
        profile = {}

        # Check profile slug for tier (e.g., "disha-vip", "eliza-ultra-vip")
        slug_lower = profile_slug.lower()
        if 'ultra-vip' in slug_lower or 'ultravip' in slug_lower:
            profile['tier'] = 'Ultra VIP'
        elif 'platinum' in slug_lower:
            profile['tier'] = 'Platinum'
        elif '-vip' in slug_lower or slug_lower.endswith('vip'):
            profile['tier'] = 'VIP'

        # Extract name from title or h1
        title_tag = soup.find('title')
        if title_tag:
            title = title_tag.get_text(strip=True)
            # Remove site name suffix
            if ' - ' in title:
                name = title.split(' - ')[0].strip()
            elif ' | ' in title:
                name = title.split(' | ')[0].strip()
            else:
                name = title

            # Extract tier from name BEFORE cleaning (only if not already set from slug)
            # Patterns: "DISHA (VIP)", "NAME (Ultra VIP)", "NAME (Platinum)"
            if 'tier' not in profile:
                tier_match = re.search(
                    r'\(?(Platinum|Ultra\s*VIP|VIP)\)?',
                    name, re.IGNORECASE
                )
                if tier_match:
                    tier_text = tier_match.group(1).strip()
                    # Normalize tier name
                    if 'platinum' in tier_text.lower():
                        profile['tier'] = 'Platinum'
                    elif 'ultra' in tier_text.lower():
                        profile['tier'] = 'Ultra VIP'
                    elif 'vip' in tier_text.lower():
                        profile['tier'] = 'VIP'
                else:
                    # No tier marker means Normal tier
                    profile['tier'] = 'Normal'

            # Clean up common suffixes/prefixes (including tier markers)
            name = re.sub(r'\s*\(?\s*(?:Platinum|Ultra\s*VIP|VIP)\s*\)?', '', name, flags=re.IGNORECASE)
            name = re.sub(r'\s*,?\s*(?:Female\s+)?Companion.*$', '', name, flags=re.IGNORECASE)
            name = re.sub(r'\s*At\s+Top\s+Drawer.*$', '', name, flags=re.IGNORECASE)
            name = re.sub(r'\s*In\s+Toronto.*$', '', name, flags=re.IGNORECASE)
            name = re.sub(r'^Elite\s+(?:Escort\s+)?Companion\s*', '', name, flags=re.IGNORECASE)
            name = re.sub(r'^Elite\s+Escort\s*', '', name, flags=re.IGNORECASE)
            profile['name'] = name.strip()

        if not profile.get('name'):
            h1 = soup.find('h1')
            if h1:
                name = h1.get_text(strip=True)
                # Extract tier if not already found
                if 'tier' not in profile:
                    tier_match = re.search(
                        r'\(?(Platinum|Ultra\s*VIP|VIP)\)?',
                        name, re.IGNORECASE
                    )
                    if tier_match:
                        tier_text = tier_match.group(1).strip()
                        if 'platinum' in tier_text.lower():
                            profile['tier'] = 'Platinum'
                        elif 'ultra' in tier_text.lower():
                            profile['tier'] = 'Ultra VIP'
                        elif 'vip' in tier_text.lower():
                            profile['tier'] = 'VIP'
                    else:
                        profile['tier'] = 'Normal'
                # Same cleanup
                name = re.sub(r'\s*\(?\s*(?:Platinum|Ultra\s*VIP|VIP)\s*\)?', '', name, flags=re.IGNORECASE)
                name = re.sub(r'\s*,?\s*(?:Female\s+)?Companion.*$', '', name, flags=re.IGNORECASE)
                name = re.sub(r'\s*At\s+Top\s+Drawer.*$', '', name, flags=re.IGNORECASE)
                profile['name'] = name.strip()

        # Find all text content and parse stats
        # TDL uses patterns like "Age: 29", "Hair Color: Brunette", "Body Size: 34C-24-34"
        page_text = soup.get_text(' ', strip=True)

        # Age pattern: "Age: 29"
        age_match = re.search(r'Age[:\s]+(\d{2})', page_text)
        if age_match:
            try:
                profile['age'] = int(age_match.group(1))
            except ValueError:
                pass

        # Height pattern: "Height: 5' 4"" or "Height: 5,6" or "Height: 5'4"
        height_match = re.search(r'Height[:\s]+(\d[\'\u2019\u2032,]\s*\d+[\"″]?)', page_text)
        if height_match:
            profile['height'] = normalize_height(height_match.group(1))

        # Weight pattern: "Weight: 120 lbs"
        weight_match = re.search(
            r'Weight[:\s]+(\d+)\s*(?:lbs?|pounds?|kg)?',
            page_text, re.IGNORECASE
        )
        if weight_match:
            profile['weight'] = normalize_weight(f"{weight_match.group(1)} lbs")

        # Body Size pattern: "Body Size: 34C-24-34" (TDL calls measurements "Body Size")
        body_match = re.search(
            r'Body\s*Size[:\s]+(\d+[A-Za-z]*[-/]\d+[-/]\d+)',
            page_text, re.IGNORECASE
        )
        if body_match:
            meas_str = body_match.group(1).strip()
            normalized = normalize_measurements(meas_str)
            if normalized:
                profile['measurements'] = normalized
                # Extract bust from measurements
                bust_match = re.match(r'(\d+[A-Za-z]*)', normalized)
                if bust_match:
                    profile['bust'] = normalize_bust_size(bust_match.group(1))

        # Hair Color pattern: "Hair Color: Dark Brown" - require "Color" to avoid "Hair Type"
        # Only allow valid color words as second word to avoid "Brown Body"
        hair_match = re.search(
            r'Hair\s+Color[:\s]+([A-Za-z]+(?:\s+(?:Brown|Blonde|Black|Red|Auburn|Brunette))?)',
            page_text, re.IGNORECASE
        )
        if hair_match:
            hair = hair_match.group(1).strip()
            profile['hair_color'] = hair.title()

        # Eye Color pattern: "Eye Color: Brown" or "Eyes: Blue"
        eye_match = re.search(
            r'Eyes?(?:\s*Color)?[:\s]+([A-Za-z]+)',
            page_text, re.IGNORECASE
        )
        if eye_match:
            eye = eye_match.group(1).strip()
            if eye.lower() not in ('color',):
                profile['eye_color'] = eye.title()

        # Race/Ethnicity pattern: "Race/Ethnicity: Canadian"
        # Only match single nationality word to avoid capturing next field
        ethnicity_match = re.search(
            r'(?:Race/Ethnicity|Race|Ethnicity)[:\s]+([A-Za-z]+)',
            page_text, re.IGNORECASE
        )
        if ethnicity_match:
            ethnicity = ethnicity_match.group(1).strip()
            # Filter out invalid captures
            if ethnicity.lower() not in ('age', 'height', 'weight'):
                profile['ethnicity'] = ethnicity.title()

        # Tattoos - store as tag if mentioned
        tattoo_match = re.search(
            r'Tattoos?[:\s]+(no|none|yes|[A-Za-z]+)',
            page_text, re.IGNORECASE
        )
        if tattoo_match:
            tattoo_val = tattoo_match.group(1).lower()
            if tattoo_val not in ('no', 'none'):
                if 'tags' not in profile:
                    profile['tags'] = []
                profile['tags'].append('Tattoos')

        # Extract images from CDN
        images = self._extract_images(soup)
        if images:
            profile['images'] = images

        return profile

    def _extract_images(self, soup: BeautifulSoup) -> List[str]:
        """Extract image URLs from profile page."""
        images = []
        seen = set()

        # Look for images from their CDN (cloudfront)
        for img in soup.find_all('img'):
            src = img.get('src') or img.get('data-src')
            if not src:
                continue

            # Look for CDN images (d2wvwvig0d1mx7 is the main image CDN)
            if 'd2wvwvig0d1mx7.cloudfront.net' in src:
                # Get higher resolution version
                # TDL uses size suffixes like /cache/0x150/, /cache/768x0/
                full_src = re.sub(r'/cache/\d+x\d+/', '/cache/1000x0/', src)

                # Fix protocol-relative URLs
                if full_src.startswith('//'):
                    full_src = 'https:' + full_src

                # Skip logo images
                if 'logo' in full_src.lower():
                    continue

                if full_src not in seen:
                    seen.add(full_src)
                    images.append(full_src)

        # Also check for lazyload images
        for img in soup.find_all('img', class_='lazyloadImage'):
            src = img.get('data-src') or img.get('src')
            if src and 'd2wvwvig0d1mx7.cloudfront.net' in src:
                # Upgrade to full size
                full_src = re.sub(r'/cache/\d+x\d+/', '/cache/1000x0/', src)
                if full_src.startswith('//'):
                    full_src = 'https:' + full_src
                if full_src not in seen and 'logo' not in full_src.lower():
                    seen.add(full_src)
                    images.append(full_src)

        return images[:10]  # Limit to 10 images

    def normalize_listing(
        self,
        schedule_item: ScheduleItem,
        profile_data: Dict[str, Any],
        all_schedule_items: Optional[List[ScheduleItem]] = None
    ) -> ScrapedListing:
        """Create a ScrapedListing from schedule and profile data."""

        # Use name from profile if available
        name = profile_data.get('name') or schedule_item.name

        # Build schedules from all schedule items
        schedules = []
        if all_schedule_items:
            for item in all_schedule_items:
                schedules.append({
                    'day_of_week': item.day_of_week,
                    'location': item.location,
                    'start_time': item.start_time,
                    'end_time': item.end_time,
                })

        return ScrapedListing(
            name=normalize_name(name),
            profile_url=schedule_item.profile_url,
            source=self.config.short_name,
            tier=profile_data.get('tier'),
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
            schedules=schedules,
        )

    async def run(self):
        """Override run to ensure crawler cleanup."""
        try:
            return await super().run()
        finally:
            if hasattr(self.crawler, 'close'):
                try:
                    await self.crawler.close()
                except Exception as e:
                    self.logger.warning(f"Error during crawler cleanup: {e}")
