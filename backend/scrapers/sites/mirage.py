"""
Mirage Entertainment scraper.

Mirage has 3 tiers:
- Regular (no tier shown in title): Fixed pricing from tiers table
- VIP (shown as "Name ♛ VIP"): Fixed pricing from tiers table
- PLATINUM VIP (shown as "Name ♛ PLATINUM VIP"): Variable per-listing pricing

Schedule structure:
- Profile page has a table with locations as rows and days (M-S) as columns
- A filled circle (<i class="fa fa-circle">) indicates availability
"""

import re
from typing import List, Dict, Any, Optional, Tuple
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


# Map day abbreviations to full names
DAY_MAP = {
    0: 'Monday',
    1: 'Tuesday',
    2: 'Wednesday',
    3: 'Thursday',
    4: 'Friday',
    5: 'Saturday',
    6: 'Sunday',
}

# Map Mirage locations to our location format
LOCATION_MAP = {
    'DT TORONTO': ('Downtown', 'DT Toronto'),
    'DOWNTOWN': ('Downtown', 'DT Toronto'),
    'NORTH YORK': ('North York', 'North York'),
    'MARKHAM': ('Markham', 'Markham'),
    'AIRPORT': ('Etobicoke', 'Airport'),
    'ETOBICOKE': ('Etobicoke', 'Airport'),
}


def parse_mirage_tier(title: str) -> str:
    """
    Extract tier from page title.

    Examples:
        "Kimmy ♛ PLATINUM VIP - Mirage Entertainment" -> "Platinum VIP"
        "Kaitlyn ♛ VIP - Mirage Entertainment" -> "VIP"
        "Sunshine - Mirage Entertainment" -> "Regular"
    """
    if 'PLATINUM VIP' in title.upper():
        return 'Platinum VIP'
    elif '♛ VIP' in title or 'VIP' in title.upper().split(' - ')[0]:
        # Check if VIP is in the name part (before " - Mirage")
        name_part = title.split(' - ')[0] if ' - ' in title else title
        if 'VIP' in name_part.upper() and 'PLATINUM' not in name_part.upper():
            return 'VIP'
    return 'Regular'


def parse_mirage_name(title: str) -> str:
    """
    Extract clean name from page title.

    Examples:
        "Kimmy ♛ PLATINUM VIP - Mirage Entertainment" -> "Kimmy"
        "Sunshine - Mirage Entertainment" -> "Sunshine"
    """
    # Remove " - Mirage Entertainment" suffix
    name = title.split(' - ')[0] if ' - ' in title else title

    # Remove tier markers
    name = re.sub(r'\s*♛\s*(PLATINUM\s+)?VIP\s*', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s*-?\s*NEW\s*$', '', name, flags=re.IGNORECASE)

    return name.strip()


def parse_mirage_pricing(pricing_text: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Parse Mirage pricing string.

    Examples:
        "HH $250 & $350HR" -> ("$250", None, "$350", "30min")
        "$200 HH & $300 HR" -> ("$200", None, "$300", "30min")
        "$160HH/$250H" -> ("$160", None, "$250", "30min")
        "$300 45Min/$350HR" -> (None, "$300", "$350", "45min")
        "N/A" -> (None, None, None, None)

    Returns:
        (incall_30min, incall_45min, incall_1hr, min_booking)
    """
    if not pricing_text or pricing_text.strip().upper() == 'N/A':
        return (None, None, None, None)

    text = pricing_text.strip()
    incall_30min = None
    incall_45min = None
    incall_1hr = None
    min_booking = None

    # Pattern: "$300 45Min/$350HR" or "$300 45min / $350 HR"
    match_45 = re.search(r'\$(\d+)\s*45\s*min', text, re.IGNORECASE)
    if match_45:
        incall_45min = f"${match_45.group(1)}"
        min_booking = "45min"

    # Pattern: "HH $250" or "$200 HH" or "$160HH"
    match_hh = re.search(r'(?:HH\s*\$(\d+)|\$(\d+)\s*HH)', text, re.IGNORECASE)
    if match_hh:
        price = match_hh.group(1) or match_hh.group(2)
        incall_30min = f"${price}"
        if not min_booking:
            min_booking = "30min"

    # Pattern: "$350HR" or "$300 HR" or "$350H" or "$250H"
    match_hr = re.search(r'\$(\d+)\s*H(?:R|our)?(?!\w)', text, re.IGNORECASE)
    if match_hr:
        incall_1hr = f"${match_hr.group(1)}"

    return (incall_30min, incall_45min, incall_1hr, min_booking)


class MirageScraper(BaseScraper):
    """
    Scraper for Mirage Entertainment.

    Site structure:
    - Schedule page: Grid of escort cards with profile links
    - Profile pages: Stats in <dt>/<dd> format, schedule table with day/location availability
    """

    def __init__(self, db_session=None):
        config = get_site_config('mirage')
        super().__init__(config, db_session)
        self.crawler = StaticCrawler(rate_limit=config.rate_limit_seconds)

    async def scrape_schedule(self) -> List[ScheduleItem]:
        """
        Scrape the schedule page to get list of escorts.

        Returns list of ScheduleItem with basic info (name, profile_url).
        Full schedule is extracted from individual profile pages.
        """
        self.logger.info(f"Fetching schedule from {self.config.schedule_url}")
        soup = await self.crawler.fetch_soup(self.config.schedule_url)
        return self._parse_schedule(soup)

    def _parse_schedule(self, soup: BeautifulSoup) -> List[ScheduleItem]:
        """Parse the schedule page HTML to extract escort profile URLs."""
        items = []
        seen_urls = set()

        # Find all escort profile links
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')

            # Match profile URLs like https://mirage-entertainment.cc/escort/name/
            if '/escort/' in href and href not in seen_urls:
                seen_urls.add(href)

                # Extract profile slug from URL
                match = re.search(r'/escort/([^/]+)/?', href)
                if match:
                    profile_slug = match.group(1)

                    # Get name from link text or slug
                    name = link.get_text(strip=True)
                    if not name or len(name) < 2:
                        name = profile_slug.replace('-', ' ').title()

                    # Clean name
                    name = parse_mirage_name(name)

                    if len(name) >= 2:
                        items.append(ScheduleItem(
                            name=normalize_name(name),
                            profile_url=profile_slug,
                            day_of_week='',  # Will be filled from profile page
                            location=None,
                            tier=None,  # Will be extracted from profile
                        ))

        self.logger.info(f"Found {len(items)} unique escorts on schedule page")
        return items

    async def scrape_profile(self, profile_url: str) -> Dict[str, Any]:
        """
        Scrape an individual profile page.

        Args:
            profile_url: Profile slug (e.g., "kimmy")

        Returns:
            Dictionary of profile data including stats, pricing, and schedule
        """
        full_url = f"{self.config.base_url}{profile_url}/"
        self.logger.debug(f"Fetching profile: {full_url}")

        soup = await self.crawler.fetch_soup(full_url)
        return self._parse_profile(soup, profile_url)

    def _parse_profile(self, soup: BeautifulSoup, profile_slug: str = "") -> Dict[str, Any]:
        """Parse profile page HTML."""
        profile = {}

        # Get title for tier and name
        title_tag = soup.find('title')
        title = title_tag.get_text(strip=True) if title_tag else ''

        profile['tier'] = parse_mirage_tier(title)
        profile['name'] = parse_mirage_name(title)

        # Parse stats from <dt>/<dd> pairs
        for dt in soup.find_all('dt'):
            label = dt.get_text(strip=True).lower().rstrip(':')
            dd = dt.find_next_sibling('dd')
            if not dd:
                # Try next element
                dd = dt.find_next('dd')
            if dd:
                value = dd.get_text(strip=True)

                if 'age' in label and value:
                    try:
                        profile['age'] = int(re.search(r'\d+', value).group())
                    except (ValueError, AttributeError):
                        pass

                elif 'height' in label and value:
                    profile['height'] = normalize_height(value)

                elif 'weight' in label and value:
                    profile['weight'] = normalize_weight(value)

                elif 'measurement' in label and value:
                    # Extract bust_type from "(Natural)" or "(Enhanced)" suffix
                    bust_type_match = re.search(r'\((Natural|Enhanced)\)', value, re.IGNORECASE)
                    if bust_type_match:
                        profile['bust_type'] = bust_type_match.group(1).title()
                        # Remove bust_type from measurement string before normalizing
                        clean_value = re.sub(r'\s*\((?:Natural|Enhanced)\)', '', value, flags=re.IGNORECASE)
                    else:
                        clean_value = value
                    
                    profile['measurements'] = normalize_measurements(clean_value)
                    # Extract bust from measurements
                    bust_match = re.match(r'(\d+[A-Z]+)', clean_value, re.IGNORECASE)
                    if bust_match:
                        profile['bust'] = normalize_bust_size(bust_match.group(1))

                elif 'hair' in label and value:
                    profile['hair_color'] = value.title()

                elif 'eye' in label and value:
                    profile['eye_color'] = value.title()

                elif 'nationality' in label and value:
                    profile['nationality'] = value.title()

                elif 'in call' in label or 'incall' in label:
                    # Parse pricing
                    incall_30, incall_45, incall_1hr, min_book = parse_mirage_pricing(value)
                    if incall_30:
                        profile['incall_30min'] = incall_30
                    if incall_45:
                        profile['incall_45min'] = incall_45
                    if incall_1hr:
                        profile['incall_1hr'] = incall_1hr
                    if min_book:
                        profile['min_booking'] = min_book

                elif 'out call' in label or 'outcall' in label:
                    if value and value.upper() != 'N/A':
                        # Parse outcall pricing if available
                        match = re.search(r'\$(\d+)', value)
                        if match:
                            profile['outcall_1hr'] = f"${match.group(1)}"

        # Parse schedule table
        schedules = self._parse_schedule_table(soup)
        if schedules:
            profile['schedules'] = schedules

        # Get images from JSON-LD or FlexSlider
        images = self._extract_images(soup)
        if images:
            profile['images'] = images

        return profile

    def _parse_schedule_table(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """
        Parse the schedule table from profile page.

        Table structure:
        - Header row: M T W T F S S
        - Data rows: Location name in <th>, availability in <td> (circle icon = available)
        """
        schedules = []

        # Find all tables - schedule table has location rows
        for table in soup.find_all('table'):
            rows = table.find_all('tr')

            for row in rows:
                # Get location from <th>
                th = row.find('th')
                if not th:
                    continue

                location_name = th.get_text(strip=True).upper()

                # Skip header row and airport (usually empty)
                if location_name in ['', 'M', 'AIRPORT']:
                    continue

                # Map to our location format
                if location_name in LOCATION_MAP:
                    town, location = LOCATION_MAP[location_name]
                else:
                    # Unknown location - use as-is
                    town = location_name.title()
                    location = 'Unknown'

                # Check each day column for availability
                cells = row.find_all('td')
                for day_idx, cell in enumerate(cells[:7]):  # Only first 7 cells (M-S)
                    # Check if cell contains circle icon (available)
                    if cell.find('i', class_='fa-circle') or cell.find('i', class_=re.compile(r'fa-circle')):
                        day_name = DAY_MAP.get(day_idx, f'Day{day_idx}')
                        schedules.append({
                            'day_of_week': day_name,
                            'location': f"{town}, {location}",
                            'start_time': None,  # Mirage doesn't show specific times
                            'end_time': None,
                        })

        return schedules

    def _extract_images(self, soup: BeautifulSoup) -> List[str]:
        """Extract image URLs from profile page."""
        images = []

        # Try JSON-LD schema first
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                import json
                data = json.loads(script.string)
                if isinstance(data, dict) and 'image' in data:
                    img = data['image']
                    if isinstance(img, str):
                        images.append(img)
                    elif isinstance(img, dict) and 'url' in img:
                        images.append(img['url'])
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and 'image' in item:
                            images.append(item['image'])
            except (json.JSONDecodeError, TypeError):
                pass

        # Try FlexSlider images
        slider = soup.find('div', id='slider') or soup.find('div', class_='flexslider')
        if slider:
            for img in slider.find_all('img'):
                src = img.get('src') or img.get('data-src')
                if src and 'wp-content/uploads' in src:
                    # Get full-size image (remove thumbnail suffix)
                    full_src = re.sub(r'-\d+x\d+\.', '.', src)
                    if full_src not in images:
                        images.append(full_src)

        # Fallback: find any gallery images
        if not images:
            for img in soup.find_all('img', src=re.compile(r'wp-content/uploads')):
                src = img.get('src')
                if src and src not in images:
                    images.append(src)

        return images[:10]  # Limit to 10 images

    def normalize_listing(self, schedule_item: ScheduleItem, profile_data: Dict[str, Any], all_schedule_items: Optional[List[ScheduleItem]] = None) -> ScrapedListing:
        """Create a ScrapedListing from schedule and profile data."""

        # Use name from profile if available
        name = profile_data.get('name') or schedule_item.name
        tier = profile_data.get('tier') or 'Regular'

        # Always save scraped prices - Mirage shows per-listing prices on profiles
        # For Regular/VIP, tiers table provides fallback if listing prices are missing
        incall_30min = profile_data.get('incall_30min')
        incall_45min = profile_data.get('incall_45min')
        incall_1hr = profile_data.get('incall_1hr')
        outcall_1hr = profile_data.get('outcall_1hr')
        min_booking = profile_data.get('min_booking')

        return ScrapedListing(
            name=normalize_name(name),
            profile_url=schedule_item.profile_url,
            source=self.config.short_name,
            tier=normalize_tier(tier) if tier else None,
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
            incall_30min=incall_30min,
            incall_45min=incall_45min,
            incall_1hr=incall_1hr,
            outcall_1hr=outcall_1hr,
            min_booking=min_booking,
            images=profile_data.get('images', []),
            tags=profile_data.get('tags', []),
            schedules=profile_data.get('schedules', []),
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
