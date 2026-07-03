from typing import Optional

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.orm import Session

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
