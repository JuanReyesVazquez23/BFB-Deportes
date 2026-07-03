"""
Seguridad: hashing de contraseñas (bcrypt) y tokens de sesión (JWT).

Decisiones de seguridad tomadas aquí:
- Contraseñas: nunca se guardan en texto plano, se usa bcrypt (passlib).
- Sesión: JWT firmado con SECRET_KEY, con expiración obligatoria.
- El token se entrega al cliente como cookie httpOnly (no accesible desde JS),
  para reducir el riesgo de robo de token vía XSS. Se usa SameSite=Lax para
  mitigar CSRF en peticiones cross-site.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(subject: str, expires_minutes: Optional[int] = None) -> str:
    """Crea un JWT cuyo 'sub' es el identificador del usuario (string)."""
    expire_minutes = expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    expire = datetime.now(timezone.utc) + timedelta(minutes=expire_minutes)
    payload = {"sub": subject, "exp": expire, "iat": datetime.now(timezone.utc)}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[str]:
    """Devuelve el 'sub' (id de usuario) si el token es válido, o None si no lo es."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None
