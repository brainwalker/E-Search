"""
SexyFriendsToronto (SFT) scraper.

This is the first site implemented with the new Crawlee-based system.
It serves as a reference implementation for other static HTML scrapers.
"""

import re
import json
from typing import List, Dict, Any, Optional, Tuple
from bs4 import BeautifulSoup

from ..base import BaseScraper, ScheduleItem
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


def parse_sft_location(location_str: str) -> Tuple[str, str]:
    """
    Parse SFT location string into town and location parts.
    
    Examples:
        "MIDTOWN YONGE & EGLINTON" -> ("Midtown", "Yonge & Eglinton")
        "DOWNTOWN UNIVERSITY & QUEEN" -> ("Downtown", "University & Queen")
        "ETOBICOKE HWY 427 & BURNHAMTHORPE RD (AIRPORT)" -> ("Etobicoke", "HWY 427 & Burnhamthorpe Rd (Airport)")
        "OAKVILLE  NEAR TRAFALGER & UPPERMIDDLE RD E" -> ("Oakville", "Near Trafalger & Uppermiddle Rd E")
        "VAUGHAN" -> ("Vaughan", "unknown")
    
    Returns:
        Tuple of (town, location)
    """
    if not location_str:
        return ("Unknown", "unknown")

    from scrapers.config import KNOWN_TOWNS_LOWER

    location_str = location_str.strip()

    # Try to find a known town at the start of the string
    location_lower = location_str.lower().strip()

    # Debug: log what we're trying to match
    import logging
    logger = logging.getLogger(__name__)
    logger.debug(f"Parsing SFT location: '{location_str}' (lowercase: '{location_lower}')")

    for town in sorted(KNOWN_TOWNS_LOWER, key=len, reverse=True):  # Check longer names first
        # Check if the location string starts with the town name (with optional space after)
        if location_lower.startswith(town):
            logger.debug(f"Matched town '{town}' in '{location_str}'")
            # Extract location part (everything after the town name)
            # Use the original case string but find the position using lowercase
            town_end_pos = len(town)
            # Skip any spaces after the town name
            while town_end_pos < len(location_str) and location_str[town_end_pos] == ' ':
                town_end_pos += 1
            location_part = location_str[town_end_pos:].strip()
            
            # Normalize town name (capitalize first letter of each word)
            town_normalized = ' '.join(word.capitalize() for word in town.split())
            
            # Normalize location part (remove extra spaces, capitalize properly)
            if location_part:
                # Clean up extra spaces
                location_part = ' '.join(location_part.split())
                # Capitalize first letter of each word, but preserve acronyms and special cases
                words = location_part.split()
                normalized_words = []
                for word in words:
                    # Preserve acronyms (all caps) and common abbreviations
                    if word.isupper() and len(word) <= 5:
                        normalized_words.append(word)
                    else:
                        normalized_words.append(word.capitalize())
                location_normalized = ' '.join(normalized_words)
            else:
                location_normalized = "unknown"
            
            logger.debug(f"Parsed result: town='{town_normalized}', location='{location_normalized}'")
            return (town_normalized, location_normalized)
    
    # If no known town found, treat whole string as town
    logger.debug(f"No town matched for '{location_str}', using fallback")
    town_normalized = ' '.join(word.capitalize() for word in location_str.split())
    return (town_normalized, "unknown")


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
                # Skip OUTCALL locations
                if current_location.upper() == 'OUTCALL' or 'OUTCALL' in current_location.upper():
                    self.logger.debug(f"Skipping OUTCALL location: '{current_location}'")
                    current_location = None  # Set to None to skip listings under this location
                    continue
                # Log location extraction for debugging
                self.logger.debug(f"Found location header: '{current_location}'")

            # Day headers (h6)
            elif element.name == 'h6':
                current_day = text

            # Listings (anchor tags)
            elif element.name == 'a' and current_day and current_location:
                # Skip if location is OUTCALL (shouldn't happen due to filtering above, but double-check)
                if current_location and ('OUTCALL' in current_location.upper() or current_location.upper() == 'OUTCALL'):
                    continue
                
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

                # Log if location is missing
                if not current_location or current_location.strip() == '':
                    self.logger.warning(f"Missing location for listing '{name}' on {current_day}")
                    current_location = 'Unknown'
                
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
        return self._parse_profile(soup, profile_url)

    def _parse_profile(self, soup: BeautifulSoup, profile_slug: str = "") -> Dict[str, Any]:
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

        # Extract schedules from profile page (div#schedule)
        schedules = self._parse_profile_schedules(soup)
        if schedules:
            profile['schedules'] = schedules

        # Note: log_profile_extraction is called in base class run() method
        # with schedule tier and items from schedule page included

        return profile

    def _parse_profile_schedules(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """
        Parse schedule information from the profile page's #schedule div.

        Structure:
        - div#schedule contains multiple .row elements (one per location)
        - Each row has h5 with location name
        - Each row has div.dateg elements for each day
        - Inside dateg: h6 has day name, p.mb-0 has time

        Returns:
            List of schedule dicts with day_of_week, location, start_time, end_time
        """
        schedules = []
        schedule_div = soup.find('div', id='schedule')

        if not schedule_div:
            self.logger.debug("No schedule div found on profile page")
            return schedules

        # Find all location rows
        for row in schedule_div.find_all('div', class_='row'):
            # Get location from h5
            location_h5 = row.find('h5')
            if not location_h5:
                continue

            location_text = location_h5.get_text(strip=True)
            # Remove INCALL prefix and clean up
            location_text = location_text.replace('INCALL', '').strip()

            # Skip OUTCALL locations
            if 'OUTCALL' in location_text.upper():
                continue

            # Find all day elements
            for dateg in row.find_all('div', class_='dateg'):
                # Get day name from h6
                day_h6 = dateg.find('h6')
                if not day_h6:
                    continue

                day_of_week = day_h6.get_text(strip=True)

                # Get time from p.mb-0
                time_p = dateg.find('p', class_='mb-0')
                if not time_p:
                    continue

                time_text = time_p.get_text(strip=True)
                if not time_text:
                    continue

                # Parse time range
                start_time, end_time = extract_time_range(time_text)

                schedules.append({
                    'day_of_week': day_of_week,
                    'location': location_text,
                    'start_time': start_time,
                    'end_time': end_time,
                })

        if schedules:
            self.logger.debug(f"Extracted {len(schedules)} schedule(s) from profile page")
        return schedules

    async def run(self):
        """Override run to ensure crawler cleanup."""
        try:
            return await super().run()
        finally:
            # Clean up HTTP client resources
            if hasattr(self.crawler, 'close'):
                try:
                    await self.crawler.close()
                except Exception as e:
                    self.logger.warning(f"Error during crawler cleanup: {e}")
