from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.core.rate_limit import enforce_rate_limit
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.schemas.user import LanguageUpdate, UserCreate, UserLogin, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session_cookie(response: Response, user_id: int) -> None:
    token = create_access_token(subject=str(user_id))
    response.set_cookie(
        key=settings.COOKIE_NAME,
        value=token,
        httponly=True,  # inaccesible desde JavaScript -> mitiga robo de token por XSS
        samesite="lax",  # mitiga CSRF en peticiones cross-site
        secure=settings.ENV == "production",  # exige HTTPS en producción
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, request: Request, response: Response, db: Session = Depends(get_db)):
    enforce_rate_limit(request, bucket="register")

    existing = (
        db.query(User)
        .filter(or_(User.username == payload.username, User.email == payload.email))
        .first()
    )
    if existing:
        # Mensaje genérico: no revelamos si fue el usuario o el correo el que ya existe.
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Usuario o correo ya registrado.")

    user = User(
        username=payload.username,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        bfb_points=settings.NEW_USER_STARTING_POINTS,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    _set_session_cookie(response, user.id)
    return user


@router.post("/login", response_model=UserOut)
def login(payload: UserLogin, request: Request, response: Response, db: Session = Depends(get_db)):
    enforce_rate_limit(request, bucket="login")

    user = db.query(User).filter(User.username == payload.username).first()

    # Mensaje idéntico tanto si el usuario no existe como si la contraseña es incorrecta,
    # para no permitir enumerar usuarios válidos.
    invalid_credentials = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario o contraseña incorrectos."
    )

    if not user or not verify_password(payload.password, user.hashed_password):
        raise invalid_credentials

    if not user.is_active:
        raise invalid_credentials

    _set_session_cookie(response, user.id)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response):
    response.delete_cookie(settings.COOKIE_NAME, path="/")
    return None


@router.get("/me", response_model=UserOut)
def read_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/me/language", response_model=UserOut)
def update_language(
    payload: LanguageUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_user.preferred_language = payload.preferred_language
    db.commit()
    db.refresh(current_user)
    return current_user
