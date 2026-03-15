"""JSearch API client for fetching job listings via RapidAPI."""

import os
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass
class Job:
    """Normalized job listing for matching and display."""

    title: str
    company: str
    description: str
    url: str
    location: str
    raw: dict[str, Any]  # original fields for optional display


def _get_config() -> tuple[str, str]:
    key = os.getenv("RAPIDAPI_KEY", "").strip()
    host = os.getenv("RAPIDAPI_HOST", "jsearch.p.rapidapi.com").strip()
    return key, host


def _jsearch_to_job(item: dict[str, Any]) -> Job:
    """Map JSearch API response item to our Job model."""
    return Job(
        title=item.get("job_title") or item.get("title") or "",
        company=item.get("employer_name") or item.get("company") or "",
        description=item.get("job_description") or item.get("description") or "",
        url=item.get("job_apply_link") or item.get("job_link") or item.get("apply_link") or "",
        location=_format_location(item),
        raw=item,
    )


def _format_location(item: dict[str, Any]) -> str:
    """Build location string from common JSearch fields."""
    parts = []
    if item.get("job_city"):
        parts.append(str(item["job_city"]))
    if item.get("job_state"):
        parts.append(str(item["job_state"]))
    if item.get("job_country"):
        parts.append(str(item["job_country"]))
    if item.get("job_is_remote") is True:
        parts.append("Remote")
    return ", ".join(parts) if parts else item.get("job_location") or ""


def fetch_jobs(
    query: str,
    *,
    num_pages: int = 3,
    page: int = 1,
) -> list[Job]:
    """
    Fetch job listings from JSearch API (RapidAPI).
    query: search string, e.g. "Software Engineer London" or "Remote".
    num_pages: how many pages to request (each page ~10 results).
    """
    key, host = _get_config()
    if not key:
        raise ValueError("RAPIDAPI_KEY is not set in environment")

    base_url = f"https://{host}"
    # JSearch on RapidAPI typically uses /search with query params
    endpoint = "/search"
    headers = {
        "X-RapidAPI-Key": key,
        "X-RapidAPI-Host": host,
    }
    all_jobs: list[Job] = []

    with httpx.Client(timeout=30.0) as client:
        for p in range(num_pages):
            params = {
                "query": query,
                "page": str(page + p),
                "num_pages": "1",
            }
            try:
                resp = client.get(f"{base_url}{endpoint}", headers=headers, params=params)
                resp.raise_for_status()
                data = resp.json()
            except (httpx.HTTPError, Exception) as e:
                if p == 0:
                    raise RuntimeError(f"JSearch API request failed: {e}") from e
                break

            # JSearch returns { "data": [ ... ] } or direct list
            items = data.get("data") if isinstance(data, dict) else data
            if not isinstance(items, list):
                break
            for item in items:
                if isinstance(item, dict):
                    all_jobs.append(_jsearch_to_job(item))
            if len(items) < 10:
                break

    return all_jobs
