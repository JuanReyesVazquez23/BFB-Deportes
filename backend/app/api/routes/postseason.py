"""
Panorama de la Postemporada MLB: bracket vivo (Wild Card -> Divisionales ->
Campeonato -> Serie Mundial) construido desde la MLB Stats API.

Fuentes (ambas oficiales, gratuitas y sin key):
  - /schedule con gameType F,D,L,W  -> juegos y marcadores reales.
  - /standings (temporada regular)  -> sembrados #1..#6 por liga.

La lógica de armado vive en app/services/postseason_service.py (pura y
testeable). Aquí solo se orquesta: caché, rate limit y manejo de errores.

Comportamiento:
  - Caché en memoria por temporada: 45 s si hay un juego en vivo, 180 s en
    otro caso y 600 s si todavía no hay postemporada.
  - Si la MLB API falla pero hay una respuesta previa, se devuelve esa con
    stale=true en lugar de romper la página.
  - Si no hay juegos de postemporada, responde postseason_active=false.
"""
import asyncio
import logging
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.rate_limit import enforce_rate_limit
from app.models.sport import League, Team
from app.services import mlb_service
from app.services.postseason_service import build_bracket, has_live_game

logger = logging.getLogger("bfb.postseason")

router = APIRouter(prefix="/postseason", tags=["postseason"])

_TTL_LIVE_SECONDS = 45
_TTL_IDLE_SECONDS = 180
_TTL_INACTIVE_SECONDS = 600
_STANDINGS_TTL_SECONDS = 3600  # los sembrados no cambian durante la postemporada
_STALE_MAX_SECONDS = 6 * 3600  # tope para servir datos viejos si la API falla

# Primera temporada con el formato actual de 12 equipos (3 series de Wild Card por liga).
_MIN_SEASON = 2022

_cache: dict[int, dict] = {}
_standings_cache: dict[int, dict] = {}
_locks: dict[int, asyncio.Lock] = {}


def _lock_for(year: int) -> asyncio.Lock:
    lock = _locks.get(year)
    if lock is None:
        lock = _locks[year] = asyncio.Lock()
    return lock


async def _get_standings(year: int) -> dict | None:
    """Posiciones de temporada regular (cacheadas 1 h). Tolera fallos: devuelve None."""
    now = time.monotonic()
    cached = _standings_cache.get(year)
    if cached and cached["expires_at"] > now:
        return cached["data"]
    try:
        data = await mlb_service.get_standings(year)
    except Exception:
        logger.exception("No se pudieron obtener las posiciones %d para los sembrados.", year)
        return cached["data"] if cached else None
    _standings_cache[year] = {"data": data, "expires_at": now + _STANDINGS_TTL_SECONDS}
    return data


def _load_logos(db: Session) -> dict[str, str | None]:
    """Logos de equipos desde la BD. Si falla, el servicio usa el CDN de MLB."""
    logos: dict[str, str | None] = {}
    try:
        league = db.query(League).filter(League.key == "mlb").first()
        if league:
            for team in db.query(Team).filter(Team.league_id == league.id).all():
                logos[str(team.external_id)] = team.logo_url
    except Exception:
        logger.exception("No se pudieron leer los logos de equipos de la BD.")
    return logos


async def _build_payload(year: int, db: Session) -> tuple[dict, int]:
    schedule = await mlb_service.get_postseason_schedule(year)
    has_games = any(day.get("games") for day in schedule.get("dates", []) or [])
    standings = await _get_standings(year) if has_games else None
    payload = build_bracket(schedule, standings, _load_logos(db) if has_games else {}, season=year)

    if not payload["postseason_active"]:
        ttl = _TTL_INACTIVE_SECONDS
    elif has_live_game(payload):
        ttl = _TTL_LIVE_SECONDS
    else:
        ttl = _TTL_IDLE_SECONDS
    return payload, ttl


@router.get("/bracket")
async def get_bracket(
    request: Request,
    season: int | None = Query(default=None, ge=_MIN_SEASON, le=2100),
    db: Session = Depends(get_db),
):
    """
    Bracket de postemporada de la temporada indicada (default: año actual).

    Respuesta: { season, postseason_active, seeds_available, updated_at, stale,
                 al: [5 series], nl: [5 series], world_series, champion }.
    Cada serie trae: id, slot (WC_A, WC_B, DS_A, DS_B, CS, WS), round, league,
    best_of, status (pending|scheduled|live|in_progress|final), teams (2
    posiciones; null = por definir), winner_id y games.
    """
    enforce_rate_limit(request, bucket="postseason", limit=30, window_seconds=60)

    year = season or datetime.now(timezone.utc).year
    cached = _cache.get(year)
    if cached and cached["expires_at"] > time.monotonic():
        return cached["payload"]

    # Un solo refresco a la vez por temporada: evita varias llamadas idénticas a la MLB API.
    async with _lock_for(year):
        cached = _cache.get(year)
        if cached and cached["expires_at"] > time.monotonic():
            return cached["payload"]
        try:
            payload, ttl = await _build_payload(year, db)
        except Exception:
            logger.exception("No se pudo obtener la postemporada %d.", year)
            if cached and time.monotonic() - cached["built_at"] < _STALE_MAX_SECONDS:
                return {**cached["payload"], "stale": True}
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="No se pudo obtener la postemporada.",
            )
        now = time.monotonic()
        _cache[year] = {"payload": payload, "expires_at": now + ttl, "built_at": now}
        return payload
