"""
Cliente genérico para balldontlie.io, usado para basketball (NBA, WNBA,
NCAAB) y fútbol (EPL, La Liga, Serie A, Bundesliga, Ligue 1, MLS,
Champions League y el Mundial).

Requiere una API key propia (variable de entorno BALLDONTLIE_API_KEY),
obtenida gratis en https://balldontlie.io. El nivel gratuito tiene límite
de peticiones por minuto, por eso los datos se cachean en PostgreSQL y se
refrescan periódicamente (ver sync_service.py) en lugar de llamar a la API
en cada request del usuario.

NOTA DE VERIFICACIÓN (revisado contra la documentación pública vigente y
ejemplos reales de respuesta antes de esta entrega):
- Basketball (NBA/WNBA/NCAAB) usa el endpoint "/games" y sus partidos
  incluyen los equipos completos embebidos como "home_team"/"visitor_team",
  con marcador en "home_team_score"/"visitor_team_score".
- Fútbol (EPL, La Liga, etc.) usa el endpoint "/matches" (NO "/games" —
  esto estaba mal en una versión anterior de este archivo), con marcador
  en "home_score"/"away_score" y los equipos solo como IDs
  ("home_team_id"/"away_team_id"), por lo que sí hace falta resolverlos
  contra /teams.
- El Mundial vive en una ruta anidada "fifa/worldcup" (ej.
  ".../fifa/worldcup/v1/matches"), no solo "fifa" como estaba antes.
- EPL confirmado en "v2" para varios endpoints; el resto de ligas de
  fútbol se asume "v1" salvo que se confirme lo contrario.
- Los logos de equipo de NBA/fútbol NO se generan aquí: a diferencia de
  MLB (con un CDN público y estable ya confirmado), no hay una fuente
  confirmada de logos para estas ligas todavía. Se deja logo_url en None
  a propósito en vez de adivinar una URL que podría estar rota — el
  frontend ya maneja bien la ausencia de logo.
- Antes de producción, se recomienda revisar los logs de sincronización
  la primera vez que corra, ya que balldontlie sigue evolucionando estos
  productos y algún detalle menor podría cambiar.
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
    "world_cup": "fifa/worldcup",
}

# Ligas de fútbol: usan el endpoint "matches" y la forma de respuesta con
# home_score/away_score + home_team_id/away_team_id (sin equipo embebido).
SOCCER_LEAGUES = {"epl", "laliga", "seriea", "bundesliga", "ligue1", "mls", "champions_league", "world_cup"}

# Ligas de basketball: usan el endpoint "games" y la forma de respuesta con
# home_team_score/visitor_team_score + home_team/visitor_team embebidos.
BASKETBALL_LEAGUES = {"nba", "wnba", "ncaab"}

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


def _games_endpoint(league_key: str) -> str:
    return "matches" if league_key in SOCCER_LEAGUES else "games"


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
    endpoint = _games_endpoint(league_key)
    url = f"{settings.BALLDONTLIE_API_BASE}/{path}/{_api_version(league_key)}/{endpoint}"
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
