from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_db
from app.models.sport import Game, League
from app.schemas.sport import GameDetailOut, GameOut

router = APIRouter(tags=["games"])


@router.get("/leagues/{league_key}/games", response_model=list[GameOut])
def list_games(
    league_key: str,
    game_date: date | None = Query(default=None, description="Fecha (YYYY-MM-DD). Por defecto: hoy."),
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
):
    league = db.query(League).filter(League.key == league_key).first()
    if not league:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Liga no encontrada.")

    target_date = game_date or datetime.now(timezone.utc).date()
    query = (
        db.query(Game)
        .options(joinedload(Game.home_team), joinedload(Game.away_team))
        .filter(Game.league_id == league.id)
        .filter(Game.start_time >= datetime.combine(target_date, datetime.min.time(), tzinfo=timezone.utc))
        .filter(Game.start_time < datetime.combine(target_date, datetime.max.time(), tzinfo=timezone.utc))
    )
    if status_filter:
        query = query.filter(Game.status == status_filter)

    return query.order_by(Game.start_time.asc()).all()


@router.get("/games/{game_id}", response_model=GameDetailOut)
def get_game_detail(game_id: int, db: Session = Depends(get_db)):
    """
    Detalle completo de un juego: incluye 'details' (JSON) con información
    específica del deporte, por ejemplo en béisbol: pitcher ganador,
    perdedor, salvamento y líderes ofensivos del juego.
    """
    game = (
        db.query(Game)
        .options(joinedload(Game.home_team), joinedload(Game.away_team))
        .filter(Game.id == game_id)
        .first()
    )
    if not game:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Partido no encontrado.")
    return game
