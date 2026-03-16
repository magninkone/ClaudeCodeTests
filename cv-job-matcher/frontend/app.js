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
  const indeedSection = document.getElementById('results-indeed');
  const linkedinSection = document.getElementById('results-linkedin');
  const indeedList = document.getElementById('results-list-indeed');
  const linkedinList = document.getElementById('results-list-linkedin');
  const profileBar = document.getElementById('profile-bar');
  const profileMeta = document.getElementById('profile-meta');
  const cacheBar = document.getElementById('cache-bar');
  const cacheMeta = document.getElementById('cache-meta');
  const refreshBtn = document.getElementById('refresh-btn');

  const API_BASE = window.location.origin;

  // Store last request so refresh can repeat it with force_refresh=true
  let lastRequest = null;

  function showLoading(show) {
    loading.classList.toggle('hidden', !show);
    submitBtn.disabled = show;
  }

  function showError(message) {
    errorEl.textContent = message;
    errorEl.classList.remove('hidden');
    errorEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }

  function hideError() {
    errorEl.classList.add('hidden');
    errorEl.textContent = '';
  }

  function showProfileBar(data) {
    const p = data.extracted_profile;
    if (!p || (!p.job_title && !p.skills)) {
      profileBar.classList.add('hidden');
      return;
    }
    profileMeta.innerHTML =
      '<span class="profile-label">Auto-detected profile · Searching for:</span> ' +
      (p.job_title ? '<span class="profile-title">' + escapeHtml(p.job_title) + '</span>' : '') +
      (p.skills ? ' <span class="profile-skills">· ' + escapeHtml(p.skills) + '</span>' : '');
    profileBar.classList.remove('hidden');
  }

  function showCacheBar(data) {
    if (!data.cache_info || !data.cache_info.cached) {
      cacheBar.classList.add('hidden');
      return;
    }
    const info = data.cache_info;
    cacheMeta.textContent =
      'Cached data · fetched ' + info.age_days + ' day' + (info.age_days === 1 ? '' : 's') +
      ' ago · refreshes in ' + info.expires_in_days + ' day' + (info.expires_in_days === 1 ? '' : 's');
    cacheBar.classList.remove('hidden');
  }

  function renderJobCard(job) {
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
    return li;
  }

  function showResults(data) {
    const indeedJobs = data.indeed || [];
    const linkedinJobs = data.linkedin || [];

    resultsSection.classList.remove('hidden');

    // Indeed section
    indeedList.innerHTML = '';
    if (indeedJobs.length > 0) {
      indeedJobs.forEach(function (job) { indeedList.appendChild(renderJobCard(job)); });
      indeedSection.classList.remove('hidden');
    } else {
      indeedSection.classList.add('hidden');
    }

    // LinkedIn section
    linkedinList.innerHTML = '';
    if (linkedinJobs.length > 0) {
      linkedinJobs.forEach(function (job) { linkedinList.appendChild(renderJobCard(job)); });
      linkedinSection.classList.remove('hidden');
    } else {
      linkedinSection.classList.add('hidden');
    }
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

  async function runMatch(cvTextValue, location, jobTitleValue, forceRefresh) {
    showLoading(true);
    profileBar.classList.add('hidden');
    cacheBar.classList.add('hidden');
    try {
      const res = await fetch(API_BASE + '/api/match', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          cv_text: cvTextValue,
          location: location,
          job_title: jobTitleValue || null,
          force_refresh: forceRefresh || false,
        })
      });
      const data = await res.json().catch(function () { return {}; });
      if (!res.ok) {
        throw new Error(data.detail || res.statusText || 'Request failed');
      }
      if (data.warning) {
        showError(data.warning);
      }
      const total = (data.indeed || []).length + (data.linkedin || []).length;
      if (total === 0 && !data.warning) {
        showError('No matching jobs found. Try a different location or job title.');
      }
      showResults(data);
      showProfileBar(data);
      showCacheBar(data);
    } catch (err) {
      showError(err.message || 'Something went wrong.');
    } finally {
      showLoading(false);
    }
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

    lastRequest = { cvTextValue, location, jobTitleValue: jobTitle.value.trim() };
    await runMatch(cvTextValue, location, jobTitle.value.trim(), false);
  });

  if (refreshBtn) {
    refreshBtn.addEventListener('click', async function () {
      if (!lastRequest) return;
      hideError();
      await runMatch(lastRequest.cvTextValue, lastRequest.location, lastRequest.jobTitleValue, true);
    });
  }
})();
