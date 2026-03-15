"""
CV–Job Matcher API: parse CV, fetch jobs via Apify, rank by semantic match.
Jobs are cached locally for 7 days to minimise API usage.
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
from job_cache import cache_info, get_cached_jobs, save_to_cache
from job_sources import Job, fetch_jobs
from matcher import score_jobs

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


def _get_jobs(keyword: str, location: str, max_results: int = 20) -> tuple[list[Job], bool]:
    """
    Return (jobs, from_cache). Checks cache first; fetches and caches on miss.
    Falls back to keyword-only search if location yields no results.
    """
    jobs = get_cached_jobs(keyword, location)
    if jobs is not None:
        return jobs, True

    try:
        jobs = fetch_jobs(keyword, location, max_results=max_results)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Job fetch failed: {e}")

    # Fallback: retry with keyword only if location yields nothing
    if not jobs and location and keyword:
        try:
            jobs = fetch_jobs(keyword, "", max_results=max_results)
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
    info = cache_info(keyword, req.location)
    return {
        "jobs": [_job_to_dict(j) for j in jobs],
        "from_cache": from_cache,
        "cache_info": info,
    }


@app.post("/api/match")
async def api_match(req: MatchRequest):
    """Fetch (or return cached) jobs, rank by CV match, return top 20."""
    keyword = req.job_title or ""
    jobs, from_cache = _get_jobs(keyword, req.location)

    if not jobs:
        return {
            "results": [],
            "warning": (
                f"No job listings found for '{keyword} {req.location}'.".strip()
                + " The Apify actor may have no coverage for this location, or the keyword returned no results."
            ),
        }

    if not req.cv_text.strip():
        return {
            "results": [_job_to_dict(j, 0.0) for j in jobs[:20]],
            "from_cache": from_cache,
        }

    jobs_with_desc = [j for j in jobs if j.description.strip()]
    jobs_without_desc = [j for j in jobs if not j.description.strip()]

    scored = score_jobs(req.cv_text, jobs_with_desc, top_k=20)
    if len(scored) < 20:
        scored += [(j, 0.0) for j in jobs_without_desc[: 20 - len(scored)]]

    info = cache_info(keyword, req.location)
    return {
        "results": [_job_to_dict(j, s) for j, s in scored],
        "from_cache": from_cache,
        "cache_info": info,
    }


_frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
if os.path.isdir(_frontend_dir):
    app.mount("/", StaticFiles(directory=_frontend_dir, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
