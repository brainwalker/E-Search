"""
SecretEscorts scraper.

Secret has:
- 3 tiers: Blush (star=1), Rose (star=2), Rouge (star=3)
- 4 locations: Etobicoke, North York, Vaughan, Oakville
- Schedule: List format grouped by day
- Tier info: Available on /secrets/ page
- Profile URL pattern: /model/{name}/

Schedule structure:
- Days listed with date headers (e.g., "Sunday December 14")
- Each entry: "Name | Time | Location" with link to profile
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


# Map day name prefixes to full day names
DAY_NAMES = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']


def parse_time_slot(time_str: str) -> tuple:
    """
    Parse time slot string into start and end times.

    Examples:
        "1pm - 1am" -> ("1:00 PM", "1:00 AM")
        "12pm - 9pm" -> ("12:00 PM", "9:00 PM")
        "10am - 6pm" -> ("10:00 AM", "6:00 PM")

    Returns:
        (start_time, end_time) tuple
    """
    if not time_str:
        return (None, None)

    time_str = time_str.strip()

    # Pattern: "1pm - 1am" or "12pm - 9pm"
    match = re.match(
        r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)\s*[-–]\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)',
        time_str,
        re.IGNORECASE
    )

    if match:
        start_hour = int(match.group(1))
        start_min = match.group(2) or '00'
        start_ampm = match.group(3).upper()
        end_hour = int(match.group(4))
        end_min = match.group(5) or '00'
        end_ampm = match.group(6).upper()

        start_time = f"{start_hour}:{start_min} {start_ampm}"
        end_time = f"{end_hour}:{end_min} {end_ampm}"

        return (start_time, end_time)

    return (None, None)


class SecretScraper(BaseScraper):
    """
    Scraper for SecretEscorts.

    Site structure:
    - Schedule page: Days with list of escorts showing Name | Time | Location
    - Secrets page: List of all escorts with their tier badges
    - Profile pages: Stats section with age/height/measurements, rates

    Note: Secret doesn't list nationality, service_type, or tags on profiles.
    """

    # Fields available on Secret profiles (no nationality, service_type, tags)
    expected_fields = [
        'age', 'ethnicity', 'height', 'weight', 'bust', 'bust_type',
        'measurements', 'hair_color', 'eye_color', 'tier', 'images', 'schedules'
    ]

    def __init__(self, db_session=None):
        config = get_site_config('secret')
        super().__init__(config, db_session)
        self.crawler = StaticCrawler(rate_limit=config.rate_limit_seconds)
        self.tier_cache: Dict[str, str] = {}  # name -> tier mapping

    async def scrape_schedule(self) -> List[ScheduleItem]:
        """
        Scrape the schedule page to get list of escorts with their availability.

        Schedule format:
        - Day headers with dates
        - Each entry: "Name | 1pm - 1am | Etobicoke" with link to profile

        Returns list of ScheduleItem objects.
        """
        self.logger.info(f"Fetching schedule from {self.config.schedule_url}")

        # First, fetch tier info from /secrets/ page
        await self._fetch_tiers()

        soup = await self.crawler.fetch_soup(self.config.schedule_url)
        return self._parse_schedule(soup)

    async def _fetch_tiers(self):
        """Fetch tier information from the /secrets/ page."""
        secrets_url = "https://secretescorts.ca/secrets/"
        self.logger.info(f"Fetching tier info from {secrets_url}")

        soup = await self.crawler.fetch_soup(secrets_url)
        self._parse_tiers(soup)

    def _parse_tiers(self, soup: BeautifulSoup):
        """Parse the secrets page to extract tier information for each escort."""
        # Look for escort cards/listings with tier badges
        # Each listing typically has name and tier badge (BLUSH, ROSE, ROUGE)

        # Find all escort cards - typically in a grid or list
        cards = soup.find_all(['div', 'article'], class_=re.compile(r'escort|model|card|entry'))

        for card in cards:
            # Find name - usually in heading or link
            name_el = card.find(['h2', 'h3', 'h4', 'a'], class_=re.compile(r'title|name'))
            if not name_el:
                name_el = card.find('a')

            if not name_el:
                continue

            name = name_el.get_text(strip=True)
            if not name or len(name) < 2:
                continue

            # Find tier badge - look for BLUSH, ROSE, ROUGE text
            card_text = card.get_text(' ', strip=True).upper()
            tier = None

            if 'ROUGE' in card_text:
                tier = 'Rouge'
            elif 'ROSE' in card_text:
                tier = 'Rose'
            elif 'BLUSH' in card_text:
                tier = 'Blush'

            if tier:
                # Normalize name for matching
                normalized = normalize_name(name)
                self.tier_cache[normalized.lower()] = tier
                self.logger.debug(f"Cached tier: {name} -> {tier}")

        self.logger.info(f"Cached {len(self.tier_cache)} escort tiers")

    def _parse_schedule(self, soup: BeautifulSoup) -> List[ScheduleItem]:
        """Parse the schedule page HTML to extract escorts and their schedules."""
        items = []
        current_day = None

        # The schedule structure uses h2 elements for both day headers and entries
        # Day headers are just the day name (e.g., "Sunday")
        # Entries are "Name | 1pm - 1am | Location" with a link to /model/

        h2_elements = soup.find_all('h2')

        for h2 in h2_elements:
            text = h2.get_text(strip=True)

            # Check if this is a day header
            for day in DAY_NAMES:
                if day.lower() == text.lower():
                    current_day = day
                    break
            else:
                # Not a day header - check if it contains a schedule entry
                link = h2.find('a', href=re.compile(r'/model/'))
                if link and current_day:
                    href = link.get('href', '')

                    # Extract profile slug from href
                    match = re.search(r'/model/([^/"]+)', href)
                    if not match:
                        continue

                    profile_slug = match.group(1).strip('/')

                    # Parse the entry: Name | Time | Location
                    parts = [p.strip() for p in text.split('|')]

                    if len(parts) >= 3:
                        name = parts[0]
                        time_str = parts[1]
                        location = parts[2]

                        # Parse time
                        start_time, end_time = parse_time_slot(time_str)

                        if start_time is None:
                            continue

                        # Normalize location
                        location = location.strip()

                        # Get tier from cache
                        normalized_name = normalize_name(name).lower()
                        tier = self.tier_cache.get(normalized_name, 'Blush')  # Default to Blush

                        items.append(ScheduleItem(
                            name=normalize_name(name),
                            profile_url=profile_slug,
                            day_of_week=current_day,
                            location=location,
                            start_time=start_time,
                            end_time=end_time,
                            tier=tier,
                        ))

        self.logger.info(f"Found {len(items)} schedule entries")
        return items

    def _find_day_for_element(self, element, soup) -> Optional[str]:
        """Find the day of week for a schedule entry by looking at preceding headers."""
        if not element:
            return None

        # Look for preceding sibling or parent that contains a day name
        current = element

        for _ in range(10):  # Look up to 10 levels
            if current is None:
                break

            # Check previous siblings
            prev = current.find_previous_sibling(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'div'])
            if prev:
                text = prev.get_text(strip=True)
                for day in DAY_NAMES:
                    if day.lower() in text.lower():
                        return day

            # Also check parent
            parent = current.parent
            if parent:
                # Check if parent has a heading before current element
                for child in parent.children:
                    if child == current:
                        break
                    if hasattr(child, 'name') and child.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                        text = child.get_text(strip=True)
                        for day in DAY_NAMES:
                            if day.lower() in text.lower():
                                return day

            current = parent

        return None

    async def scrape_profile(self, profile_url: str) -> Dict[str, Any]:
        """
        Scrape an individual profile page.

        Args:
            profile_url: Profile slug (e.g., "amari")

        Returns:
            Dictionary of profile data including stats
        """
        full_url = f"{self.config.base_url}{profile_url}/"
        self.logger.debug(f"Fetching profile: {full_url}")

        soup = await self.crawler.fetch_soup(full_url)
        return self._parse_profile(soup, profile_url)

    def _parse_profile(self, soup: BeautifulSoup, profile_slug: str = "") -> Dict[str, Any]:
        """Parse profile page HTML."""
        profile = {}

        # Get name from model-title-bg span (this is the correct location)
        title_span = soup.find('span', class_='model-title-bg')
        if title_span:
            profile['name'] = title_span.get_text(strip=True)

        # Fallback to h2 with subtitle class
        if 'name' not in profile:
            subtitle = soup.find('h2', class_='subtitle')
            if subtitle:
                profile['name'] = subtitle.get_text(strip=True)

        # Last resort: use profile slug
        if 'name' not in profile and profile_slug:
            # Convert slug to name (e.g., "tina-lockett" -> "Tina Lockett")
            profile['name'] = ' '.join(word.title() for word in profile_slug.replace('-', ' ').split())

        # Get page text for regex parsing
        body = soup.find('body')
        # Parse dl/dt/dd structure for stats - much cleaner than regex
        stats = {}
        for dl in soup.find_all('dl'):
            dt = dl.find('dt')
            dd = dl.find('dd')
            if dt and dd:
                key = dt.get_text(strip=True).lower()
                value = dd.get_text(strip=True)
                if value:
                    stats[key] = value

        # Extract fields from dl/dt/dd stats
        if 'age' in stats:
            try:
                profile['age'] = int(re.search(r'\d+', stats['age']).group())
            except (ValueError, AttributeError):
                pass

        if 'height' in stats:
            profile['height'] = normalize_height(stats['height'])

        if 'weight' in stats:
            profile['weight'] = normalize_weight(stats['weight'])

        # Check for combined measurements field first (e.g., "32-24-36", "34B-26-35", or "A28/24/34")
        meas_key = next((k for k in stats if 'measurement' in k.lower()), None)
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

        # Fallback: build measurements from separate bust/waist/hips fields
        if 'measurements' not in profile:
            bust_val = stats.get('bust', '')
            waist_val = stats.get('waist', '')
            hips_val = stats.get('hips', '')
            if bust_val and waist_val and hips_val:
                profile['measurements'] = f"{bust_val}-{waist_val}-{hips_val}"

        # Extract bust if not already found
        if 'bust' not in profile and 'bust' in stats:
            bust_val = stats['bust']
            if re.search(r'[A-Za-z]', bust_val):
                profile['bust'] = normalize_bust_size(bust_val)
            else:
                profile['bust'] = bust_val  # Just the number

        # Bust type - check various key formats
        bust_type_key = next((k for k in stats if 'natural' in k.lower() or 'enhanced' in k.lower()), None)
        if bust_type_key:
            profile['bust_type'] = stats[bust_type_key].title()

        # Hair color - get full value
        hair_key = next((k for k in stats if 'hair' in k.lower()), None)
        if hair_key:
            profile['hair_color'] = stats[hair_key].title()

        # Eye color - get full value
        eye_key = next((k for k in stats if 'eye' in k.lower()), None)
        if eye_key:
            profile['eye_color'] = stats[eye_key].title()

        # Background/Ethnicity - get full value
        bg_key = next((k for k in stats if 'background' in k.lower()), None)
        if bg_key:
            profile['ethnicity'] = stats[bg_key].title()

        # Fallback to text-based regex for fields not in dl/dt/dd
        text = body.get_text(' ', strip=True) if body else ''

        # Get tier from page - look for Incall section with tier name
        tier_match = re.search(r'Incall\s*[-–]\s*(Blush|Rose|Rouge)', text, re.IGNORECASE)
        if tier_match:
            profile['tier'] = tier_match.group(1).title()
        else:
            # Try from tier cache
            name = profile.get('name', profile_slug)
            normalized = normalize_name(name).lower()
            profile['tier'] = self.tier_cache.get(normalized, 'Blush')

        # Images - look for gallery images
        images = self._extract_images(soup)
        if images:
            profile['images'] = images

        return profile

    def _extract_images(self, soup: BeautifulSoup) -> List[str]:
        """Extract image URLs from profile page."""
        images = []

        # Look for gallery or main images
        gallery = soup.find('div', class_=re.compile(r'gallery|slider|photos|images'))
        if gallery:
            for img in gallery.find_all('img'):
                src = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
                if src and 'wp-content/uploads' in src:
                    # Get full-size image
                    full_src = re.sub(r'-\d+x\d+\.', '.', src)
                    if full_src not in images:
                        images.append(full_src)

        # Try main content images
        if not images:
            content = soup.find('div', class_=re.compile(r'entry-content|content|single'))
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
                        'location': item.location or 'Etobicoke',
                        'start_time': item.start_time,
                        'end_time': item.end_time,
                    })

        # Get tier from profile or schedule item
        tier = profile_data.get('tier') or schedule_item.tier or 'Blush'

        return ScrapedListing(
            name=normalize_name(name),
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
