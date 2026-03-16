# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project: CV–Job Matcher

A web app that matches a user's CV against real job listings fetched from Indeed and LinkedIn via Apify, then ranks them by semantic similarity using sentence-transformers.

## Running the Project

```bash
cd cv-job-matcher/backend
.venv/bin/uvicorn app:app --port 8000
# then open http://localhost:8000
```

The frontend is served by the backend — no separate server needed.

## Architecture

```
cv-job-matcher/
  backend/
    app.py          # FastAPI: /api/parse-cv, /api/jobs, /api/match, /api/cache/status
    cv_parser.py    # PDF/DOCX/text → plain text (pdfplumber, python-docx)
    cv_profiler.py  # CV auto-extraction via Claude Haiku (job title + skills)
    job_sources.py  # Apify actors: misceres/indeed-scraper, curious_coder/linkedin-jobs-scraper
    job_cache.py    # Per-source disk cache (7-day TTL, keyed by keyword+location+source)
    matcher.py      # sentence-transformers cosine similarity, top-20 ranking per source
    requirements.txt
  frontend/
    index.html      # Single-page form: CV upload/paste, job title, location
    style.css
    app.js          # Vanilla JS: calls backend, renders dual-source results
  .env              # ANTHROPIC_API_KEY, APIFY_API_TOKEN (never commit)
  .env.example
```

## Key behaviours

- **CV parsing**: accepts PDF, DOCX, or pasted text; normalised to plain text.
- **CV auto-extraction**: when no job title is provided, Claude Haiku extracts a job title and key skills from the CV text. The extracted title is used as the search keyword; skills are appended to the CV before cosine scoring for richer semantic matching. Gracefully degrades if `ANTHROPIC_API_KEY` is absent or the call fails.
- **Job search**: fetches Indeed and LinkedIn concurrently via `asyncio.gather()`. Indeed uses `misceres/indeed-scraper`; LinkedIn uses `curious_coder/linkedin-jobs-scraper` via a direct LinkedIn search URL.
- **Country detection**: the Indeed actor requires an ISO country code. The country is auto-detected from the location string (e.g. "Paris" → `FR`, "London" → `GB`), with `APIFY_COUNTRY` as the fallback default.
- **Caching**: results are cached per source on disk (7-day TTL). Cache key = `md5(keyword|location|source)`. A cache-bar is shown in the UI when serving stale data, with a "Refresh" button.
- **Matching**: `sentence-transformers` `all-MiniLM-L6-v2`, cosine similarity between CV embedding and each job's `title + description`. Scored independently per source; top 20 returned per source.
- **Results**: displayed in two separate sections (Indeed / LinkedIn), each showing up to 20 ranked results with match score, company, location, and description snippet.
- **Static files**: frontend served via FastAPI `StaticFiles` mount at `/`.

## Secrets

- `ANTHROPIC_API_KEY` — used for CV profile extraction. If unset, auto-extraction is silently disabled.
- `APIFY_API_TOKEN` — required for job fetching.
- Both live in `cv-job-matcher/.env` — never expose to frontend or commit.

## Git & GitHub

- Remote: `https://github.com/magninkone/ClaudeCodeTests`
- Always commit with descriptive messages and push after each meaningful change.
