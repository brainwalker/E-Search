import re
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import httpx
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session
from api.database import Listing, Schedule, Source, Tag


class SexyFriendsTorontoScraper:
    def __init__(self, db: Session):
        self.db = db
        self.base_url = "https://www.sexyfriendstoronto.com"
        self.schedule_url = f"{self.base_url}/toronto-escorts/schedule"
        self.source_name = "SexyFriendsToronto"

    def get_or_create_source(self) -> Source:
        source = self.db.query(Source).filter_by(name=self.source_name).first()
        if not source:
            source = Source(
                name=self.source_name,
                url=self.base_url,
                active=True
            )
            self.db.add(source)
            self.db.commit()
        return source

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

    def extract_tier(self, text: str) -> Optional[str]:
        """Extract tier from listing text (PLATINUM VIP, ELITE, ULTRA VIP, etc.)"""
        tiers = ['PLATINUM VIP', 'ULTRA VIP', 'ELITE', 'VIP']
        text_upper = text.upper()
        for tier in tiers:
            if tier in text_upper:
                return tier
        return None

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

                    # Clean up name - remove trailing punctuation and numbers
                    name = re.sub(r'[;,\s]+$', '', clean_text).strip()

                    # Skip if name is too short (likely invalid)
                    if len(name) < 2:
                        continue

                    listings.append({
                        'name': name,
                        'profile_slug': profile_slug.strip(),
                        'profile_url': f"{self.base_url}/toronto-escorts/{profile_slug.strip()}",
                        'tier': tier,
                        'location': current_location,
                        'day_of_week': current_day,
                        'start_time': start_time,
                        'end_time': end_time
                    })

        return listings

    async def scrape_profile(self, profile_url: str) -> Dict:
        """Scrape individual profile page for detailed information"""
        html = await self.fetch_page(profile_url)
        soup = BeautifulSoup(html, 'html.parser')

        profile_data = {}

        # Extract all text content - try body if no content div
        content = soup.find('div', class_='content')
        if not content:
            content = soup.find('body')
        if not content:
            content = soup

        text = content.get_text()

        # Extract age
        age_match = re.search(r'Age:\s*(\d+)', text, re.IGNORECASE)
        if age_match:
            profile_data['age'] = int(age_match.group(1))

        # Extract nationality (stop at next field or newline)
        nationality_match = re.search(r'Nationality:\s*([A-Za-z\s]+?)(?:Bust|Height|Weight|Eyes|Hair|\n|$)', text, re.IGNORECASE)
        if nationality_match:
            profile_data['nationality'] = nationality_match.group(1).strip()

        # Extract bust measurements with type
        bust_match = re.search(r'Bust:\s*([\dA-Z\-]+)\s*(Natural|Enhanced)?', text, re.IGNORECASE)
        if bust_match:
            bust_measurements = bust_match.group(1).strip()
            bust_type = bust_match.group(2)

            profile_data['bust'] = bust_measurements

            # Extract bust type (Natural or Enhanced)
            if bust_type:
                profile_data['bust_type'] = bust_type.capitalize()
            else:
                profile_data['bust_type'] = None

        # Extract height (formats: 5'9, 5'9", 5 ft 9, etc.)
        # Handles all quote types including U+2019 (') and HTML entity &rsquo;
        height_match = re.search(r"Height:\s*(\d+['′''`´']\d*[\"″]?)", text, re.IGNORECASE)
        if height_match:
            profile_data['height'] = height_match.group(1).strip()

        # Extract weight (stop at next field)
        weight_match = re.search(r'Weight:\s*([\d\s]+lbs?)', text, re.IGNORECASE)
        if weight_match:
            profile_data['weight'] = weight_match.group(1).strip()

        # Extract eye color
        eyes_match = re.search(r'Eyes?:\s*([A-Za-z\s]+?)(?:Hair|GF|PSE|MASSAGE|\n|$)', text, re.IGNORECASE)
        if eyes_match:
            profile_data['eye_color'] = eyes_match.group(1).strip()

        # Extract hair color
        hair_match = re.search(r'Hair:\s*([A-Za-z\s]+?)(?:GF|PSE|MASSAGE|INCALL|OUTCALL|\n|$)', text, re.IGNORECASE)
        if hair_match:
            profile_data['hair_color'] = hair_match.group(1).strip()

        # Extract tier from profile page text (appears multiple times)
        # Look for tier mentions near rates or in title
        tier_match = re.search(r'(ULTRA VIP|PLATINUM VIP|ELITE|VIP)(?:\s+\d+mins?|\s+\d+\+?/HR|\s+POLINA|\s+[A-Z]+)', text, re.IGNORECASE)
        if tier_match:
            tier_text = tier_match.group(1).strip().upper()
            # Normalize tier names
            if 'ULTRA' in tier_text:
                profile_data['tier'] = 'ULTRA VIP'
            elif 'PLATINUM' in tier_text:
                profile_data['tier'] = 'PLATINUM VIP'
            elif 'ELITE' in tier_text:
                profile_data['tier'] = 'ELITE'
            elif tier_text == 'VIP':
                profile_data['tier'] = 'VIP'

        # Extract service type
        service_match = re.search(r'(GF ENTERTAINER|PSE|MASSAGE|FETISH FRIENDLY|DOMINATRIX)', text, re.IGNORECASE)
        if service_match:
            profile_data['service_type'] = service_match.group(1).strip()

        # Extract rates - INCALL
        # Pattern: "30mins/230" or "30 mins/230"
        incall_30_match = re.search(r'30\s*mins?\s*/\s*(\d+)', text, re.IGNORECASE)
        if incall_30_match:
            profile_data['incall_30min'] = int(incall_30_match.group(1))

        incall_45_match = re.search(r'45\s*mins?\s*/\s*(\d+)', text, re.IGNORECASE)
        if incall_45_match:
            profile_data['incall_45min'] = int(incall_45_match.group(1))

        incall_1hr_match = re.search(r'1\s*hr?\s*/\s*(\d+)', text, re.IGNORECASE)
        if incall_1hr_match:
            profile_data['incall_1hr'] = int(incall_1hr_match.group(1))

        # Extract rates - OUTCALL (format: "350+/HR")
        outcall_match = re.search(r'(\d+)\s*\+\s*/\s*HR', text, re.IGNORECASE)
        if outcall_match:
            profile_data['outcall_1hr'] = int(outcall_match.group(1))

        # Extract images
        images = []
        img_tags = soup.find_all('img', class_='p_gallery_img')
        for img in img_tags:
            src = img.get('src', '')
            if src and src.startswith('http'):
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

            # Update basic fields
            listing.tier = item.get('tier')
            listing.is_active = True
            listing.is_expired = False

            # Always scrape full profile to ensure we have complete data
            try:
                profile_data = await self.scrape_profile(item['profile_url'])

                # Update listing with profile data
                for key, value in profile_data.items():
                    if key != 'tags':
                        setattr(listing, key, value)

                # Handle tags
                if 'tags' in profile_data:
                    for tag_name in profile_data['tags']:
                        tag = self.db.query(Tag).filter_by(name=tag_name).first()
                        if not tag:
                            tag = Tag(name=tag_name)
                            self.db.add(tag)
                        if tag not in listing.tags:
                            listing.tags.append(tag)

                profile_scraped_count += 1
            except Exception as e:
                print(f"Error scraping profile {item['profile_url']}: {e}")

            if is_new:
                self.db.add(listing)
                saved_count += 1
            else:
                updated_count += 1

            self.db.commit()

            # Add schedule
            schedule = Schedule(
                listing_id=listing.id,
                day_of_week=item['day_of_week'],
                start_time=item.get('start_time'),
                end_time=item.get('end_time'),
                location=item['location']
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
