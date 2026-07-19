/**
 * Buscador de estadísticas: el usuario escribe un nombre (nunca un ID) y
 * elige de una lista de sugerencias reales, traídas de /stats/search.
 * El resultado se muestra como una tarjeta legible, no como JSON crudo.
 */
let statsDebounceTimer = null;
let statsSelectedType = 'team';
let compareMode = false;
let firstComparedPlayer = null; // {id, label} del primer jugador elegido en modo comparación

function outcomeLabel(outcome) {
  return outcome === 'W' ? t('stats.win') : t('stats.loss');
}

function compareRow(labelKey, valueA, valueB) {
  return `
    <tr>
      <td class="compare-value">${valueA ?? '-'}</td>
      <td class="compare-label">${t(labelKey)}</td>
      <td class="compare-value">${valueB ?? '-'}</td>
    </tr>`;
}

function renderPlayerCompareCard(data) {
  const a = data.player_a;
  const b = data.player_b;
  const ba = a.batting_stats || {};
  const bb = b.batting_stats || {};
  const pa = a.pitching_stats || {};
  const pb = b.pitching_stats || {};
  const hasBatting = a.batting_stats || b.batting_stats;
  const hasPitching = a.pitching_stats || b.pitching_stats;

  return `
    <div class="stats-card">
      <div class="compare-header-row">
        <div class="compare-header-side">
          ${a.team?.logo_url ? `<img src="${a.team.logo_url}" alt="">` : ''}
          <h3>${a.full_name}</h3>
          <span class="stats-subtitle">${a.team ? a.team.name : ''}</span>
        </div>
        <span class="compare-vs">VS</span>
        <div class="compare-header-side">
          ${b.team?.logo_url ? `<img src="${b.team.logo_url}" alt="">` : ''}
          <h3>${b.full_name}</h3>
          <span class="stats-subtitle">${b.team ? b.team.name : ''}</span>
        </div>
      </div>
      ${
        hasBatting
          ? `<h4 class="stats-section-label">${t('stats.battingStats')}</h4>
        <table class="compare-table">
          ${compareRow('stats.avg', ba.avg, bb.avg)}
          ${compareRow('stats.homeRuns', ba.home_runs, bb.home_runs)}
          ${compareRow('stats.hits', ba.hits, bb.hits)}
          ${compareRow('stats.rbi', ba.rbi, bb.rbi)}
          ${compareRow('stats.obp', ba.obp, bb.obp)}
          ${compareRow('stats.ops', ba.ops, bb.ops)}
        </table>`
          : ''
      }
      ${
        hasPitching
          ? `<h4 class="stats-section-label">${t('stats.pitchingStats')}</h4>
        <table class="compare-table">
          ${compareRow('stats.era', pa.era, pb.era)}
          ${compareRow('stats.strikeouts', pa.strikeouts, pb.strikeouts)}
          ${compareRow('stats.saves', pa.saves, pb.saves)}
        </table>`
          : ''
      }
      ${!hasBatting && !hasPitching ? `<p class="empty-state">${t('stats.noStatsYet')}</p>` : ''}
    </div>`;
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

function renderBattingStatsBlock(stats) {
  if (!stats) return '';
  return `
    <h4 class="stats-section-label">${t('stats.battingStats')}</h4>
    <div class="stats-record-row stats-record-wrap">
      <div><strong>${stats.avg ?? '-'}</strong><span>${t('stats.avg')}</span></div>
      <div><strong>${stats.home_runs ?? 0}</strong><span>${t('stats.homeRuns')}</span></div>
      <div><strong>${stats.hits ?? 0}</strong><span>${t('stats.hits')}</span></div>
      <div><strong>${stats.rbi ?? 0}</strong><span>${t('stats.rbi')}</span></div>
      <div><strong>${stats.obp ?? '-'}</strong><span>${t('stats.obp')}</span></div>
      <div><strong>${stats.slg ?? '-'}</strong><span>${t('stats.slg')}</span></div>
      <div><strong>${stats.ops ?? '-'}</strong><span>${t('stats.ops')}</span></div>
      <div><strong>${stats.stolen_bases ?? 0}</strong><span>${t('stats.stolenBases')}</span></div>
    </div>`;
}

function renderPitchingStatsBlock(stats) {
  if (!stats) return '';
  return `
    <h4 class="stats-section-label">${t('stats.pitchingStats')}</h4>
    <div class="stats-record-row stats-record-wrap">
      <div><strong>${stats.wins ?? 0}-${stats.losses ?? 0}</strong><span>${t('stats.record')}</span></div>
      <div><strong>${stats.era ?? '-'}</strong><span>${t('stats.era')}</span></div>
      <div><strong>${stats.strikeouts ?? 0}</strong><span>${t('stats.strikeouts')}</span></div>
      <div><strong>${stats.saves ?? 0}</strong><span>${t('stats.saves')}</span></div>
      <div><strong>${stats.innings_pitched ?? '-'}</strong><span>${t('stats.inningsPitched')}</span></div>
      <div><strong>${stats.whip ?? '-'}</strong><span>WHIP</span></div>
    </div>`;
}

function renderPlayerCard(player) {
  const hasStats = player.batting_stats || player.pitching_stats;
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
      ${renderBattingStatsBlock(player.batting_stats)}
      ${renderPitchingStatsBlock(player.pitching_stats)}
      ${!hasStats ? `<p class="empty-state">${t('stats.noStatsYet')}</p>` : ''}
    </div>`;
}

async function fetchSuggestions(query) {
  const suggestionsBox = document.getElementById('stats-suggestions');
  if (query.length < 2) {
    suggestionsBox.classList.add('hidden');
    return;
  }
  try {
    const results = await api.get(`/stats/search?q=${encodeURIComponent(query)}&type=${statsSelectedType}&sport=${activeSport}`);
    if (!results.length) {
      suggestionsBox.innerHTML = `<div class="stats-suggestion-empty">${t('stats.noMatches')}</div>`;
      suggestionsBox.classList.remove('hidden');
      return;
    }
    suggestionsBox.innerHTML = results
      .map(
        (r) => `
        <button type="button" class="stats-suggestion-item" data-id="${r.id}" data-type="${r.type}" data-label="${r.label}">
          ${r.logo_url ? `<img src="${r.logo_url}" alt="">` : ''}
          <span>${r.label}</span>
          <small>${r.sublabel || ''}</small>
        </button>`
      )
      .join('');
    suggestionsBox.classList.remove('hidden');

    suggestionsBox.querySelectorAll('.stats-suggestion-item').forEach((btn) => {
      btn.addEventListener('click', () => selectStatsResult(btn.dataset.type, btn.dataset.id, btn.dataset.label));
    });
  } catch (err) {
    suggestionsBox.classList.add('hidden');
  }
}

async function selectStatsResult(type, id, label) {
  document.getElementById('stats-suggestions').classList.add('hidden');
  const resultEl = document.getElementById('stats-result');
  const statusEl = document.getElementById('stats-compare-status');
  const input = document.getElementById('stats-query');

  if (compareMode && type === 'player') {
    if (!firstComparedPlayer) {
      firstComparedPlayer = { id, label };
      input.value = '';
      statusEl.classList.remove('hidden');
      statusEl.textContent = `${t('stats.compareFirstPicked')}: ${label}. ${t('stats.compareNowPickSecond')}`;
      return;
    }

    resultEl.innerHTML = `<p class="empty-state">${t('common.loading')}</p>`;
    try {
      const data = await api.get(`/stats/players/compare?id_a=${firstComparedPlayer.id}&id_b=${id}`);
      resultEl.innerHTML = renderPlayerCompareCard(data);
    } catch (err) {
      resultEl.innerHTML = `<p class="empty-state">${err.message}</p>`;
    }
    firstComparedPlayer = null;
    statusEl.classList.add('hidden');
    return;
  }

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
  const compareToggleRow = document.getElementById('stats-compare-toggle-row');
  const compareToggle = document.getElementById('stats-compare-toggle');
  const statusEl = document.getElementById('stats-compare-status');
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

    // Comparar solo aplica a jugadores (NO se pueden cruzar deportes ni tipos).
    compareToggleRow.classList.toggle('hidden', statsSelectedType !== 'player');
    if (statsSelectedType !== 'player') {
      compareToggle.checked = false;
      compareMode = false;
      firstComparedPlayer = null;
      statusEl.classList.add('hidden');
    }
  });

  compareToggle.addEventListener('change', (e) => {
    compareMode = e.target.checked;
    firstComparedPlayer = null;
    statusEl.classList.add('hidden');
    document.getElementById('stats-result').innerHTML = '';
  });

  document.addEventListener('click', (e) => {
    if (!e.target.closest('.stats-autocomplete-wrap')) {
      document.getElementById('stats-suggestions').classList.add('hidden');
    }
  });
}
