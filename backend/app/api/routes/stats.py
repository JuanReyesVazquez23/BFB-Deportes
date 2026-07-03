from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.sport import Player, Team

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/team/{team_id}")
def team_stats(team_id: int, db: Session = Depends(get_db)):
    team = db.get(Team, team_id)
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Equipo no encontrado.")
    return {
        "id": team.id,
        "name": team.name,
        "wins": team.wins,
        "losses": team.losses,
        "ties": team.ties,
        "win_pct": team.win_pct,
        "division": team.division,
        "conference": team.conference,
    }


@router.get("/player/{player_id}")
def player_stats(player_id: int, db: Session = Depends(get_db)):
    player = db.get(Player, player_id)
    if not player:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Jugador no encontrado.")
    return {
        "id": player.id,
        "full_name": player.full_name,
        "position": player.position,
        "jersey_number": player.jersey_number,
        "team_id": player.team_id,
    }
