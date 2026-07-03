from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.favorite import Favorite
from app.models.sport import League, Player, Team
from app.models.user import User
from app.schemas.favorite import FavoriteCreate, FavoriteOut

router = APIRouter(prefix="/favorites", tags=["favorites"])


def _validate_target_exists(db: Session, favorite_type: str, target_id: int) -> None:
    model_map = {"team": Team, "player": Player, "league": League}
    model = model_map[favorite_type]
    if not db.get(model, target_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{favorite_type} no encontrado.")


@router.get("/me", response_model=list[FavoriteOut])
def list_my_favorites(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Favorite).filter(Favorite.user_id == current_user.id).all()


@router.post("", response_model=FavoriteOut, status_code=status.HTTP_201_CREATED)
def add_favorite(
    payload: FavoriteCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _validate_target_exists(db, payload.favorite_type, payload.target_id)

    favorite = Favorite(
        user_id=current_user.id,
        favorite_type=payload.favorite_type,
        team_id=payload.target_id if payload.favorite_type == "team" else None,
        player_id=payload.target_id if payload.favorite_type == "player" else None,
        league_id=payload.target_id if payload.favorite_type == "league" else None,
    )
    db.add(favorite)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ya está en tus favoritos.")
    db.refresh(favorite)
    return favorite


@router.delete("/{favorite_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_favorite(
    favorite_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    favorite = db.get(Favorite, favorite_id)
    if not favorite or favorite.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Favorito no encontrado.")
    db.delete(favorite)
    db.commit()
    return None
