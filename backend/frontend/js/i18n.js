/**
 * Internacionalización simple basada en diccionarios JSON (es/en).
 * El idioma elegido se guarda en localStorage (dato no sensible: solo una
 * preferencia de interfaz) y, si el usuario tiene sesión iniciada, también
 * se sincroniza con su perfil en el backend.
 */
const i18nState = {
  lang: localStorage.getItem('bfb_lang') || 'es',
  dict: {},
};

async function loadDictionary(lang) {
  const res = await fetch(`i18n/${lang}.json`);
  return res.json();
}

function t(key) {
  const parts = key.split('.');
  let value = i18nState.dict;
  for (const part of parts) {
    value = value?.[part];
  }
  return value ?? key;
}

function applyTranslations() {
  document.querySelectorAll('[data-i18n]').forEach((el) => {
    el.textContent = t(el.dataset.i18n);
  });
  document.querySelectorAll('[data-i18n-placeholder]').forEach((el) => {
    el.placeholder = t(el.dataset.i18nPlaceholder);
  });
  document.documentElement.lang = i18nState.lang;
}

async function setLanguage(lang) {
  i18nState.lang = lang;
  localStorage.setItem('bfb_lang', lang);
  i18nState.dict = await loadDictionary(lang);
  applyTranslations();

  // Si hay sesión activa, guarda la preferencia en el backend también.
  if (window.currentUser) {
    api.patch('/auth/me/language', { preferred_language: lang }).catch(() => {});
  }

  document.dispatchEvent(new CustomEvent('bfb:language-changed', { detail: { lang } }));
}

async function initI18n() {
  i18nState.dict = await loadDictionary(i18nState.lang);
  applyTranslations();
  const selector = document.getElementById('lang-select');
  if (selector) {
    selector.value = i18nState.lang;
    selector.addEventListener('change', (e) => setLanguage(e.target.value));
  }
}
