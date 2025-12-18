"""
HiddenGemEscorts (HGE) scraper.

This site uses JavaScript rendering for schedule content.
Profile pages have stats in obj-title-box/obj-box-value pairs.

Site structure:
- Schedule page: Dynamic JS tabs (Daily/Weekly)
- Gems list page: /meet-our-toronto-escorts-gems/ (static HTML with profile links)
- Profile pages: /gem/{name}/ with stats in structured HTML
"""

import re
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup

from ..base import BaseScraper, ScheduleItem
from ..config import get_site_config
from ..crawlers.crawlee_stealth import CrawleeStealth
from ..utils.normalizers import (
    normalize_name,
    normalize_weight,
    normalize_height,
    normalize_measurements,
    normalize_bust_size,
)


# HGE tier mapping
HGE_TIER_MAP = {
    'quartz': 'Quartz',
    'pearl': 'Pearl',
    'sapphire': 'Sapphire',
    'diamond': 'Diamond',
}


def normalize_hge_tier(tier: str) -> Optional[str]:
    """Normalize HGE tier names to consistent format."""
    if not tier:
        return None
    tier_lower = tier.strip().lower()
    return HGE_TIER_MAP.get(tier_lower, tier.strip().title())


class HiddenGemScraper(BaseScraper):
    """
    Scraper for HiddenGemEscorts.

    Site structure:
    - Gems list page: /meet-our-toronto-escorts-gems/ has all profile links
    - Profile pages: /gem/{name}/ with stats in obj-title-box/obj-box-value pairs
    - Schedule page uses JS rendering, so we use gems list as primary source

    Note: HGE doesn't list nationality or tags on profiles.
    """

    # Fields available on HGE profiles (no nationality, no tags)
    expected_fields = [
        'age', 'ethnicity', 'height', 'weight', 'bust', 'bust_type',
        'measurements', 'hair_color', 'eye_color', 'tier', 'images', 'schedules'
    ]

    def __init__(self, db_session=None):
        config = get_site_config('hiddengem')
        super().__init__(config, db_session)
        self.crawler = CrawleeStealth(
            rate_limit=2.0,
            headless=True,
            max_retries=3
        )

    async def scrape_schedule(self) -> List[ScheduleItem]:
        """
        Scrape the gems list page to get all escort profiles.

        Since the schedule page uses JS rendering, we use the gems list page
        which has static HTML with all profile links.

        Returns list of ScheduleItem objects.
        """
        gems_list_url = "https://hiddengemescorts.ca/meet-our-toronto-escorts-gems/"
        self.logger.info(f"Fetching gems list from {gems_list_url}")

        soup = await self.crawler.fetch_soup(gems_list_url)
        return self._parse_gems_list(soup)

    def _parse_gems_list(self, soup: BeautifulSoup) -> List[ScheduleItem]:
        """Parse the gems list page to extract profile links."""
        items = []
        seen_profiles = set()

        # Find all profile links with pattern /gem/{name}/
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            match = re.search(r'/gem/([^/]+)/?$', href)
            if match:
                profile_slug = match.group(1)

                # Skip duplicates
                if profile_slug in seen_profiles:
                    continue
                seen_profiles.add(profile_slug)

                # Extract name from slug (convert hyphens to spaces, title case)
                name = profile_slug.replace('-', ' ').title()

                # Create schedule item - actual schedule will be filled from profile
                items.append(ScheduleItem(
                    name=normalize_name(name),
                    profile_url=profile_slug,
                    day_of_week='Available',  # Placeholder - HGE doesn't show specific days on list
                    location='Toronto',  # HGE operates in Toronto area
                    tier=None,  # Will be extracted from profile
                ))

        self.logger.info(f"Found {len(items)} gems from list page")
        return items

    async def scrape_profile(self, profile_url: str) -> Dict[str, Any]:
        """
        Scrape an individual profile page.

        Args:
            profile_url: Profile slug (e.g., "maya")

        Returns:
            Dictionary of profile data
        """
        full_url = f"{self.config.base_url}{profile_url}/"
        self.logger.debug(f"Fetching profile: {full_url}")

        soup = await self.crawler.fetch_soup(full_url)
        return self._parse_profile(soup, profile_url)

    def _parse_profile(self, soup: BeautifulSoup, profile_slug: str = "") -> Dict[str, Any]:
        """Parse profile page HTML."""
        profile = {}

        # Extract name from page title
        title_tag = soup.find('title')
        if title_tag:
            title_text = title_tag.get_text(strip=True)
            # Title format: "Name | Hidden Gem Escorts"
            if ' | ' in title_text:
                profile['name'] = title_text.split(' | ')[0].strip()

        # Parse stats from obj-title-box/obj-box-value pairs
        stats = {}
        title_boxes = soup.find_all('p', class_='obj-title-box')

        for title_box in title_boxes:
            label = title_box.get_text(strip=True).lower()
            # Find the next sibling with class obj-box-value
            value_box = title_box.find_next_sibling('p', class_='obj-box-value')
            if not value_box:
                # Try finding it as next element
                next_elem = title_box.find_next('p', class_='obj-box-value')
                if next_elem:
                    value_box = next_elem

            if value_box:
                value = value_box.get_text(strip=True)
                if value:
                    stats[label] = value

        self.logger.debug(f"Parsed stats for {profile_slug}: {stats}")

        # Extract fields from parsed stats
        # Tier
        if 'tier' in stats:
            profile['tier'] = normalize_hge_tier(stats['tier'])

        # Age
        if 'age' in stats:
            try:
                profile['age'] = int(re.search(r'\d+', stats['age']).group())
            except (ValueError, AttributeError):
                pass

        # Stats/Measurements (e.g., "34C-26-35")
        if 'stats' in stats:
            meas_value = stats['stats']
            normalized_meas = normalize_measurements(meas_value)
            profile['measurements'] = normalized_meas

            # Extract bust from measurements
            if normalized_meas:
                bust_match = re.match(r'(\d+[A-Za-z]*)', normalized_meas)
                if bust_match:
                    bust_val = bust_match.group(1)
                    if re.search(r'[A-Za-z]', bust_val):
                        profile['bust'] = normalize_bust_size(bust_val)
                    else:
                        profile['bust'] = bust_val

        # Height
        if 'height' in stats:
            profile['height'] = normalize_height(stats['height'])

        # Weight
        if 'weight' in stats:
            profile['weight'] = normalize_weight(stats['weight'])

        # Eyes
        if 'eyes' in stats:
            profile['eye_color'] = stats['eyes'].title()

        # Hair
        if 'hair' in stats:
            profile['hair_color'] = stats['hair'].title()

        # Background -> Ethnicity
        if 'background' in stats:
            profile['ethnicity'] = stats['background'].title()

        # Body -> Bust type (Natural/Enhanced)
        if 'body' in stats:
            body_val = stats['body'].lower()
            if 'natural' in body_val:
                profile['bust_type'] = 'Natural'
            elif 'enhanced' in body_val:
                profile['bust_type'] = 'Enhanced'

        # Talents -> Service type
        if 'talents' in stats:
            profile['service_type'] = stats['talents'].upper()

        # Extract images from figure.obj-figure elements
        images = self._extract_images(soup)
        if images:
            profile['images'] = images

        # Extract schedule from profile page if available
        schedules = self._parse_profile_schedules(soup)
        if schedules:
            profile['schedules'] = schedules

        return profile

    def _extract_images(self, soup: BeautifulSoup) -> List[str]:
        """Extract image URLs from profile page."""
        images = []

        # Look for images in figure.obj-figure elements
        for figure in soup.find_all('figure', class_='obj-figure'):
            img = figure.find('img')
            if img:
                src = img.get('src') or img.get('data-src')
                if src and 'wp-content/uploads' in src:
                    # Extract path relative to wp-content/uploads/
                    uploads_index = src.find('wp-content/uploads/')
                    if uploads_index != -1:
                        relative_path = src[uploads_index + len('wp-content/uploads/'):]
                        # Remove query parameters
                        relative_path = relative_path.split('?')[0]
                        if relative_path and relative_path not in images:
                            images.append(relative_path)

        # Also check for any other images in content area
        content_area = soup.find('article') or soup.find('main') or soup
        for img in content_area.find_all('img'):
            src = img.get('src') or img.get('data-src')
            if src and 'wp-content/uploads' in src and 'logo' not in src.lower():
                uploads_index = src.find('wp-content/uploads/')
                if uploads_index != -1:
                    relative_path = src[uploads_index + len('wp-content/uploads/'):]
                    relative_path = relative_path.split('?')[0]
                    if relative_path and relative_path not in images:
                        images.append(relative_path)

        return images[:10]  # Limit to 10 images

    def _parse_profile_schedules(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """
        Parse schedule information from the profile page.

        Structure:
        <div class="obj-inner-body active" data-target="weekly">
          <div class="obj-dates owl-carousel">
            <div class="obj-dates-day">
              <span class="obj-text-day-l">Wednesday</span>
              <span class="obj-text-value">5 pm - 9 pm</span>  (or "Unavailable")
              <span class="obj-text-location">Downtown Incall, King&Bathurst</span>
            </div>
          </div>
        </div>
        """
        schedules = []
        seen_days = set()

        # Find weekly schedule section
        weekly_section = soup.find('div', {'data-target': 'weekly'})
        if not weekly_section:
            return schedules

        # Find all day entries
        for day_div in weekly_section.find_all('div', class_='obj-dates-day'):
            # Get day of week
            day_elem = day_div.find('span', class_='obj-text-day-l')
            if not day_elem:
                continue

            day_of_week = day_elem.get_text(strip=True)
            if not day_of_week or day_of_week in seen_days:
                continue

            # Get time value
            time_elem = day_div.find('span', class_='obj-text-value')
            time_text = time_elem.get_text(strip=True) if time_elem else ''

            # Skip if unavailable
            if 'unavailable' in time_text.lower():
                continue

            # Parse time range (e.g., "5 pm - 9 pm")
            start_time = None
            end_time = None
            time_match = re.search(r'(\d+(?::\d+)?\s*(?:am|pm)?)\s*-\s*(\d+(?::\d+)?\s*(?:am|pm)?)', time_text, re.IGNORECASE)
            if time_match:
                start_time = time_match.group(1).strip()
                end_time = time_match.group(2).strip()

            # Get location
            location_elem = day_div.find('span', class_='obj-text-location')
            location_text = location_elem.get_text(strip=True) if location_elem else ''

            # Parse location (e.g., "Downtown Incall, King&Bathurst" -> town: Downtown, location: King&Bathurst)
            town = 'Toronto'  # Default
            location = 'unknown'

            if location_text:
                # Extract town from location text
                location_lower = location_text.lower()
                if 'downtown' in location_lower:
                    town = 'Downtown'
                elif 'etobicoke' in location_lower:
                    town = 'Etobicoke'
                elif 'north york' in location_lower:
                    town = 'North York'
                elif 'scarborough' in location_lower:
                    town = 'Scarborough'
                elif 'mississauga' in location_lower:
                    town = 'Mississauga'
                elif 'vaughan' in location_lower:
                    town = 'Vaughan'
                elif 'markham' in location_lower:
                    town = 'Markham'

                # Extract specific location (after comma)
                if ',' in location_text:
                    location = location_text.split(',')[-1].strip()
                else:
                    location = location_text

            seen_days.add(day_of_week)
            schedules.append({
                'day_of_week': day_of_week,
                'town': town,
                'location': location,
                'start_time': start_time,
                'end_time': end_time,
            })

        return schedules

    async def run(self):
        """Override run to ensure crawler cleanup."""
        try:
            return await super().run()
        finally:
            try:
                await self.crawler.close()
            except Exception as e:
                self.logger.warning(f"Error during crawler cleanup: {e}")
