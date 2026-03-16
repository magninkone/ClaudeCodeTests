"""
Apify-based job fetchers.

Sources:
  Indeed   — misceres/indeed-scraper         ($0.005/result, default 25 results)
  LinkedIn — curious_coder/linkedin-jobs-scraper ($0.001/result, default 50 results)

Actor IDs and result limits are configurable via environment variables.
"""

import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

from apify_client import ApifyClient


@dataclass
class Job:
    """Normalized job listing for matching and display."""

    title: str
    company: str
    description: str
    url: str
    location: str
    source: str   # "Indeed" or "LinkedIn"
    raw: dict[str, Any]


def _get_client() -> ApifyClient:
    token = os.getenv("APIFY_API_TOKEN", "").strip()
    if not token:
        raise ValueError("APIFY_API_TOKEN is not set in environment")
    return ApifyClient(token)


# Maps location keywords → ISO 3166-1 alpha-2 country codes for Indeed.
_LOCATION_COUNTRY_MAP: dict[str, str] = {
    # France
    "france": "FR", "paris": "FR", "lyon": "FR", "marseille": "FR",
    "toulouse": "FR", "nice": "FR", "bordeaux": "FR", "strasbourg": "FR",
    "nantes": "FR", "montpellier": "FR", "rennes": "FR", "lille": "FR",
    # United Kingdom
    "uk": "GB", "united kingdom": "GB", "britain": "GB", "england": "GB",
    "london": "GB", "manchester": "GB", "birmingham": "GB", "leeds": "GB",
    "glasgow": "GB", "edinburgh": "GB", "bristol": "GB", "liverpool": "GB",
    "sheffield": "GB", "cambridge": "GB", "oxford": "GB",
    # Germany
    "germany": "DE", "deutschland": "DE", "berlin": "DE", "munich": "DE",
    "münchen": "DE", "hamburg": "DE", "frankfurt": "DE", "cologne": "DE",
    "düsseldorf": "DE", "stuttgart": "DE", "dortmund": "DE",
    # United States
    "usa": "US", "united states": "US", "america": "US", "remote": "US",
    "new york": "US", "los angeles": "US", "chicago": "US", "houston": "US",
    "san francisco": "US", "seattle": "US", "boston": "US", "austin": "US",
    "denver": "US", "atlanta": "US", "miami": "US",
    # Canada
    "canada": "CA", "toronto": "CA", "vancouver": "CA", "montreal": "CA",
    "calgary": "CA", "ottawa": "CA",
    # Australia
    "australia": "AU", "sydney": "AU", "melbourne": "AU", "brisbane": "AU",
    "perth": "AU", "adelaide": "AU",
    # Netherlands
    "netherlands": "NL", "holland": "NL", "amsterdam": "NL", "rotterdam": "NL",
    "the hague": "NL", "utrecht": "NL",
    # Spain
    "spain": "ES", "madrid": "ES", "barcelona": "ES", "valencia": "ES",
    "seville": "ES", "bilbao": "ES",
    # Italy
    "italy": "IT", "rome": "IT", "milan": "IT", "milano": "IT",
    "turin": "IT", "naples": "IT",
    # Belgium
    "belgium": "BE", "brussels": "BE", "bruxelles": "BE", "antwerp": "BE",
    # Switzerland
    "switzerland": "CH", "zurich": "CH", "zürich": "CH", "geneva": "CH",
    # Poland
    "poland": "PL", "warsaw": "PL", "kraków": "PL", "krakow": "PL",
    # India
    "india": "IN", "bangalore": "IN", "bengaluru": "IN", "mumbai": "IN",
    "delhi": "IN", "hyderabad": "IN", "chennai": "IN", "pune": "IN",
    # Singapore
    "singapore": "SG",
    # Brazil
    "brazil": "BR", "são paulo": "BR", "sao paulo": "BR", "rio": "BR",
}


def _country_from_location(location: str, default: str) -> str:
    """Infer ISO country code from a free-text location string."""
    loc = location.lower().strip()
    for keyword, code in _LOCATION_COUNTRY_MAP.items():
        if keyword in loc:
            return code
    return default


# ---------------------------------------------------------------------------
# Indeed
# ---------------------------------------------------------------------------

def _map_indeed(item: dict[str, Any]) -> Job:
    return Job(
        title=str(item.get("positionName") or item.get("title") or "").strip(),
        company=str(item.get("company") or item.get("companyName") or "").strip(),
        description=str(item.get("description") or "").strip(),
        url=str(item.get("url") or item.get("externalApplyLink") or "").strip(),
        location=str(item.get("location") or "").strip(),
        source="Indeed",
        raw=item,
    )


def fetch_indeed_jobs(keyword: str, location: str, *, max_results: int = 25) -> list[Job]:
    """
    Fetch jobs from Indeed via misceres/indeed-scraper.
    Actor: https://apify.com/misceres/indeed-scraper
    Pricing: $0.005/result.
    """
    actor_id = os.getenv("APIFY_INDEED_ACTOR_ID", "misceres/indeed-scraper").strip()
    default_country = os.getenv("APIFY_COUNTRY", "US").strip().upper()
    country = _country_from_location(location, default_country)
    client = _get_client()

    run = client.actor(actor_id).call(
        run_input={
            "position": keyword,
            "location": location,
            "maxItems": max_results,
            "country": country,
        }
    )
    items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
    return [_map_indeed(i) for i in items if isinstance(i, dict)][:max_results]


# ---------------------------------------------------------------------------
# LinkedIn
# ---------------------------------------------------------------------------

def _map_linkedin(item: dict[str, Any]) -> Job:
    return Job(
        title=str(item.get("title") or item.get("positionName") or "").strip(),
        company=str(item.get("companyName") or item.get("company") or "").strip(),
        description=str(item.get("descriptionText") or item.get("description") or "").strip(),
        url=str(item.get("link") or item.get("applyUrl") or "").strip(),
        location=str(item.get("location") or "").strip(),
        source="LinkedIn",
        raw=item,
    )


def fetch_linkedin_jobs(keyword: str, location: str, *, max_results: int = 50) -> list[Job]:
    """
    Fetch jobs from LinkedIn via curious_coder/linkedin-jobs-scraper.
    Actor: https://apify.com/curious_coder/linkedin-jobs-scraper
    Pricing: $0.001/result.

    The actor does not respect maxResults — it scrapes until timeout.
    We cap the results by slicing the dataset after the run completes.
    Timeout is configurable via APIFY_LINKEDIN_TIMEOUT_SECS (default 90).
    """
    actor_id = os.getenv("APIFY_LINKEDIN_ACTOR_ID", "curious_coder/linkedin-jobs-scraper").strip()
    timeout_secs = int(os.getenv("APIFY_LINKEDIN_TIMEOUT_SECS", "90"))
    client = _get_client()

    search_url = (
        "https://www.linkedin.com/jobs/search/"
        f"?keywords={quote(keyword)}&location={quote(location)}"
    )

    run = client.actor(actor_id).call(
        run_input={"urls": [search_url]},
        timeout_secs=timeout_secs,
        memory_mbytes=1024,
    )
    items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
    return [_map_linkedin(i) for i in items if isinstance(i, dict)][:max_results]
