/**
 * Historial de predicciones del usuario y aviso de resultados nuevos.
 *
 * Cómo funciona el aviso: cada predicción tiene un campo "seen". Al
 * resolverse (cuando el partido termina), el backend la marca seen=false.
 * Cada vez que el usuario entra o refresca con sesión iniciada, se revisa
 * el historial buscando resultados con seen=false, se muestra un aviso
 * flotante por cada uno, y se marcan como vistos para no repetir el aviso.
 */

function showToast(message, kind = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast toast-${kind}`;
  toast.textContent = message;
  container.appendChild(toast);

  setTimeout(() => toast.classList.add('toast-visible'), 10);
  setTimeout(() => {
    toast.classList.remove('toast-visible');
    setTimeout(() => toast.remove(), 300);
  }, 6000);
}

function formatMatchup(prediction) {
  const game = prediction.game;
  if (!game || !game.home_team || !game.away_team) return '';
  return `${game.away_team.name} @ ${game.home_team.name}`;
}

async function checkForNewPredictionResults() {
  let predictions;
  try {
    predictions = await api.get('/predictions/me');
  } catch (_) {
    return; // sin sesión válida u otro error: no interrumpe el resto de la página
  }

  const unseen = predictions.filter((p) => p.status !== 'pending' && !p.seen);
  if (!unseen.length) return;

  unseen.forEach((p) => {
    const matchup = formatMatchup(p);
    if (p.status === 'correct') {
      showToast(`¡Ganaste! Acertaste ${p.predicted_team?.name || 'tu equipo'} en ${matchup} (+${p.points_awarded} BFB points)`, 'success');
    } else {
      showToast(`Perdiste tu predicción de ${p.predicted_team?.name || ''} en ${matchup} (${p.points_awarded} BFB points)`, 'error');
    }
  });

  api.post('/predictions/me/mark-seen', { prediction_ids: unseen.map((p) => p.id) }).catch(() => {});
}

function renderPredictionHistoryRow(p) {
  const matchup = formatMatchup(p);
  const game = p.game;
  const score = game && game.status === 'final' ? `${game.away_score} - ${game.home_score}` : '';

  const statusLabel = { pending: 'Pendiente', correct: 'Acertaste', incorrect: 'Fallaste' }[p.status] || p.status;
  const statusClass = { pending: '', correct: 'prediction-correct', incorrect: 'prediction-incorrect' }[p.status] || '';

  let pointsTag = '';
  if (p.status === 'correct') {
    pointsTag = `<span class="points-pill">+${p.points_awarded}</span>`;
  } else if (p.status === 'incorrect') {
    pointsTag = `<span class="points-pill points-pill-loss">${p.points_awarded}</span>`;
  }

  return `
    <div class="prediction-row ${statusClass}">
      <div>
        <strong>${p.predicted_team?.name || '—'}</strong>
        <span class="stats-subtitle">${matchup} ${score ? '· ' + score : ''}</span>
      </div>
      <div class="prediction-row-status">
        <span>${statusLabel}</span>
        ${pointsTag}
      </div>
    </div>`;
}

async function openPredictionsModal() {
  const backdrop = document.getElementById('predictions-modal-backdrop');
  const listEl = document.getElementById('predictions-list');
  if (!backdrop || !listEl) return;

  backdrop.classList.remove('hidden');
  listEl.innerHTML = 'Cargando…';

  try {
    const predictions = await api.get('/predictions/me');
    if (!predictions.length) {
      listEl.innerHTML = '<p class="empty-state">Todavía no has hecho ninguna predicción.</p>';
      return;
    }
    listEl.innerHTML = predictions.map(renderPredictionHistoryRow).join('');
  } catch (err) {
    listEl.innerHTML = `<p class="empty-state">${err.message}</p>`;
  }
}

function closePredictionsModal() {
  document.getElementById('predictions-modal-backdrop')?.classList.add('hidden');
}

function initPredictionsModal() {
  document.getElementById('predictions-modal-close')?.addEventListener('click', closePredictionsModal);
  document.getElementById('predictions-modal-backdrop')?.addEventListener('click', (e) => {
    if (e.target.id === 'predictions-modal-backdrop') closePredictionsModal();
  });
}

document.addEventListener('DOMContentLoaded', initPredictionsModal);
