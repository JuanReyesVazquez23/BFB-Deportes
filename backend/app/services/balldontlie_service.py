"""
Cliente genérico para balldontlie.io, usado para basketball (NBA, WNBA,
NCAAB) y fútbol (EPL, La Liga, Serie A, Bundesliga, Ligue 1, MLS,
Champions League y el Mundial).

Requiere una API key propia (variable de entorno BALLDONTLIE_API_KEY),
obtenida gratis en https://balldontlie.io. El nivel gratuito tiene límite
de peticiones por minuto, por eso los datos se cachean en PostgreSQL y se
refrescan periódicamente (ver sync_service.py) en lugar de llamar a la API
en cada request del usuario.

NOTA DE VERIFICACIÓN (revisado contra la documentación pública vigente de
balldontlie antes de esta entrega):
- Cada liga tiene su propio segmento de ruta confirmado en su spec OpenAPI
  oficial (ej. openapi/laliga.yml, openapi/fifa.yml existen como specs
  independientes). El segmento "laliga" es real, NO es un alias de "epl"
  como estaba antes en este archivo (era un placeholder incorrecto).
- EPL publicó una "API V2" para sus endpoints de detalle de partido
  (eventos, alineaciones, lesiones, stats por jugador). Por eso EPL usa
  API_VERSION_OVERRIDES; el resto de ligas sigue en v1 salvo que la
  documentación indique lo contrario.
- Ligue 1 expone el roster de un equipo como "/ligue1/v1/rosters", no
  "/ligue1/v1/players" (confirmado en su documentación). Por eso existe
  PLAYERS_ENDPOINT_OVERRIDES.
- Antes de producción, se recomienda hacer una prueba real con tu API key
  contra cada liga que vayas a activar (una llamada a /teams basta) y
  ajustar aquí si la documentación cambia, ya que balldontlie sigue
  evolucionando estos productos.
"""
from datetime import date

import httpx

from app.core.config import settings

TIMEOUT = httpx.Timeout(10.0, connect=5.0)

# Mapeo de "key" interna de la liga -> segmento de ruta en la API de balldontlie.
LEAGUE_PATHS = {
    "nba": "nba",
    "wnba": "wnba",
    "ncaab": "ncaab",
    "epl": "epl",
    "laliga": "laliga",
    "seriea": "seriea",
    "bundesliga": "bundesliga",
    "ligue1": "ligue1",
    "mls": "mls",
    "champions_league": "ucl",
    "world_cup": "fifa",
}

# Versión de API por liga. Por defecto "v1"; solo se declara aquí la que es distinta.
API_VERSION_OVERRIDES = {
    "epl": "v2",
}

# Nombre del endpoint de jugadores/plantilla por liga. Por defecto "players".
PLAYERS_ENDPOINT_OVERRIDES = {
    "ligue1": "rosters",
}


def _api_version(league_key: str) -> str:
    return API_VERSION_OVERRIDES.get(league_key, "v1")


def _players_endpoint(league_key: str) -> str:
    return PLAYERS_ENDPOINT_OVERRIDES.get(league_key, "players")


def _headers() -> dict:
    if not settings.BALLDONTLIE_API_KEY:
        raise RuntimeError(
            "Falta configurar BALLDONTLIE_API_KEY en el archivo .env. "
            "Obtén una clave gratuita en https://balldontlie.io"
        )
    return {"Authorization": settings.BALLDONTLIE_API_KEY}


async def get_games(league_key: str, target_date: date) -> dict:
    path = LEAGUE_PATHS[league_key]
    url = f"{settings.BALLDONTLIE_API_BASE}/{path}/{_api_version(league_key)}/games"
    params = {"dates[]": target_date.isoformat()}
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(url, params=params, headers=_headers())
        resp.raise_for_status()
        return resp.json()


async def get_teams(league_key: str) -> dict:
    path = LEAGUE_PATHS[league_key]
    url = f"{settings.BALLDONTLIE_API_BASE}/{path}/{_api_version(league_key)}/teams"
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(url, headers=_headers())
        resp.raise_for_status()
        return resp.json()


async def get_standings(league_key: str, season: int) -> dict:
    path = LEAGUE_PATHS[league_key]
    url = f"{settings.BALLDONTLIE_API_BASE}/{path}/{_api_version(league_key)}/standings"
    params = {"season": season}
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(url, params=params, headers=_headers())
        resp.raise_for_status()
        return resp.json()


async def get_players(league_key: str, team_id: int) -> dict:
    path = LEAGUE_PATHS[league_key]
    endpoint = _players_endpoint(league_key)
    url = f"{settings.BALLDONTLIE_API_BASE}/{path}/{_api_version(league_key)}/{endpoint}"
    params = {"team_id": team_id} if endpoint == "rosters" else {"team_ids[]": team_id}
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(url, params=params, headers=_headers())
        resp.raise_for_status()
        return resp.json()


async def get_odds(league_key: str, game_id: int) -> dict:
    """
    Cuotas/odds del partido, si el plan contratado en balldontlie las incluye.
    Se usan para calcular una probabilidad real en vez de la heurística interna.
    """
    path = LEAGUE_PATHS[league_key]
    url = f"{settings.BALLDONTLIE_API_BASE}/{path}/{_api_version(league_key)}/odds"
    params = {"game_id": game_id}
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(url, params=params, headers=_headers())
        resp.raise_for_status()
        return resp.json()
