"""
Site configurations for all 14 escort listing sources.

Each site has a SiteConfig that defines:
- URLs for schedule and profile pages
- Scraper type (static, javascript, stealth)
- Rate limiting and other settings
"""

from .base import SiteConfig, ScraperType


# ============================================================
# KNOWN TOWNS (Greater Toronto Area)
# Used for location parsing and auto-creation
# ============================================================
KNOWN_TOWNS = {
    'Vaughan', 'Midtown', 'Downtown', 'Etobicoke', 'Oakville',
    'Mississauga', 'Brampton', 'North York', 'Scarborough',
    'Markham', 'Richmond Hill', 'Ajax', 'Pickering', 'Whitby',
    'Oshawa', 'Burlington', 'Hamilton', 'Milton', 'Newmarket',
    'Aurora', 'King City', 'Woodbridge', 'Thornhill', 'Concord',
}

# Case-insensitive lookup set
KNOWN_TOWNS_LOWER = {t.lower() for t in KNOWN_TOWNS}


# ============================================================
# SITE CONFIGURATIONS
# ============================================================

SITES = {
    # ========== STATIC (7 sites) ==========
    # These use BeautifulSoupCrawler - fast, no JS needed

    'sft': SiteConfig(
        name='SexyFriendsToronto',
        short_name='SFT',
        schedule_url='https://www.sexyfriendstoronto.com/toronto-escorts/schedule',
        base_url='https://www.sexyfriendstoronto.com/toronto-escorts/',
        image_base_url='https://www.sexyfriendstoronto.com/toronto-escorts/thumbnails/',
        scraper_type=ScraperType.STATIC,
        rate_limit_seconds=1.0,
        enabled=True,
    ),

    'secret': SiteConfig(
        name='SecretEscorts',
        short_name='SECRET',
        schedule_url='https://secretescorts.ca/availability/',
        base_url='https://secretescorts.ca/',
        scraper_type=ScraperType.STATIC,
        requires_age_gate=True,
        rate_limit_seconds=1.0,
        enabled=False,  # Not yet implemented
    ),

    'select': SiteConfig(
        name='SelectCompanyEscorts',
        short_name='SELECT',
        schedule_url='https://www.selectcompanyescorts.com/schedule/',
        base_url='https://www.selectcompanyescorts.com/',
        scraper_type=ScraperType.STATIC,
        rate_limit_seconds=1.0,
        enabled=False,
    ),

    'allegra': SiteConfig(
        name='AllegraEscortsCollective',
        short_name='ALLEGRA',
        schedule_url='https://allegraescortscollective.com/schedule-booking-rates/',
        base_url='https://allegraescortscollective.com/',
        scraper_type=ScraperType.STATIC,
        rate_limit_seconds=1.0,
        enabled=False,
    ),

    'highsociety': SiteConfig(
        name='HighSocietyGirls',
        short_name='HSG',
        schedule_url='https://highsocietygirls.ca/',
        base_url='https://highsocietygirls.ca/',
        scraper_type=ScraperType.STATIC,
        rate_limit_seconds=1.0,
        enabled=False,
    ),

    'garden': SiteConfig(
        name='GardenOfEdenEscorts',
        short_name='EDEN',
        schedule_url='https://gardenofedenescorts.com/schedule/',
        base_url='https://gardenofedenescorts.com/',
        scraper_type=ScraperType.STATIC,
        rate_limit_seconds=1.0,
        enabled=False,
    ),

    'cupids': SiteConfig(
        name='CupidsEscorts',
        short_name='CUPIDS',
        schedule_url='https://www.cupidsescorts.ca/schedule/',
        base_url='https://www.cupidsescorts.ca/',
        scraper_type=ScraperType.STATIC,
        rate_limit_seconds=1.0,
        enabled=False,
    ),

    # ========== JAVASCRIPT (4 sites) ==========
    # These use PlaywrightCrawler - need JS rendering

    'mirage': SiteConfig(
        name='MirageEntertainment',
        short_name='Mirage',
        schedule_url='https://mirage-entertainment.cc/toronto-escorts-schedule/',
        base_url='https://mirage-entertainment.cc/escort/',
        image_base_url='https://mirage-entertainment.cc/wp-content/uploads/',
        scraper_type=ScraperType.STATIC,  # Uses static HTML, no JS needed
        rate_limit_seconds=1.5,
        enabled=True,
    ),

    'topdrawer': SiteConfig(
        name='TopDrawerLadies',
        short_name='TDL',
        schedule_url='https://www.topdrawerladies.com/pages/schedule',
        base_url='https://www.topdrawerladies.com/',
        scraper_type=ScraperType.JAVASCRIPT,
        rate_limit_seconds=2.0,
        enabled=False,
    ),

    'hotpink': SiteConfig(
        name='HotPinkList',
        short_name='HPL',
        schedule_url='https://hotpinklist.com/schedule/',
        base_url='https://hotpinklist.com/',
        scraper_type=ScraperType.JAVASCRIPT,
        rate_limit_seconds=2.0,
        enabled=False,
    ),

    'passions': SiteConfig(
        name='TorontoPassions',
        short_name='PASSIONS',
        schedule_url='https://www.torontopassions.com/toronto-escorts-availability',
        base_url='https://www.torontopassions.com/',
        scraper_type=ScraperType.JAVASCRIPT,
        rate_limit_seconds=2.0,
        enabled=False,
    ),

    # ========== STEALTH (3 sites) ==========
    # These use Camoufox - need anti-bot bypass

    'discreet': SiteConfig(
        name='DiscreetDolls',
        short_name='DD',
        schedule_url='https://discreetdolls.com/daily-schedule/',
        base_url='https://discreetdolls.com/',
        image_base_url='https://discreetdolls.com/wp-content/uploads/',
        scraper_type=ScraperType.STEALTH,
        rate_limit_seconds=3.0,
        enabled=True,
    ),

    'hiddengem': SiteConfig(
        name='HiddenGemEscorts',
        short_name='HGE',
        schedule_url='https://hiddengemescorts.ca/toronto-escorts-schedule/',
        base_url='https://hiddengemescorts.ca/',
        scraper_type=ScraperType.STEALTH,
        rate_limit_seconds=3.0,
        enabled=False,
    ),

    'torontogf': SiteConfig(
        name='TorontoGirlfriends',
        short_name='TGF',
        schedule_url='https://torontogirlfriends.com/schedule/',
        base_url='https://torontogirlfriends.com/',
        scraper_type=ScraperType.STEALTH,
        rate_limit_seconds=3.0,
        enabled=False,
    ),
}


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_site_config(site_key: str) -> SiteConfig:
    """
    Get configuration for a site by its key.

    Args:
        site_key: Site identifier (e.g., 'sft', 'discreet')

    Returns:
        SiteConfig for the site

    Raises:
        ValueError: If site_key is not found
    """
    if site_key not in SITES:
        valid_keys = ', '.join(sorted(SITES.keys()))
        raise ValueError(f"Unknown site: '{site_key}'. Valid sites: {valid_keys}")
    return SITES[site_key]


def get_sites_by_type(scraper_type: ScraperType) -> dict:
    """Get all sites of a specific scraper type."""
    return {k: v for k, v in SITES.items() if v.scraper_type == scraper_type}


def get_enabled_sites() -> dict:
    """Get all enabled sites."""
    return {k: v for k, v in SITES.items() if v.enabled}


def get_all_sites() -> dict:
    """Get all sites regardless of enabled status."""
    return SITES.copy()


def list_sites() -> list:
    """List all site keys."""
    return list(SITES.keys())


def get_site_summary() -> list:
    """Get a summary of all sites for display."""
    summary = []
    for key, config in SITES.items():
        summary.append({
            'key': key,
            'name': config.name,
            'short_name': config.short_name,
            'type': config.scraper_type.value,
            'enabled': config.enabled,
            'url': config.schedule_url,
        })
    return summary
