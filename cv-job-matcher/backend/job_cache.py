"""
Job listing cache — persists fetched jobs to disk for 7 days.

Jobs are cached per (keyword, location) pair so the same search
reuses results across all CV matches that week, minimising API calls.
"""

import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from job_sources import Job

CACHE_DIR = Path(__file__).parent.parent / "cache"
CACHE_TTL = timedelta(days=7)


def _cache_key(keyword: str, location: str) -> str:
    raw = f"{keyword.lower().strip()}|{location.lower().strip()}"
    return hashlib.md5(raw.encode()).hexdigest()


def _cache_path(keyword: str, location: str) -> Path:
    return CACHE_DIR / f"{_cache_key(keyword, location)}.json"


def get_cached_jobs(keyword: str, location: str) -> Optional[list[Job]]:
    """Return cached jobs if present and not expired, else None."""
    path = _cache_path(keyword, location)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        fetched_at = datetime.fromisoformat(data["fetched_at"])
        # Treat naive datetimes as UTC
        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=timezone.utc)
        if datetime.now(tz=timezone.utc) - fetched_at > CACHE_TTL:
            return None
        return [
            Job(
                title=j["title"],
                company=j["company"],
                description=j["description"],
                url=j["url"],
                location=j["location"],
                raw={},
            )
            for j in data["jobs"]
        ]
    except Exception:
        return None


def save_to_cache(keyword: str, location: str, jobs: list[Job]) -> None:
    """Persist jobs to disk cache."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(keyword, location)
    payload = {
        "keyword": keyword,
        "location": location,
        "fetched_at": datetime.now(tz=timezone.utc).isoformat(),
        "jobs": [
            {
                "title": j.title,
                "company": j.company,
                "description": j.description,
                "url": j.url,
                "location": j.location,
            }
            for j in jobs
        ],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def cache_info(keyword: str, location: str) -> dict:
    """Return cache status for a given query (for API responses)."""
    path = _cache_path(keyword, location)
    if not path.exists():
        return {"cached": False}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        fetched_at = datetime.fromisoformat(data["fetched_at"])
        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=timezone.utc)
        age = datetime.now(tz=timezone.utc) - fetched_at
        expired = age > CACHE_TTL
        return {
            "cached": not expired,
            "fetched_at": fetched_at.isoformat(),
            "age_days": round(age.total_seconds() / 86400, 1),
            "expires_in_days": round((CACHE_TTL - age).total_seconds() / 86400, 1) if not expired else 0,
        }
    except Exception:
        return {"cached": False}
