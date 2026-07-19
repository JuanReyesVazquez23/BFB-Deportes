from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_db
from app.models.sport import Game, League, Player, Sport, Team
from app.services import mlb_service

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/search")
def search_entities(
    q: str = Query(min_length=2, description="Nombre a buscar (mínimo 2 caracteres)"),
    entity_type: str = Query(default="team", alias="type", pattern="^(team|player)$"),
    sport_key: str = Query(alias="sport", pattern="^(baseball|football|basketball)$"),
    db: Session = Depends(get_db),
):
    """
    Búsqueda por nombre para el autocompletado del buscador de estadísticas.
    Nunca se busca por ID: el usuario escribe un nombre y elige de la lista.

    IMPORTANTE: "sport" es obligatorio y nunca se cruzan deportes — si la
    página está en Fútbol, jamás debe aparecer un resultado de béisbol o
    basketball, y viceversa.
    """
    sport = db.query(Sport).filter(Sport.key == sport_key).first()
    if not sport:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deporte no encontrado.")

    if entity_type == "player":
        matches = (
            db.query(Player)
            .join(Team, Player.team_id == Team.id)
            .join(League, Team.league_id == League.id)
            .options(joinedload(Player.team))
            .filter(Player.full_name.ilike(f"%{q}%"), League.sport_id == sport.id)
            .limit(10)
            .all()
        )
        return [
            {
                "id": p.id,
                "type": "player",
                "label": p.full_name,
                "sublabel": f"{p.position or ''} · {p.team.name if p.team else ''}".strip(" ·"),
            }
            for p in matches
        ]

    matches = (
        db.query(Team)
        .join(League, Team.league_id == League.id)
        .filter(Team.name.ilike(f"%{q}%"), Team.is_placeholder.is_(False), League.sport_id == sport.id)
        .limit(10)
        .all()
    )
    return [
        {
            "id": t.id,
            "type": "team",
            "label": t.name,
            "sublabel": t.division or t.city or "",
            "logo_url": t.logo_url,
        }
        for t in matches
    ]


@router.get("/team/{team_id}")
def team_stats(team_id: int, db: Session = Depends(get_db)):
    """Perfil real de un equipo: récord, posición y sus últimos partidos jugados."""
    team = db.get(Team, team_id)
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Equipo no encontrado.")

    recent_games = (
        db.query(Game)
        .options(joinedload(Game.home_team), joinedload(Game.away_team))
        .filter(Game.status == "final")
        .filter((Game.home_team_id == team.id) | (Game.away_team_id == team.id))
        .order_by(Game.start_time.desc())
        .limit(5)
        .all()
    )

    def _result_line(game) -> dict:
        is_home = game.home_team_id == team.id
        team_score = game.home_score if is_home else game.away_score
        rival = game.away_team if is_home else game.home_team
        rival_score = game.away_score if is_home else game.home_score
        outcome = "W" if (team_score or 0) > (rival_score or 0) else "L"
        return {
            "date": game.start_time.date().isoformat(),
            "rival": rival.name,
            "score": f"{team_score}-{rival_score}",
            "outcome": outcome,
        }

    return {
        "id": team.id,
        "name": team.name,
        "short_name": team.short_name,
        "logo_url": team.logo_url,
        "league": team.league.name if team.league else None,
        "record": {"wins": team.wins, "losses": team.losses, "ties": team.ties, "win_pct": team.win_pct},
        "division": team.division,
        "conference": team.conference,
        "recent_results": [_result_line(g) for g in recent_games],
    }


async def _build_player_profile(player_id: int, db: Session) -> dict:
    """
    Construye el perfil completo de un jugador (posición, equipo, y
    estadísticas reales si es de MLB). Función compartida entre el
    endpoint de un solo jugador y el de comparación, para no duplicar
    la misma lógica dos veces.
    """
    player = (
        db.query(Player)
        .options(joinedload(Player.team).joinedload(Team.league))
        .filter(Player.id == player_id)
        .first()
    )
    if not player:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Jugador no encontrado.")

    batting_stats = None
    pitching_stats = None

    is_mlb_player = player.team and player.team.league and player.team.league.data_provider == "mlb_stats_api"
    if is_mlb_player:
        try:
            current_season = datetime.now(timezone.utc).year
            raw_stats = await mlb_service.get_player_season_stats(int(player.external_id), current_season)
            batting_stats = mlb_service.extract_batting_stats(raw_stats["hitting"])
            pitching_stats = mlb_service.extract_pitching_stats(raw_stats["pitching"])
        except Exception:
            pass  # el perfil se muestra igual, solo sin números, en vez de fallar la petición completa

    return {
        "id": player.id,
        "full_name": player.full_name,
        "position": player.position,
        "jersey_number": player.jersey_number,
        "team": {
            "id": player.team.id,
            "name": player.team.name,
            "logo_url": player.team.logo_url,
        }
        if player.team
        else None,
        "sport_id": player.team.league.sport_id if player.team and player.team.league else None,
        "batting_stats": batting_stats,
        "pitching_stats": pitching_stats,
    }


@router.get("/player/{player_id}")
async def player_stats(player_id: int, db: Session = Depends(get_db)):
    """
    Perfil real de un jugador: posición, número, equipo, y sus estadísticas
    reales de la temporada actual (home runs, hits, OBP, etc. si es
    bateador; wins, ERA, ponches si es pitcher).

    Los números se consultan en vivo a MLB Stats API en el momento de la
    búsqueda (solo para jugadores de esa liga por ahora). Si la consulta
    externa falla, se muestra igual el perfil del jugador sin números en
    vez de romper la página completa.
    """
    profile = await _build_player_profile(player_id, db)
    profile.pop("sport_id", None)  # detalle interno, no se expone en el perfil individual
    return profile


@router.get("/players/compare")
async def compare_players(
    id_a: int = Query(description="ID del primer jugador"),
    id_b: int = Query(description="ID del segundo jugador"),
    db: Session = Depends(get_db),
):
    """
    Compara dos jugadores lado a lado. NUNCA se permite comparar jugadores
    de deportes distintos (ej. un jugador de MLB contra uno de NBA) — se
    valida explícitamente y se rechaza con 400 si no coinciden.
    """
    if id_a == id_b:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Elige dos jugadores distintos.")

    player_a = await _build_player_profile(id_a, db)
    player_b = await _build_player_profile(id_b, db)

    if player_a["sport_id"] is None or player_b["sport_id"] is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se pudo determinar el deporte de uno de los jugadores.",
        )
    if player_a["sport_id"] != player_b["sport_id"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se pueden comparar jugadores de deportes distintos.",
        )

    player_a.pop("sport_id", None)
    player_b.pop("sport_id", None)
    return {"player_a": player_a, "player_b": player_b}
