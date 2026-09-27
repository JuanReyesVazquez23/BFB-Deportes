/**
 * escape.js — helpers XSS mínimos, sin dependencias.
 *
 * - esc(value): escapa &<>"' para interpolar texto en innerHTML.
 * - safeUrl(url): allowlist de URLs para href/src. Solo admite http:, https:
 *   y rutas relativas (/... o sin esquema). Cualquier otro esquema
 *   (javascript:, data:, vbscript:, file:) devuelve '#'.
 * - safeImg(url): igual que safeUrl pero admite además data:image/* (logos
 *   embebidos). El resto de data: se rechaza.
 */

function esc(value) {
  if (value === null || value === undefined) return '';
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function _isHttpUrl(parsed) {
  return parsed.protocol === 'http:' || parsed.protocol === 'https:';
}

function safeUrl(value) {
  if (value === null || value === undefined) return '#';
  const raw = String(value).trim();
  if (!raw || raw.startsWith('#')) return raw || '#';
  // Rutas relativas ("/x", "x/y", "./x", "?q=1") sin esquema: seguras.
  if (raw.startsWith('/') || raw.startsWith('./') || raw.startsWith('../') || raw.startsWith('?')) return raw;
  try {
    const parsed = new URL(raw, window.location.origin);
    // Si el input no traía esquema, URL lo resolvió contra el origen:
    // solo se acepta si quedó en el mismo origen (relativa real).
    const hasScheme = /^[a-zA-Z][a-zA-Z0-9+.-]*:/.test(raw);
    if (!hasScheme) {
      return parsed.origin === window.location.origin ? raw : '#';
    }
    return _isHttpUrl(parsed) ? parsed.href : '#';
  } catch (_) {
    return '#';
  }
}

function safeImg(value) {
  if (value === null || value === undefined) return '';
  const raw = String(value).trim();
  if (!raw) return '';
  if (raw.startsWith('data:image/')) {
    // data:image/png;base64,... — se acepta solo si no contiene < o ".
    if (/[<"]/.test(raw)) return '';
    return raw;
  }
  const out = safeUrl(raw);
  return out === '#' ? '' : out;
}

// Exposición global (scripts clásicos, sin bundler).
window.esc = esc;
window.safeUrl = safeUrl;
window.safeImg = safeImg;
