"""
SelectCompanyEscorts scraper.

Select has:
- Single tier: Standard pricing (from tiers table)
- Single location: Downtown Toronto
- Schedule: Table format with escort names in rows, days in columns
- Profile URL pattern: /toronto-companions/{name}/

Schedule structure:
- HTML table with 7-day columns (Mon-Sun)
- Cell values: Time slots ("1-9pm"), "CALL", or "OFF"
"""

import re
from typing import List, Dict, Any, Optional
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


# Day columns in schedule table order
DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']


def parse_time_slot(time_str: str) -> tuple:
    """
    Parse time slot string into start and end times.

    Examples:
        "1-9pm" -> ("1:00 PM", "9:00 PM")
        "12pm-8pm" -> ("12:00 PM", "8:00 PM")
        "10am-6pm" -> ("10:00 AM", "6:00 PM")
        "12pm-9pm" -> ("12:00 PM", "9:00 PM")
        "CALL" -> (None, None)
        "OFF" -> (None, None)

    Returns:
        (start_time, end_time) tuple
    """
    if not time_str:
        return (None, None)

    time_str = time_str.strip().upper()

    # Skip non-time values
    if time_str in ['CALL', 'OFF', '', '-']:
        return (None, None)

    # Pattern: "1-9pm" or "12pm-8pm" or "10am-6pm"
    match = re.match(
        r'(\d{1,2})(?::(\d{2}))?\s*(AM|PM)?\s*[-–]\s*(\d{1,2})(?::(\d{2}))?\s*(AM|PM)?',
        time_str,
        re.IGNORECASE
    )

    if match:
        start_hour = int(match.group(1))
        start_min = match.group(2) or '00'
        start_ampm = match.group(3)
        end_hour = int(match.group(4))
        end_min = match.group(5) or '00'
        end_ampm = match.group(6)

        # If no AM/PM on start, infer from context
        if not start_ampm and end_ampm:
            end_ampm_upper = end_ampm.upper()
            # For typical escort schedules, if end is PM:
            # - start hour <= 12 is usually PM (daytime schedule like 12-9pm)
            # - start hour > end hour would be AM (overnight like 10-2am, rare)
            if end_ampm_upper == 'PM':
                # Daytime schedule - start is also PM unless it would make no sense
                if start_hour <= 12:
                    start_ampm = 'PM'
                else:
                    start_ampm = 'AM'
            else:  # end is AM (overnight)
                start_ampm = 'PM'

        # Default to PM if still missing (most escort schedules are daytime)
        start_ampm = start_ampm or 'PM'
        end_ampm = end_ampm or 'PM'

        start_time = f"{start_hour}:{start_min} {start_ampm.upper()}"
        end_time = f"{end_hour}:{end_min} {end_ampm.upper()}"

        return (start_time, end_time)

    return (None, None)


class SelectScraper(BaseScraper):
    """
    Scraper for SelectCompanyEscorts.

    Site structure:
    - Schedule page: Table with escort names in first column, days as column headers
    - Profile pages: Stats section with age/height/weight/measurements, pricing info

    Note: Select doesn't list nationality, service_type, or tags on profiles.
    """

    # Fields available on Select profiles (no nationality, service_type, tags)
    expected_fields = [
        'age', 'ethnicity', 'height', 'weight', 'bust', 'bust_type',
        'measurements', 'hair_color', 'eye_color', 'tier', 'images', 'schedules'
    ]

    def __init__(self, db_session=None):
        config = get_site_config('select')
        super().__init__(config, db_session)
        self.crawler = StaticCrawler(rate_limit=config.rate_limit_seconds)

    async def scrape_schedule(self) -> List[ScheduleItem]:
        """
        Scrape the schedule page to get list of escorts with their availability.

        Schedule table structure:
        - First row: Headers (Name, Mon Dec 15, Tue Dec 16, ...)
        - Subsequent rows: Escort name in first cell, availability in remaining cells
        - Cell values: Time ("1-9pm"), "CALL", or "OFF"

        Returns list of ScheduleItem objects.
        """
        self.logger.info(f"Fetching schedule from {self.config.schedule_url}")
        soup = await self.crawler.fetch_soup(self.config.schedule_url)
        return self._parse_schedule(soup)

    def _parse_schedule(self, soup: BeautifulSoup) -> List[ScheduleItem]:
        """Parse the schedule page HTML to extract escorts and their schedules."""
        items = []

        # Find the schedule table by ID
        table = soup.find('table', id='escort-schedule')
        if not table:
            # Fallback to any table
            table = soup.find('table')
        if not table:
            self.logger.warning("No schedule table found")
            return items

        rows = table.find_all('tr')
        if len(rows) < 2:
            self.logger.warning("Schedule table has no data rows")
            return items

        # Parse header row to get day mapping
        header_row = rows[0]
        header_cells = header_row.find_all(['th', 'td'])

        # Map column index to day name (skip first column which is name)
        day_mapping = {}
        for idx, cell in enumerate(header_cells[1:], start=1):
            cell_text = cell.get_text(strip=True).lower()
            for i, day in enumerate(DAY_NAMES):
                if day.lower()[:3] in cell_text:
                    day_mapping[idx] = day
                    break

        self.logger.debug(f"Day mapping: {day_mapping}")

        # Parse data rows
        for row in rows[1:]:
            cells = row.find_all(['th', 'td'])
            if not cells:
                continue

            # First cell contains escort name with link
            name_cell = cells[0]
            link = name_cell.find('a')

            if not link:
                continue

            href = link.get('href', '')
            name = link.get_text(strip=True)

            # Extract profile slug from href
            # Pattern: /toronto-escorts/Name or /toronto-companions/Name/
            match = re.search(r'/toronto-(?:companions|escorts)/([^/"]+)', href, re.IGNORECASE)
            if not match:
                self.logger.debug(f"No profile slug found in href: {href}")
                continue

            profile_slug = match.group(1).strip('/')

            if len(name) < 2:
                continue

            # Parse each day's availability
            for col_idx, cell in enumerate(cells[1:], start=1):
                if col_idx not in day_mapping:
                    continue

                day_name = day_mapping[col_idx]
                cell_text = cell.get_text(strip=True)

                # Skip empty or OFF cells
                if not cell_text or cell_text.upper() == 'OFF':
                    continue

                # Parse time slot
                start_time, end_time = parse_time_slot(cell_text)

                # Only include days with actual time values, skip "CALL" entries
                if start_time is None or end_time is None:
                    continue

                items.append(ScheduleItem(
                    name=normalize_name(name),
                    profile_url=profile_slug,
                    day_of_week=day_name,
                    location='Downtown',  # Select operates in Downtown Toronto only
                    start_time=start_time,
                    end_time=end_time,
                    tier='Standard',  # All Select escorts use Standard tier
                ))

        self.logger.info(f"Found {len(items)} schedule entries")
        return items

    async def scrape_profile(self, profile_url: str) -> Dict[str, Any]:
        """
        Scrape an individual profile page.

        Args:
            profile_url: Profile slug (e.g., "Katerina")

        Returns:
            Dictionary of profile data including stats
        """
        # Profile slugs should be lowercase for /toronto-companions/ URLs
        full_url = f"{self.config.base_url}{profile_url.lower()}/"
        self.logger.debug(f"Fetching profile: {full_url}")

        soup = await self.crawler.fetch_soup(full_url)
        return self._parse_profile(soup, profile_url)

    def _parse_profile(self, soup: BeautifulSoup, profile_slug: str = "") -> Dict[str, Any]:
        """Parse profile page HTML."""
        profile = {
            'tier': 'Standard',  # All Select escorts use Standard tier
        }

        # Get name from title or h1
        title_tag = soup.find('title')
        if title_tag:
            title = title_tag.get_text(strip=True)
            # Remove " - Select Company Escorts" suffix
            name = title.split(' - ')[0].split(' | ')[0].strip()
            profile['name'] = name

        # Try h1 as fallback
        if 'name' not in profile:
            h1 = soup.find('h1')
            if h1:
                profile['name'] = h1.get_text(strip=True)

        # Parse structured HTML: <table class="shop_attributes">
        # Each row: <tr><th>Label</th><td>Value</td></tr>
        stats = {}
        shop_table = soup.find('table', class_='shop_attributes')
        if shop_table:
            for row in shop_table.find_all('tr'):
                th = row.find('th')
                td = row.find('td')
                if th and td:
                    label = th.get_text(strip=True).lower().rstrip(':')
                    value = td.get_text(strip=True)
                    if value:
                        stats[label] = value

            self.logger.debug(f"Parsed stats for {profile_slug}: {stats}")

        # Extract fields from parsed stats
        # Age
        age_key = next((k for k in stats if 'age' in k), None)
        if age_key:
            try:
                profile['age'] = int(re.search(r'\d+', stats[age_key]).group())
            except (ValueError, AttributeError):
                pass

        # Height - full value like "5'8""
        height_key = next((k for k in stats if 'height' in k), None)
        if height_key:
            profile['height'] = normalize_height(stats[height_key])

        # Weight - full value like "130 lbs"
        weight_key = next((k for k in stats if 'weight' in k), None)
        if weight_key:
            profile['weight'] = normalize_weight(stats[weight_key])

        # Measurements - full value like "34C-26-36", "32-24-36", or "A28/24/34"
        meas_key = next((k for k in stats if 'measurement' in k), None)
        if meas_key:
            normalized_meas = normalize_measurements(stats[meas_key])
            profile['measurements'] = normalized_meas
            # Extract bust from normalized measurements (handles "A28/24/34" -> "28A-24-34")
            if normalized_meas:
                bust_match = re.match(r'(\d+[A-Za-z]*)', normalized_meas)
                if bust_match:
                    bust_val = bust_match.group(1)
                    if re.search(r'[A-Za-z]', bust_val):
                        profile['bust'] = normalize_bust_size(bust_val)
                    else:
                        profile['bust'] = bust_val  # Just the number

        # Bust (standalone) if not found in measurements
        if 'bust' not in profile:
            bust_key = next((k for k in stats if 'bust' in k or 'figure' in k), None)
            if bust_key:
                profile['bust'] = normalize_bust_size(stats[bust_key])

        # Bust type - "Natural" or "Enhanced"
        bust_type_key = next((k for k in stats if 'breast' in k), None)
        if bust_type_key:
            profile['bust_type'] = stats[bust_type_key].title()

        # Hair color - full value (handles "Blonde with highlights")
        hair_key = next((k for k in stats if 'hair' in k), None)
        if hair_key:
            profile['hair_color'] = stats[hair_key].title()

        # Eye color - full value
        eye_key = next((k for k in stats if 'eye' in k), None)
        if eye_key:
            profile['eye_color'] = stats[eye_key].title()

        # Background/Ethnicity - full value (handles "Russian Canadian", "Latina, Colombian")
        bg_key = next((k for k in stats if 'background' in k or 'ethnicity' in k), None)
        if bg_key:
            profile['ethnicity'] = stats[bg_key].title()

        # Images - look for product images
        images = self._extract_images(soup)
        if images:
            profile['images'] = images

        return profile

    def _extract_images(self, soup: BeautifulSoup) -> List[str]:
        """Extract image URLs from profile page."""
        images = []

        # Try WooCommerce product images
        gallery = soup.find('div', class_=re.compile(r'product-gallery|woocommerce-product-gallery'))
        if gallery:
            for img in gallery.find_all('img'):
                src = img.get('src') or img.get('data-src') or img.get('data-large_image')
                if src and 'wp-content/uploads' in src:
                    # Get full-size image
                    full_src = re.sub(r'-\d+x\d+\.', '.', src)
                    if full_src not in images:
                        images.append(full_src)

        # Try featured image
        if not images:
            featured = soup.find('img', class_=re.compile(r'wp-post-image|attachment-full'))
            if featured:
                src = featured.get('src')
                if src:
                    images.append(src)

        # Fallback: any images in content area
        if not images:
            content = soup.find('div', class_=re.compile(r'entry-content|product'))
            if content:
                for img in content.find_all('img'):
                    src = img.get('src')
                    if src and 'wp-content/uploads' in src:
                        full_src = re.sub(r'-\d+x\d+\.', '.', src)
                        if full_src not in images:
                            images.append(full_src)

        return images[:10]  # Limit to 10 images

    def normalize_listing(self, schedule_item: ScheduleItem, profile_data: Dict[str, Any], all_schedule_items: Optional[List[ScheduleItem]] = None) -> ScrapedListing:
        """Create a ScrapedListing from schedule and profile data."""

        # Use name from profile if available
        name = profile_data.get('name') or schedule_item.name

        # Build schedules from all_schedule_items for this profile
        schedules = []
        if all_schedule_items:
            for item in all_schedule_items:
                if item.profile_url == schedule_item.profile_url:
                    schedules.append({
                        'day_of_week': item.day_of_week,
                        'location': item.location or 'Downtown',
                        'start_time': item.start_time,
                        'end_time': item.end_time,
                    })

        return ScrapedListing(
            name=normalize_name(name),
            profile_url=schedule_item.profile_url,
            source=self.config.short_name,
            tier='Standard',  # All Select escorts use Standard tier
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
