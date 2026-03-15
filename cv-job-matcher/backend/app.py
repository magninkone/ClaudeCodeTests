"""
CV–Job Matcher API: parse CV, fetch jobs via Apify, rank by semantic match.
Jobs are cached locally per source for 7 days to minimise Apify free-tier usage.
Free tier: $5/month → ~28 unique searches (25 Indeed + 50 LinkedIn = $0.175/search).
"""

import asyncio
import os
from typing import Any, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Load .env from project root (cv-job-matcher/) when running from backend/
load_dotenv()
_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(_root, ".env"))

from cv_parser import parse_cv
from job_cache import all_cache_entries, cache_info, get_cached_jobs, monthly_usage, save_to_cache
from job_sources import Job, fetch_indeed_jobs, fetch_linkedin_jobs
from matcher import score_jobs

_INDEED_MAX = int(os.getenv("APIFY_INDEED_MAX_RESULTS", "25"))
_LINKEDIN_MAX = int(os.getenv("APIFY_LINKEDIN_MAX_RESULTS", "50"))
_TOP_K = 20

app = FastAPI(title="CV–Job Matcher", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ParseTextRequest(BaseModel):
    text: str


class ParseTextResponse(BaseModel):
    text: str


class JobsRequest(BaseModel):
    location: str
    job_title: Optional[str] = None


class MatchRequest(BaseModel):
    cv_text: str
    location: str
    job_title: Optional[str] = None
    force_refresh: bool = False


def _job_to_dict(job: Job, score: Optional[float] = None) -> dict[str, Any]:
    d = {
        "title": job.title,
        "company": job.company,
        "description": job.description,
        "url": job.url,
        "location": job.location,
        "source": job.source,
    }
    if score is not None:
        d["match_score"] = round(score * 100, 1)
    return d


def _deduplicate(jobs: list[Job]) -> list[Job]:
    """Remove duplicate jobs by (title, company) — keep first occurrence."""
    seen: set[tuple[str, str]] = set()
    unique: list[Job] = []
    for job in jobs:
        key = (job.title.lower().strip(), job.company.lower().strip())
        if key not in seen:
            seen.add(key)
            unique.append(job)
    return unique


async def _fetch_source(
    fetch_fn,
    keyword: str,
    location: str,
    source_name: str,
    max_results: int,
    force: bool,
) -> tuple[list[Job], Optional[str]]:
    """
    Fetch jobs for one source. Returns (jobs, error_message).
    Checks cache first; on miss runs fetch_fn in a thread.
    """
    cached = get_cached_jobs(keyword, location, source_name, force=force)
    if cached is not None:
        return cached, None

    try:
        jobs = await asyncio.to_thread(fetch_fn, keyword, location, max_results=max_results)
    except ValueError as e:
        return [], str(e)
    except Exception as e:
        return [], f"{source_name} fetch failed: {e}"

    if jobs:
        save_to_cache(keyword, location, source_name, jobs)
    return jobs, None


async def _get_jobs(
    keyword: str, location: str, force: bool = False
) -> tuple[list[Job], dict[str, Any], list[str]]:
    """
    Fetch Indeed and LinkedIn concurrently.
    Returns (deduplicated_jobs, cache_info_dict, warnings).
    """
    indeed_task = _fetch_source(
        fetch_indeed_jobs, keyword, location, "indeed", _INDEED_MAX, force
    )
    linkedin_task = _fetch_source(
        fetch_linkedin_jobs, keyword, location, "linkedin", _LINKEDIN_MAX, force
    )

    (indeed_jobs, indeed_err), (linkedin_jobs, linkedin_err) = await asyncio.gather(
        indeed_task, linkedin_task
    )

    warnings: list[str] = []
    if indeed_err:
        warnings.append(f"Indeed: {indeed_err}")
    if linkedin_err:
        warnings.append(f"LinkedIn: {linkedin_err}")

    all_jobs = _deduplicate(indeed_jobs + linkedin_jobs)

    info = {
        "indeed": cache_info(keyword, location, "indeed"),
        "linkedin": cache_info(keyword, location, "linkedin"),
        # combined "cached" = both sources came from cache
        "cached": (
            cache_info(keyword, location, "indeed").get("cached", False)
            and cache_info(keyword, location, "linkedin").get("cached", False)
        ),
        "age_days": max(
            cache_info(keyword, location, "indeed").get("age_days", 0),
            cache_info(keyword, location, "linkedin").get("age_days", 0),
        ),
        "expires_in_days": min(
            cache_info(keyword, location, "indeed").get("expires_in_days", 0),
            cache_info(keyword, location, "linkedin").get("expires_in_days", 0),
        ),
    }

    return all_jobs, info, warnings


@app.post("/api/parse-cv", response_model=ParseTextResponse)
async def api_parse_cv(
    file: Optional[UploadFile] = File(None),
    text: Optional[str] = Form(None),
):
    """Extract and normalize CV text from uploaded file or pasted text."""
    if file and file.filename:
        contents = await file.read()
        try:
            out = parse_cv(contents, file.filename)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to parse file: {e}")
        return ParseTextResponse(text=out)
    if text is not None:
        return ParseTextResponse(text=parse_cv(text))
    raise HTTPException(status_code=400, detail="Provide either a file upload or 'text' in form body.")


@app.post("/api/parse-cv/json", response_model=ParseTextResponse)
async def api_parse_cv_json(body: ParseTextRequest):
    """Parse CV from JSON body with 'text' field."""
    return ParseTextResponse(text=parse_cv(body.text))


@app.post("/api/jobs")
async def api_jobs(req: JobsRequest):
    """Fetch (or return cached) jobs for the given keyword and location."""
    keyword = req.job_title or ""
    jobs, info, warnings = await _get_jobs(keyword, req.location)
    response: dict[str, Any] = {
        "jobs": [_job_to_dict(j) for j in jobs],
        "cache_info": info,
    }
    if not jobs:
        response["warning"] = f"No job listings found for '{keyword} {req.location}'.".strip()
    elif warnings:
        response["warning"] = " | ".join(warnings)
    return response


@app.post("/api/match")
async def api_match(req: MatchRequest):
    """Fetch (or return cached) jobs, rank by CV match, return top results."""
    keyword = req.job_title or ""
    jobs, info, warnings = await _get_jobs(keyword, req.location, force=req.force_refresh)

    if not jobs:
        return {
            "results": [],
            "warning": (
                f"No job listings found for '{keyword} {req.location}'.".strip()
                + " Try a different location or job title."
            ),
        }

    if not req.cv_text.strip():
        return {
            "results": [_job_to_dict(j, 0.0) for j in jobs],
            "cache_info": info,
        }

    jobs_with_desc = [j for j in jobs if j.description.strip()]
    jobs_without_desc = [j for j in jobs if not j.description.strip()]

    scored = score_jobs(req.cv_text, jobs_with_desc, top_k=_TOP_K)
    if len(scored) < _TOP_K:
        scored += [(j, 0.0) for j in jobs_without_desc[: _TOP_K - len(scored)]]

    response: dict[str, Any] = {
        "results": [_job_to_dict(j, s) for j, s in scored],
        "cache_info": info,
    }
    if warnings:
        response["warning"] = " | ".join(warnings)
    return response


@app.get("/api/cache/status")
async def api_cache_status():
    """Show all cached searches, their age, and monthly Apify usage/cost."""
    return {
        "entries": all_cache_entries(),
        "monthly_usage": monthly_usage(),
    }


_frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
if os.path.isdir(_frontend_dir):
    app.mount("/", StaticFiles(directory=_frontend_dir, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
