/**
 * Orquesta la interfaz principal de StrikeHub (solo MLB): renderizado de
 * posiciones, "jugadores hoy" (pitchers probables), noticias y partidos
 * (en vivo / finalizados / próximos con barra de probabilidad).
 */

/**
 * StrikeHub es solo MLB: una única liga ('mlb'), sin pestañas de deporte.
 * activeLeague existe para conservar la fecha elegida entre re-renders.
 */
const LEAGUE_KEY = 'mlb';
const SPORT_KEY = 'baseball';
let activeLeague = LEAGUE_KEY;

function formatDate(iso) {
  return new Date(iso).toLocaleString(i18nState.lang === 'es' ? 'es-ES' : 'en-US', {
    dateStyle: 'medium',
    timeStyle: 'short',
  });
}

/* ---------------------- Posiciones ---------------------- */
async function renderStandings(leagueKey) {
  const container = document.getElementById('standings-container');
  container.innerHTML = `<p class="empty-state">${t('common.loading')}</p>`;
  try {
    const groups = await api.get(`/leagues/${leagueKey}/standings`);
    if (!groups.length || !groups.some((g) => g.teams.length)) {
      container.innerHTML = `<p class="empty-state">${t('common.standingsUnavailable')}</p>`;
      return;
    }

    container.innerHTML = groups
      .map((group) => {
        const rows = group.teams
          .map(
            (team) => `
            <tr>
              <td>
                <div class="team-cell">
                  <button class="fav-star" data-fav-type="team" data-fav-id="${Number(team.id)}" aria-label="favorito">★</button>
                  ${team.logo_url ? `<img src="${esc(safeImg(team.logo_url))}" alt="" loading="lazy" decoding="async">` : ''}
                  ${esc(team.name)}
                </div>
              </td>
              <td>${Number(team.wins)}</td>
              <td>${Number(team.losses)}</td>
              <td>${team.games_back === 0 ? '-' : esc(team.games_back)}</td>
            </tr>`
          )
          .join('');
        return `
          <h3 class="standings-group-title">${esc(group.group_name)}</h3>
          <table class="standings-table">
            <thead>
              <tr><th>${t('stats.team')}</th><th>G</th><th>P</th><th>GB</th></tr>
            </thead>
            <tbody>${rows}</tbody>
          </table>`;
      })
      .join('');

    markFavoriteStars(container);
  } catch (err) {
    container.innerHTML = `<p class="empty-state">${t('common.error')}</p>`;
  }
}

/* ---------------------- Jugadores hoy (pitchers probables en MLB) ---------------------- */
async function renderPlayersToday(leagueKey) {
  const container = document.getElementById('players-today-container');
  container.innerHTML = `<p class="empty-state">${t('common.loading')}</p>`;
  try {
    const games = await api.get(`/leagues/${leagueKey}/games?status=scheduled`);

    if (!games.length) {
      container.innerHTML = `<p class="empty-state">${t('common.noGamesToday')}</p>`;
      return;
    }

    // Se pide el detalle de cada juego para leer los pitchers probables.
    const details = await Promise.all(games.slice(0, 6).map((g) => api.get(`/games/${g.id}`)));

    container.innerHTML = details
      .map((g) => {
        const homePitcher = g.details?.home_pitcher || '—';
        const awayPitcher = g.details?.away_pitcher || '—';
        return `
        <div class="player-card">
          <div>
            <div class="name">${esc(g.away_team.name)} @ ${esc(g.home_team.name)}</div>
            <div class="role">${t('game.probablePitcher')}: ${esc(awayPitcher)} vs ${esc(homePitcher)}</div>
          </div>
        </div>`;
      })
      .join('');
  } catch (err) {
    container.innerHTML = `<p class="empty-state">${t('common.error')}</p>`;
  }
}

/* ---------------------- Noticias ---------------------- */
async function renderNews(sportKey) {
  const container = document.getElementById('news-container');
  container.innerHTML = `<p class="empty-state">${t('common.loading')}</p>`;
  try {
    // sort=trending: prioriza noticias sobre equipos de los que hay más
    // cobertura reciente (relevancia real por menciones), no solo la más nueva.
    const articles = await api.get(`/news/${sportKey}?sort=trending&lang=${i18nState.lang}`);
    if (!articles.length) {
      container.innerHTML = `<p class="empty-state">${t('common.newsEmpty')}</p>`;
      return;
    }
    container.innerHTML = articles
      .map(
        (a) => `
        <article class="card news-card">
          ${a.image_url ? `<img src="${esc(safeImg(a.image_url))}" alt="" loading="lazy" decoding="async">` : ''}
          <div class="card-body">
            <div class="news-meta">
              ${t('common.source')}: ${esc(a.source)} · ${esc(formatDate(a.published_at))}
            </div>
            <h3>${esc(a.title)}</h3>
            ${a.summary ? `<p>${esc(a.summary)}</p>` : ''}
            <a class="btn btn-outline btn-small" href="${esc(safeUrl(a.article_url))}" target="_blank" rel="noopener noreferrer">${t('common.readMore')}</a>
          </div>
        </article>`
      )
      .join('');
  } catch (err) {
    container.innerHTML = `<p class="empty-state">${t('common.error')}</p>`;
  }
}

/* ---------------------- Partidos: en vivo / finalizados / próximos ---------------------- */
function gameStatusLabel(game) {
  if (game.status === 'live') {
    // period_status ya lo calcula el backend (ej. "Inning 7" en MLB). Si algún
    // día no viene (otras ligas todavía sin ese dato), solo se muestra "En vivo".
    const period = game.period_status ? ` · ${esc(game.period_status)}` : '';
    return `<span class="game-status live">● ${t('game.live')}${period}</span>`;
  }
  if (game.status === 'final') return `<span class="game-status">${t('game.final')}</span>`;
  return `<span class="game-status">${t('game.scheduled')}</span>`;
}

function renderGameDetailsBlock(game) {
  if (game.status !== 'final' || !game.details) return '';
  const d = game.details;
  const rows = [];
  if (d.winning_pitcher) rows.push(`${t('game.winningPitcher')}: ${esc(d.winning_pitcher)}`);
  if (d.losing_pitcher) rows.push(`${t('game.losingPitcher')}: ${esc(d.losing_pitcher)}`);
  if (d.save_pitcher) rows.push(`${t('game.savePitcher')}: ${esc(d.save_pitcher)}`);
  if (!rows.length) return '';

  return `<div class="game-details-box">${rows.join(' · ')}</div>`;
}

async function renderPredictionRow(game) {
  if (game.status !== 'scheduled') return '';

  const homeProb = game.home_win_probability ?? 0.5;
  const awayProb = 1 - homeProb;

  const barHtml = `
    <div class="probability-wrap">
      <div class="probability-bar">
        <div class="probability-fill-home" style="width:${(homeProb * 100).toFixed(0)}%"></div>
        <div class="probability-fill-away" style="width:${(awayProb * 100).toFixed(0)}%"></div>
      </div>
      <div class="probability-labels">
        <span>${esc(game.home_team.abbreviation || game.home_team.name)} ${(homeProb * 100).toFixed(0)}%</span>
        <span>${(awayProb * 100).toFixed(0)}% ${esc(game.away_team.abbreviation || game.away_team.name)}</span>
      </div>
    </div>`;

  if (!window.currentUser) {
    return `${barHtml}
      <div class="predict-row">
        <button class="btn btn-outline btn-small" data-open-auth="login">${t('game.loginToPredict')}</button>
      </div>`;
  }

  const homePts = pointsFromProbability(homeProb);
  const awayPts = pointsFromProbability(awayProb);
  const homeLoss = pointsLostFromProbability(homeProb);
  const awayLoss = pointsLostFromProbability(awayProb);

  return `${barHtml}
    <div class="predict-row">
      <button class="predict-btn" data-game-id="${Number(game.id)}" data-team-id="${Number(game.home_team.id)}">
        ${esc(game.home_team.name)}
        <span class="points-tag points-tag-win">+${Number(homePts)}</span>
        <span class="points-tag points-tag-loss">-${Number(homeLoss)} ${t('game.ifWrong')}</span>
      </button>
      <button class="predict-btn" data-game-id="${Number(game.id)}" data-team-id="${Number(game.away_team.id)}">
        ${esc(game.away_team.name)}
        <span class="points-tag points-tag-win">+${Number(awayPts)}</span>
        <span class="points-tag points-tag-loss">-${Number(awayLoss)} ${t('game.ifWrong')}</span>
      </button>
    </div>`;
}

// Debe reflejar exactamente _skew_probability_for_points en app/services/probability_service.py
function skewProbabilityForPoints(p, strength = 1.8) {
  const centered = (p - 0.5) * 2;
  const sign = centered >= 0 ? 1 : -1;
  const skewed = sign * Math.pow(Math.abs(centered), 1 / strength);
  return Math.max(0, Math.min(1, skewed / 2 + 0.5));
}

// Debe reflejar exactamente points_for_prediction en app/services/probability_service.py
function pointsFromProbability(p) {
  const MIN = 2, MAX = 20;
  const points = MAX - (MAX - MIN) * skewProbabilityForPoints(p);
  return Math.round(Math.max(MIN, Math.min(MAX, points)));
}

// Debe reflejar exactamente points_lost_for_prediction en app/services/probability_service.py
function pointsLostFromProbability(p) {
  const MIN = 2, MAX = 20;
  const points = MIN + (MAX - MIN) * skewProbabilityForPoints(p);
  return Math.round(Math.max(MIN, Math.min(MAX, points)));
}

function renderTicker(games) {
  const track = document.getElementById('ticker-track');
  if (!games || !games.length) {
    track.innerHTML = `<span class="ticker-item">${t('common.tickerEmpty')}</span>`;
    return;
  }

  const items = games
    .map((g) => {
      const isFinal = g.status === 'final';
      const score = g.status === 'scheduled' ? formatDate(g.start_time) : `${g.home_score ?? 0}-${g.away_score ?? 0}`;
      const awayLogo = g.away_team.logo_url ? `<img src="${esc(safeImg(g.away_team.logo_url))}" alt="" class="ticker-logo" loading="lazy" decoding="async">` : '';
      const homeLogo = g.home_team.logo_url ? `<img src="${esc(safeImg(g.home_team.logo_url))}" alt="" class="ticker-logo" loading="lazy" decoding="async">` : '';
      return `
        <span class="ticker-item ${isFinal ? 'final' : ''}">
          <span class="ticker-dot"></span>
          ${awayLogo}${esc(g.away_team.abbreviation || g.away_team.name)} @ ${homeLogo}${esc(g.home_team.abbreviation || g.home_team.name)} · ${esc(score)}
        </span>`;
    })
    .join('');

  // Se duplica el contenido para lograr un scroll continuo sin salto (ver @keyframes ticker-scroll).
  track.innerHTML = items + items;
}

function scoreDisplay(game) {
  // No mostrar marcador numérico en partidos que aún no comienzan: la API
  // devuelve 0 (no null) para esos casos, y 0-0 se confundía con un
  // partido realmente empatado en 0. Se decide por el status, no por el valor.
  if (game.status === 'scheduled') return 'VS';
  return `${game.home_score ?? 0} : ${game.away_score ?? 0}`;
}

async function renderGameCard(game) {
  const predictionRow = await renderPredictionRow(game);
  const liveSlot = game.status === 'live' ? `<div class="live-situation-slot" data-game-id="${Number(game.id)}"></div>` : '';
  return `
    <div class="game-card">
      <div class="game-top-row">
        ${gameStatusLabel(game)}
        <span class="game-status">${esc(formatDate(game.start_time))}</span>
      </div>
      <div class="scoreboard-row">
        <div class="team-block home">
          ${game.home_team.logo_url ? `<img src="${esc(safeImg(game.home_team.logo_url))}" alt="" loading="lazy" decoding="async">` : ''}
          <span class="team-name">${esc(game.home_team.name)}</span>
          <span class="team-role">${t('game.homeTeam')}</span>
        </div>
        <div class="score-led">${esc(scoreDisplay(game))}</div>
        <div class="team-block away">
          ${game.away_team.logo_url ? `<img src="${esc(safeImg(game.away_team.logo_url))}" alt="" loading="lazy" decoding="async">` : ''}
          <span class="team-name">${esc(game.away_team.name)}</span>
          <span class="team-role">${t('game.awayTeam')}</span>
        </div>
      </div>
      ${liveSlot}
      ${renderGameDetailsBlock(game)}
      ${predictionRow}
    </div>`;
}

async function renderGameGroup(titleKey, games) {
  if (!games.length) return '';
  const cards = await Promise.all(games.map(renderGameCard));
  return `
    <h3 class="game-group-title">${t(titleKey)}</h3>
    ${cards.join('')}`;
}

/* ---------- Situación en vivo (diamante, outs, última jugada) ---------- */
const LIVE_POLL_INTERVAL_MS = 15000; // "rápido, sin refresh manual" según lo pedido
let activeLivePolls = [];

function renderDiamond(bases) {
  return `
    <div class="diamond-wrap">
      <div class="diamond">
        <div class="diamond-base second ${bases.second ? 'occupied' : ''}"></div>
        <div class="diamond-base third ${bases.third ? 'occupied' : ''}"></div>
        <div class="diamond-base first ${bases.first ? 'occupied' : ''}"></div>
        <div class="diamond-base home"></div>
      </div>
    </div>`;
}

function renderOuts(outs) {
  const dots = [0, 1, 2].map((i) => `<span class="out-dot ${i < outs ? 'filled' : ''}"></span>`).join('');
  return `<div class="outs-row">${t('game.outs')}: ${dots}</div>`;
}

function renderLiveSituationHtml(situation) {
  if (!situation) return '';
  const halfArrow = situation.inning_half === 'Top' ? '▲' : '▼';
  return `
    <div class="live-situation">
      <div class="diamond-wrap">
        ${renderDiamond(situation.bases)}
        ${renderOuts(situation.outs)}
      </div>
      <div class="live-situation-info">
        <span>${halfArrow} ${t('game.inning')} ${situation.inning ?? '-'}</span>
        <span class="count">${Number(situation.balls ?? 0)}-${Number(situation.strikes ?? 0)} · ${t('game.outs')} ${Number(situation.outs ?? 0)}</span>
        ${situation.batter ? `<span>${t('game.atBat')}: ${esc(situation.batter)}</span>` : ''}
        ${situation.pitcher ? `<span>${t('game.pitching')}: ${esc(situation.pitcher)}</span>` : ''}
        ${situation.last_play ? `<span class="last-play">${t('game.lastPlay')}: ${esc(situation.last_play)}</span>` : ''}
      </div>
    </div>`;
}

async function refreshLiveSituation(gameId) {
  const slot = document.querySelector(`.live-situation-slot[data-game-id="${gameId}"]`);
  if (!slot) return; // la tarjeta ya no está en pantalla (cambiaron de liga/pestaña)

  try {
    const data = await api.get(`/games/${gameId}/live?lang=${i18nState.lang}`);
    if (data.status !== 'live') {
      slot.innerHTML = ''; // el partido ya terminó: se quita el diamante en el siguiente refresh general
      return;
    }
    slot.innerHTML = renderLiveSituationHtml(data.situation);
  } catch (err) {
    // Si falla una consulta puntual no se rompe la tarjeta; se reintenta en el siguiente ciclo.
  }
}

function stopLivePolling() {
  activeLivePolls.forEach((intervalId) => clearInterval(intervalId));
  activeLivePolls = [];
}

function startLivePolling(gameIds) {
  stopLivePolling();
  gameIds.forEach((gameId) => {
    refreshLiveSituation(gameId); // primera carga inmediata, sin esperar el primer intervalo
    const intervalId = setInterval(() => refreshLiveSituation(gameId), LIVE_POLL_INTERVAL_MS);
    activeLivePolls.push(intervalId);
  });
}

async function fetchDisplayGames(leagueKey, specificDate = null) {
  const dateParam = specificDate ? `?game_date=${specificDate}` : '';
  const games = await api.get(`/leagues/${leagueKey}/games${dateParam}`);

  const todayIso = new Date().toISOString().slice(0, 10);
  const isPastDateSearch = Boolean(specificDate) && specificDate < todayIso;

  // Si se busca una fecha pasada, se fuerza status='final' en una copia de
  // cada juego (sin mutar el original). Así toda la lógica de abajo
  // (etiqueta, si se muestra el diamante, agrupación) es consistente, sin
  // importar qué status haya quedado guardado por error en el backend.
  const displayGames = isPastDateSearch ? games.map((g) => ({ ...g, status: 'final' })) : games;
  return { displayGames, isPastDateSearch };
}

async function renderLiveSection(leagueKey) {
  const container = document.getElementById('live-container');
  container.innerHTML = `<p class="empty-state">${t('common.loading')}</p>`;
  try {
    const { displayGames } = await fetchDisplayGames(leagueKey);
    renderTicker(displayGames);

    const live = displayGames.filter((g) => g.status === 'live');
    const finished = displayGames.filter((g) => g.status === 'final');

    if (!live.length && !finished.length) {
      container.innerHTML = `<p class="empty-state">${t('common.noGamesToday')}</p>`;
      stopLivePolling();
      return;
    }

    container.innerHTML =
      (await renderGameGroup('sections.liveNow', live)) +
      (await renderGameGroup('sections.finished', finished));
    startLivePolling(live.map((g) => g.id));
  } catch (err) {
    container.innerHTML = `<p class="empty-state">${t('common.error')}</p>`;
  }
}

async function renderCalendarSection(leagueKey, specificDate = null) {
  const container = document.getElementById('calendar-container');
  container.innerHTML = `<p class="empty-state">${t('common.loading')}</p>`;
  try {
    const { displayGames, isPastDateSearch } = await fetchDisplayGames(leagueKey, specificDate);
    if (!isPastDateSearch) renderTicker(displayGames);

    if (!displayGames.length) {
      container.innerHTML = `<p class="empty-state">${t('common.noGamesToday')}</p>`;
      return;
    }

    const upcoming = displayGames.filter((g) => g.status === 'scheduled');
    const finished = displayGames.filter((g) => g.status === 'final');
    const groups = specificDate
      ? (await renderGameGroup('sections.finished', finished)) +
        (await renderGameGroup('sections.upcoming', upcoming))
      : await renderGameGroup('sections.upcoming', upcoming);

    container.innerHTML = groups || `<p class="empty-state">${t('common.noGamesToday')}</p>`;
    attachPredictionHandlers(container);
  } catch (err) {
    container.innerHTML = `<p class="empty-state">${t('common.error')}</p>`;
  }
}

function attachPredictionHandlers(container) {
  // Botón "inicia sesión para predecir" (reemplaza el onclick inline,
  // incompatible con CSP sin 'unsafe-inline').
  container.querySelectorAll('[data-open-auth]').forEach((btn) => {
    btn.addEventListener('click', () => openAuthModal(btn.dataset.openAuth || 'login'));
  });
  container.querySelectorAll('.predict-btn').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const gameId = Number(btn.dataset.gameId);
      const teamId = Number(btn.dataset.teamId);
      try {
        await api.post('/predictions', { game_id: gameId, predicted_team_id: teamId });
        btn.classList.add('chosen');
        btn.disabled = true;
        const sibling = btn.parentElement.querySelectorAll('.predict-btn');
        sibling.forEach((b) => { if (b !== btn) b.disabled = true; });
      } catch (err) {
        if (typeof showToast === 'function') showToast(err.message, 'error');
        else alert(err.message);
      }
    });
  });
}

/* ---------------------- Postemporada (bracket) ---------------------- */
function renderSeriesCard(series) {
  const roundName = t(`postseason.${series.round}`);
  const teamRows = series.teams
    .map(
      (tm, idx) => `
      <div class="series-team ${idx === 0 ? 'top-seed' : ''}">
        ${tm.logo_url ? `<img src="${esc(safeImg(tm.logo_url))}" alt="" loading="lazy" decoding="async">` : ''}
        <span class="series-seed">${tm.seed != null ? esc(tm.seed) : ''}</span>
        <span class="series-team-name">${esc(tm.abbreviation || tm.name)}</span>
        <span class="series-wins">${Number(tm.wins)}</span>
      </div>`
    )
    .join('');
  const gamesRows = (series.games || [])
    .map((g) => {
      const label =
        g.status === 'final'
          ? `${esc(g.away_abbreviation)} ${g.away_score ?? 0} · ${g.home_score ?? 0} ${esc(g.home_abbreviation)}`
          : g.status === 'live'
            ? `${esc(g.away_abbreviation)} ${g.away_score ?? 0} · ${g.home_score ?? 0} ${esc(g.home_abbreviation)} ●`
            : esc(formatDate(g.date));
      return `<div class="series-game ${esc(g.status)}">${label}</div>`;
    })
    .join('');
  return `
    <div class="series-card">
      <div class="series-round">${esc(roundName)} · ${t('postseason.bestOf')} ${Number(series.best_of)}</div>
      ${teamRows}
      ${series.leader_text ? `<div class="series-leader">${esc(series.leader_text)}</div>` : ''}
      <div class="series-games">${gamesRows}</div>
    </div>`;
}

function renderLeagueBracket(seriesList) {
  const rounds = ['WC', 'DS', 'CS'];
  return rounds
    .map((r) => {
      const items = seriesList.filter((s) => s.round === r);
      if (!items.length) return '';
      return `
        <div class="bracket-round">
          <h4 class="bracket-round-title">${esc(t(`postseason.${r}`))}</h4>
          ${items.map(renderSeriesCard).join('')}
        </div>`;
    })
    .join('');
}

async function renderPostseason() {
  const container = document.getElementById('postseason-container');
  container.innerHTML = `<p class="empty-state">${t('common.loading')}</p>`;
  try {
    const data = await api.get('/postseason/bracket');
    if (!data.postseason_active) {
      container.innerHTML = `<p class="empty-state">${t('postseason.notActive')}</p>`;
      return;
    }
    container.innerHTML = `
      <div class="bracket-grid">
        <div class="bracket-side">
          <h3 class="bracket-league-title">AL · American League</h3>
          ${renderLeagueBracket(data.al || [])}
        </div>
        <div class="bracket-center">
          <h3 class="bracket-league-title">${esc(t('postseason.WS'))}</h3>
          ${data.world_series ? renderSeriesCard(data.world_series) : `<p class="empty-state">${t('postseason.notActive')}</p>`}
        </div>
        <div class="bracket-side">
          <h3 class="bracket-league-title">NL · National League</h3>
          ${renderLeagueBracket(data.nl || [])}
        </div>
      </div>`;
  } catch (err) {
    container.innerHTML = `<p class="empty-state">${t('common.error')}</p>`;
  }
}

/* ---------------------- Favoritos ---------------------- */
async function markFavoriteStars(container) {
  if (!window.currentUser) return;
  try {
    const favorites = await api.get('/favorites/me');
    container.querySelectorAll('.fav-star').forEach((star) => {
      const type = star.dataset.favType;
      const id = Number(star.dataset.favId);
      const match = favorites.find((f) => f.favorite_type === type && f[`${type}_id`] === id);
      if (match) {
        star.classList.add('active');
        star.dataset.favoriteRecordId = match.id;
      }
      star.addEventListener('click', () => toggleFavorite(star, type, id));
    });
  } catch (_) {
    /* silencioso: si falla, simplemente no se marcan estrellas */
  }
}

async function toggleFavorite(star, type, id) {
  if (!window.currentUser) {
    openAuthModal('login');
    return;
  }
  try {
    if (star.classList.contains('active')) {
      await api.delete(`/favorites/${star.dataset.favoriteRecordId}`);
      star.classList.remove('active');
    } else {
      const created = await api.post('/favorites', { favorite_type: type, target_id: id });
      star.dataset.favoriteRecordId = created.id;
      star.classList.add('active');
    }
  } catch (err) {
    if (typeof showToast === 'function') showToast(err.message, 'error');
    else alert(err.message);
  }
}

/* ---------------------- Vistas (una sección a la vez) ----------------------
   La página se divide en vistas con botones: En vivo, Calendario,
   Posiciones, Postemporada, Noticias y Estadísticas. Cada vista carga su
   contenido la primera vez que se muestra (rápido al entrar: solo En vivo).
   La vista de noticias incluye el complemento "Jugadores Hoy". */
const loadedViews = new Set();
let activeView = 'live';

const VIEW_LOADERS = {
  live: () => renderLiveSection(activeLeague),
  calendar: () => renderCalendarSection(activeLeague, document.getElementById('games-date-input')?.value || null),
  standings: () => renderStandings(activeLeague),
  postseason: () => renderPostseason(),
  news: () => Promise.all([renderNews(SPORT_KEY), renderPlayersToday(activeLeague)]),
  stats: () => Promise.resolve(),
};

function showView(name) {
  if (!VIEW_LOADERS[name]) return;
  activeView = name;
  document.querySelectorAll('.view-tab').forEach((tab) => {
    tab.classList.toggle('active', tab.dataset.view === name);
  });
  document.querySelectorAll('[data-view-section]').forEach((section) => {
    section.classList.toggle('hidden', section.dataset.viewSection !== name);
  });
  // El polling en vivo solo tiene sentido en su vista.
  if (name !== 'live') stopLivePolling();
  if (loadedViews.has(name)) {
    if (name === 'live') renderLiveSection(activeLeague);
    return;
  }
  loadedViews.add(name);
  VIEW_LOADERS[name]();
}

function initViewNav() {
  document.querySelectorAll('.view-tab').forEach((tab) => {
    tab.addEventListener('click', () => showView(tab.dataset.view));
  });
}

function initDateSearch() {
  const dateInput = document.getElementById('games-date-input');
  const todayBtn = document.getElementById('games-date-today');

  dateInput.addEventListener('change', (e) => {
    if (e.target.value) renderCalendarSection(activeLeague, e.target.value);
  });

  todayBtn.addEventListener('click', () => {
    dateInput.value = '';
    renderCalendarSection(activeLeague);
  });
}

async function loadMainContent() {
  resetStatsSearch();
  activeLeague = LEAGUE_KEY;
  const dateInput = document.getElementById('games-date-input');
  if (dateInput) dateInput.value = '';
  loadedViews.clear();
  showView('live');
}

document.addEventListener('bfb:language-changed', () => {
  // Recarga la vista actual en el nuevo idioma; las demás se recargarán
  // cuando se visiten (loadedViews se limpia).
  loadedViews.clear();
  showView(activeView);
});

// Tras login/logout/registro el estado de usuario cambia: las tarjetas ya
// pintadas (botones de predecir, estrellas de favorito) quedarían con el
// estado anterior. Se re-renderizan las vistas cargadas que dependen de
// la sesión (noticias/stats no).
document.addEventListener('bfb:user-changed', () => {
  if (!activeLeague) return;
  if (loadedViews.has('live')) renderLiveSection(activeLeague);
  if (loadedViews.has('calendar')) {
    const dateInput = document.getElementById('games-date-input');
    renderCalendarSection(activeLeague, dateInput?.value || null);
  }
  if (loadedViews.has('standings')) renderStandings(activeLeague);
});

async function initApp() {
  await initI18n();
  initAuth();
  initViewNav();
  initDateSearch();
  initStatsSearch();
  await loadMainContent();
}

document.addEventListener('DOMContentLoaded', initApp);
