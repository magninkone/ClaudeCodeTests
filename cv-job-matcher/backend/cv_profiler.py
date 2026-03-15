"""
Extract a job search profile (job title + key skills) from CV text using Claude.

Used when the user submits a CV without providing a job title, so the app
can derive a meaningful Apify search query automatically.

Model: claude-haiku-4-5 (fast, cheap — extraction is a simple single-call task).
Falls back to empty strings silently if ANTHROPIC_API_KEY is missing or the
call fails, so the app degrades gracefully rather than blocking the search.
"""

import json
import os

import anthropic


def extract_profile(cv_text: str) -> dict[str, str]:
    """
    Return {"job_title": "...", "skills": "..."} derived from the CV text.
    Both values are empty strings on any error or missing API key.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        return {"job_title": "", "skills": ""}

    client = anthropic.Anthropic(api_key=api_key)

    prompt = (
        "Extract a job search profile from this CV text.\n"
        "Return JSON with exactly two fields:\n"
        '- "job_title": the most appropriate job title (2-4 words, '
        'e.g. "Senior Python Developer")\n'
        '- "skills": top 5-8 technical skills as a comma-separated string '
        '(e.g. "Python, FastAPI, AWS, Docker")\n\n'
        f"CV text:\n{cv_text[:3000]}\n\n"
        "Respond with JSON only, no explanation."
    )

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        # Strip markdown code fences if present (```json ... ```)
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        data = json.loads(text)
        return {
            "job_title": str(data.get("job_title", "")).strip(),
            "skills": str(data.get("skills", "")).strip(),
        }
    except Exception:
        return {"job_title": "", "skills": ""}
