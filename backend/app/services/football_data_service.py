"""
Cliente para football-data.org (https://www.football-data.org).

Elegido para fútbol/Mundial porque, a diferencia de balldontlie, su nivel
gratuito SÍ cubre estas competencias sin necesitar un plan de pago por
deporte: Premier League, La Liga, Serie A, Bundesliga, Ligue 1, Champions
League y el Mundial (12 competencias en total en su nivel gratis). El
propio creador del proyecto (Daniel Freitag, desde 2013) se ha comprometido
públicamente a mantener esas competencias gratis para siempre.

Ventaja adicional confirmada: cada equipo trae su logo real en el campo
"crest" — no hay que adivinar un patrón de CDN como se tuvo que hacer con
MLB o intentar con NBA.

Límite de la cuenta gratuita: 10 peticiones por minuto. Por eso cada
llamada se espacia (ver sync_service.py), igual que con balldontlie.
"""
from datetime import date, timedelta

import httpx

from app.core.config import settings

from app.services.http_client import DEFAULT_HTTP_TIMEOUT as TIMEOUT

# Códigos de competencia de football-data.org (confirmados en su documentación oficial).
COMPETITION_CODES = {
    "epl": "PL",
    "laliga": "PD",
    "bundesliga": "BL1",
    "seriea": "SA",
    "ligue1": "FL1",
    "champions_league": "CL",
    "world_cup": "WC",
}


def _headers() -> dict:
    if not settings.FOOTBALL_DATA_API_KEY:
        raise RuntimeError(
            "Falta configurar FOOTBALL_DATA_API_KEY en el archivo .env. "
            "Obtén un token gratis en https://www.football-data.org/client/register"
        )
    return {"X-Auth-Token": settings.FOOTBALL_DATA_API_KEY}


async def get_teams(league_key: str) -> dict:
    code = COMPETITION_CODES[league_key]
    url = f"{settings.FOOTBALL_DATA_API_BASE}/competitions/{code}/teams"
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(url, headers=_headers())
        resp.raise_for_status()
        return resp.json()


async def get_matches(league_key: str, date_from: date | None = None, date_to: date | None = None) -> dict:
    """
    Partidos de la competencia. Por defecto trae una ventana de "ayer a
    mañana" (3 días) en una sola llamada — football-data.org soporta rango
    de fechas directo, a diferencia de la MLB Stats API que necesita una
    llamada por día.
    """
    code = COMPETITION_CODES[league_key]
    url = f"{settings.FOOTBALL_DATA_API_BASE}/competitions/{code}/matches"
    today = date.today()
    params = {
        "dateFrom": (date_from or today - timedelta(days=1)).isoformat(),
        "dateTo": (date_to or today + timedelta(days=1)).isoformat(),
    }
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(url, params=params, headers=_headers())
        resp.raise_for_status()
        return resp.json()


async def get_standings(league_key: str) -> dict:
    """
    Tabla de posiciones. No disponible (404) para competencias tipo copa/
    torneo con grupos (ej. el Mundial) — quien llama a esto debe evitar
    pedirlo para esas competencias, o manejar el error.
    """
    code = COMPETITION_CODES[league_key]
    url = f"{settings.FOOTBALL_DATA_API_BASE}/competitions/{code}/standings"
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(url, headers=_headers())
        resp.raise_for_status()
        return resp.json()
