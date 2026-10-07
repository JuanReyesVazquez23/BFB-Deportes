"""
Panorama de la Postemporada MLB: bracket vivo (Wild Card -> Divisionales ->
Campeonato -> Serie Mundial) construido desde MLB Stats API
(/schedule con gameType F,D,L,W + seriesStatus hidratado).

Se consulta en vivo con caché corta (120s) para no golpear la API en cada
visita; si no hay juegos de postemporada (ej. fuera de octubre),
responde con postseason_active=false y el frontend muestra el aviso.
"""
import logging
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.rate_limit import enforce_rate_limit
from app.models.sport import League, Team
from app.services import mlb_service

logger = logging.getLogger("bfb.postseason")

router = APIRouter(prefix="/postseason", tags=["postseason"])

_CACHE_TTL_SECONDS = 120
_cache: dict = {"expires_at": 0.0, "payload": None}

# gameType -> (round_key, best_of). El orden define las columnas del bracket.
_ROUNDS = [
    ("WC", 3, ("wild card",)),
    ("DS", 5, ("division",)),
    ("CS", 7, ("championship",)),
    ("WS", 7, ("world series",)),
]

_AL_LEAGUE_ID = 103
_NL_LEAGUE_ID = 104


def _map_game_status(detailed: str) -> str:
    state = (detailed or "").lower()
    if "final" in state:
        return "final"
    if "live" in state or "progress" in state or "review" in state:
        return "live"
    return "scheduled"


def _round_of(description: str) -> tuple[str, int] | None:
    desc = (description or "").lower()
    for key, best_of, needles in _ROUNDS:
        if any(n in desc for n in needles):
            return key, best_of
    return None


def _league_of(game: dict, description: str) -> str | None:
    if "world series" in (description or "").lower():
        return None
    try:
        league_id = game["teams"]["home"]["league"]["id"]
    except (KeyError, TypeError):
        return None
    if league_id == _AL_LEAGUE_ID:
        return "AL"
    if league_id == _NL_LEAGUE_ID:
        return "NL"
    return None


def _build_bracket(schedule: dict, logos: dict[str, str | None]) -> dict:
    series: dict[tuple, dict] = {}
    for day in schedule.get("dates", []):
        for game in day.get("games", []):
            desc = game.get("seriesDescription") or ""
            round_info = _round_of(desc)
            if not round_info:
                continue
            round_key, best_of = round_info
            league = _league_of(game, desc)

            home = game.get("teams", {}).get("home", {})
            away = game.get("teams", {}).get("away", {})
            home_team = home.get("team", {})
            away_team = away.get("team", {})
            matchup = tuple(sorted([str(home_team.get("id")), str(away_team.get("id"))]))
            key = (league or "WS", round_key, matchup)

            entry = series.get(key)
            if entry is None:
                entry = {
                    "round": round_key,
                    "league": league,
                    "best_of": best_of,
                    "description": desc,
                    "teams": {},
                    "games": [],
                    "status": "scheduled",
                }
                series[key] = entry

            for side, info in (("home", home), ("away", away)):
                tid = str(info.get("team", {}).get("id"))
                if tid not in entry["teams"]:
                    entry["teams"][tid] = {
                        "id": tid,
                        "name": info.get("team", {}).get("name", ""),
                        "abbreviation": info.get("team", {}).get("abbreviation", ""),
                        "logo_url": logos.get(tid),
                        "seed": info.get("seriesNumber"),
                        "wins": 0,
                    }

            status = _map_game_status(game.get("status", {}).get("detailedState", ""))
            entry["games"].append(
                {
                    "id": game.get("gamePk"),
                    "date": game.get("gameDate"),
                    "status": status,
                    "home_id": str(home_team.get("id")),
                    "away_id": str(away_team.get("id")),
                    "home_score": home.get("score"),
                    "away_score": away.get("score"),
                    "home_abbreviation": home_team.get("abbreviation", ""),
                    "away_abbreviation": away_team.get("abbreviation", ""),
                }
            )
            if status == "live":
                entry["status"] = "live"
            elif status == "final" and entry["status"] == "scheduled":
                entry["status"] = "final"

            short = (game.get("seriesStatus", {}) or {}).get("shortName") or ""
            if short:
                entry["leader_text"] = short

    ordered = sorted(series.values(), key=lambda s: (s["league"] or "WS", s["round"]))
    for entry in ordered:
        # Victorias contadas de los finales reales (no del texto de la API).
        for g in entry["games"]:
            if g["status"] != "final" or g["home_score"] is None or g["away_score"] is None:
                continue
            winner = g["home_id"] if g["home_score"] > g["away_score"] else g["away_id"]
            if winner in entry["teams"]:
                entry["teams"][winner]["wins"] += 1
        entry["teams"] = sorted(
            entry["teams"].values(), key=lambda t: (t["seed"] is None, t["seed"] or 0)
        )
        entry["games"] = sorted(entry["games"], key=lambda g: g["date"] or "")
    return ordered


@router.get("/bracket")
async def get_bracket(
    request: Request,
    season: int | None = Query(default=None, ge=2000, le=2100),
    db: Session = Depends(get_db),
):
    """
    Bracket de postemporada de la temporada indicada (default: año actual).
    Cacheado 120s en memoria; con rate-limit por ser 1 llamada externa.
    """
    enforce_rate_limit(request, bucket="postseason", limit=20, window_seconds=60)

    year = season or datetime.now(timezone.utc).year
    now = time.monotonic()
    if _cache["payload"] is not None and _cache["expires_at"] > now and _cache["payload"].get("season") == year:
        return _cache["payload"]

    try:
        schedule = await mlb_service.get_postseason_schedule(year)
    except Exception:
        logger.exception("No se pudo obtener la postemporada %d.", year)
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudo obtener la postemporada.",
        )

    league = db.query(League).filter(League.key == "mlb").first()
    logos: dict[str, str | None] = {}
    if league:
        for team in db.query(Team).filter(Team.league_id == league.id).all():
            logos[str(team.external_id)] = team.logo_url

    all_series = _build_bracket(schedule, logos)
    payload = {
        "season": year,
        "postseason_active": bool(all_series),
        "al": [s for s in all_series if s["league"] == "AL"],
        "nl": [s for s in all_series if s["league"] == "NL"],
        "world_series": next((s for s in all_series if s["league"] is None), None),
    }
    _cache["payload"] = payload
    _cache["expires_at"] = now + _CACHE_TTL_SECONDS
    return payload
