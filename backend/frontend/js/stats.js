/**
 * Buscador de estadísticas: el usuario escribe un nombre (nunca un ID) y
 * elige de una lista de sugerencias reales, traídas de /stats/search.
 * El resultado se muestra como una tarjeta legible, no como JSON crudo.
 */
let statsDebounceTimer = null;
let statsSelectedType = 'team';

function outcomeLabel(outcome) {
  return outcome === 'W' ? t('stats.win') : t('stats.loss');
}

function renderTeamCard(team) {
  const resultsHtml = team.recent_results.length
    ? team.recent_results
        .map(
          (r) => `
        <div class="stats-result-row">
          <span class="outcome-tag ${r.outcome === 'W' ? 'win' : 'loss'}">${outcomeLabel(r.outcome)}</span>
          <span>${r.rival}</span>
          <span class="stats-mono">${r.score}</span>
          <span class="stats-mono">${r.date}</span>
        </div>`
        )
        .join('')
    : `<p class="empty-state">${t('stats.noRecentGames')}</p>`;

  return `
    <div class="stats-card">
      <div class="stats-card-header">
        ${team.logo_url ? `<img src="${team.logo_url}" alt="">` : ''}
        <div>
          <h3>${team.name}</h3>
          <span class="stats-subtitle">${team.league || ''} ${team.division ? '· ' + team.division : ''}</span>
        </div>
      </div>
      <div class="stats-record-row">
        <div><strong>${team.record.wins}</strong><span>${t('stats.wins')}</span></div>
        <div><strong>${team.record.losses}</strong><span>${t('stats.losses')}</span></div>
        <div><strong>${(team.record.win_pct * 100).toFixed(1)}%</strong><span>${t('stats.winPct')}</span></div>
      </div>
      <h4 class="stats-section-label">${t('stats.recentResults')}</h4>
      ${resultsHtml}
    </div>`;
}

function renderPlayerCard(player) {
  return `
    <div class="stats-card">
      <div class="stats-card-header">
        ${player.team?.logo_url ? `<img src="${player.team.logo_url}" alt="">` : ''}
        <div>
          <h3>${player.full_name}</h3>
          <span class="stats-subtitle">
            ${player.position || ''} ${player.jersey_number ? '· #' + player.jersey_number : ''}
            ${player.team ? '· ' + player.team.name : ''}
          </span>
        </div>
      </div>
    </div>`;
}

async function fetchSuggestions(query) {
  const suggestionsBox = document.getElementById('stats-suggestions');
  if (query.length < 2) {
    suggestionsBox.classList.add('hidden');
    return;
  }
  try {
    const results = await api.get(`/stats/search?q=${encodeURIComponent(query)}&type=${statsSelectedType}`);
    if (!results.length) {
      suggestionsBox.innerHTML = `<div class="stats-suggestion-empty">${t('stats.noMatches')}</div>`;
      suggestionsBox.classList.remove('hidden');
      return;
    }
    suggestionsBox.innerHTML = results
      .map(
        (r) => `
        <button type="button" class="stats-suggestion-item" data-id="${r.id}" data-type="${r.type}">
          ${r.logo_url ? `<img src="${r.logo_url}" alt="">` : ''}
          <span>${r.label}</span>
          <small>${r.sublabel || ''}</small>
        </button>`
      )
      .join('');
    suggestionsBox.classList.remove('hidden');

    suggestionsBox.querySelectorAll('.stats-suggestion-item').forEach((btn) => {
      btn.addEventListener('click', () => selectStatsResult(btn.dataset.type, btn.dataset.id));
    });
  } catch (err) {
    suggestionsBox.classList.add('hidden');
  }
}

async function selectStatsResult(type, id) {
  document.getElementById('stats-suggestions').classList.add('hidden');
  const resultEl = document.getElementById('stats-result');
  resultEl.innerHTML = `<p class="empty-state">${t('common.loading')}</p>`;
  try {
    const data = await api.get(`/stats/${type}/${id}`);
    resultEl.innerHTML = type === 'team' ? renderTeamCard(data) : renderPlayerCard(data);
  } catch (err) {
    resultEl.innerHTML = `<p class="empty-state">${t('common.error')}</p>`;
  }
}

function initStatsSearch() {
  const input = document.getElementById('stats-query');
  const typeSelect = document.getElementById('stats-type');
  if (!input) return;

  input.addEventListener('input', (e) => {
    clearTimeout(statsDebounceTimer);
    const value = e.target.value;
    statsDebounceTimer = setTimeout(() => fetchSuggestions(value), 300);
  });

  typeSelect.addEventListener('change', (e) => {
    statsSelectedType = e.target.value;
    input.value = '';
    document.getElementById('stats-suggestions').classList.add('hidden');
    input.placeholder = t(statsSelectedType === 'team' ? 'stats.placeholderTeam' : 'stats.placeholderPlayer');
  });

  document.addEventListener('click', (e) => {
    if (!e.target.closest('.stats-autocomplete-wrap')) {
      document.getElementById('stats-suggestions').classList.add('hidden');
    }
  });
}
