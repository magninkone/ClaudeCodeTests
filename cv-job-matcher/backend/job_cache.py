"""
Job listing cache — persists fetched jobs to disk for 7 days.

Jobs are cached per (keyword, location, source) tuple so the same search
reuses results across all CV matches that week, minimising API calls.

Free tier budget: Apify gives $5/month.
Pricing: Indeed $0.005/result, LinkedIn $0.001/result.
At 25 Indeed + 50 LinkedIn per search: $0.175/search → ~28 unique searches/month free.
"""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from job_sources import Job

CACHE_DIR = Path(__file__).parent.parent / "cache"
CACHE_TTL = timedelta(days=7)
FREE_TIER_BUDGET_USD = 5.00

COST_PER_RESULT = {
    "indeed": 0.005,
    "linkedin": 0.001,
}


def _cache_key(keyword: str, location: str, source: str) -> str:
    raw = f"{keyword.lower().strip()}|{location.lower().strip()}|{source.lower().strip()}"
    return hashlib.md5(raw.encode()).hexdigest()


def _cache_path(keyword: str, location: str, source: str) -> Path:
    return CACHE_DIR / f"{_cache_key(keyword, location, source)}.json"


def get_cached_jobs(keyword: str, location: str, source: str, force: bool = False) -> Optional[list[Job]]:
    """Return cached jobs if present and not expired, else None.
    If force=True, ignore the cache and return None to trigger a fresh fetch."""
    if force:
        return None
    path = _cache_path(keyword, location, source)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        fetched_at = datetime.fromisoformat(data["fetched_at"])
        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=timezone.utc)
        if datetime.now(tz=timezone.utc) - fetched_at > CACHE_TTL:
            return None
        cached_source = data.get("source", source)
        return [
            Job(
                title=j["title"],
                company=j["company"],
                description=j["description"],
                url=j["url"],
                location=j["location"],
                source=j.get("source", cached_source),
                raw={},
            )
            for j in data["jobs"]
        ]
    except Exception:
        return None


def save_to_cache(keyword: str, location: str, source: str, jobs: list[Job]) -> None:
    """Persist jobs to disk cache."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(keyword, location, source)
    payload = {
        "keyword": keyword,
        "location": location,
        "source": source,
        "fetched_at": datetime.now(tz=timezone.utc).isoformat(),
        "jobs": [
            {
                "title": j.title,
                "company": j.company,
                "description": j.description,
                "url": j.url,
                "location": j.location,
                "source": j.source,
            }
            for j in jobs
        ],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def cache_info(keyword: str, location: str, source: str) -> dict[str, Any]:
    """Return cache status for a given query and source (for API responses)."""
    path = _cache_path(keyword, location, source)
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


def all_cache_entries() -> list[dict[str, Any]]:
    """Return metadata for every entry currently in the cache."""
    if not CACHE_DIR.exists():
        return []
    entries = []
    now = datetime.now(tz=timezone.utc)
    for path in sorted(CACHE_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            fetched_at = datetime.fromisoformat(data["fetched_at"])
            if fetched_at.tzinfo is None:
                fetched_at = fetched_at.replace(tzinfo=timezone.utc)
            age = now - fetched_at
            expired = age > CACHE_TTL
            job_count = len(data.get("jobs", []))
            source = data.get("source", "indeed")
            cost_per = COST_PER_RESULT.get(source.lower(), 0.005)
            entries.append({
                "keyword": data.get("keyword", ""),
                "location": data.get("location", ""),
                "source": source,
                "job_count": job_count,
                "fetched_at": fetched_at.isoformat(),
                "age_days": round(age.total_seconds() / 86400, 1),
                "expires_in_days": round((CACHE_TTL - age).total_seconds() / 86400, 1) if not expired else 0,
                "expired": expired,
                "estimated_cost_usd": round(job_count * cost_per, 3),
            })
        except Exception:
            continue
    return entries


def monthly_usage() -> dict[str, Any]:
    """Estimate API calls and cost for the current calendar month."""
    entries = all_cache_entries()
    now = datetime.now(tz=timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    this_month = [
        e for e in entries
        if datetime.fromisoformat(e["fetched_at"]) >= month_start
    ]
    total_results = sum(e["job_count"] for e in this_month)
    total_cost = round(sum(e["estimated_cost_usd"] for e in this_month), 3)
    remaining_budget = round(FREE_TIER_BUDGET_USD - total_cost, 3)

    return {
        "month": now.strftime("%Y-%m"),
        "api_calls_this_month": len(this_month),
        "results_fetched_this_month": total_results,
        "estimated_cost_usd": total_cost,
        "free_tier_budget_usd": FREE_TIER_BUDGET_USD,
        "remaining_budget_usd": max(0.0, remaining_budget),
        "within_free_tier": total_cost <= FREE_TIER_BUDGET_USD,
    }
