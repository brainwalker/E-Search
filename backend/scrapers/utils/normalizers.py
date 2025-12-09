"""
Data normalization utilities for scrapers.

These functions standardize scraped data into consistent formats.
"""

import re
from typing import Optional


def normalize_name(name: str) -> str:
    """
    Normalize name from ALL CAPS to Title Case.

    Examples:
        AHRI -> Ahri
        LETICIA EVA -> Leticia Eva
        DAISY DUKES -> Daisy Dukes
    """
    if not name:
        return name
    return name.strip().title()


def normalize_tier(tier: str) -> Optional[str]:
    """
    Normalize tier to consistent format.

    Examples:
        ELITE -> Elite
        VIP -> VIP
        ULTRA VIP -> Ultra VIP
        PLATINUM VIP -> Platinum VIP
    """
    if not tier:
        return None

    tier = tier.strip().upper()
    tier_map = {
        'ELITE': 'Elite',
        'VIP': 'VIP',
        'ULTRA VIP': 'Ultra VIP',
        'PLATINUM VIP': 'Platinum VIP',
    }
    return tier_map.get(tier, tier.title())


def normalize_weight(weight_text: str) -> Optional[str]:
    """
    Convert weight to kg format.

    Examples:
        130 lbs -> 59 kg
        130lbs -> 59 kg
        55 kg -> 55 kg
    """
    if not weight_text:
        return None

    weight_text = weight_text.strip()

    # Already in kg
    if 'kg' in weight_text.lower():
        match = re.search(r'(\d+)\s*kg', weight_text, re.IGNORECASE)
        if match:
            return f"{match.group(1)} kg"
        return weight_text

    # Convert from lbs
    lbs_match = re.search(r'(\d+)\s*(?:lbs?|pounds?)?', weight_text, re.IGNORECASE)
    if lbs_match:
        lbs = int(lbs_match.group(1))
        kg = round(lbs * 0.453592)
        return f"{kg} kg"

    return weight_text


def normalize_height(height_text: str) -> Optional[str]:
    """
    Normalize height to standard format.

    Examples:
        5'9 -> 5'9
        5'9" -> 5'9
        5,4 -> 5'4
        5"7 -> 5'7
        170 cm -> 170 cm
    """
    if not height_text:
        return None

    height_text = height_text.strip()

    # Handle cm format
    cm_match = re.search(r'(\d{2,3})\s*cm', height_text, re.IGNORECASE)
    if cm_match:
        return f"{cm_match.group(1)} cm"

    # Handle feet/inches format - normalize various separators
    # Match patterns like 5'9, 5"7, 5,4, 5'9"
    ft_in_match = re.search(
        r"(\d+)[\u2019\u2018\u0027\u2032\u0060\u00b4\u2033\"',]+(\d+)",
        height_text
    )
    if ft_in_match:
        feet = ft_in_match.group(1)
        inches = ft_in_match.group(2)
        return f"{feet}'{inches}"

    return height_text


def normalize_measurements(measurements_text: str) -> Optional[str]:
    """
    Normalize measurements to standard format: 34DD-26-36

    Examples:
        34DD/25/34 -> 34DD-25-34
        34DD- 26-36 -> 34DD-26-36
        34C2636 -> 34C-26-36
        32D-23- 35 -> 32D-23-35
    """
    if not measurements_text:
        return None

    measurements = measurements_text.strip()

    # Replace slashes with dashes
    measurements = measurements.replace('/', '-')

    # Remove spaces around dashes
    measurements = re.sub(r'\s*-\s*', '-', measurements)

    # Remove space between bust number and cup
    measurements = re.sub(r'^(\d+)\s+([A-Z]+)', r'\1\2', measurements, flags=re.IGNORECASE)

    # Try to parse as bust-waist-hip format
    match = re.match(r'^(\d+)([A-Z]+)-(\d+)-(\d+)$', measurements, re.IGNORECASE)
    if match:
        bust_num = match.group(1)
        bust_cup = match.group(2).upper()
        waist = match.group(3)
        hip = match.group(4)
        return f"{bust_num}{bust_cup}-{waist}-{hip}"

    # Handle compact format: 34C2636 -> 34C-26-36
    compact_match = re.match(r'^(\d{2})([A-Z]+)[-\s]?(\d{2})(\d{2})$', measurements, re.IGNORECASE)
    if compact_match:
        bust_num = compact_match.group(1)
        bust_cup = compact_match.group(2).upper()
        waist = compact_match.group(3)
        hip = compact_match.group(4)
        return f"{bust_num}{bust_cup}-{waist}-{hip}"

    return measurements


def normalize_bust_size(bust_text: str) -> Optional[str]:
    """
    Normalize bust size to standard format: 34 DD

    Examples:
        34DD -> 34 DD
        32B -> 32 B
        34 DD -> 34 DD
    """
    if not bust_text:
        return None

    bust = bust_text.strip().upper()

    # Already has space
    if re.match(r'^\d+\s+[A-Z]+$', bust):
        return bust

    # Add space between number and letters
    match = re.match(r'^(\d+)([A-Z]+)$', bust)
    if match:
        return f"{match.group(1)} {match.group(2)}"

    return bust


def normalize_service_type(service_text: str) -> Optional[str]:
    """
    Normalize service type to standard format.

    Examples:
        GF ENTERTAINER -> GFE
        Gfe -> GFE
        gfe -> GFE
    """
    if not service_text:
        return None

    service = service_text.strip().upper()
    service = re.sub(r'\s+', ' ', service)

    if service == 'GF ENTERTAINER':
        return 'GFE'

    return service


def normalize_color(color_text: str) -> Optional[str]:
    """
    Normalize color strings (hair, eyes).

    Examples:
        BROWN -> Brown
        dark brown -> Dark Brown
        Blue/ Green -> Blue/Green
    """
    if not color_text:
        return None

    color = color_text.strip()

    # Normalize spacing around /
    color = re.sub(r'\s*/\s*', '/', color)

    # Title case
    return color.title()
