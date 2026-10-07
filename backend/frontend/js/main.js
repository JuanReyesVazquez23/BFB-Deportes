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

/* ---------------------- Postemporada (bracket) ----------------------
   Cuadro dibujado en SVG (como el "Panorama de la Postemporada" de MLB):
   Liga Americana a la izquierda, Nacional a la derecha y la Serie Mundial
   al centro. Los datos vienen de GET /postseason/bracket (siempre 5 series
   por liga + la Serie Mundial; un equipo null = por definir). */
const PS_GEO = {
  R: 31, // semi-diagonal del rombo de cada equipo
  W: 1000,
  H: 664,
  col: [60, 172, 284, 396],
  center: 500,
  centerY: 355,
};
const PS_REFRESH_MS = 60000;
let postseasonTimer = null;

function stopPostseasonPolling() {
  if (postseasonTimer) {
    clearInterval(postseasonTimer);
    postseasonTimer = null;
  }
}

function startPostseasonPolling() {
  stopPostseasonPolling();
  postseasonTimer = setInterval(() => {
    if (document.hidden || activeView !== 'postseason') return;
    renderPostseason(true);
  }, PS_REFRESH_MS);
}

function psColor(value) {
  return /^#[0-9a-fA-F]{3,8}$/.test(value || '') ? value : '#3d3d43';
}

function psRoundLabel(series) {
  if (series.round === 'WS') return t('postseason.WS');
  if (series.round === 'WC') return `${series.league} ${t('postseason.WC')}`;
  return `${series.league}${series.round === 'DS' ? 'DS' : 'CS'}`;
}

function psPoints(cx, cy, r) {
  return `${cx},${cy - r} ${cx + r},${cy} ${cx},${cy + r} ${cx - r},${cy}`;
}

/* Un equipo (rombo con logo, sembrado y victorias) o un rombo vacío. */
function psNode(node) {
  const { team, x, y, showWins } = node;
  const r = node.r || PS_GEO.R;
  if (!team) {
    return `<polygon class="ps-diamond ps-empty" points="${psPoints(x, y, r)}"><title>${esc(t('postseason.tbd'))}</title></polygon>`;
  }
  const cls = `ps-node${team.eliminated ? ' ps-out' : ''}${team.is_winner ? ' ps-win' : ''}`;
  const logo = safeImg(team.logo_url);
  const side = r * 1.2;
  const inner = logo
    ? `<image href="${esc(logo)}" x="${x - side / 2}" y="${y - side / 2}" width="${side}" height="${side}" preserveAspectRatio="xMidYMid meet"/>`
    : `<text class="ps-abbr" x="${x}" y="${y}">${esc(team.abbreviation || '')}</text>`;
  const seed = team.seed != null
    ? `<g class="ps-seed"><circle cx="${x - r * 0.62}" cy="${y - r * 0.62}" r="9"/><text x="${x - r * 0.62}" y="${y - r * 0.62}">${esc(team.seed)}</text></g>`
    : '';
  const wins = showWins
    ? `<g class="ps-wins"><rect x="${x + r * 0.32}" y="${y + r * 0.32}" width="22" height="19" rx="5"/><text x="${x + r * 0.32 + 11}" y="${y + r * 0.32 + 10}">${Number(team.wins)}</text></g>`
    : '';
  const title = `${team.name || team.abbreviation}${team.seed != null ? ` · #${team.seed}` : ''}${showWins ? ` · ${Number(team.wins)}` : ''}`;
  return `<g class="${cls}"><title>${esc(title)}</title>
    <polygon class="ps-diamond" stroke="${psColor(team.color)}" points="${psPoints(x, y, r)}"/>
    ${inner}${seed}${wins}</g>`;
}

/* Líneas en codo desde cada entrada hasta el nodo de la serie siguiente. */
function psConnectors(inputs, target, dir, series) {
  const r = PS_GEO.R;
  const endX = target.x - dir * r;
  const lines = inputs.map((n) => {
    const startX = n.x + dir * r;
    const midX = (startX + endX) / 2;
    const win = n.team && n.team.is_winner ? ' win' : '';
    return `<path class="ps-line${win}" d="M${startX} ${n.y} H${midX} V${target.y} H${endX}"/>`;
  });
  const startX = inputs[0].x + dir * r;
  const live = series && series.status === 'live'
    ? `<circle class="ps-live-dot" cx="${(startX + endX) / 2}" cy="${target.y}" r="4.5"/>`
    : '';
  return lines.join('') + live;
}

function psSeriesDone(series) {
  return !!series && ['live', 'in_progress', 'final'].includes(series.status);
}

/* Un lado del cuadro (dir = 1 liga Americana, -1 liga Nacional, espejo). */
function psSide(league, list, ws, dir) {
  const slot = (name) => list.find((s) => s.slot === name);
  const wcA = slot('WC_A'), wcB = slot('WC_B'), dsA = slot('DS_A'), dsB = slot('DS_B'), cs = slot('CS');
  if (!wcA || !wcB || !dsA || !dsB || !cs || !ws) return '';
  const X = (i) => (dir > 0 ? PS_GEO.col[i] : PS_GEO.W - PS_GEO.col[i]);
  const cy = PS_GEO.centerY;
  const N = (series, idx, col, y) => ({ team: series.teams[idx], x: X(col), y, showWins: psSeriesDone(series) });

  const wcA0 = N(wcA, 0, 0, 95), wcA1 = N(wcA, 1, 0, 185);
  const wcB0 = N(wcB, 0, 0, 415), wcB1 = N(wcB, 1, 0, 505);
  const dsA0 = N(dsA, 0, 1, 140), dsA1 = N(dsA, 1, 1, 250);
  const dsB0 = N(dsB, 0, 1, 460), dsB1 = N(dsB, 1, 1, 570);
  const cs0 = N(cs, 0, 2, 195), cs1 = N(cs, 1, 2, 515);
  const wsIdx = dir > 0 ? 0 : 1;
  const wsN = N(ws, wsIdx, 3, cy);

  const lines =
    psConnectors([wcA0, wcA1], dsA0, dir, wcA) +
    psConnectors([wcB0, wcB1], dsB0, dir, wcB) +
    psConnectors([dsA0, dsA1], cs0, dir, dsA) +
    psConnectors([dsB0, dsB1], cs1, dir, dsB) +
    psConnectors([cs0, cs1], wsN, dir, cs);
  const nodes = [wcA0, wcA1, wcB0, wcB1, dsA0, dsA1, dsB0, dsB1, cs0, cs1, wsN].map(psNode).join('');

  const mid = (a, b) => (X(a) + X(b)) / 2;
  const label = (x, main, sub) =>
    `<text class="ps-label" x="${x}" y="634">${esc(main)}</text><text class="ps-sub" x="${x}" y="650">${esc(sub)}</text>`;
  const bestOf = (n) => `${t('postseason.bestOf')} ${n}`;
  const labels =
    label(mid(0, 1), t('postseason.WC').toUpperCase(), bestOf(wcA.best_of)) +
    label(mid(1, 2), `${league}DS`, bestOf(dsA.best_of)) +
    label(mid(2, 3), `${league}CS`, bestOf(cs.best_of));
  const leagueTitle = `<text class="ps-league" x="${dir > 0 ? 30 : PS_GEO.W - 30}" y="30" text-anchor="${dir > 0 ? 'start' : 'end'}">${esc(t(`postseason.${league}`).toUpperCase())}</text>`;

  return `<g>${lines}${nodes}${labels}${leagueTitle}</g>`;
}

/* Centro: Serie Mundial y campeón. */
function psCenter(ws, season) {
  const cx = PS_GEO.center, cy = PS_GEO.centerY;
  const champ = (ws.teams || []).find((tm) => tm && tm.is_winner) || null;
  const rBig = 46;
  const left = ws.teams[0], right = ws.teams[1];
  const lines = [
    `<path class="ps-line${left && left.is_winner ? ' win' : ''}" d="M${PS_GEO.col[3] + PS_GEO.R} ${cy} H${cx - rBig}"/>`,
    `<path class="ps-line${right && right.is_winner ? ' win' : ''}" d="M${PS_GEO.W - PS_GEO.col[3] - PS_GEO.R} ${cy} H${cx + rBig}"/>`,
    ws.status === 'live' ? `<circle class="ps-live-dot" cx="${cx - rBig - 18}" cy="${cy}" r="4.5"/><circle class="ps-live-dot" cx="${cx + rBig + 18}" cy="${cy}" r="4.5"/>` : '',
  ].join('');
  const node = champ
    ? psNode({ team: { ...champ, eliminated: false, is_winner: true }, x: cx, y: cy, r: rBig, showWins: false })
    : `<polygon class="ps-diamond ps-empty ps-ws-empty" points="${psPoints(cx, cy, rBig)}"><title>${esc(t('postseason.WS'))}</title></polygon>`;

  const wins = psSeriesDone(ws) && left && right
    ? `${esc(left.abbreviation)} ${Number(left.wins)} – ${Number(right.wins)} ${esc(right.abbreviation)}`
    : '';
  const caption = champ
    ? `<text class="ps-label ps-champ" x="${cx}" y="${cy + rBig + 28}">${esc(t('postseason.champion').toUpperCase())}</text>
       <text class="ps-sub" x="${cx}" y="${cy + rBig + 46}">${esc(champ.name || champ.abbreviation)}</text>`
    : `<text class="ps-sub" x="${cx}" y="${cy + rBig + 28}">${esc(t('postseason.bestOf'))} ${Number(ws.best_of)}</text>`;
  return `<g>${lines}
    <text class="ps-ws-title" x="${cx}" y="${cy - rBig - 40}">${esc(t('postseason.WS').toUpperCase())}</text>
    <text class="ps-sub" x="${cx}" y="${cy - rBig - 20}">${esc(season)}</text>
    ${node}
    ${wins ? `<text class="ps-label" x="${cx}" y="${cy + rBig + (champ ? 66 : 48)}">${wins}</text>` : ''}
    ${caption}</g>`;
}

function renderBracketSvg(data) {
  const ws = data.world_series;
  if (!ws) return '';
  return `<svg class="ps-svg" viewBox="0 0 ${PS_GEO.W} ${PS_GEO.H}" role="img" aria-label="${esc(t('postseason.aria'))}" xmlns="http://www.w3.org/2000/svg">
    ${psSide('AL', data.al || [], ws, 1)}
    ${psSide('NL', data.nl || [], ws, -1)}
    ${psCenter(ws, data.season)}
  </svg>`;
}

/* Tarjeta con el detalle de una serie (marcadores juego por juego). */
function renderSeriesCard(series) {
  const teams = (series.teams || []).filter(Boolean);
  const teamRows = teams
    .map(
      (tm) => `
      <div class="series-team${tm.is_winner ? ' winner' : ''}${tm.eliminated ? ' out' : ''}">
        ${tm.logo_url ? `<img src="${esc(safeImg(tm.logo_url))}" alt="" loading="lazy" decoding="async">` : ''}
        <span class="series-seed">${tm.seed != null ? esc(tm.seed) : ''}</span>
        <span class="series-team-name">${esc(tm.abbreviation || tm.name)}</span>
        <span class="series-wins">${Number(tm.wins)}</span>
      </div>`
    )
    .join('');
  const gamesRows = (series.games || [])
    .map((g) => {
      const num = g.game_number != null ? `${t('postseason.gameShort')}${Number(g.game_number)} · ` : '';
      const score = `${esc(g.away_abbreviation)} ${g.away_score ?? 0} · ${g.home_score ?? 0} ${esc(g.home_abbreviation)}`;
      const label =
        g.status === 'final' ? score
          : g.status === 'live' ? `${score} ●`
            : g.date ? esc(formatDate(g.date)) : '';
      return `<div class="series-game ${esc(g.status)}">${num}${label}</div>`;
    })
    .join('');
  return `
    <div class="series-card">
      <div class="series-round">${esc(psRoundLabel(series))} · ${esc(t('postseason.bestOf'))} ${Number(series.best_of)}</div>
      ${teamRows}
      <div class="series-games">${gamesRows}</div>
    </div>`;
}

function renderSeriesDetails(data) {
  const order = { WS: 0, CS: 1, DS: 2, WC: 3 };
  const all = [...(data.al || []), ...(data.nl || []), ...(data.world_series ? [data.world_series] : [])]
    .filter((s) => s.status !== 'pending' && (s.teams || []).every(Boolean) && (s.games || []).length)
    .sort((a, b) => order[a.round] - order[b.round]);
  if (!all.length) return '';
  return `
    <h3 class="ps-detail-title">${esc(t('postseason.details'))}</h3>
    <div class="ps-detail-grid">${all.map(renderSeriesCard).join('')}</div>`;
}

async function renderPostseason(silent = false) {
  const container = document.getElementById('postseason-container');
  if (!container) return;
  if (!silent) container.innerHTML = `<p class="empty-state">${t('common.loading')}</p>`;
  try {
    const data = await api.get('/postseason/bracket');
    if (!data.postseason_active) {
      stopPostseasonPolling();
      container.innerHTML = `<p class="empty-state">${t('postseason.notActive')}</p>`;
      return;
    }
    const prevScroller = container.querySelector('.ps-scroll');
    const prevLeft = prevScroller ? prevScroller.scrollLeft : null;

    const time = data.updated_at
      ? new Date(data.updated_at).toLocaleTimeString(i18nState.lang === 'es' ? 'es-ES' : 'en-US', { hour: '2-digit', minute: '2-digit' })
      : '';
    const champ = data.champion;
    container.innerHTML = `
      <div class="ps-head">
        <h3 class="ps-title">${esc(t('postseason.title'))} <small>${esc(data.season)}</small></h3>
        <div class="ps-meta">
          ${data.stale ? `<span class="ps-stale">${esc(t('postseason.stale'))}</span> · ` : ''}${time ? `${esc(t('postseason.updated'))} ${esc(time)}` : ''}
        </div>
      </div>
      ${champ ? `<div class="ps-champion">🏆 ${esc(t('postseason.champion'))}: ${champ.logo_url ? `<img src="${esc(safeImg(champ.logo_url))}" alt="" decoding="async">` : ''}<strong>${esc(champ.name || champ.abbreviation)}</strong></div>` : ''}
      <p class="ps-hint">${esc(t('postseason.scrollHint'))}</p>
      <div class="ps-scroll">${renderBracketSvg(data)}</div>
      ${renderSeriesDetails(data)}`;

    const scroller = container.querySelector('.ps-scroll');
    if (scroller) {
      scroller.scrollLeft = prevLeft != null ? prevLeft : Math.max(0, (scroller.scrollWidth - scroller.clientWidth) / 2);
    }
    startPostseasonPolling();
  } catch (err) {
    // En una actualización silenciosa se conserva el cuadro que ya estaba en pantalla.
    if (!silent || !container.querySelector('.ps-scroll')) {
      container.innerHTML = `<p class="empty-state">${t('common.error')}</p>`;
    }
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
  if (name !== 'postseason') stopPostseasonPolling();
  if (loadedViews.has(name)) {
    if (name === 'live') renderLiveSection(activeLeague);
    // El cuadro de postemporada cambia con cada juego: se actualiza al volver (sin parpadeo si ya estaba dibujado).
    if (name === 'postseason') renderPostseason(!!document.querySelector('#postseason-container .ps-scroll'));
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
