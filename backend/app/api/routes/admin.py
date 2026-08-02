"""
Panel de administración mínimo: solo sirve para ver y borrar manualmente
equipos incorrectos de la base de datos (ej. si la limpieza automática de
sync_service.py no alcanzó a cubrir algún caso). No incluye ninguna otra
función a propósito, para mantener la superficie de riesgo lo más chica
posible.

Protegido por get_current_admin_user (ver app/api/deps.py): requiere una
sesión ya iniciada con un usuario incluido en ADMIN_USERNAMES. No hay un
segundo password ni un sistema nuevo — reutiliza el login que ya existe.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin_user
from app.core.database import get_db
from app.models.sport import League, Team
from app.models.user import User
from app.services.sync_service import delete_teams_cascade

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/teams")
def list_all_teams(
    league_key: str,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin_user),
):
    """
    Lista TODOS los equipos de la liga, incluyendo los que el resto de la
    app oculta (placeholders, sin conferencia asignada, etc.) — a propósito,
    para poder verlos y decidir si hay que borrar alguno a mano.
    """
    league = db.query(League).filter(League.key == league_key).first()
    if not league:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Liga no encontrada.")

    teams = db.query(Team).filter(Team.league_id == league.id).order_by(Team.name).all()
    return [
        {
            "id": t.id,
            "external_id": t.external_id,
            "name": t.name,
            "conference": t.conference,
            "division": t.division,
            "is_placeholder": t.is_placeholder,
            "wins": t.wins,
            "losses": t.losses,
        }
        for t in teams
    ]


@router.delete("/teams/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_team(
    team_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin_user),
):
    """Borra un equipo y todo lo que dependa de él (partidos, jugadores, favoritos)."""
    team = db.get(Team, team_id)
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Equipo no encontrado.")

    delete_teams_cascade(db, [team_id])
    db.commit()
    return None
