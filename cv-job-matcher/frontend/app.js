(function () {
  const form = document.getElementById('match-form');
  const cvFile = document.getElementById('cv-file');
  const cvText = document.getElementById('cv-text');
  const jobTitle = document.getElementById('job-title');
  const locationInput = document.getElementById('location');
  const submitBtn = document.getElementById('submit-btn');
  const loading = document.getElementById('loading');
  const errorEl = document.getElementById('error');
  const resultsSection = document.getElementById('results-section');
  const resultsList = document.getElementById('results-list');

  // Base URL for API: same origin when frontend is served by backend, or set for dev
  const API_BASE = window.location.origin;

  function showLoading(show) {
    loading.classList.toggle('hidden', !show);
    submitBtn.disabled = show;
  }

  function showError(message) {
    errorEl.textContent = message;
    errorEl.classList.remove('hidden');
  }

  function hideError() {
    errorEl.classList.add('hidden');
    errorEl.textContent = '';
  }

  function showResults(results) {
    resultsSection.classList.remove('hidden');
    resultsList.innerHTML = '';
    results.forEach(function (job) {
      const li = document.createElement('li');
      li.className = 'result-card';
      const score = job.match_score != null ? job.match_score + '% match' : '';
      let desc = (job.description || '').slice(0, 200);
      if (job.description && job.description.length > 200) desc += '…';
      li.innerHTML =
        '<p class="title">' + escapeHtml(job.title || 'Untitled') + '</p>' +
        '<p class="meta">' + escapeHtml(job.company || '') + (job.location ? ' · ' + escapeHtml(job.location) : '') + '</p>' +
        (score ? '<span class="score">' + escapeHtml(score) + '</span>' : '') +
        (desc ? '<p class="description">' + escapeHtml(desc) + '</p>' : '') +
        (job.url ? '<a href="' + escapeAttr(job.url) + '" target="_blank" rel="noopener">Apply / View job</a>' : '');
      resultsList.appendChild(li);
    });
  }

  function escapeHtml(s) {
    if (!s) return '';
    const div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML;
  }

  function escapeAttr(s) {
    if (!s) return '#';
    const div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML.replace(/"/g, '&quot;');
  }

  form.addEventListener('submit', async function (e) {
    e.preventDefault();
    hideError();
    resultsSection.classList.add('hidden');
    const location = locationInput.value.trim();
    if (!location) {
      showError('Please enter a location.');
      return;
    }

    let cvTextValue = cvText.value.trim();

    if (cvFile.files && cvFile.files.length > 0) {
      showLoading(true);
      try {
        const formData = new FormData();
        formData.append('file', cvFile.files[0]);
        const parseRes = await fetch(API_BASE + '/api/parse-cv', {
          method: 'POST',
          body: formData
        });
        if (!parseRes.ok) {
          const err = await parseRes.json().catch(() => ({ detail: parseRes.statusText }));
          throw new Error(err.detail || 'Failed to parse CV file');
        }
        const parsed = await parseRes.json();
        cvTextValue = parsed.text || '';
      } catch (err) {
        showLoading(false);
        showError(err.message || 'Failed to parse CV.');
        return;
      }
    }

    if (!cvTextValue) {
      showError('Please upload a CV file or paste your CV text.');
      if (!loading.classList.contains('hidden')) showLoading(false);
      return;
    }

    showLoading(true);
    try {
      const res = await fetch(API_BASE + '/api/match', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          cv_text: cvTextValue,
          location: location,
          job_title: jobTitle.value.trim() || null
        })
      });
      const data = await res.json().catch(function () { return {}; });
      if (!res.ok) {
        throw new Error(data.detail || res.statusText || 'Request failed');
      }
      if (data.warning) {
        showError(data.warning);
      }
      if ((data.results || []).length === 0 && !data.warning) {
        showError('No matching jobs found. Try a different location or job title.');
      }
      showResults(data.results || []);
    } catch (err) {
      showError(err.message || 'Something went wrong.');
    } finally {
      showLoading(false);
    }
  });
})();
