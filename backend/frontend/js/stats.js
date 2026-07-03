/**
 * Apartado de estadísticas: el usuario decide si busca por equipo o por
 * jugador. Por ahora la búsqueda es por ID (ver nota en README sobre el
 * próximo paso: un endpoint de búsqueda por nombre con autocompletado).
 */
function initStatsSearch() {
  const form = document.getElementById('stats-form');
  if (!form) return;

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const type = document.getElementById('stats-type').value;
    const idValue = document.getElementById('stats-id').value.trim();
    const resultEl = document.getElementById('stats-result');

    if (!idValue) return;

    resultEl.textContent = t('common.loading');
    try {
      const data = await api.get(`/stats/${type}/${idValue}`);
      resultEl.textContent = JSON.stringify(data, null, 2);
    } catch (err) {
      resultEl.textContent = err.message;
    }
  });
}
