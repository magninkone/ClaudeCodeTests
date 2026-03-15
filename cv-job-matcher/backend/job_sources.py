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
    country = os.getenv("APIFY_COUNTRY", "US").strip().upper()
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
