/**
 * Orquesta la interfaz principal: cambio de pestaña por deporte y
 * renderizado de posiciones, "jugadores hoy", noticias y partidos
 * (en vivo / finalizados / próximos con barra de probabilidad).
 */

// Configuración de la liga principal a mostrar por cada deporte.
// El botón de la pestaña también permite, a futuro, listar otras ligas
// del mismo deporte (endpoint /sports/{sport_key}/leagues ya existe).
const PRIMARY_LEAGUE_BY_SPORT = {
  baseball: 'mlb',
  football: 'epl', // liga de fútbol de ejemplo; el buscador de ligas se alimenta de /sports/football/leagues
  basketball: 'nba',
  worldcup: 'world_cup', // apartado especial: usa la liga "world_cup" de balldontlie
};

// El Mundial no es un deporte aparte en la base de datos, es parte de "football".
// Por eso sus noticias generales se toman del deporte fútbol.
const NEWS_SPORT_BY_TAB = {
  baseball: 'baseball',
  football: 'football',
  basketball: 'basketball',
  worldcup: 'football',
};

const SPORT_READY = {
  // La MLB corre sobre la API oficial gratuita: funciona sin configuración adicional.
  baseball: true,
  // Ya construido y conectado a balldontlie. Si no ves datos, confirma en los
  // logs de Railway que BALLDONTLIE_API_KEY esté configurada y que el primer
  // ciclo de sincronización (cada 5 min) ya haya corrido.
  football: true,
  basketball: true,
  worldcup: true,
};

let activeSport = 'baseball';

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
    const teams = await api.get(`/leagues/${leagueKey}/standings`);
    if (!teams.length) {
      container.innerHTML = `<p class="empty-state">${t('common.standingsUnavailable')}</p>`;
      return;
    }
    const rows = teams
      .map(
        (team) => `
        <tr>
          <td>
            <div class="team-cell">
              <button class="fav-star" data-fav-type="team" data-fav-id="${team.id}" aria-label="favorito">★</button>
              ${team.logo_url ? `<img src="${team.logo_url}" alt="">` : ''}
              ${team.name}
            </div>
          </td>
          <td>${team.wins}</td>
          <td>${team.losses}</td>
          <td>${(team.win_pct * 100).toFixed(1)}%</td>
          <td>${team.division ?? '-'}</td>
        </tr>`
      )
      .join('');

    container.innerHTML = `
      <table class="standings-table">
        <thead>
          <tr><th>Equipo</th><th>G</th><th>P</th><th>%</th><th>División</th></tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>`;

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
            <div class="name">${g.away_team.name} @ ${g.home_team.name}</div>
            <div class="role">${t('game.probablePitcher')}: ${awayPitcher} vs ${homePitcher}</div>
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
    const articles = await api.get(`/news/${sportKey}?sort=trending`);
    if (!articles.length) {
      container.innerHTML = `<p class="empty-state">${t('common.comingSoon')}</p>`;
      return;
    }
    container.innerHTML = articles
      .map(
        (a) => `
        <article class="card news-card">
          ${a.image_url ? `<img src="${a.image_url}" alt="" loading="lazy">` : ''}
          <div class="card-body">
            <div class="news-meta">
              ${a.team_logo_url ? `<img src="${a.team_logo_url}" alt="" class="news-team-logo">` : ''}
              ${t('common.source')}: ${a.source} · ${formatDate(a.published_at)}
            </div>
            <h3>${a.title}</h3>
            ${a.summary ? `<p>${a.summary}</p>` : ''}
            <a class="btn btn-outline btn-small" href="${a.article_url}" target="_blank" rel="noopener noreferrer">${t('common.readMore')}</a>
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
    const period = game.period_status ? ` · ${game.period_status}` : '';
    return `<span class="game-status live">● ${t('game.live')}${period}</span>`;
  }
  if (game.status === 'final') return `<span class="game-status">${t('game.final')}</span>`;
  return `<span class="game-status">${t('game.scheduled')}</span>`;
}

function renderGameDetailsBlock(game) {
  if (game.status !== 'final' || !game.details) return '';
  const d = game.details;
  const rows = [];
  if (d.winning_pitcher) rows.push(`${t('game.winningPitcher')}: ${d.winning_pitcher}`);
  if (d.losing_pitcher) rows.push(`${t('game.losingPitcher')}: ${d.losing_pitcher}`);
  if (d.save_pitcher) rows.push(`${t('game.savePitcher')}: ${d.save_pitcher}`);
  if (!rows.length) return '';

  const id = `details-${game.id}`;
  return `
    <button class="game-details-toggle" onclick="document.getElementById('${id}').classList.toggle('hidden')">
      ${t('game.details')}
    </button>
    <div class="game-details-box hidden" id="${id}">${rows.join(' · ')}</div>
  `;
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
        <span>${game.home_team.abbreviation || game.home_team.name} ${(homeProb * 100).toFixed(0)}%</span>
        <span>${(awayProb * 100).toFixed(0)}% ${game.away_team.abbreviation || game.away_team.name}</span>
      </div>
    </div>`;

  if (!window.currentUser) {
    return `${barHtml}
      <div class="predict-row">
        <button class="btn btn-outline btn-small" onclick="openAuthModal('login')">${t('game.loginToPredict')}</button>
      </div>`;
  }

  const homePts = pointsFromProbability(homeProb);
  const awayPts = pointsFromProbability(awayProb);

  return `${barHtml}
    <div class="predict-row">
      <button class="predict-btn" data-game-id="${game.id}" data-team-id="${game.home_team.id}">
        ${game.home_team.name}
        <span class="points-tag">+${homePts} ${t('auth.points')}</span>
      </button>
      <button class="predict-btn" data-game-id="${game.id}" data-team-id="${game.away_team.id}">
        ${game.away_team.name}
        <span class="points-tag">+${awayPts} ${t('auth.points')}</span>
      </button>
    </div>`;
}

// Debe reflejar exactamente la fórmula de app/services/probability_service.py
function pointsFromProbability(p) {
  const MIN = 2, MAX = 20;
  const points = MAX - (MAX - MIN) * p;
  return Math.round(Math.max(MIN, Math.min(MAX, points)));
}

function renderTicker(games) {
  const track = document.getElementById('ticker-track');
  if (!games || !games.length) {
    track.innerHTML = `<span class="ticker-item">${t('common.comingSoon')}</span>`;
    return;
  }

  const items = games
    .map((g) => {
      const isFinal = g.status === 'final';
      const score = g.status === 'scheduled' ? formatDate(g.start_time) : `${g.home_score ?? 0}-${g.away_score ?? 0}`;
      const awayLogo = g.away_team.logo_url ? `<img src="${g.away_team.logo_url}" alt="" class="ticker-logo">` : '';
      const homeLogo = g.home_team.logo_url ? `<img src="${g.home_team.logo_url}" alt="" class="ticker-logo">` : '';
      return `
        <span class="ticker-item ${isFinal ? 'final' : ''}">
          <span class="ticker-dot"></span>
          ${awayLogo}${g.away_team.abbreviation || g.away_team.name} @ ${homeLogo}${g.home_team.abbreviation || g.home_team.name} · ${score}
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
  return `
    <div class="game-card">
      <div class="game-top-row">
        ${gameStatusLabel(game)}
        <span class="game-status">${formatDate(game.start_time)}</span>
      </div>
      <div class="scoreboard-row">
        <div class="team-block home">
          ${game.home_team.logo_url ? `<img src="${game.home_team.logo_url}" alt="">` : ''}
          <span class="team-name">${game.home_team.name}</span>
        </div>
        <div class="score-led">${scoreDisplay(game)}</div>
        <div class="team-block away">
          ${game.away_team.logo_url ? `<img src="${game.away_team.logo_url}" alt="">` : ''}
          <span class="team-name">${game.away_team.name}</span>
        </div>
      </div>
      ${renderGameDetailsBlock(game)}
      ${predictionRow}
    </div>`;
}

async function renderGameGroup(titleKey, games) {
  if (!games.length) return '';
  const cards = await Promise.all(games.map(renderGameCard));
  return `
    <h3 class="section-title" style="font-size:16px;margin-top:22px;">${t(titleKey)}</h3>
    ${cards.join('')}`;
}

async function renderGamesSection(leagueKey) {
  const container = document.getElementById('games-container');
  container.innerHTML = `<p class="empty-state">${t('common.loading')}</p>`;
  try {
    const games = await api.get(`/leagues/${leagueKey}/games`);
    renderTicker(games);

    if (!games.length) {
      container.innerHTML = `<p class="empty-state">${t('common.noGamesToday')}</p>`;
      return;
    }

    // Organizados por estado: en vivo primero (lo más urgente), luego los
    // que faltan por jugar (para predecir), y al final los ya terminados.
    const live = games.filter((g) => g.status === 'live');
    const upcoming = games.filter((g) => g.status === 'scheduled');
    const finished = games.filter((g) => g.status === 'final');

    const html =
      (await renderGameGroup('sections.liveNow', live)) +
      (await renderGameGroup('sections.upcoming', upcoming)) +
      (await renderGameGroup('sections.finished', finished));

    container.innerHTML = html;
    attachPredictionHandlers(container);
  } catch (err) {
    container.innerHTML = `<p class="empty-state">${t('common.error')}</p>`;
  }
}

function attachPredictionHandlers(container) {
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
        alert(err.message);
      }
    });
  });
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
    alert(err.message);
  }
}

/* ---------------------- Cambio de pestaña de deporte ---------------------- */
async function loadSportSection(sportKey) {
  activeSport = sportKey;
  document.querySelectorAll('.sport-tab').forEach((tab) => {
    tab.classList.toggle('active', tab.dataset.sport === sportKey);
  });

  const leagueKey = PRIMARY_LEAGUE_BY_SPORT[sportKey];
  const isReady = SPORT_READY[sportKey];

  await renderNews(NEWS_SPORT_BY_TAB[sportKey]); // las noticias generales del deporte siempre se muestran

  if (!isReady) {
    ['standings-container', 'players-today-container', 'games-container'].forEach((id) => {
      document.getElementById(id).innerHTML = `<p class="empty-state">${t('common.comingSoon')}</p>`;
    });
    renderTicker([]);
    return;
  }

  await Promise.all([
    renderStandings(leagueKey),
    renderPlayersToday(leagueKey),
    renderGamesSection(leagueKey),
  ]);
}

function initSportTabs() {
  document.querySelectorAll('.sport-tab').forEach((tab) => {
    tab.addEventListener('click', () => loadSportSection(tab.dataset.sport));
  });
}

document.addEventListener('bfb:language-changed', () => loadSportSection(activeSport));

async function initApp() {
  await initI18n();
  initAuth();
  initSportTabs();
  initStatsSearch();
  await loadSportSection('baseball');
}

document.addEventListener('DOMContentLoaded', initApp);
