/**
 * Cliente HTTP hacia el backend de BFB Deportes.
 *
 * - Usa `credentials: 'include'` para enviar/recibir la cookie httpOnly de
 *   sesión (ver backend/app/api/routes/auth.py). El token JWT nunca se toca
 *   ni se guarda desde JavaScript, precisamente para reducir el riesgo de
 *   robo de sesión por XSS.
 * - BASE_URL apunta al mismo origen por defecto (backend sirviendo también
 *   el frontend). Si despliegas el frontend en otro dominio, cambia esto.
 */
const API_BASE_URL = `${window.location.origin}/api/v1`;

class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

async function apiRequest(path, { method = 'GET', body = null } = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    credentials: 'include',
    headers: body ? { 'Content-Type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined,
  });

  if (response.status === 204) return null;

  let data = null;
  try {
    data = await response.json();
  } catch (_) {
    data = null;
  }

  if (!response.ok) {
    const message = (data && data.detail) || 'Error de comunicación con el servidor.';
    throw new ApiError(message, response.status);
  }

  return data;
}

const api = {
  get: (path) => apiRequest(path),
  post: (path, body) => apiRequest(path, { method: 'POST', body }),
  patch: (path, body) => apiRequest(path, { method: 'PATCH', body }),
  delete: (path) => apiRequest(path, { method: 'DELETE' }),
};
