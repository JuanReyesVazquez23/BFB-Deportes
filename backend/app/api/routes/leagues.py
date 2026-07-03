from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.sport import League, Sport, Team
from app.schemas.sport import LeagueOut, SportOut, TeamOut

router = APIRouter(tags=["leagues"])


@router.get("/sports", response_model=list[SportOut])
def list_sports(db: Session = Depends(get_db)):
    return db.query(Sport).all()


@router.get("/sports/{sport_key}/leagues", response_model=list[LeagueOut])
def list_leagues(sport_key: str, db: Session = Depends(get_db)):
    sport = db.query(Sport).filter(Sport.key == sport_key).first()
    if not sport:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deporte no encontrado.")
    return db.query(League).filter(League.sport_id == sport.id).order_by(League.is_primary.desc()).all()


@router.get("/leagues/{league_key}/teams", response_model=list[TeamOut])
def list_teams(league_key: str, db: Session = Depends(get_db)):
    league = db.query(League).filter(League.key == league_key).first()
    if not league:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Liga no encontrada.")
    return (
        db.query(Team)
        .filter(Team.league_id == league.id)
        .order_by(Team.win_pct.desc())
        .all()
    )


@router.get("/leagues/{league_key}/standings", response_model=list[TeamOut])
def get_standings(league_key: str, db: Session = Depends(get_db)):
    """
    Tabla de posiciones. Los datos se sirven desde la base de datos local,
    que se mantiene actualizada por el proceso de sincronización periódica
    (ver app/services/sync_service.py), no llamando a la API externa en
    cada request de usuario.
    """
    league = db.query(League).filter(League.key == league_key).first()
    if not league:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Liga no encontrada.")
    return (
        db.query(Team)
        .filter(Team.league_id == league.id)
        .order_by(Team.win_pct.desc())
        .all()
    )
