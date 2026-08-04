/**
 * Botón para "instalar" el sitio (agregarlo a la pantalla principal).
 *
 * Solo aparece cuando el navegador realmente lo soporta y lo permite
 * (Chrome/Android dispara el evento beforeinstallprompt cuando el sitio
 * cumple los requisitos de instalación). En navegadores que no lo
 * soportan (ej. Safari/iOS no tiene esta API) el botón nunca aparece —
 * mejor no mostrar nada que mostrar un botón que no haría nada.
 *
 * Se puede cerrar con la "x"; una vez cerrado, no se vuelve a mostrar en
 * este navegador (se guarda en localStorage, no en el servidor — es solo
 * una preferencia de UI de este dispositivo).
 */
let deferredInstallPrompt = null;

function showInstallBanner() {
  if (localStorage.getItem('bfb_install_dismissed') === 'true') return;
  document.getElementById('install-app-banner')?.classList.remove('hidden');
}

function hideInstallBanner() {
  document.getElementById('install-app-banner')?.classList.add('hidden');
}

window.addEventListener('beforeinstallprompt', (e) => {
  e.preventDefault(); // evita el banner nativo del navegador; usamos el nuestro, más discreto
  deferredInstallPrompt = e;
  showInstallBanner();
});

window.addEventListener('appinstalled', () => {
  deferredInstallPrompt = null;
  hideInstallBanner();
});

function initInstallBanner() {
  document.getElementById('install-app-btn')?.addEventListener('click', async () => {
    if (!deferredInstallPrompt) return;
    deferredInstallPrompt.prompt();
    await deferredInstallPrompt.userChoice;
    deferredInstallPrompt = null;
    hideInstallBanner();
  });
  document.getElementById('install-app-dismiss')?.addEventListener('click', () => {
    localStorage.setItem('bfb_install_dismissed', 'true');
    hideInstallBanner();
  });
}

document.addEventListener('DOMContentLoaded', initInstallBanner);
