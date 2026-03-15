# CV–Job Matcher

Finds the top 20 jobs that best match your CV using the **JSearch** API (RapidAPI) and **sentence-transformers** for semantic matching.

## Prerequisites

- Python 3.9+
- A [RapidAPI](https://rapidapi.com) account and subscription to **JSearch** (free tier: 200 requests/month)

## Setup

1. **Create `.env` from the example** (do not commit `.env`):

   ```bash
   cd cv-job-matcher
   cp .env.example .env
   ```

2. **Edit `.env`** and set your RapidAPI key and host:

   ```
   RAPIDAPI_KEY=your_actual_key_here
   RAPIDAPI_HOST=jsearch.p.rapidapi.com
   ```

   Get your key and the correct host from the [JSearch API page on RapidAPI](https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch). If the host is different in your dashboard, use that value for `RAPIDAPI_HOST`.

3. **Install backend dependencies**:

   ```bash
   cd backend
   python -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

   The first run will download the sentence-transformers model (~90MB); this is one-time.

## Run

1. **Start the API server** (from the `backend` directory with your venv active):

   ```bash
   uvicorn app:app --reload --host 0.0.0.0 --port 8000
   ```

2. **Open the app** in your browser:

   - **Option A**: Go to [http://localhost:8000](http://localhost:8000). The server serves the frontend at the root.
   - **Option B**: Open `frontend/index.html` directly in the browser (file://). Then set the API base in the frontend or run the backend so it’s on the same origin (e.g. use a simple static server that proxies to the API, or just use Option A).

   Recommended: use **Option A** so the frontend and API are on the same origin and CORS is unnecessary.

## Usage

1. **CV**: Upload a PDF/DOCX file or paste your CV text.
2. **Job title** (optional): e.g. “Software Engineer”, “Data Scientist”.
3. **Location**: e.g. “London”, “Remote”, “New York”.
4. Click **Find my best jobs**. The app fetches jobs from JSearch, ranks them by similarity to your CV, and shows the top 20 with match scores and apply links.

## Project layout

- `backend/` — FastAPI app, CV parsing, JSearch client, sentence-transformers matcher
- `frontend/` — Single-page HTML/CSS/JS form and results list
- `.env.example` — Template for environment variables (copy to `.env` and fill in)
- `.gitignore` — Excludes `.env`, `venv`, etc.

## API endpoints

- `POST /api/parse-cv` — Parse CV from uploaded file or form `text`; returns normalized text.
- `POST /api/jobs` — Fetch jobs from JSearch (body: `location`, optional `job_title`).
- `POST /api/match` — Fetch jobs, rank by CV match, return top 20 (body: `cv_text`, `location`, optional `job_title`).
