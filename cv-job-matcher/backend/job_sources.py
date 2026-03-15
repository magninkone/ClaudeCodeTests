"""Apify-based job fetcher using LinkedIn Jobs Scraper."""

import os
from dataclasses import dataclass
from typing import Any

from apify_client import ApifyClient


@dataclass
class Job:
    """Normalized job listing for matching and display."""

    title: str
    company: str
    description: str
    url: str
    location: str
    raw: dict[str, Any]


def _get_client() -> tuple[ApifyClient, str]:
    token = os.getenv("APIFY_API_TOKEN", "").strip()
    actor_id = os.getenv("APIFY_ACTOR_ID", "bebity/linkedin-jobs-scraper").strip()
    if not token:
        raise ValueError("APIFY_API_TOKEN is not set in environment")
    return ApifyClient(token), actor_id


def _map_item(item: dict[str, Any]) -> Job:
    """Map Apify actor output item to Job model, handling multiple field name conventions."""
    title = (
        item.get("title") or item.get("job_title") or item.get("jobTitle")
        or item.get("position") or ""
    )
    company = (
        item.get("company") or item.get("company_name") or item.get("companyName")
        or item.get("employer") or item.get("employer_name") or ""
    )
    description = (
        item.get("description") or item.get("job_description") or item.get("jobDescription")
        or item.get("descriptionText") or item.get("summary") or ""
    )
    url = (
        item.get("url") or item.get("link") or item.get("URL")
        or item.get("jobUrl") or item.get("applyUrl") or item.get("apply_link") or ""
    )
    location = (
        item.get("location") or item.get("job_location") or item.get("jobLocation")
        or item.get("place") or item.get("city") or ""
    )
    return Job(
        title=str(title).strip(),
        company=str(company).strip(),
        description=str(description).strip(),
        url=str(url).strip(),
        location=str(location).strip(),
        raw=item,
    )


def fetch_jobs(
    keyword: str,
    location: str,
    *,
    max_results: int = 20,
) -> list[Job]:
    """
    Fetch job listings via Apify actor.

    keyword: job title or search terms (e.g. "Python Developer").
    location: location string (e.g. "London", "Remote"). Pass "" for global/remote.
    max_results: maximum number of results to return.

    Default actor: bebity/linkedin-jobs-scraper
    Override via APIFY_ACTOR_ID env var.

    Expected actor input: { "keyword": str, "location": str, "pages": int }
    Expected actor output items with fields: title, company, url, location,
    description (field names vary by actor — _map_item handles common conventions).
    """
    client, actor_id = _get_client()

    run_input: dict[str, Any] = {
        "keyword": keyword,
        "location": location,
        "pages": max(1, max_results // 10),
    }

    run = client.actor(actor_id).call(run_input=run_input)
    items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
    jobs = [_map_item(item) for item in items if isinstance(item, dict)]
    return jobs[:max_results]
