"""
Rate limiter en memoria, pensado para proteger /auth/login y /auth/register
contra ataques de fuerza bruta.

NOTA: esta implementación guarda el estado en memoria del proceso. Funciona
bien para un solo servidor/worker. Si en producción se despliega con varios
workers o instancias, se recomienda sustituir esto por un backend compartido
(Redis) para que el límite aplique globalmente.
"""
import time
from collections import defaultdict
from threading import Lock

from fastapi import HTTPException, Request, status

from app.core.config import settings

_attempts: dict[str, list[float]] = defaultdict(list)
_lock = Lock()


def enforce_rate_limit(request: Request, bucket: str) -> None:
    """Lanza 429 si la IP supera el número de intentos permitidos en la ventana configurada."""
    client_ip = request.client.host if request.client else "unknown"
    key = f"{bucket}:{client_ip}"
    now = time.time()
    window = settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS
    limit = settings.LOGIN_RATE_LIMIT_ATTEMPTS

    with _lock:
        attempts = [t for t in _attempts[key] if now - t < window]
        if len(attempts) >= limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Demasiados intentos. Inténtalo de nuevo más tarde.",
            )
        attempts.append(now)
        _attempts[key] = attempts
