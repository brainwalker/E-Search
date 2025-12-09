import re
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import httpx
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session
from api.database import Listing, Schedule, Source, Tag, Location


class SexyFriendsTorontoScraper:
    def __init__(self, db: Session):
        self.db = db
        self.source_name = "SFT"  # Updated from SexyFriendsToronto

        # Get source from database
        self.source = self.get_or_create_source()

        # Use URLs from database
        self.schedule_url = self.source.url
        self.base_url = self.source.base_url or "https://www.sexyfriendstoronto.com/toronto-escorts/"
        self.image_base_url = self.source.image_base_url or "https://www.sexyfriendstoronto.com/toronto-escorts/thumbnails/"

    def get_or_create_source(self) -> Source:
        # First, try to find source with new name
        source = self.db.query(Source).filter_by(name=self.source_name).first()
        
        if not source:
            # Migration: Check for old name "SexyFriendsToronto" and update it
            old_source = self.db.query(Source).filter_by(name="SexyFriendsToronto").first()
            if old_source:
                # Migrate old source to new name
                old_source.name = self.source_name
                # Update URLs if they're missing
                if not old_source.url:
                    old_source.url = "https://www.sexyfriendstoronto.com/toronto-escorts/schedule"
                if not old_source.base_url:
                    old_source.base_url = "https://www.sexyfriendstoronto.com/toronto-escorts/"
                if not old_source.image_base_url:
                    old_source.image_base_url = "https://www.sexyfriendstoronto.com/toronto-escorts/thumbnails/"
                self.db.commit()
                return old_source
        
        if not source:
            # Create new source with proper URLs
            source = Source(
                name=self.source_name,
                url="https://www.sexyfriendstoronto.com/toronto-escorts/schedule",
                base_url="https://www.sexyfriendstoronto.com/toronto-escorts/",
                image_base_url="https://www.sexyfriendstoronto.com/toronto-escorts/thumbnails/",
                active=True
            )
            self.db.add(source)
            self.db.commit()
        
        return source

    def match_location(self, location_string: str, source_id: int) -> int:
        """
        Match a location string from the schedule page to a Location ID.
        Returns the location_id or the default location if no match found.
        """
        # Normalize the location string
        location_string = location_string.strip()

        # Try to find a matching location
        # First, try exact match on the full location string (e.g., "Vaughan - unknown")
        # The format from schedule page seems to be "Town - Location"
        if ' - ' in location_string or ', ' in location_string:
            # Try splitting by different delimiters
            parts = None
            if ' - ' in location_string:
                parts = location_string.split(' - ', 1)
            elif ', ' in location_string:
                parts = location_string.split(', ', 1)

            if parts and len(parts) == 2:
                town = parts[0].strip()
                location = parts[1].strip()

                # Try exact match
                db_location = self.db.query(Location).filter(
                    Location.source_id == source_id,
                    Location.town == town,
                    Location.location == location
                ).first()

                if db_location:
                    return db_location.id

        # If no exact match, try fuzzy matching by searching for keywords
        # Search for locations that match parts of the string
        locations = self.db.query(Location).filter(Location.source_id == source_id).all()

        for loc in locations:
            if loc.is_default:
                continue  # Skip default, use as last resort

            # Check if town and location are in the string
            if loc.town.lower() in location_string.lower() and loc.location.lower() in location_string.lower():
                return loc.id

        # Return default location if no match found
        default_location = self.db.query(Location).filter(
            Location.source_id == source_id,
            Location.is_default == True
        ).first()

        if default_location:
            return default_location.id

        # If no default exists, create one
        print(f"Warning: No default location found for source {source_id}, creating one...")
        default_location = Location(
            source_id=source_id,
            town="Unknown",
            location="unknown",
            is_default=True
        )
        self.db.add(default_location)
        self.db.commit()
        return default_location.id

    async def fetch_page(self, url: str) -> str:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.text

    def parse_time_range(self, time_str: str) -> tuple:
        """Parse time range like '12PM-12AM' into start and end times"""
        if '-' in time_str:
            parts = time_str.split('-')
            return parts[0].strip(), parts[1].strip()
        return time_str, time_str

    def get_date_from_day_of_week(self, day_of_week: str) -> datetime:
        """Convert day of week string to actual date (next occurrence of that day)"""
        # Map day names to weekday numbers (0 = Monday, 6 = Sunday)
        day_map = {
            'Monday': 0,
            'Tuesday': 1,
            'Wednesday': 2,
            'Thursday': 3,
            'Friday': 4,
            'Saturday': 5,
            'Sunday': 6
        }

        today = datetime.now()
        target_day = day_map.get(day_of_week)

        if target_day is None:
            # If day not recognized, return today's date
            return today.replace(hour=0, minute=0, second=0, microsecond=0)

        # Calculate days until target day
        current_day = today.weekday()
        days_ahead = target_day - current_day

        # If the day is today or has passed this week, get next week's occurrence
        if days_ahead <= 0:
            days_ahead += 7

        target_date = today + timedelta(days=days_ahead)
        return target_date.replace(hour=0, minute=0, second=0, microsecond=0)

    def extract_tier(self, text: str) -> Optional[str]:
        """Extract tier from listing text (PLATINUM VIP, ELITE, ULTRA VIP, etc.)"""
        # Check higher tiers first so we don't default to ELITE when more specific exists
        tiers = ['PLATINUM VIP', 'ULTRA VIP', 'VIP', 'ELITE']
        text_upper = text.upper()
        for tier in tiers:
            if tier in text_upper:
                return tier
        return None

    def normalize_weight(self, weight_text: str) -> Optional[str]:
        """Convert weight like '130 lbs' or '130lbs' to rounded kg string (e.g., '59 kg')"""
        try:
            # Match number followed by optional space and lbs/lb
            lbs_match = re.search(r'(\d+)\s*(?:lbs?|pounds?)', weight_text, re.IGNORECASE)
            if not lbs_match:
                # Try just extracting any number
                num_match = re.search(r'(\d+)', weight_text)
                if num_match:
                    lbs = int(num_match.group(1))
                    kg = round(lbs * 0.453592)
                    return f"{kg} kg"
                return weight_text.strip()
            lbs = int(lbs_match.group(1))
            kg = round(lbs * 0.453592)
            return f"{kg} kg"
        except Exception:
            return weight_text.strip()

    def normalize_measurements(self, measurements_text: str) -> Optional[str]:
        """
        Normalize measurements to standard format: "34DD-26-36"
        Handles:
        - 34DD/25/34 -> 34DD-25-34 (slashes to dashes)
        - 34DD- 26-36 -> 34DD-26-36 (extra spaces)
        - 34C-2636 -> 34C-26-36 (compact format)
        - 32D-23- 35 -> 32D-23-35 (spaces around dashes)
        - 34 DD-26-36 -> 34DD-26-36 (remove space in bust)
        """
        if not measurements_text:
            return measurements_text

        measurements_text = measurements_text.strip()
        
        # Replace slashes with dashes
        measurements_text = measurements_text.replace('/', '-')
        
        # Remove spaces around dashes
        measurements_text = re.sub(r'\s*-\s*', '-', measurements_text)
        
        # Remove space between bust number and cup (34 DD -> 34DD)
        measurements_text = re.sub(r'^(\d+)\s+([A-Z]+)', r'\1\2', measurements_text, flags=re.IGNORECASE)
        
        # Try to parse as bust-waist-hip format and normalize
        match = re.match(r'^(\d+)([A-Z]+)-(\d+)-(\d+)$', measurements_text, re.IGNORECASE)
        if match:
            bust_num = match.group(1)
            bust_cup = match.group(2).upper()
            waist = match.group(3)
            hip = match.group(4)
            return f"{bust_num}{bust_cup}-{waist}-{hip}"
        
        # Handle compact format: 34C2636 -> 34C-26-36
        compact_match = re.match(r'^(\d{2})([A-Z]+)[-\s]?(\d{2})(\d{2})$', measurements_text, re.IGNORECASE)
        if compact_match:
            bust_num = compact_match.group(1)
            bust_cup = compact_match.group(2).upper()
            waist = compact_match.group(3)
            hip = compact_match.group(4)
            return f"{bust_num}{bust_cup}-{waist}-{hip}"

        return measurements_text

    def normalize_bust_size(self, bust_text: str) -> Optional[str]:
        """
        Normalize bust size to standard format: "34 DD"
        Handles:
        - 34DD -> 34 DD
        - 32B -> 32 B
        - 34 DD -> 34 DD (already normalized)
        """
        if not bust_text:
            return bust_text

        bust_text = bust_text.strip().upper()
        
        # Already in good format with space
        if re.match(r'^\d+\s+[A-Z]+$', bust_text):
            return bust_text
        
        # Add space between number and letters: 34DD -> 34 DD
        match = re.match(r'^(\d+)([A-Z]+)$', bust_text)
        if match:
            return f"{match.group(1)} {match.group(2)}"

        return bust_text

    def normalize_service_type(self, service_text: str) -> str:
        """
        Normalize service type to standard format: "GFE"
        Handles:
        - GF ENTERTAINER -> GFE
        - GF  ENTERTAINER -> GFE (multiple spaces)
        - Gfe -> GFE
        - gfe -> GFE
        """
        if not service_text:
            return service_text
        
        service = service_text.strip().upper()
        # Normalize multiple spaces
        service = re.sub(r'\s+', ' ', service)
        
        # GF ENTERTAINER -> GFE
        if service == 'GF ENTERTAINER':
            return 'GFE'
        
        return service

    def normalize_name(self, name_text: str) -> str:
        """
        Normalize name from ALL CAPS to Title Case
        Handles:
        - AHRI -> Ahri
        - LETICIA EVA -> Leticia Eva
        - DAISY DUKES -> Daisy Dukes
        """
        if not name_text:
            return name_text
        
        name = name_text.strip()
        # Convert to title case (first letter of each word capitalized)
        return name.title()

    def normalize_tier(self, tier_text: str) -> str:
        """
        Normalize tier from ALL CAPS to proper case
        Handles:
        - ELITE -> Elite
        - VIP -> VIP (keep as is)
        - ULTRA VIP -> Ultra VIP
        - PLATINUM VIP -> Platinum VIP
        """
        if not tier_text:
            return tier_text
        
        tier = tier_text.strip().upper()
        tier_map = {
            'ELITE': 'Elite',
            'VIP': 'VIP',
            'ULTRA VIP': 'Ultra VIP',
            'PLATINUM VIP': 'Platinum VIP'
        }
        return tier_map.get(tier, tier.title())

    def parse_schedule_page(self, html: str) -> List[Dict]:
        """Parse the schedule page and extract all listings"""
        soup = BeautifulSoup(html, 'html.parser')
        listings = []

        # Find all sections (locations) - search in body if content div doesn't exist
        content = soup.find('div', class_='content')
        if not content:
            content = soup.find('body')
        if not content:
            content = soup

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
                profile_slug = element.get('href', '').strip('/')
                if profile_slug and not profile_slug.startswith('http'):
                    full_text = element.get_text(strip=True)

                    # Skip non-listing links (design credits, etc.)
                    skip_patterns = ['P100.ca', 'Design', 'Website', 'Contact', 'About']
                    if any(pattern.lower() in full_text.lower() for pattern in skip_patterns):
                        continue

                    # Extract tier first
                    tier = self.extract_tier(full_text)

                    # Remove tier markers
                    clean_text = full_text
                    for t in ['*PLATINUM VIP*', '*ULTRA VIP*', '*ELITE*', '*VIP*']:
                        clean_text = clean_text.replace(t, '').strip()

                    # Enhanced time pattern to handle more formats:
                    # 12PM-12AM, 7P-11PM, 11AM-LATE, 3;30PM, 3PM, 1M-5PM, 10AM-3PM, 7:30PM-11;30PM
                    time_patterns = [
                        # Standard ranges (handles both : and ; in times): 12PM-12AM, 11:30AM-3:30PM, 7:30PM-11;30PM
                        r'(\d{1,2}(?:[;:]\d{2})?\s*(?:AM|PM)\s*-\s*\d{1,2}(?:[;:]\d{2})?\s*(?:AM|PM))',
                        # Missing M: 7P-11PM, 1M-5PM
                        r'(\d{1,2}\s*[PM]\s*-\s*\d{1,2}(?:[;:]\d{2})?\s*(?:AM|PM))',
                        # LATE: 11AM-LATE, 1PM-LATE
                        r'(\d{1,2}(?:[;:]\d{2})?\s*(?:AM|PM)\s*-\s*LATE)',
                        # Semicolon or colon time (only if not part of range): 3;30PM, 11:30AM
                        r'(\d{1,2}[;:]\d{2}\s*(?:AM|PM))',
                        # Just time: 3PM, 3P (trailing)
                        r'(\d{1,2}\s*(?:AM|PM|P))\s*$',
                    ]

                    time_str = None
                    start_time = None
                    end_time = None

                    for pattern in time_patterns:
                        time_match = re.search(pattern, clean_text, re.IGNORECASE)
                        if time_match:
                            time_str = time_match.group(1)
                            # Remove time from text to get clean name
                            clean_text = clean_text.replace(time_str, '').strip()
                            # Fix common typos in time string
                            time_str = time_str.replace(';', ':')  # 3;30PM -> 3:30PM
                            time_str = re.sub(r'(\d)P\b', r'\1PM', time_str)  # 7P -> 7PM
                            time_str = re.sub(r'(\d)M\b', r'\1AM', time_str)  # 1M -> 1AM

                            if '-' in time_str:
                                start_time, end_time = self.parse_time_range(time_str)
                            else:
                                start_time = time_str
                                end_time = time_str
                            break

                    # Clean up name - remove trailing punctuation, numbers, and leftover time patterns
                    name = re.sub(r'[;,\s]+$', '', clean_text).strip()
                    # Remove any remaining time patterns (e.g., "7:30PM-", "12PM", but NOT single A/P)
                    # Only match if there's a digit before AM/PM to avoid removing name endings like "A"
                    name = re.sub(r'\d+:?\d*\s*(?:AM|PM)\s*-?\s*$', '', name, flags=re.IGNORECASE).strip()
                    # Remove trailing numbers and dashes
                    name = re.sub(r'[\d\-]+$', '', name).strip()

                    # Skip if name is too short (likely invalid)
                    if len(name) < 2:
                        continue

                    listings.append({
                        'name': self.normalize_name(name),
                        'profile_slug': profile_slug.strip(),  # Just the slug
                        'profile_url': profile_slug.strip(),  # Store only the path/slug, not full URL
                        'tier': self.normalize_tier(tier) if tier else None,
                        'location': current_location,
                        'day_of_week': current_day,
                        'start_time': start_time,
                        'end_time': end_time
                    })

        return listings

    async def scrape_profile(self, profile_slug: str) -> Dict:
        """Scrape individual profile page for detailed information"""
        # Build full URL from base_url and slug
        full_profile_url = f"{self.base_url}{profile_slug}"
        html = await self.fetch_page(full_profile_url)
        soup = BeautifulSoup(html, 'html.parser')

        profile_data = {}

        # Extract all text content - try body if no content div
        content = soup.find('div', class_='content')
        if not content:
            content = soup.find('body')
        if not content:
            content = soup

        text = content.get_text()

        # Extract age - handles "Age: 26" and "Age 26" (no colon)
        age_match = re.search(r'Age[:\s]+(\d+)', text, re.IGNORECASE)
        if age_match:
            profile_data['age'] = int(age_match.group(1))

        # Extract nationality - handles many variations:
        # "Nationality: Canadian", "Nationality (Citizen of the country): Chilean"
        # "Nationality (Country Citizen): Pakistani", "Nationality (Country Citizen): CDN"
        # "Nationality/Ethnicity: Asian", "Nationality/Race: Brazilian Canadian"
        nationality_match = re.search(
            r'Nationality(?:\s*\([^)]+\))?(?:/(?:Ethnicity|Race))?:\s*([A-Za-z\s/&,]+?)(?:Ethnicity|Race|Bust|Height|Weight|Eyes|Hair|Measurement|Age|Enhancement|\n|$)', 
            text, re.IGNORECASE
        )
        if nationality_match:
            profile_data['nationality'] = nationality_match.group(1).strip().rstrip(',')

        # Extract ethnicity/race - handles:
        # "Ethnicity (Race): latina", "Ethnicity: Asian", "Race: Black"
        # "Ethnicity (Race): Brazilian / Canadian"
        # "Ethnicity (Race): Caucasian, Canadian born"
        ethnicity_match = re.search(
            r'(?:Ethnicity|Race)(?:\s*\([^)]+\))?:\s*([A-Za-z\s/&,]+?)(?:Nationality|Bust|Height|Weight|Eyes|Hair|Measurement|Age|Enhancement|\n|$)', 
            text, re.IGNORECASE
        )
        if ethnicity_match:
            ethnicity_val = ethnicity_match.group(1).strip().rstrip(',')
            # Clean up non-breaking spaces
            ethnicity_val = ethnicity_val.replace('\xa0', ' ').strip()
            profile_data['ethnicity'] = ethnicity_val

        # Extract measurements - handles:
        # "Measurements (Chest/Waist/Hips): 34DD/25/34"
        # "(Chest/Waist/Hips): 34DD-28-38"
        # "Measurements: 34-26-36"
        # "Measurements (Chost/Tap/Hips): 34DD/25/34" (typos)
        # "Measurements (Chest/Waist/Hips): 34DD- 26-36" (spaces around dashes)
        # "Measurements 32B-32-35" (no colon)
        # "Measurements: 34-24-34" (no cup letter)
        measurements_match = re.search(
            r'Measurements?(?:\s*\([^)]+\))?[:\s]+(\d+[A-Z]*\s*[-/]\s*\d+\s*[-/]\s*\d+)', 
            text, re.IGNORECASE
        )
        if measurements_match:
            measurements_val = measurements_match.group(1).strip()
            # Normalize to standard format: "34 DD-26-36"
            profile_data['measurements'] = self.normalize_measurements(measurements_val)
            
            # Extract bust from measurements if not already set
            # First part is bust (e.g., "34DD" from "34DD-28-38")
            bust_from_measurements = re.match(r'(\d+\s*[A-Z]+)', measurements_val, re.IGNORECASE)
            if bust_from_measurements:
                bust_raw = bust_from_measurements.group(1).replace(' ', '').upper()
                profile_data['bust'] = self.normalize_bust_size(bust_raw)

        # Extract bust measurements with type (if explicitly stated)
        # Handles:
        # "Bust: 32D-23- 35 ( Enhanced )" - full measurement with type
        # "Bust: 34B-25-36 Natural" - full measurement with type  
        # "Bust: 34DD-27-37 NaturalHeight:" - no space before next field
        # "Bust: 34D-24-34 (Ehanced)" - typo in Enhanced
        # "Bust: 34DD" - just bust size
        bust_match = re.search(r'Bust:\s*(\d+[A-Z]+(?:\s*[-/]\s*\d+\s*[-/]\s*\d+)?)\s*\(?\s*(Natural|Enhanced?|Ehanced)?\s*\)?', text, re.IGNORECASE)
        if bust_match:
            bust_val = bust_match.group(1).strip().rstrip('-/')
            bust_type = bust_match.group(2)
            
            # Check if bust_val is actually a full measurement (e.g., "32D-23-35" or "32D-23- 35")
            # Remove extra spaces first for matching
            bust_clean = re.sub(r'\s*-\s*', '-', bust_val)
            full_measurement_match = re.match(r'^(\d+[A-Z]+)-(\d+)-(\d+)$', bust_clean, re.IGNORECASE)
            if full_measurement_match:
                # It's a full measurement - extract just the bust and set measurements
                bust_raw = full_measurement_match.group(1).upper()
                profile_data['bust'] = self.normalize_bust_size(bust_raw)
                if 'measurements' not in profile_data:
                    profile_data['measurements'] = self.normalize_measurements(bust_clean)
                # Extract bust type (Natural or Enhanced) - fix typo "Ehanced"
                if bust_type:
                    bt = bust_type.strip().capitalize()
                    profile_data['bust_type'] = 'Enhanced' if bt in ['Enhanced', 'Ehanced'] else bt
            elif re.match(r'^\d+[A-Z]+$', bust_val, re.IGNORECASE):
                # It's a valid bust size (not "BUSTY" header)
                profile_data['bust'] = self.normalize_bust_size(bust_val)
                # Extract bust type (Natural or Enhanced) - fix typo "Ehanced"
                if bust_type:
                    bt = bust_type.strip().capitalize()
                    profile_data['bust_type'] = 'Enhanced' if bt in ['Enhanced', 'Ehanced'] else bt
        
        # Ensure bust is normalized to "34 DD" format
        if 'bust' in profile_data:
            # Check if bust contains full measurement
            bust_check = re.match(r'^(\d+\s*[A-Z]+)\s*[-/]\s*\d+\s*[-/]\s*\d+$', profile_data['bust'], re.IGNORECASE)
            if bust_check:
                # bust contains full measurement - extract just the bust
                if 'measurements' not in profile_data:
                    profile_data['measurements'] = self.normalize_measurements(profile_data['bust'])
                bust_raw = bust_check.group(1).replace(' ', '').upper()
                profile_data['bust'] = self.normalize_bust_size(bust_raw)
            else:
                # Normalize bust format
                profile_data['bust'] = self.normalize_bust_size(profile_data['bust'])
        
        # Infer bust type from text if not explicitly stated
        if 'bust' in profile_data and 'bust_type' not in profile_data:
            # Check for "Enhancements none" or "Enhancements: none"
            enhancements_match = re.search(r'Enhancements?[:\s]+(none|yes|no|natural|enhanced)', text, re.IGNORECASE)
            if enhancements_match:
                enh_val = enhancements_match.group(1).lower()
                if enh_val in ['none', 'no', 'natural']:
                    profile_data['bust_type'] = 'Natural'
                elif enh_val in ['yes', 'enhanced']:
                    profile_data['bust_type'] = 'Enhanced'
            elif 'enhanced' in text.lower() or 'Enhanced: Yes' in text:
                profile_data['bust_type'] = 'Enhanced'
            elif 'natural' in text.lower() or 'Enhanced: No' in text or 'Enhanced: no' in text:
                profile_data['bust_type'] = 'Natural'

        # Extract height (formats: 5'9, 5'9", 5 ft 9, 5"7, 5,4, etc.)
        # Handles many variations:
        # - U+2019 (RIGHT SINGLE QUOTATION MARK): 5'9
        # - Regular apostrophe: 5'9
        # - Double quote for feet: 5"7
        # - Comma for feet: 5,4
        # - Unicode prime/double prime: 5′9, 5″3
        # Pattern: digit + separator (quote/comma/prime) + digits
        height_match = re.search(r'Height:\s*(\d+[\u2019\u2018\u0027\u2032\u0060\u00b4\u2033"\',]+\d+)', text, re.IGNORECASE)
        if height_match:
            height_val = height_match.group(1).strip()
            # Normalize all separators to standard apostrophe
            height_val = re.sub(r'[\u2019\u2018\u2032\u0060\u00b4\u2033"\',]', "'", height_val)
            profile_data['height'] = height_val
        else:
            # Try alternative formats: 5 ft 9, 5ft 9in, etc.
            height_alt = re.search(r"Height:\s*(\d+\s*ft\.?\s*\d*\s*(?:in\.?)?)", text, re.IGNORECASE)
            if height_alt:
                profile_data['height'] = height_alt.group(1).strip()
            else:
                # Try cm format: 170 cm, 170cm, 156cm
                cm_match = re.search(r"Height:\s*(\d{2,3}\s*cm)", text, re.IGNORECASE)
                if cm_match:
                    profile_data['height'] = cm_match.group(1).strip()

        # Extract weight (formats: 100 lbs, 100lbs, 100 lb, 45 kg, or just 128)
        # First try with units
        weight_match = re.search(r'Weight:\s*(\d+\s*(?:lbs?|kg|pounds?))', text, re.IGNORECASE)
        if weight_match:
            weight_val = weight_match.group(1).strip()
            # If already in kg, keep as is
            if 'kg' in weight_val.lower():
                profile_data['weight'] = weight_val
            else:
                profile_data['weight'] = self.normalize_weight(weight_val)
        else:
            # Try weight without units (assume lbs if no unit specified)
            weight_no_unit = re.search(r'Weight:\s*(\d{2,3})(?:\s|$|[^a-zA-Z])', text, re.IGNORECASE)
            if weight_no_unit:
                weight_val = weight_no_unit.group(1).strip()
                # Convert to kg (assume lbs)
                profile_data['weight'] = self.normalize_weight(f"{weight_val} lbs")

        # Extract eye color - handles:
        # "Eye color: brown", "Eye Colour: Blue", "Eyes: Green"
        # "Eye Colour: Blue/ Green" (multiple colors with /)
        # "Eye colour is green" (uses "is" instead of colon)
        eyes_match = re.search(r'Eye(?:s)?\s*(?:color|colour)(?:\s+is|[:\s]+)\s*([A-Za-z\s/]+?)(?:Hair|GF|PSE|MASSAGE|Details|Shoe|Measurement|Enhancement|Height|Weight|\xa0|\n|$)', text, re.IGNORECASE)
        if not eyes_match:
            # Try "Eyes: color" format
            eyes_match = re.search(r'Eyes:\s*([A-Za-z\s/]+?)(?:Hair|GF|PSE|MASSAGE|Details|Shoe|\xa0|\n|$)', text, re.IGNORECASE)
        if eyes_match:
            eye_color = eyes_match.group(1).strip()
            # Normalize spacing around /
            eye_color = re.sub(r'\s*/\s*', '/', eye_color)
            profile_data['eye_color'] = eye_color

        # Extract hair color - handles:
        # "Hair color: brown", "Hair Colour: black", "Hair Colour brunette" (no colon but has colour)
        # "Hair: Blonde/Brown" (multiple colors with /)
        # "Hair colour is dark brown" (uses "is" instead of colon)
        # Must have "color", "colour", ":" or "is" after Hair to avoid matching "HAIR" tag headers
        hair_match = re.search(r'Hair\s+(?:color|colour)(?:\s+is|[:\s]+)\s*([A-Za-z\s/]+?)(?:Eye|GF|PSE|MASSAGE|INCALL|OUTCALL|Details|Height|Bust|Weight|Measurement|Enhancement|Shoe|Tattoo|I\'m|\xa0|\n|$)', text, re.IGNORECASE)
        if not hair_match:
            # Try "Hair: color" format (colon right after Hair)
            hair_match = re.search(r'Hair:\s*([A-Za-z\s/]+?)(?:Eye|GF|PSE|MASSAGE|INCALL|OUTCALL|Details|Height|Bust|Weight|Measurement|Enhancement|Shoe|Tattoo|\xa0|\n|$)', text, re.IGNORECASE)
        if hair_match:
            hair_color = hair_match.group(1).strip()
            # Normalize spacing around /
            hair_color = re.sub(r'\s*/\s*', '/', hair_color)
            profile_data['hair_color'] = hair_color

        # Extract tier from profile page - use RATES section which is most reliable
        # Format: "INCALL RATES ELITE 30mins" or "INCALL RATES PLATINUM VIP 30mins"
        rates_tier_match = re.search(r'INCALL RATES\s+(PLATINUM VIP|ULTRA VIP|VIP|ELITE)\s+\d+mins?', text, re.IGNORECASE)
        if rates_tier_match:
            tier_text = rates_tier_match.group(1).strip()
            profile_data['tier'] = self.normalize_tier(tier_text)
        else:
            # Fallback: Look for tier in the profile header (NAME*TIER* format)
            # This appears in title and header like "AHRI*PLATINUM VIP*"
            name_tier_match = re.search(r'\*\s*(PLATINUM VIP|ULTRA VIP|VIP|ELITE)\s*\*', text, re.IGNORECASE)
            if name_tier_match:
                profile_data['tier'] = self.normalize_tier(name_tier_match.group(1).strip())

        # Extract service type - handles:
        # "Details: GFE"
        # "GF ENTERTAINER", "GF  ENTERTAINER" (multiple spaces)
        # "Service Details:Gfe" (no space after colon)
        # "Service Details: GFE"
        # Keep all services found EXCEPT MASSAGE
        found_services = []
        
        # Map regex patterns to normalized service names
        service_patterns = {
            r'GFE': 'GFE',
            r'GF\s+ENTERTAINER': 'GFE',  # Normalize to GFE
            r'PSE': 'PSE',
            r'FETISH\s+FRIENDLY': 'FETISH FRIENDLY',
            r'DOMINATRIX': 'DOMINATRIX',
        }
        
        # Find all service types mentioned in text (excluding MASSAGE)
        for pattern, service_name in service_patterns.items():
            if re.search(r'\b' + pattern + r'\b', text, re.IGNORECASE):
                if service_name not in found_services:
                    found_services.append(service_name)
        
        # Store all found services (comma-separated if multiple)
        if found_services:
            profile_data['service_type'] = ', '.join(found_services)

        # Note: Individual rates are no longer extracted from profiles
        # Rates are now determined by the tier from the tiers table

        # Extract images - store only the filename/path
        images = []
        img_tags = soup.find_all('img', class_='p_gallery_img')
        for img in img_tags:
            src = img.get('src', '')
            if src:
                # Extract just the filename from the URL
                # E.g., https://example.com/thumbnails/image.jpg -> image.jpg
                if src.startswith('http'):
                    # Extract filename from full URL
                    filename = src.split('/')[-1]
                    images.append(filename)
                else:
                    # Already a relative path
                    images.append(src)
        profile_data['images'] = json.dumps(images)

        # Extract tags from profile
        tags = []
        tag_keywords = ['NEW', 'BLONDE', 'BRUNETTE', 'BUSTY', 'PETITE', 'ASIAN', 'EUROPEAN', 'LATINA']
        for tag in tag_keywords:
            if tag.lower() in text.lower():
                tags.append(tag)
        profile_data['tags'] = tags

        return profile_data

    async def scrape_profile_with_debug(self, profile_slug: str) -> Dict:
        """Scrape profile with detailed debug info showing what text was matched for each field"""
        full_profile_url = f"{self.base_url}{profile_slug}"
        html = await self.fetch_page(full_profile_url)
        soup = BeautifulSoup(html, 'html.parser')

        # Get text content
        content = soup.find('div', class_='content')
        if not content:
            content = soup.find('body')
        if not content:
            content = soup

        text = content.get_text()
        
        # Store extraction details
        extractions = {}
        profile_data = {}

        # Age
        age_match = re.search(r'Age:\s*(\d+)', text, re.IGNORECASE)
        if age_match:
            profile_data['age'] = int(age_match.group(1))
            extractions['age'] = {
                'matched': True,
                'pattern': r'Age:\s*(\d+)',
                'raw_text': age_match.group(0),
                'extracted_value': age_match.group(1),
                'final_value': profile_data['age']
            }
        else:
            extractions['age'] = {'matched': False, 'pattern': r'Age:\s*(\d+)'}

        # Nationality - handles various formats
        nationality_match = re.search(
            r'Nationality(?:\s*\([^)]+\))?(?:/Ethnicity)?:\s*([A-Za-z\s]+?)(?:Ethnicity|Bust|Height|Weight|Eyes|Hair|Measurement|\n|$)', 
            text, re.IGNORECASE
        )
        if nationality_match:
            profile_data['nationality'] = nationality_match.group(1).strip()
            extractions['nationality'] = {
                'matched': True,
                'pattern': r'Nationality(?:\s*\([^)]+\))?(?:/Ethnicity)?:\s*...',
                'raw_text': nationality_match.group(0)[:80],
                'extracted_value': nationality_match.group(1),
                'final_value': profile_data['nationality']
            }
        else:
            extractions['nationality'] = {'matched': False, 'pattern': r'Nationality...:\s*...'}

        # Ethnicity/Race
        ethnicity_match = re.search(
            r'(?:Ethnicity|Race)(?:\s*\([^)]+\))?:\s*([A-Za-z\s/&]+?)(?:Nationality|Bust|Height|Weight|Eyes|Hair|Measurement|Age|\n|$)', 
            text, re.IGNORECASE
        )
        if ethnicity_match:
            ethnicity_val = ethnicity_match.group(1).strip().replace('\xa0', ' ').strip()
            profile_data['ethnicity'] = ethnicity_val
            extractions['ethnicity'] = {
                'matched': True,
                'pattern': r'(?:Ethnicity|Race)(?:\s*\([^)]+\))?:\s*...',
                'raw_text': ethnicity_match.group(0)[:80],
                'extracted_value': ethnicity_match.group(1),
                'final_value': profile_data['ethnicity']
            }
        else:
            extractions['ethnicity'] = {'matched': False, 'pattern': r'Ethnicity/Race:\s*...'}

        # Measurements (Chest/Waist/Hips) - handles spaces around dashes, no colon, no cup letter
        measurements_match = re.search(
            r'Measurements?(?:\s*\([^)]+\))?[:\s]+(\d+[A-Z]*\s*[-/]\s*\d+\s*[-/]\s*\d+)', 
            text, re.IGNORECASE
        )
        if measurements_match:
            measurements_val = measurements_match.group(1).strip()
            profile_data['measurements'] = self.normalize_measurements(measurements_val)
            
            # Extract bust from measurements
            bust_from_measurements = re.match(r'(\d+\s*[A-Z]+)', measurements_val, re.IGNORECASE)
            if bust_from_measurements:
                bust_raw = bust_from_measurements.group(1).replace(' ', '').upper()
                profile_data['bust'] = self.normalize_bust_size(bust_raw)
            
            extractions['measurements'] = {
                'matched': True,
                'pattern': r'Measurements:\s*(with spaces around dashes)',
                'raw_text': measurements_match.group(0)[:60],
                'extracted_value': measurements_match.group(1),
                'final_value': profile_data['measurements'],
                'bust_extracted': profile_data.get('bust')
            }
        else:
            extractions['measurements'] = {'matched': False, 'pattern': r'Measurements:\s*...'}

        # Bust (explicit field) - handles full measurements like "34DD-27-37 Natural"
        bust_match = re.search(r'Bust:\s*(\d+[A-Z]+(?:\s*[-/]\s*\d+\s*[-/]\s*\d+)?)\s*\(?\s*(Natural|Enhanced)?\s*\)?', text, re.IGNORECASE)
        if bust_match:
            bust_val = bust_match.group(1).strip().rstrip('-/')
            bust_type = bust_match.group(2)
            
            # Check if it's a full measurement (e.g., "34DD-27-37")
            bust_clean = re.sub(r'\s*-\s*', '-', bust_val)
            full_measurement_match = re.match(r'^(\d+[A-Z]+)-(\d+)-(\d+)$', bust_clean, re.IGNORECASE)
            
            if full_measurement_match:
                # It's a full measurement - extract just the bust
                bust_raw = full_measurement_match.group(1).upper()
                profile_data['bust'] = self.normalize_bust_size(bust_raw)
                if 'measurements' not in profile_data:
                    profile_data['measurements'] = self.normalize_measurements(bust_clean)
                if bust_type:
                    profile_data['bust_type'] = bust_type.strip().capitalize()
                extractions['bust'] = {
                    'matched': True,
                    'pattern': r'Bust:\s*(\d+[A-Z]+[-/]\d+[-/]\d+)\s*(Natural|Enhanced)?',
                    'raw_text': bust_match.group(0)[:60],
                    'extracted_value': bust_val,
                    'final_value': profile_data['bust'],
                    'measurements_extracted': profile_data.get('measurements'),
                    'bust_type': profile_data.get('bust_type')
                }
            elif re.match(r'^\d+[A-Z]+$', bust_val, re.IGNORECASE):
                # Just a bust size
                profile_data['bust'] = self.normalize_bust_size(bust_val)
                if bust_type:
                    profile_data['bust_type'] = bust_type.strip().capitalize()
                extractions['bust'] = {
                    'matched': True,
                    'pattern': r'Bust:\s*(\d+[A-Z]+)\s*(Natural|Enhanced)?',
                    'raw_text': bust_match.group(0),
                    'extracted_value': bust_val,
                    'final_value': profile_data['bust'],
                    'bust_type': profile_data.get('bust_type')
                }
            else:
                extractions['bust'] = {'matched': False, 'pattern': r'Bust:\s*...', 'note': f'Matched "{bust_val}" but not a valid bust size'}
        elif 'bust' in profile_data:
            extractions['bust'] = {'matched': True, 'source': 'measurements', 'final_value': profile_data['bust']}
        else:
            extractions['bust'] = {'matched': False, 'pattern': r'Bust:\s*(\d+[A-Z]+...)'}

        # Height
        height_match = re.search(r'Height:\s*(\d+[\u2019\u2018\u0027\u2032\u0060\u00b4\u2033"\',]+\d+)', text, re.IGNORECASE)
        if height_match:
            height_val = re.sub(r'[\u2019\u2018\u2032\u0060\u00b4\u2033"\',]', "'", height_match.group(1).strip())
            profile_data['height'] = height_val
            extractions['height'] = {
                'matched': True,
                'pattern': r'Height:\s*(\d+[quote-chars]+\d+)',
                'raw_text': height_match.group(0),
                'extracted_value': height_match.group(1),
                'final_value': profile_data['height'],
                'note': 'Normalized quote characters to apostrophe'
            }
        else:
            # Try cm format
            cm_match = re.search(r"Height:\s*(\d{2,3}\s*cm)", text, re.IGNORECASE)
            if cm_match:
                profile_data['height'] = cm_match.group(1).strip()
                extractions['height'] = {
                    'matched': True,
                    'pattern': r'Height:\s*(\d{2,3}\s*cm)',
                    'raw_text': cm_match.group(0),
                    'extracted_value': cm_match.group(1),
                    'final_value': profile_data['height']
                }
            else:
                extractions['height'] = {'matched': False, 'pattern': r'Height:\s*...'}

        # Weight - with or without units
        weight_match = re.search(r'Weight:\s*(\d+\s*(?:lbs?|kg|pounds?))', text, re.IGNORECASE)
        if weight_match:
            weight_val = weight_match.group(1).strip()
            if 'kg' in weight_val.lower():
                profile_data['weight'] = weight_val
            else:
                profile_data['weight'] = self.normalize_weight(weight_val)
            extractions['weight'] = {
                'matched': True,
                'pattern': r'Weight:\s*(\d+\s*(?:lbs?|kg|pounds?))',
                'raw_text': weight_match.group(0),
                'extracted_value': weight_match.group(1),
                'final_value': profile_data['weight'],
                'note': 'Converted lbs to kg' if 'lbs' in weight_val.lower() else None
            }
        else:
            # Try weight without units (assume lbs)
            weight_no_unit = re.search(r'Weight:\s*(\d{2,3})(?:\s|$|[^a-zA-Z])', text, re.IGNORECASE)
            if weight_no_unit:
                weight_val = weight_no_unit.group(1).strip()
                profile_data['weight'] = self.normalize_weight(f"{weight_val} lbs")
                extractions['weight'] = {
                    'matched': True,
                    'pattern': r'Weight:\s*(\d{2,3}) (no units)',
                    'raw_text': weight_no_unit.group(0),
                    'extracted_value': weight_val,
                    'final_value': profile_data['weight'],
                    'note': 'No units found, assumed lbs and converted to kg'
                }
            else:
                extractions['weight'] = {'matched': False, 'pattern': r'Weight:\s*(\d+\s*(?:lbs?|kg|pounds?))'}

        # Eye color - handles "Eye color:", "Eye Colour:", "Eyes:"
        eyes_match = re.search(r'Eye(?:s)?\s*(?:color|colour)?:\s*([A-Za-z\s]+?)(?:Hair|GF|PSE|MASSAGE|Details|\n|$)', text, re.IGNORECASE)
        if eyes_match:
            profile_data['eye_color'] = eyes_match.group(1).strip()
            extractions['eye_color'] = {
                'matched': True,
                'pattern': r'Eye(?:s)?\s*(?:color|colour)?:\s*...',
                'raw_text': eyes_match.group(0)[:50],
                'extracted_value': eyes_match.group(1),
                'final_value': profile_data['eye_color']
            }
        else:
            extractions['eye_color'] = {'matched': False, 'pattern': r'Eye color/colour:\s*...'}

        # Hair color - handles "Hair color:", "Hair Colour:", "Hair:"
        hair_match = re.search(r'Hair\s*(?:color|colour)?:\s*([A-Za-z\s]+?)(?:Eye|GF|PSE|MASSAGE|INCALL|OUTCALL|Details|\n|$)', text, re.IGNORECASE)
        if hair_match:
            profile_data['hair_color'] = hair_match.group(1).strip()
            extractions['hair_color'] = {
                'matched': True,
                'pattern': r'Hair\s*(?:color|colour)?:\s*...',
                'raw_text': hair_match.group(0)[:50],
                'extracted_value': hair_match.group(1),
                'final_value': profile_data['hair_color']
            }
        else:
            extractions['hair_color'] = {'matched': False, 'pattern': r'Hair color/colour:\s*...'}

        # Tier - use normalize_tier() to match scrape_profile() behavior
        rates_tier_match = re.search(r'INCALL RATES\s+(PLATINUM VIP|ULTRA VIP|VIP|ELITE)\s+\d+mins?', text, re.IGNORECASE)
        if rates_tier_match:
            raw_tier = rates_tier_match.group(1).strip()
            profile_data['tier'] = self.normalize_tier(raw_tier)
            extractions['tier'] = {
                'matched': True,
                'pattern': r'INCALL RATES\s+(TIER)\s+\d+mins?',
                'raw_text': rates_tier_match.group(0),
                'extracted_value': raw_tier,
                'final_value': profile_data['tier'],
                'source': 'rates_section'
            }
        else:
            name_tier_match = re.search(r'\*\s*(PLATINUM VIP|ULTRA VIP|VIP|ELITE)\s*\*', text, re.IGNORECASE)
            if name_tier_match:
                raw_tier = name_tier_match.group(1).strip()
                profile_data['tier'] = self.normalize_tier(raw_tier)
                extractions['tier'] = {
                    'matched': True,
                    'pattern': r'\*\s*(TIER)\s*\*',
                    'raw_text': name_tier_match.group(0),
                    'extracted_value': raw_tier,
                    'final_value': profile_data['tier'],
                    'source': 'name_header'
                }
            else:
                extractions['tier'] = {'matched': False, 'pattern': r'INCALL RATES / *TIER*'}

        # Service type - keep all found services except MASSAGE
        found_services = []
        
        service_patterns = {
            r'GFE': 'GFE',
            r'GF\s+ENTERTAINER': 'GFE',  # Normalize to GFE
            r'PSE': 'PSE',
            r'FETISH\s+FRIENDLY': 'FETISH FRIENDLY',
            r'DOMINATRIX': 'DOMINATRIX',
        }
        
        for pattern, service_name in service_patterns.items():
            if re.search(r'\b' + pattern + r'\b', text, re.IGNORECASE):
                if service_name not in found_services:
                    found_services.append(service_name)
        
        if found_services:
            profile_data['service_type'] = ', '.join(found_services)
            extractions['service_type'] = {
                'matched': True,
                'pattern': 'all services except MASSAGE',
                'all_found': found_services,
                'final_value': profile_data['service_type']
            }
        else:
            extractions['service_type'] = {'matched': False, 'pattern': r'(GF ENTERTAINER|PSE|...)'}

        # Note: Rates are now determined by tier from tiers table, not extracted from profile
        extractions['rates_note'] = {
            'note': 'Rates are determined by tier from the tiers table, not extracted from profile'
        }

        # Images
        images = []
        img_tags = soup.find_all('img', class_='p_gallery_img')
        for img in img_tags:
            src = img.get('src', '')
            if src:
                if src.startswith('http'):
                    images.append(src.split('/')[-1])
                else:
                    images.append(src)
        profile_data['images'] = json.dumps(images)
        extractions['images'] = {
            'matched': len(images) > 0,
            'count': len(images),
            'final_value': images[:5] if images else []
        }

        # Tags
        tags = []
        tag_keywords = ['NEW', 'BLONDE', 'BRUNETTE', 'BUSTY', 'PETITE', 'ASIAN', 'EUROPEAN', 'LATINA']
        for tag in tag_keywords:
            if tag.lower() in text.lower():
                tags.append(tag)
        profile_data['tags'] = tags
        extractions['tags'] = {
            'matched': len(tags) > 0,
            'keywords_searched': tag_keywords,
            'final_value': tags
        }

        # Get relevant text snippets for debugging
        text_snippets = {}
        for field in ['Age', 'Height', 'Weight', 'Bust', 'Nationality', 'Eyes', 'Hair']:
            idx = text.lower().find(field.lower())
            if idx >= 0:
                text_snippets[field] = text[idx:idx+80].replace('\n', ' ').strip()

        return {
            'profile_url': full_profile_url,
            'profile_data': profile_data,
            'extractions': extractions,
            'text_snippets': text_snippets,
            'full_text_length': len(text)
        }

    async def scrape_and_save(self) -> Dict:
        """Main scraping function"""
        source = self.get_or_create_source()

        # Fetch schedule page
        html = await self.fetch_page(self.schedule_url)
        schedule_listings = self.parse_schedule_page(html)

        saved_count = 0
        updated_count = 0
        profile_scraped_count = 0

        for item in schedule_listings:
            # Check if listing exists
            listing = self.db.query(Listing).filter_by(
                name=item['name'],
                source_id=source.id
            ).first()

            is_new = listing is None

            if is_new:
                listing = Listing(
                    name=item['name'],
                    profile_url=item['profile_url'],
                    tier=item['tier'],
                    source_id=source.id
                )

            # Update basic fields - schedule page tier is most reliable
            schedule_tier = item.get('tier')
            if schedule_tier:
                listing.tier = schedule_tier
            listing.is_active = True
            listing.is_expired = False

            # Always scrape full profile to ensure we have complete data
            try:
                profile_data = await self.scrape_profile(item['profile_url'])

                # Update listing with profile data
                for key, value in profile_data.items():
                    if key == 'tags':
                        continue
                    # Only use profile tier if schedule didn't have one
                    if key == 'tier' and schedule_tier:
                        continue
                    if value is not None:  # Don't overwrite with None
                        setattr(listing, key, value)

                # Handle tags - clear and re-add to avoid duplicates
                if 'tags' in profile_data:
                    # Get existing tag IDs for this listing
                    existing_tag_ids = {t.id for t in listing.tags if t.id}
                    
                    for tag_name in profile_data['tags']:
                        tag = self.db.query(Tag).filter_by(name=tag_name).first()
                        if not tag:
                            tag = Tag(name=tag_name)
                            self.db.add(tag)
                            self.db.flush()  # Get the ID
                        # Only add if not already associated
                        if tag.id not in existing_tag_ids:
                            listing.tags.append(tag)
                            existing_tag_ids.add(tag.id)

                profile_scraped_count += 1
            except Exception as e:
                print(f"Error scraping profile {item['profile_url']}: {e}")

            if is_new:
                self.db.add(listing)
                saved_count += 1
            else:
                updated_count += 1

            self.db.commit()

            # Match location string to location_id
            location_id = self.match_location(item['location'], source.id)

            # Calculate date from day of week
            schedule_date = self.get_date_from_day_of_week(item['day_of_week'])

            # Check if schedule already exists for this listing, day, and location
            existing_schedule = self.db.query(Schedule).filter_by(
                listing_id=listing.id,
                day_of_week=item['day_of_week'],
                location_id=location_id
            ).first()

            if existing_schedule:
                # Update existing schedule
                existing_schedule.date = schedule_date
                existing_schedule.start_time = item.get('start_time')
                existing_schedule.end_time = item.get('end_time')
                existing_schedule.is_expired = False
            else:
                # Add new schedule
                schedule = Schedule(
                    listing_id=listing.id,
                    day_of_week=item['day_of_week'],
                    date=schedule_date,
                    start_time=item.get('start_time'),
                    end_time=item.get('end_time'),
                    location_id=location_id
                )
                self.db.add(schedule)

        self.db.commit()

        # Update source last_scraped
        source.last_scraped = datetime.utcnow()
        self.db.commit()

        return {
            'source': self.source_name,
            'total_listings': len(schedule_listings),
            'new_listings': saved_count,
            'updated_listings': updated_count,
            'profiles_scraped': profile_scraped_count,
            'timestamp': datetime.utcnow().isoformat()
        }
