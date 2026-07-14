from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_db
from app.models.sport import Game, League
from app.schemas.sport import GameDetailOut, GameOut
from app.services import mlb_service, translation_service

router = APIRouter(tags=["games"])


@router.get("/leagues/{league_key}/games", response_model=list[GameOut])
def list_games(
    league_key: str,
    game_date: date | None = Query(default=None, description="Fecha exacta (YYYY-MM-DD). Si no se da, usa una ventana de 24h."),
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
):
    league = db.query(League).filter(League.key == league_key).first()
    if not league:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Liga no encontrada.")

    query = (
        db.query(Game)
        .options(joinedload(Game.home_team), joinedload(Game.away_team))
        .filter(Game.league_id == league.id)
    )

    if game_date:
        # Fecha explícita: se respeta el día calendario exacto pedido.
        query = query.filter(
            Game.start_time >= datetime.combine(game_date, datetime.min.time(), tzinfo=timezone.utc)
        ).filter(Game.start_time < datetime.combine(game_date, datetime.max.time(), tzinfo=timezone.utc))
    else:
        # Sin fecha explícita ("hoy" por defecto): se usa una ventana móvil de
        # 24h hacia atrás y 36h hacia adelante, en vez de un día calendario
        # UTC fijo. Un día calendario fijo pierde partidos que cruzan la
        # medianoche UTC (ej. un juego de la Costa Oeste en vivo a la 1 AM UTC
        # queda fuera de "hoy" aunque esté sucediendo ahora mismo).
        now = datetime.now(timezone.utc)
        query = query.filter(Game.start_time >= now - timedelta(hours=24)).filter(
            Game.start_time <= now + timedelta(hours=36)
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


@router.get("/games/{game_id}/live")
async def get_game_live_situation(
    game_id: int,
    lang: str = Query(default="es", pattern="^(es|en)$"),
    db: Session = Depends(get_db),
):
    """
    Situación en vivo de un juego de MLB (bases, outs, bateador, pitcher,
    última jugada). A diferencia de /games/{id}, esto consulta a MLB
    DIRECTAMENTE en el momento de la petición, sin pasar por la base de
    datos ni esperar al ciclo de sincronización de 5 minutos — así el
    frontend puede sondear este endpoint cada pocos segundos y mostrar
    algo realmente "al momento" mientras el usuario ve el partido.

    lang: si es "es", la descripción de "última jugada" se traduce al
    momento (cambia en cada jugada, así que no tiene sentido guardarla
    traducida). Nombres de jugadores nunca se traducen.
    """
    game = db.query(Game).options(joinedload(Game.league)).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Partido no encontrado.")

    if game.league.data_provider != "mlb_stats_api":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El detalle en vivo solo está disponible para partidos de MLB por ahora.",
        )

    if game.status != "live":
        return {"status": game.status, "situation": None}

    try:
        live_feed = await mlb_service.get_live_feed(int(game.external_id))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="No se pudo obtener el estado en vivo del partido."
        )

    situation = mlb_service.extract_live_situation(live_feed)
    if lang == "es" and situation.get("last_play"):
        situation["last_play"] = translation_service.translate_to_spanish(situation["last_play"]) or situation[
            "last_play"
        ]

    return {"status": game.status, "situation": situation}
