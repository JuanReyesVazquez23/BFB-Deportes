"""
Rate limiter en memoria, pensado para proteger /auth/login y /auth/register
contra ataques de fuerza bruta, y los endpoints costosos (búsquedas con
llamadas a APIs externas) contra abuso de cuota.

NOTA: esta implementación guarda el estado en memoria del proceso. Funciona
bien para un solo servidor/worker. Si en producción se despliega con varios
workers o instancias, se recomienda sustituir esto por un backend compartido
(Redis) para que el límite aplique globalmente.
"""
import time
from collections import defaultdict
from threading import Lock
from typing import Optional

from fastapi import HTTPException, Request, status

from app.core.config import settings

_attempts: dict[str, list[float]] = defaultdict(list)
_lock = Lock()

# Tope de buckets en memoria: evita crecimiento ilimitado (un atacante
# rotando IPs/buckets no puede agotar la RAM del proceso).
_MAX_BUCKETS = 10000


def enforce_rate_limit(
    request: Request,
    bucket: str,
    limit: Optional[int] = None,
    window_seconds: Optional[int] = None,
) -> None:
    """
    Lanza 429 si la IP supera el número de intentos permitidos en la ventana.
    Si no se pasan limit/window, se usan los de login (más estrictos).
    """
    client_ip = request.client.host if request.client else "unknown"
    key = f"{bucket}:{client_ip}"
    now = time.time()
    window = window_seconds if window_seconds is not None else settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS
    max_attempts = limit if limit is not None else settings.LOGIN_RATE_LIMIT_ATTEMPTS

    with _lock:
        attempts = [t for t in _attempts[key] if now - t < window]
        if len(attempts) >= max_attempts:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Demasiados intentos. Inténtalo de nuevo más tarde.",
            )
        attempts.append(now)
        _attempts[key] = attempts
        # Evicción: si hay demasiados buckets, se purgan los expirados.
        if len(_attempts) > _MAX_BUCKETS:
            expired = [k for k, v in _attempts.items() if not v or now - v[-1] >= window]
            for k in expired[: len(_attempts) - _MAX_BUCKETS]:
                _attempts.pop(k, None)
