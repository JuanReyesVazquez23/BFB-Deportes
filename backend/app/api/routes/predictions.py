from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.prediction import Prediction
from app.models.sport import Game
from app.models.user import User
from app.schemas.prediction import PredictionCreate, PredictionOut
from app.services.probability_service import points_for_prediction

router = APIRouter(prefix="/predictions", tags=["predictions"])


@router.get("/me", response_model=list[PredictionOut])
def list_my_predictions(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return (
        db.query(Prediction)
        .filter(Prediction.user_id == current_user.id)
        .order_by(Prediction.created_at.desc())
        .all()
    )


@router.post("", response_model=PredictionOut, status_code=status.HTTP_201_CREATED)
def create_prediction(
    payload: PredictionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Registra la predicción de un usuario sobre el ganador de un partido.

    Reglas:
    - Solo se puede predecir un partido que aún no ha comenzado (status = scheduled).
    - Solo una predicción por usuario y partido.
    - No se descuentan puntos al predecir; solo se otorgan puntos si acierta,
      una vez el partido finaliza (ver services/sync_service.resolve_predictions).
    """
    game = db.get(Game, payload.game_id)
    if not game:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Partido no encontrado.")

    if game.status != "scheduled":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se puede predecir un partido que aún no ha comenzado.",
        )

    if game.start_time <= datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El partido ya va a comenzar.")

    if payload.predicted_team_id not in (game.home_team_id, game.away_team_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El equipo elegido no participa en este partido.",
        )

    if game.home_win_probability is None:
        probability_of_chosen_team = 0.5
    elif payload.predicted_team_id == game.home_team_id:
        probability_of_chosen_team = game.home_win_probability
    else:
        probability_of_chosen_team = 1 - game.home_win_probability

    prediction = Prediction(
        user_id=current_user.id,
        game_id=game.id,
        predicted_team_id=payload.predicted_team_id,
        probability_at_pick=probability_of_chosen_team,
    )
    db.add(prediction)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ya predijiste este partido.")
    db.refresh(prediction)
    return prediction


@router.get("/potential-points/{game_id}/{team_id}")
def preview_potential_points(game_id: int, team_id: int, db: Session = Depends(get_db)):
    """Permite mostrar en el frontend cuántos puntos se ganarían ANTES de confirmar la predicción."""
    game = db.get(Game, game_id)
    if not game:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Partido no encontrado.")
    if team_id not in (game.home_team_id, game.away_team_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Equipo no participa en este partido.")

    probability = game.home_win_probability if game.home_win_probability is not None else 0.5
    prob_of_team = probability if team_id == game.home_team_id else 1 - probability
    return {"probability": round(prob_of_team, 3), "potential_points": points_for_prediction(prob_of_team)}
