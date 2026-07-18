from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.sport import League, Sport, Team
from app.schemas.sport import LeagueOut, SportOut, StandingsGroupOut, TeamOut

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
        .filter(Team.league_id == league.id, Team.is_placeholder.is_(False))
        .order_by(Team.win_pct.desc())
        .all()
    )


@router.get("/leagues/{league_key}/standings", response_model=list[StandingsGroupOut])
def get_standings(league_key: str, db: Session = Depends(get_db)):
    """
    Tabla de posiciones, agrupada por división (o conferencia si no hay
    división, o toda la liga en un solo grupo si no aplica ninguna) con
    "games_back" (partidos detrás del líder del grupo) en vez de un
    porcentaje plano — así se ve como una tabla de posiciones real.

    Los datos se sirven desde la base de datos local, que se mantiene
    actualizada por el proceso de sincronización periódica (ver
    app/services/sync_service.py), no llamando a la API externa en cada
    request de usuario.
    """
    league = db.query(League).filter(League.key == league_key).first()
    if not league:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Liga no encontrada.")

    teams = (
        db.query(Team)
        .filter(Team.league_id == league.id, Team.is_placeholder.is_(False))
        .order_by(Team.win_pct.desc())
        .all()
    )

    groups: dict[str, list[Team]] = {}
    for team in teams:
        group_key = team.division or team.conference or league.name
        groups.setdefault(group_key, []).append(team)

    result = []
    for group_name, group_teams in groups.items():
        leader_wins = group_teams[0].wins
        leader_losses = group_teams[0].losses
        group_out = []
        for team in group_teams:
            games_back = ((leader_wins - team.wins) + (team.losses - leader_losses)) / 2
            team_dict = TeamOut.model_validate(team).model_dump()
            team_dict["games_back"] = round(max(games_back, 0.0), 1)
            group_out.append(team_dict)
        result.append({"group_name": group_name, "teams": group_out})

    return result
