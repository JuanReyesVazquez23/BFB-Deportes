from typing import Optional

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User


def get_current_user(
    bfb_session: Optional[str] = Cookie(default=None),
    db: Session = Depends(get_db),
) -> User:
    """
    Obtiene el usuario autenticado a partir de la cookie httpOnly de sesión.
    Lanza 401 si no hay sesión válida.
    """
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No autenticado. Inicia sesión para continuar.",
    )
    if not bfb_session:
        raise credentials_error

    user_id = decode_access_token(bfb_session)
    if user_id is None:
        raise credentials_error

    user = db.get(User, int(user_id))
    if user is None or not user.is_active:
        raise credentials_error

    return user


def get_current_user_optional(
    bfb_session: Optional[str] = Cookie(default=None),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Igual que get_current_user pero devuelve None en vez de lanzar error (para endpoints públicos)."""
    if not bfb_session:
        return None
    user_id = decode_access_token(bfb_session)
    if user_id is None:
        return None
    return db.get(User, int(user_id))


def get_current_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """
    Igual que get_current_user, pero además exige que el usuario esté en
    ADMIN_USERNAMES (ver core/config.py). Se usa solo para el panel de
    administración (borrar equipos incorrectos manualmente) — nunca para
    rutas de uso normal de la app.
    """
    if not settings.is_admin_username(current_user.username):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No autorizado.")
    return current_user
