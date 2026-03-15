# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project: CV–Job Matcher

A web app that matches a user's CV against real job listings fetched from JSearch (RapidAPI) and ranks them by semantic similarity using sentence-transformers.

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
    app.py          # FastAPI: /api/parse-cv, /api/jobs, /api/match
    cv_parser.py    # PDF/DOCX/text → plain text (pdfplumber, python-docx)
    job_sources.py  # JSearch API client (RapidAPI)
    matcher.py      # sentence-transformers cosine similarity, top-20 ranking
    requirements.txt
  frontend/
    index.html      # Single-page form: CV upload/paste, job title, location
    style.css
    app.js          # Vanilla JS: calls backend, renders results
  .env              # RAPIDAPI_KEY, RAPIDAPI_HOST (never commit)
  .env.example
```

## Key behaviours

- **CV parsing**: accepts PDF, DOCX, or pasted text; normalised to lowercase plain text.
- **Job search**: builds JSearch query as `"{job_title} {location}"`. JSearch covers US/UK English-language boards (LinkedIn, Indeed, Glassdoor); it has no coverage for non-English markets (e.g. France).
- **Fallback**: if 0 results are returned for the full query, `/api/match` retries with job title only.
- **Matching**: sentence-transformers `all-MiniLM-L6-v2`, cosine similarity between CV embedding and `title + description` of each job. Only jobs with a non-empty description are scored; page 3+ from JSearch often returns null descriptions.
- **Static files**: frontend served via FastAPI `StaticFiles` mount at `/`.

## Secrets

- `RAPIDAPI_KEY` and `RAPIDAPI_HOST` live in `cv-job-matcher/.env` — never expose to frontend or commit.

## Git & GitHub

- Remote: `https://github.com/magninkone/ClaudeCodeTests`
- Always commit with descriptive messages and push after each meaningful change.
