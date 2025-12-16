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

from ..base import BaseScraper, ScheduleItem
from ..config import get_site_config
from ..crawlers.stealth import StealthCrawler
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
    'platinum dolls': 'Platinum Doll',
    'platinum doll': 'Platinum Doll',
    'sapphire dolls': 'Sapphire Doll',
    'sapphire doll': 'Sapphire Doll',
}


def normalize_dd_tier(tier: str) -> Optional[str]:
    """Normalize DD tier names to consistent format."""
    if not tier:
        return None
    tier_lower = tier.strip().lower()
    return DD_TIER_MAP.get(tier_lower, tier.strip().title())


def parse_dd_location(location_str: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Parse DD location string into town and location.

    Examples:
        "Downtown Richmond-Peter" -> ("Downtown", "Richmond-Peter")
        "Etobicoke HWY427-Bloor" -> ("Etobicoke", "HWY427-Bloor")
        "North York" -> ("North York", "unknown")
        "Outcall" -> (None, None)  # Skip outcall

    Returns:
        Tuple of (town, location) or (None, None) for Outcall
    """
    if not location_str:
        return ("unknown", "unknown")

    location_str = location_str.strip()

    # Skip Outcall locations
    if location_str.lower() == 'outcall' or 'outcall' in location_str.lower():
        return (None, None)

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


def parse_dd_date(date_str: str, filter_past: bool = True) -> Optional[str]:
    """
    Parse DD date string to get day of week.
    
    Optionally filters out past dates to avoid duplicate schedules
    for the same day of week (e.g., "Sun, Dec 07" vs "Sun, Dec 14").

    Examples:
        "Mon, Dec 08" -> "Monday"
        "Fri, Dec 12" -> "Friday"
        "Sun, Dec 07" -> None (if past and filter_past=True)

    Returns:
        Full day name or None (if date is in the past and filter_past=True)
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

    date_str_clean = date_str.strip().lower()
    
    # Find the day of week
    day_of_week = None
    for abbrev, full in day_map.items():
        if date_str_clean.startswith(abbrev):
            day_of_week = full
            break
    
    if not day_of_week:
        return None
    
    # Filter out past dates if requested
    if filter_past:
        # Try to parse the date to check if it's in the past
        # Format: "Mon, Dec 08" or "Sun, Dec 14"
        match = re.search(r'([a-z]{3})\s+(\d{1,2})', date_str_clean)
        if match:
            month_abbrev = match.group(1)
            day_num = int(match.group(2))
            
            month_map = {
                'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4,
                'may': 5, 'jun': 6, 'jul': 7, 'aug': 8,
                'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
            }
            
            month_num = month_map.get(month_abbrev)
            if month_num:
                today = datetime.now()
                # Assume current year for the date
                year = today.year
                # Handle year rollover (e.g., current month is Dec, date is Jan)
                if month_num < today.month - 6:
                    year += 1
                
                try:
                    parsed_date = datetime(year, month_num, day_num)
                    # Allow today and future dates
                    if parsed_date.date() < today.date():
                        return None  # Skip past dates
                except ValueError:
                    pass  # Invalid date, proceed with day_of_week
    
    return day_of_week


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
        self.crawler = StealthCrawler(
            rate_limit=config.rate_limit_seconds,  # Use config value (3.0s) to avoid rate limiting
            headless=True,
            reuse_page=True,  # Reuse browser page for speed
            timeout=20.0,
            max_retries=3  # More retries for 403 errors
        )
        self._crawler_initialized = False

    async def _ensure_crawler(self):
        """Ensure crawler is initialized."""
        if not self._crawler_initialized:
            try:
                await self.crawler._init_browser()
                # Verify browser is actually working
                if not await self.crawler._check_context_valid():
                    raise Exception("Browser initialized but context is invalid")
                self._crawler_initialized = True
            except Exception as e:
                self.logger.error(f"Failed to initialize crawler: {e}")
                self._crawler_initialized = False
                # Ensure cleanup of any partially allocated resources
                try:
                    await self.crawler.close()
                except Exception as cleanup_error:
                    self.logger.warning(f"Error during cleanup after failed initialization: {cleanup_error}")
                raise

    async def scrape_schedule(self) -> List[ScheduleItem]:
        """
        Scrape the schedule page.

        Returns list of ScheduleItem objects with basic info from data-doll-info.
        """
        await self._ensure_crawler()
        self.logger.info(f"Fetching schedule from {self.config.schedule_url}")
        soup = await self.crawler.fetch_soup(self.config.schedule_url)
        return self._parse_schedule(soup)

    def _parse_schedule(self, soup: BeautifulSoup) -> List[ScheduleItem]:
        """Parse the schedule page HTML with data-doll-info JSON."""
        items = []
        seen_profiles = set()  # Track unique profiles to avoid duplicates

        # Find all card elements with data-doll-info
        cards = soup.find_all('a', class_='card', attrs={'data-doll-info': True})

        self.logger.info(f"Found {len(cards)} escort cards on schedule page")

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
                                loc_list = json.loads(loc_str) if loc_str else []
                                location_str = loc_list[0] if loc_list else ''
                            except (json.JSONDecodeError, TypeError, IndexError):
                                location_str = ''

                            # Parse time from span.hours
                            hours_elem = sched.find('span', class_='hours')
                            hours_str = hours_elem.get_text(strip=True) if hours_elem else ''
                            start_time, end_time = parse_dd_time(hours_str)

                            day_of_week = parse_dd_date(date_str)
                            town, location = parse_dd_location(location_str)

                            # Skip if Outcall (town is None)
                            if town is None:
                                self.logger.debug(f"Skipping Outcall schedule for {name}")
                                continue

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
                                seen_profiles.add(profile_slug)
                else:
                    # Use date_location from JSON
                    for date_loc in date_locations:
                        if len(date_loc) >= 2:
                            location_str = date_loc[0]
                            date_str = date_loc[1]

                            day_of_week = parse_dd_date(date_str)
                            town, location = parse_dd_location(location_str)

                            # Skip if Outcall (town is None)
                            if town is None:
                                self.logger.debug(f"Skipping Outcall schedule for {name}")
                                continue

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
                                seen_profiles.add(profile_slug)

            except Exception as e:
                self.logger.error(f"Error parsing card: {e}")
                continue

        self.logger.info(f"Parsed {len(items)} schedule items for {len(seen_profiles)} unique escorts")
        return items

    async def scrape_profile(self, profile_url: str) -> Dict[str, Any]:
        """
        Scrape an individual profile page.

        Args:
            profile_url: Profile slug (not full URL)

        Returns:
            Dictionary of profile data
        """
        await self._ensure_crawler()
        full_url = f"{self.config.base_url}{profile_url}/"

        soup = await self.crawler.fetch_soup(full_url)
        profile = self._parse_profile(soup, profile_url)

        return profile

    async def run(self):
        """Override run to ensure crawler cleanup."""
        try:
            return await super().run()
        finally:
            # Always attempt cleanup, even if initialization failed
            # This ensures resources are freed even if _ensure_crawler() failed
            try:
                await self.crawler.close()
            except Exception as e:
                self.logger.warning(f"Error during crawler cleanup: {e}")
            finally:
                self._crawler_initialized = False

    def _parse_profile(self, soup: BeautifulSoup, profile_slug: str = "") -> Dict[str, Any]:
        """Parse profile page HTML."""
        profile = {}

        # Try to extract name from profile page (more reliable than schedule card)
        # Look for h1, h2, or title elements that might contain the proper name
        name_candidates = []
        
        # Check page title
        title_tag = soup.find('title')
        if title_tag:
            title_text = title_tag.get_text(strip=True)
            # Title might be like "Aeryn Monroe - DiscreetDolls" or "Aeryn Monroe | DD"
            if ' - ' in title_text:
                name_candidates.append(title_text.split(' - ')[0].strip())
            elif ' | ' in title_text:
                name_candidates.append(title_text.split(' | ')[0].strip())
        
        # Check h1 heading
        h1 = soup.find('h1')
        if h1:
            h1_text = h1.get_text(strip=True)
            if h1_text and len(h1_text) < 50:  # Reasonable name length
                name_candidates.append(h1_text)
        
        # Check for name in header/banner area
        header_name = soup.find('div', class_='doll-name') or soup.find('span', class_='name')
        if header_name:
            name_candidates.append(header_name.get_text(strip=True))
        
        # Use the first valid candidate that has a space (proper two-word name)
        for candidate in name_candidates:
            if candidate and ' ' in candidate and len(candidate) < 50:
                profile['name'] = candidate
                self.logger.debug(f"Extracted name from profile page for {profile_slug}: {candidate}")
                break
        
        if not profile.get('name'):
            self.logger.debug(f"No name found on profile page for {profile_slug}, candidates: {name_candidates}")

        # Find stats table (left side info)
        stats_table = soup.find('div', class_='doll-table-info')

        if stats_table:
            # Extract stats from table rows
            text = stats_table.get_text(' ', strip=True)
            self.logger.debug(f"Stats table text for {profile_slug}: {text[:200]}...")

            # Age
            age_match = re.search(r'Age[:\s]+(\d+)', text, re.IGNORECASE)
            if age_match:
                profile['age'] = int(age_match.group(1))

            # Height - handle various formats
            height_match = re.search(
                r'Height[:\s]+(\d+[\'\u2019\u2032]?\s*\d*[\"\u2033]?|\d+\s*cm)',
                text, re.IGNORECASE
            )
            if height_match:
                profile['height'] = normalize_height(height_match.group(1))

            # Weight
            weight_match = re.search(r'Weight[:\s]+(\d+\s*(?:lbs?|kg)?)', text, re.IGNORECASE)
            if weight_match:
                profile['weight'] = normalize_weight(weight_match.group(1))

            # Bust - try multiple patterns
            bust_match = re.search(r'Bust[:\s]+(\d+\s*[A-Za-z]+)', text, re.IGNORECASE)
            if bust_match:
                profile['bust'] = normalize_bust_size(bust_match.group(1))

            # Figure/Measurements - handle multiple formats:
            # "Figure: 34H" (bust only with cup)
            # "Figure: 36C–25–36" (full measurements with en-dash/em-dash and cup)
            # "Figure: 32D-24-36" (full measurements with hyphen and cup)
            # "Figure: 35-27-36" (full measurements without cup letter)
            figure_match = re.search(
                r'(?:Figure|Measurements?)[:\s]+(\d+[A-Za-z]*(?:\s*[–—\-/]\s*\d+\s*[–—\-/]\s*\d+)?)',
                text, re.IGNORECASE
            )
            if figure_match:
                figure_value = figure_match.group(1).strip()
                # Check if it's just bust size (e.g., "34H") or full measurements
                if re.match(r'^\d+[A-Za-z]+$', figure_value):
                    # Just bust size with cup letter - extract and set bust if not already found
                    if not profile.get('bust'):
                        profile['bust'] = normalize_bust_size(figure_value)
                elif re.match(r'^\d+$', figure_value):
                    # Just a number (rare, skip)
                    pass
                else:
                    # Full measurements - normalize and set
                    # Replace en-dash/em-dash with hyphen for normalization
                    measurements = figure_value.replace('–', '-').replace('—', '-')
                    measurements = normalize_measurements(measurements)
                    profile['measurements'] = measurements
                    # Also extract bust from figure if not already found
                    if not profile.get('bust'):
                        # Try with cup letter first (e.g., "34DD-26-36")
                        bust_from_fig = re.match(r'(\d+[A-Za-z]+)', measurements)
                        if bust_from_fig:
                            profile['bust'] = normalize_bust_size(bust_from_fig.group(1))
                        else:
                            # No cup letter, just use the number (e.g., "35-27-36" -> "35")
                            bust_num = re.match(r'(\d+)', measurements)
                            if bust_num:
                                profile['bust'] = bust_num.group(1)

            # Nationality - handle patterns like "Nationality: European" or "Nationality: Spanish & Columbian"
            nat_match = re.search(r'Nationality[:\s]+([A-Za-z\s/&-]+?)(?:\s+[A-Z][a-z]+:|$)', text, re.IGNORECASE)
            if nat_match:
                nationality = nat_match.group(1).strip()
                # Clean up and validate
                if nationality and len(nationality) > 1:
                    profile['nationality'] = nationality.title()

            # Ethnicity - handle patterns like:
            # "Ethnicity: Caucasian"
            # "Ethnicity: Middle Eastern"
            # "Ethnicity: Caucasian (Irish, British, German)"
            # "Ethnicity: Caucasian (French/Scottish)"
            # Stop before next field label like "Nationality:"
            eth_match = re.search(
                r'Ethnicity[:\s]+(.+?)(?:\s+(?:Nationality|Hair|Eye|Height|Weight|Age|Figure|Bust|Service)[:\s]|$)',
                text, re.IGNORECASE
            )
            if eth_match:
                ethnicity = eth_match.group(1).strip()
                ethnicity = ethnicity.strip().rstrip('.,;:')
                if ethnicity and len(ethnicity) > 1:
                    profile['ethnicity'] = ethnicity.title()

            # Hair color
            hair_match = re.search(r'Hair[:\s]+([A-Za-z\s/]+?)(?:\s+[A-Z][a-z]+:|$)', text, re.IGNORECASE)
            if hair_match:
                hair = hair_match.group(1).strip()
                if hair and len(hair) > 1:
                    profile['hair_color'] = hair.title()

            # Eye color
            eye_match = re.search(r'Eyes?[:\s]+([A-Za-z\s/]+?)(?:\s+[A-Z][a-z]+:|$)', text, re.IGNORECASE)
            if eye_match:
                eyes = eye_match.group(1).strip()
                if eyes and len(eyes) > 1:
                    profile['eye_color'] = eyes.title()

            # Breast type (Natural/Enhanced)
            if 'natural' in text.lower():
                profile['bust_type'] = 'Natural'
            elif 'enhanced' in text.lower():
                profile['bust_type'] = 'Enhanced'

        # Extract tier from page - look for tier badges/labels
        # DD tiers: Doll, Diamond Doll, Platinum Doll, Sapphire Doll
        page_text = soup.get_text(' ', strip=True).lower()
        if 'sapphire doll' in page_text or 'sapphire' in page_text:
            profile['tier'] = 'Sapphire Doll'
        elif 'platinum doll' in page_text or 'platinum' in page_text:
            profile['tier'] = 'Platinum Doll'
        elif 'diamond doll' in page_text or 'diamond' in page_text:
            profile['tier'] = 'Diamond Doll'
        elif 'doll' in page_text:
            # Check for just "Doll" tier (base tier) - but be careful not to match site name
            # Look for tier-specific elements
            tier_elem = soup.find(class_=re.compile(r'tier|badge|rank|level', re.IGNORECASE))
            if tier_elem and 'doll' in tier_elem.get_text(strip=True).lower():
                profile['tier'] = 'Doll'

        # Extract service type from right side div - "Service Details: GFE" or "Service Details:GFE & PSE"
        right_div = soup.find('div', class_='right')
        if right_div:
            right_text = right_div.get_text(' ', strip=True)
            service_match = re.search(r'Service\s*(?:Details?|Type)?[:\s]+([A-Za-z\s/,&]+?)(?:\s+[A-Z][a-z]+:|$)', right_text, re.IGNORECASE)
            if service_match:
                service = service_match.group(1).strip()
                if service and len(service) > 1:
                    profile['service_type'] = service.upper()

        # Also try to find service type in stats table if not found
        if not profile.get('service_type') and stats_table:
            text = stats_table.get_text(' ', strip=True)
            service_match = re.search(r'Service\s*(?:Details?|Type)?[:\s]+([A-Za-z\s/,&]+?)(?:\s+[A-Z][a-z]+:|$)', text, re.IGNORECASE)
            if service_match:
                service = service_match.group(1).strip()
                if service and len(service) > 1:
                    profile['service_type'] = service.upper()

        # Extract images from rightside
        images = []
        rightside = soup.find('div', class_='rightside')
        if rightside:
            for img in rightside.find_all('img'):
                src = img.get('src', '')
                if src and 'wp-content/uploads' in src:
                    # Extract path relative to wp-content/uploads/ (includes date directory)
                    uploads_index = src.find('wp-content/uploads/')
                    if uploads_index != -1:
                        # Get everything after 'wp-content/uploads/'
                        relative_path = src[uploads_index + len('wp-content/uploads/'):]
                        # Remove query parameters if any
                        relative_path = relative_path.split('?')[0]
                        if relative_path and relative_path not in images:
                            images.append(relative_path)

        # Also check for gallery images
        gallery = soup.find_all('img', class_='skip-lazy')
        for img in gallery:
            src = img.get('src', '')
            if src and 'wp-content/uploads' in src:
                # Extract path relative to wp-content/uploads/ (includes date directory)
                uploads_index = src.find('wp-content/uploads/')
                if uploads_index != -1:
                    # Get everything after 'wp-content/uploads/'
                    relative_path = src[uploads_index + len('wp-content/uploads/'):]
                    # Remove query parameters if any
                    relative_path = relative_path.split('?')[0]
                    if relative_path and relative_path not in images:
                        images.append(relative_path)

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

        # Extract schedules from profile page
        # Note: Profile page schedules are handled differently - the main schedule comes
        # from the schedule page (data-doll-info JSON), not the profile page.
        # The profile page may have a schedule display section but it's typically
        # for display purposes only. We get authoritative schedule data from the
        # schedule page parsing in _parse_schedule() which is passed through to 
        # normalize_listing() via all_schedule_items parameter.
        
        # Look for schedule div for additional schedule info (if different from schedule page)
        schedule_div = soup.find('div', class_='schedule')
        if schedule_div:
            schedules = []
            # Method 1: Check for <p> elements with data-date attributes
            schedule_entries = schedule_div.find_all('p', attrs={'data-date': True})
            
            for entry in schedule_entries:
                date_str = entry.get('data-date', '')
                loc_str = entry.get('data-location', '[]')
                
                # Parse location from data-location attribute
                try:
                    loc_list = json.loads(loc_str) if loc_str else []
                    location_str = loc_list[0] if loc_list else ''
                except (json.JSONDecodeError, TypeError, IndexError):
                    location_str = ''
                
                # Parse time from span.hours
                hours_elem = entry.find('span', class_='hours')
                hours_str = hours_elem.get_text(strip=True) if hours_elem else ''
                start_time, end_time = parse_dd_time(hours_str)
                
                day_of_week = parse_dd_date(date_str)
                town, location = parse_dd_location(location_str)
                
                # Skip if Outcall (town is None)
                if town is None:
                    continue
                
                if day_of_week:
                    schedules.append({
                        'day_of_week': day_of_week,
                        'location': f"{town}, {location}",
                        'start_time': start_time,
                        'end_time': end_time,
                    })
            
            # Method 2: If no data-date entries, look for other schedule formats
            if not schedules:
                # Try finding schedule items in different formats
                # Check for list items or divs with schedule info
                for item in schedule_div.find_all(['li', 'div', 'span'], class_=lambda x: x and 'schedule' in x.lower() if x else False):
                    text = item.get_text(' ', strip=True)
                    # Try to extract day from text
                    for day_abbrev, day_full in [('mon', 'Monday'), ('tue', 'Tuesday'), ('wed', 'Wednesday'),
                                                  ('thu', 'Thursday'), ('fri', 'Friday'), ('sat', 'Saturday'), ('sun', 'Sunday')]:
                        if day_abbrev in text.lower():
                            # Found a day, try to extract time
                            start_time, end_time = parse_dd_time(text)
                            schedules.append({
                                'day_of_week': day_full,
                                'location': 'unknown, unknown',
                                'start_time': start_time,
                                'end_time': end_time,
                            })
                            break
            
            if schedules:
                profile['schedules'] = schedules
                self.logger.debug(f"Extracted {len(schedules)} schedule(s) from profile page for {profile_slug}")

        # Note: log_profile_extraction is called in base class run() method
        # with schedule tier and items from schedule page included

        return profile
    # normalize_listing uses base class implementation
