"""
CV–Job Matcher API: parse CV, fetch jobs via Apify, rank by semantic match.
Jobs are cached locally for 7 days to minimise Apify free-tier usage.
Free tier: $5/month → ~66 searches at 15 results each (misceres/indeed-scraper).
"""

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
from job_sources import Job, fetch_jobs
from matcher import score_jobs

# Max results per Apify call — keep low to conserve free-tier budget.
# $0.005/result × 15 = $0.075/search → ~66 free searches/month.
_MAX_RESULTS = int(os.getenv("APIFY_MAX_RESULTS", "15"))

app = FastAPI(title="CV–Job Matcher", version="1.0.0")

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
    }
    if score is not None:
        d["match_score"] = round(score * 100, 1)
    return d


def _get_jobs(keyword: str, location: str, force: bool = False) -> tuple[list[Job], bool]:
    """
    Return (jobs, from_cache). Checks cache first (unless force=True).
    On cache miss, fetches from Apify and saves result.
    Falls back to keyword-only search if location yields no results.
    """
    jobs = get_cached_jobs(keyword, location, force=force)
    if jobs is not None:
        return jobs, True

    try:
        jobs = fetch_jobs(keyword, location, max_results=_MAX_RESULTS)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Job fetch failed: {e}")

    # Fallback: retry with keyword only if location yields nothing
    if not jobs and location and keyword:
        try:
            jobs = fetch_jobs(keyword, "", max_results=_MAX_RESULTS)
        except Exception:
            jobs = []

    if jobs:
        save_to_cache(keyword, location, jobs)

    return jobs, False


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
    jobs, from_cache = _get_jobs(keyword, req.location)
    if not jobs:
        return {
            "jobs": [],
            "warning": f"No job listings found for '{keyword} {req.location}'.".strip(),
        }
    return {
        "jobs": [_job_to_dict(j) for j in jobs],
        "from_cache": from_cache,
        "cache_info": cache_info(keyword, req.location),
    }


@app.post("/api/match")
async def api_match(req: MatchRequest):
    """Fetch (or return cached) jobs, rank by CV match, return top results."""
    keyword = req.job_title or ""
    jobs, from_cache = _get_jobs(keyword, req.location, force=req.force_refresh)

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
            "from_cache": from_cache,
            "cache_info": cache_info(keyword, req.location),
        }

    jobs_with_desc = [j for j in jobs if j.description.strip()]
    jobs_without_desc = [j for j in jobs if not j.description.strip()]

    scored = score_jobs(req.cv_text, jobs_with_desc, top_k=_MAX_RESULTS)
    if len(scored) < _MAX_RESULTS:
        scored += [(j, 0.0) for j in jobs_without_desc[: _MAX_RESULTS - len(scored)]]

    return {
        "results": [_job_to_dict(j, s) for j, s in scored],
        "from_cache": from_cache,
        "cache_info": cache_info(keyword, req.location),
    }


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
