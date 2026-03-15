"""
CV–Job Matcher API: parse CV, fetch jobs via JSearch, rank by semantic match.
"""

import os
from typing import Any, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Load .env from project root (cv-job-matcher/) when running from backend/
load_dotenv()
_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(_root, ".env"))

from cv_parser import parse_cv
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
    """Fetch jobs from JSearch for the given location and optional job title."""
    query_parts = [req.job_title] if req.job_title else []
    query_parts.append(req.location)
    query = " ".join(p.strip() for p in query_parts if p and p.strip()) or req.location
    try:
        jobs = fetch_jobs(query, num_pages=3)
        return {"jobs": [_job_to_dict(j) for j in jobs]}
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Job search failed: {e}")


@app.post("/api/match")
async def api_match(req: MatchRequest):
    """Fetch jobs from JSearch, rank by CV match, return top 20."""
    query_parts = [req.job_title] if req.job_title else []
    query_parts.append(req.location)
    query = " ".join(p.strip() for p in query_parts if p and p.strip()) or req.location
    print(f"[match] query={query!r} cv_text_len={len(req.cv_text)}", flush=True)
    try:
        jobs = fetch_jobs(query, num_pages=2)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Job search failed: {e}")

    # Fallback: if no results with location, try job title only (covers markets with limited JSearch coverage)
    fallback_used = None
    if not jobs and req.job_title:
        fallback_used = req.job_title
        print(f"[match] no results for {query!r}, retrying with job title only: {fallback_used!r}", flush=True)
        try:
            jobs = fetch_jobs(fallback_used, num_pages=2)
        except Exception:
            pass

    if not jobs:
        return {
            "results": [],
            "warning": f"No job listings found for '{query}'. JSearch primarily covers US/UK/English-language boards and may have limited coverage for this location.",
        }

    print(f"[match] fetched {len(jobs)} jobs (fallback={fallback_used!r})", flush=True)
    # Only match against jobs that have a description; include description-less jobs after
    jobs_with_desc = [j for j in jobs if j.description.strip()]
    jobs_without_desc = [j for j in jobs if not j.description.strip()]

    if not req.cv_text.strip():
        return {"results": [_job_to_dict(j, 0.0) for j in jobs[:20]]}

    scored = score_jobs(req.cv_text, jobs_with_desc, top_k=20)
    # Append unscored jobs if top 20 not filled
    if len(scored) < 20:
        scored += [(j, 0.0) for j in jobs_without_desc[: 20 - len(scored)]]
    return {
        "results": [_job_to_dict(j, s) for j, s in scored],
    }



_frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
if os.path.isdir(_frontend_dir):
    app.mount("/", StaticFiles(directory=_frontend_dir, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
