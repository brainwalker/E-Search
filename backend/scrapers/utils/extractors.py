"""
Data extraction utilities for scrapers.

These functions extract specific data from HTML text using regex patterns.
"""

import re
import json
from typing import Optional, List, Tuple
from bs4 import BeautifulSoup


def extract_tier(text: str) -> Optional[str]:
    """
    Extract tier from text.

    Checks for tiers in order of priority (highest first).

    Args:
        text: Text to search

    Returns:
        Tier string or None
    """
    tiers = ['PLATINUM VIP', 'ULTRA VIP', 'VIP', 'ELITE']
    text_upper = text.upper()
    for tier in tiers:
        if tier in text_upper:
            return tier
    return None


def extract_time_range(text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract start and end time from text.

    Handles formats like:
        12PM-12AM
        7P-11PM
        11AM-LATE
        3:30PM-8PM

    Args:
        text: Text to search

    Returns:
        Tuple of (start_time, end_time)
    """
    # Standard time range patterns
    patterns = [
        # 12PM-12AM, 11:30AM-3:30PM
        r'(\d{1,2}(?::\d{2})?\s*(?:AM|PM))\s*-\s*(\d{1,2}(?::\d{2})?\s*(?:AM|PM))',
        # Missing M: 7P-11PM
        r'(\d{1,2}\s*P)\s*-\s*(\d{1,2}(?::\d{2})?\s*(?:AM|PM))',
        # With LATE: 11AM-LATE
        r'(\d{1,2}(?::\d{2})?\s*(?:AM|PM))\s*-\s*(LATE)',
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            start = match.group(1).strip()
            end = match.group(2).strip()

            # Fix common typos
            start = re.sub(r'(\d)P$', r'\1PM', start, flags=re.IGNORECASE)
            end = re.sub(r'(\d)P$', r'\1PM', end, flags=re.IGNORECASE)
            start = start.replace(';', ':')
            end = end.replace(';', ':')

            return start, end

    # Single time only
    single_match = re.search(r'(\d{1,2}(?::\d{2})?\s*(?:AM|PM))\s*$', text, re.IGNORECASE)
    if single_match:
        time = single_match.group(1).strip()
        return time, time

    return None, None


def extract_age(text: str) -> Optional[int]:
    """
    Extract age from text.

    Args:
        text: Text to search

    Returns:
        Age as integer or None
    """
    match = re.search(r'Age[:\s]+(\d+)', text, re.IGNORECASE)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            pass
    return None


def extract_nationality(text: str) -> Optional[str]:
    """
    Extract nationality from text.

    Handles various formats:
        Nationality: Canadian
        Nationality (Citizen of the country): Chilean
        Nationality/Ethnicity: Asian
    """
    match = re.search(
        r'Nationality(?:\s*\([^)]+\))?(?:/(?:Ethnicity|Race))?:\s*([A-Za-z\s/&,]+?)(?:Ethnicity|Race|Bust|Height|Weight|Eyes|Hair|Measurement|Age|Enhancement|\n|$)',
        text, re.IGNORECASE
    )
    if match:
        return match.group(1).strip().rstrip(',')
    return None


def extract_ethnicity(text: str) -> Optional[str]:
    """
    Extract ethnicity/race from text.

    Handles:
        Ethnicity (Race): latina
        Ethnicity: Asian
        Race: Black
    """
    match = re.search(
        r'(?:Ethnicity|Race)(?:\s*\([^)]+\))?:\s*([A-Za-z\s/&,]+?)(?:Nationality|Bust|Height|Weight|Eyes|Hair|Measurement|Age|Enhancement|\n|$)',
        text, re.IGNORECASE
    )
    if match:
        value = match.group(1).strip().rstrip(',')
        return value.replace('\xa0', ' ').strip()
    return None


def extract_height(text: str) -> Optional[str]:
    """
    Extract height from text.

    Handles:
        Height: 5'9
        Height: 170 cm
        Height: 5 ft 9
    """
    # Standard feet/inches
    match = re.search(
        r'Height:\s*(\d+[\u2019\u2018\u0027\u2032\u0060\u00b4\u2033"\',]+\d+)',
        text, re.IGNORECASE
    )
    if match:
        return match.group(1).strip()

    # CM format
    cm_match = re.search(r'Height:\s*(\d{2,3}\s*cm)', text, re.IGNORECASE)
    if cm_match:
        return cm_match.group(1).strip()

    # ft in format
    ft_match = re.search(r"Height:\s*(\d+\s*ft\.?\s*\d*\s*(?:in\.?)?)", text, re.IGNORECASE)
    if ft_match:
        return ft_match.group(1).strip()

    return None


def extract_weight(text: str) -> Optional[str]:
    """
    Extract weight from text.

    Handles:
        Weight: 130 lbs
        Weight: 55 kg
        Weight: 128
    """
    # With units
    match = re.search(r'Weight:\s*(\d+\s*(?:lbs?|kg|pounds?))', text, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # Without units (assume lbs)
    match = re.search(r'Weight:\s*(\d{2,3})(?:\s|$|[^a-zA-Z])', text, re.IGNORECASE)
    if match:
        return f"{match.group(1)} lbs"

    return None


def extract_hair_color(text: str) -> Optional[str]:
    """
    Extract hair color from text.

    Handles:
        Hair color: brown
        Hair Colour: black
        Hair: Blonde/Brown
    """
    match = re.search(
        r'Hair\s+(?:color|colour)(?:\s+is|[:\s]+)\s*([A-Za-z\s/]+?)(?:Eye|GF|PSE|MASSAGE|INCALL|OUTCALL|Details|Height|Bust|Weight|\n|$)',
        text, re.IGNORECASE
    )
    if not match:
        match = re.search(
            r'Hair:\s*([A-Za-z\s/]+?)(?:Eye|GF|PSE|MASSAGE|INCALL|OUTCALL|Details|Height|Bust|Weight|\n|$)',
            text, re.IGNORECASE
        )
    if match:
        color = match.group(1).strip()
        return re.sub(r'\s*/\s*', '/', color)
    return None


def extract_eye_color(text: str) -> Optional[str]:
    """
    Extract eye color from text.

    Handles:
        Eye color: brown
        Eye Colour: Blue
        Eyes: Green
    """
    match = re.search(
        r'Eye(?:s)?\s*(?:color|colour)?(?:\s+is|[:\s]+)\s*([A-Za-z\s/]+?)(?:Hair|GF|PSE|MASSAGE|Details|Shoe|Measurement|\n|$)',
        text, re.IGNORECASE
    )
    if match:
        color = match.group(1).strip()
        return re.sub(r'\s*/\s*', '/', color)
    return None


def extract_bust(text: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Extract bust size, type, and measurements from text.

    Returns:
        Tuple of (bust_size, bust_type, measurements)
    """
    bust_size = None
    bust_type = None
    measurements = None

    # Full measurement pattern: Bust: 32D-23-35 (Enhanced)
    match = re.search(
        r'Bust:\s*(\d+[A-Z]+(?:\s*[-/]\s*\d+\s*[-/]\s*\d+)?)\s*\(?\s*(Natural|Enhanced?)?\s*\)?',
        text, re.IGNORECASE
    )

    if match:
        bust_val = match.group(1).strip().rstrip('-/')
        bust_type_raw = match.group(2)

        # Check if it's a full measurement
        bust_clean = re.sub(r'\s*-\s*', '-', bust_val)
        full_match = re.match(r'^(\d+[A-Z]+)-(\d+)-(\d+)$', bust_clean, re.IGNORECASE)

        if full_match:
            bust_size = full_match.group(1).upper()
            measurements = bust_clean
        elif re.match(r'^\d+[A-Z]+$', bust_val, re.IGNORECASE):
            bust_size = bust_val.upper()

        if bust_type_raw:
            bt = bust_type_raw.strip().capitalize()
            bust_type = 'Enhanced' if bt in ['Enhanced', 'Ehanced'] else bt

    # Check for measurements field
    if not measurements:
        meas_match = re.search(
            r'Measurements?(?:\s*\([^)]+\))?[:\s]+(\d+[A-Z]*\s*[-/]\s*\d+\s*[-/]\s*\d+)',
            text, re.IGNORECASE
        )
        if meas_match:
            measurements = meas_match.group(1).strip()
            # Extract bust from measurements if not already set
            if not bust_size:
                bust_from_meas = re.match(r'(\d+\s*[A-Z]+)', measurements, re.IGNORECASE)
                if bust_from_meas:
                    bust_size = bust_from_meas.group(1).replace(' ', '').upper()

    return bust_size, bust_type, measurements


def extract_service_type(text: str) -> Optional[str]:
    """
    Extract service type(s) from text.

    Returns comma-separated list of services found.
    Excludes MASSAGE as per original logic.
    
    Handles formats like:
    - "Service Details: GFE"
    - "Service Details:GFE & PSE" (no space after colon, with & separator)
    - "GF ENTERTAINER"
    """
    found_services = []

    service_patterns = {
        r'GFE': 'GFE',
        r'GF\s+ENTERTAINER': 'GFE',
        r'PSE': 'PSE',
        r'FETISH\s+FRIENDLY': 'FETISH FRIENDLY',
        r'DOMINATRIX': 'DOMINATRIX',
    }

    for pattern, service_name in service_patterns.items():
        # Use flexible word boundaries that allow for &, comma, and other separators
        # This handles cases like "Service Details:GFE & PSE"
        flexible_pattern = r'(?:^|[^\w])' + pattern + r'(?:[^\w]|$)'
        if re.search(flexible_pattern, text, re.IGNORECASE):
            if service_name not in found_services:
                found_services.append(service_name)

    return ', '.join(found_services) if found_services else None


def extract_images(soup: BeautifulSoup, class_name: str = 'p_gallery_img') -> List[str]:
    """
    Extract image filenames from BeautifulSoup.

    Args:
        soup: BeautifulSoup object
        class_name: CSS class of image elements

    Returns:
        List of image filenames
    """
    images = []
    for img in soup.find_all('img', class_=class_name):
        src = img.get('src', '')
        if src:
            # Extract just the filename
            if src.startswith('http'):
                filename = src.split('/')[-1]
            else:
                filename = src
            images.append(filename)
    return images


def extract_tags(text: str, keywords: List[str] = None) -> List[str]:
    """
    Extract tags from text based on keywords.

    Args:
        text: Text to search
        keywords: List of keywords to look for

    Returns:
        List of found tags
    """
    if keywords is None:
        keywords = ['NEW', 'BLONDE', 'BRUNETTE', 'BUSTY', 'PETITE', 'ASIAN', 'EUROPEAN', 'LATINA']

    tags = []
    text_lower = text.lower()
    for keyword in keywords:
        if keyword.lower() in text_lower:
            tags.append(keyword)
    return tags
