/**
 * Panel de administración mínimo: solo borra equipos incorrectos a mano.
 *
 * Gesto de entrada: 5 taps en el footer, sin ningún popup ni contraseña
 * nueva — tal cual se pidió. La protección real está en el backend
 * (get_current_admin_user, ver app/api/deps.py): si el usuario logueado no
 * está en ADMIN_USERNAMES, el panel simplemente no muestra nada útil y las
 * peticiones al backend responden 403. No hay una segunda contraseña; se
 * reutiliza la sesión que ya existe para favoritos/predicciones.
 */
const ADMIN_LEAGUE_KEYS = ['mlb', 'nba', 'epl', 'laliga', 'seriea', 'bundesliga', 'ligue1', 'champions_league'];

let adminTapCount = 0;
let adminTapTimer = null;

function toggleAdminPanel() {
  const panel = document.getElementById('admin-panel');
  if (!panel) return;
  // Si quien toca no es el admin (o no ha iniciado sesión), los 5 taps no
  // hacen nada visible — nada distingue "no soy admin" de "no pasó nada".
  if (!window.currentUser?.is_admin) return;
  panel.classList.toggle('hidden');
  if (!panel.classList.contains('hidden')) {
    renderAdminLeagueOptions();
    loadAdminLeagues();
  }
}

function renderAdminLeagueOptions() {
  const select = document.getElementById('admin-league-select');
  if (!select || select.dataset.filled) return;
  select.innerHTML = ADMIN_LEAGUE_KEYS.map((key) => `<option value="${key}">${key}</option>`).join('');
  select.dataset.filled = 'true';
}

async function loadAdminTeams() {
  const select = document.getElementById('admin-league-select');
  const listEl = document.getElementById('admin-team-list');
  if (!select || !listEl) return;

  listEl.innerHTML = 'Cargando…';
  try {
    const teams = await api.get(`/admin/teams?league_key=${select.value}`);
    if (!teams.length) {
      listEl.innerHTML = '<p>No hay equipos en esta liga.</p>';
    } else {
      listEl.innerHTML = teams
        .map(
          (team) => `
        <div class="admin-team-row" data-team-id="${team.id}">
          <span>
            ${team.name || '(sin nombre)'}
            ${team.is_placeholder ? ' · placeholder' : ''}
            ${!team.conference && !team.division ? ' · sin conferencia/división' : ''}
          </span>
          <button class="btn btn-danger btn-small admin-delete-btn" data-team-id="${team.id}" data-team-name="${team.name || ''}">
            Borrar
          </button>
        </div>`
        )
        .join('');

      listEl.querySelectorAll('.admin-delete-btn').forEach((btn) => {
        btn.addEventListener('click', () => handleAdminDelete(btn.dataset.teamId, btn.dataset.teamName));
      });
    }
  } catch (err) {
    listEl.innerHTML = `<p>${err.message}</p>`;
  }

  loadExcludedTeams();
}

async function loadExcludedTeams() {
  const select = document.getElementById('admin-league-select');
  const listEl = document.getElementById('admin-excluded-list');
  if (!select || !listEl) return;

  try {
    const excluded = await api.get(`/admin/excluded-teams?league_key=${select.value}`);
    if (!excluded.length) {
      listEl.innerHTML = '';
      return;
    }
    listEl.innerHTML =
      '<h4 class="stats-section-label">Borrados (se pueden restaurar)</h4>' +
      excluded
        .map(
          (e) => `
      <div class="admin-team-row">
        <span>${e.team_name || e.external_id}</span>
        <button class="btn btn-outline btn-small admin-restore-btn" data-excluded-id="${e.id}">
          Restaurar
        </button>
      </div>`
        )
        .join('');

    listEl.querySelectorAll('.admin-restore-btn').forEach((btn) => {
      btn.addEventListener('click', () => handleAdminRestore(btn.dataset.excludedId));
    });
  } catch (err) {
    listEl.innerHTML = `<p>${err.message}</p>`;
  }
}

async function handleAdminDelete(teamId, teamName) {
  const confirmed = window.confirm(
    `¿Borrar "${teamName}"? También borra sus partidos, jugadores y favoritos asociados. Puedes restaurarlo después desde "Borrados" si te equivocas.`
  );
  if (!confirmed) return;

  try {
    await api.delete(`/admin/teams/${teamId}`);
    loadAdminTeams();
  } catch (err) {
    window.alert(err.message);
  }
}

async function handleAdminRestore(excludedId) {
  try {
    await api.delete(`/admin/excluded-teams/${excludedId}`);
    window.alert('Restaurado. Puede tardar hasta 5 minutos en volver a aparecer (la próxima sincronización lo recrea).');
    loadAdminTeams();
  } catch (err) {
    window.alert(err.message);
  }
}

async function loadAdminLeagues() {
  const listEl = document.getElementById('admin-leagues-list');
  if (!listEl) return;

  listEl.innerHTML = 'Cargando…';
  try {
    const leagues = await api.get('/admin/leagues');
    listEl.innerHTML = leagues
      .map(
        (lg) => `
      <div class="admin-team-row">
        <span>
          ${lg.name} · ${lg.team_count} equipo(s)
          ${!lg.sync_enabled ? ' · <strong>borrada</strong>' : ''}
        </span>
        ${
          lg.sync_enabled
            ? `<button class="btn btn-danger btn-small admin-delete-league-btn" data-league-key="${lg.key}" data-league-name="${lg.name}">Borrar liga</button>`
            : `<button class="btn btn-outline btn-small admin-enable-league-btn" data-league-key="${lg.key}">Reactivar</button>`
        }
      </div>`
      )
      .join('');

    listEl.querySelectorAll('.admin-delete-league-btn').forEach((btn) => {
      btn.addEventListener('click', () => handleDeleteLeague(btn.dataset.leagueKey, btn.dataset.leagueName));
    });
    listEl.querySelectorAll('.admin-enable-league-btn').forEach((btn) => {
      btn.addEventListener('click', () => handleEnableLeague(btn.dataset.leagueKey));
    });
  } catch (err) {
    listEl.innerHTML = `<p>${err.message}</p>`;
  }
}

async function handleDeleteLeague(leagueKey, leagueName) {
  const confirmed = window.confirm(
    `¿Borrar TODA la liga "${leagueName}"? Esto borra todos sus equipos, partidos, jugadores y favoritos, y detiene su sincronización automática (útil para un evento ya pasado). Se puede reactivar después desde este mismo panel.`
  );
  if (!confirmed) return;

  try {
    await api.delete(`/admin/leagues/${leagueKey}`);
    loadAdminLeagues();
  } catch (err) {
    window.alert(err.message);
  }
}

async function handleEnableLeague(leagueKey) {
  try {
    await api.post(`/admin/leagues/${leagueKey}/enable`, {});
    window.alert('Reactivada. Sus datos se vuelven a sincronizar solos en los próximos minutos.');
    loadAdminLeagues();
  } catch (err) {
    window.alert(err.message);
  }
}

function initAdminPanel() {
  const footer = document.getElementById('app-footer');
  const loadBtn = document.getElementById('admin-load-btn');
  if (footer) {
    footer.addEventListener('click', () => {
      adminTapCount += 1;
      clearTimeout(adminTapTimer);
      adminTapTimer = setTimeout(() => {
        adminTapCount = 0;
      }, 2000);
      if (adminTapCount >= 5) {
        adminTapCount = 0;
        toggleAdminPanel();
      }
    });
  }
  if (loadBtn) loadBtn.addEventListener('click', loadAdminTeams);
}

document.addEventListener('DOMContentLoaded', initAdminPanel);
