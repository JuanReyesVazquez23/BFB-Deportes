"""
Cliente para la MLB Stats API oficial (https://statsapi.mlb.com).

Es una API pública, gratuita y sin necesidad de API key. Se usa como fuente
principal para la liga MLB (deporte: béisbol), incluyendo detalle de
pitchers abridores y ganadores/perdedores por juego.

Todas las funciones son async y usan httpx.AsyncClient. Los datos crudos
se devuelven como dicts (JSON) y son transformados/guardados en la capa de
sincronización (ver app/services/sync_service.py).
"""
from datetime import date

import httpx

from app.core.config import settings
from app.services.http_client import DEFAULT_HTTP_TIMEOUT as TIMEOUT

MLB_SPORT_ID = 1  # id interno de MLB en statsapi.mlb.com (Grandes Ligas)

# IDs de división de MLB: fijos y permanentes (no cambian). Confirmados
# contra una respuesta real del endpoint /standings, que solo trae
# {"id": ..., "link": ...} en record["division"] -- NUNCA el nombre. El
# nombre hay que mapearlo por ID, no se puede pedir directamente.
MLB_DIVISION_NAMES = {
    200: "AL West",
    201: "AL East",
    202: "AL Central",
    203: "NL West",
    204: "NL East",
    205: "NL Central",
}


async def get_standings(season: int) -> dict:
    """Posiciones actuales de la MLB por división."""
    url = f"{settings.MLB_STATS_API_BASE}/standings"
    params = {"leagueId": "103,104", "season": season, "standingsTypes": "regularSeason"}
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()


async def get_schedule(target_date: date) -> dict:
    """
    Calendario/resultados del día indicado. Incluye pitchers probables y,
    si el juego ya inició/terminó, el linescore básico.
    """
    url = f"{settings.MLB_STATS_API_BASE}/schedule"
    params = {
        "sportId": MLB_SPORT_ID,
        "date": target_date.isoformat(),
        "hydrate": "team,linescore,probablePitcher,decisions",
    }
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()


async def get_live_feed(game_pk: int) -> dict:
    """
    Feed en vivo/boxscore completo de un juego: pitcher ganador, perdedor,
    salvamento, líderes ofensivos, etc. game_pk es el id de juego de MLB.
    """
    url = f"{settings.MLB_STATS_API_BASE.replace('/api/v1', '')}/api/v1.1/game/{game_pk}/feed/live"
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()


def extract_live_situation(live_feed: dict) -> dict:
    """
    Extrae la situación de juego en vivo (bases, outs, bateador, pitcher,
    última jugada) del feed GUMBO de MLB. Estructura confirmada contra la
    documentación oficial de MLB Stats API (linescore.offense/defense).

    Las bases solo aparecen como clave en el JSON cuando están ocupadas
    (no vienen como null/false); por eso se detecta con bool(...) sobre la
    presencia de la clave, no comparando un valor.
    """
    linescore = live_feed.get("liveData", {}).get("linescore", {})
    offense = linescore.get("offense", {})
    defense = linescore.get("defense", {})
    current_play = live_feed.get("liveData", {}).get("plays", {}).get("currentPlay", {})

    return {
        "inning": linescore.get("currentInning"),
        "inning_half": linescore.get("inningHalf"),  # "Top" | "Bottom"
        "outs": linescore.get("outs", 0),
        "balls": linescore.get("balls", 0),
        "strikes": linescore.get("strikes", 0),
        "bases": {
            "first": bool(offense.get("first")),
            "second": bool(offense.get("second")),
            "third": bool(offense.get("third")),
        },
        "batter": offense.get("batter", {}).get("fullName"),
        "pitcher": defense.get("pitcher", {}).get("fullName"),
        "last_play": current_play.get("result", {}).get("description"),
    }


async def get_teams(season: int) -> dict:
    url = f"{settings.MLB_STATS_API_BASE}/teams"
    params = {"sportId": MLB_SPORT_ID, "season": season}
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()


async def get_team_roster(team_id: int, season: int) -> dict:
    url = f"{settings.MLB_STATS_API_BASE}/teams/{team_id}/roster"
    params = {"season": season}
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()


async def get_player_season_stats(person_id: int, season: int) -> dict:
    """
    Estadísticas reales de temporada de un jugador: bateo y pitcheo. Se
    consulta en vivo solo cuando el usuario busca a ese jugador (no se
    guarda en BD), así siempre está al día y no hace falta otra migración.
    Un bateador no tendrá datos de pitcheo y viceversa; eso es normal.
    """
    url = f"{settings.MLB_STATS_API_BASE}/people/{person_id}/stats"
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        hitting_resp = await client.get(url, params={"stats": "season", "group": "hitting", "season": season})
        pitching_resp = await client.get(url, params={"stats": "season", "group": "pitching", "season": season})
    hitting_resp.raise_for_status()
    pitching_resp.raise_for_status()
    return {"hitting": hitting_resp.json(), "pitching": pitching_resp.json()}


def _first_split_stat(stats_response: dict) -> dict | None:
    splits = (stats_response.get("stats") or [{}])[0].get("splits", [])
    return splits[0]["stat"] if splits else None


def extract_batting_stats(hitting_response: dict) -> dict | None:
    """Devuelve None si el jugador no tiene estadísticas de bateo esta temporada (ej. es pitcher puro)."""
    stat = _first_split_stat(hitting_response)
    if not stat:
        return None
    return {
        "games": stat.get("gamesPlayed"),
        "at_bats": stat.get("atBats"),
        "hits": stat.get("hits"),
        "home_runs": stat.get("homeRuns"),
        "rbi": stat.get("rbi"),
        "avg": stat.get("avg"),
        "obp": stat.get("obp"),
        "slg": stat.get("slg"),
        "ops": stat.get("ops"),
        "stolen_bases": stat.get("stolenBases"),
    }


def extract_pitching_stats(pitching_response: dict) -> dict | None:
    """Devuelve None si el jugador no tiene estadísticas de pitcheo esta temporada (ej. es bateador puro)."""
    stat = _first_split_stat(pitching_response)
    if not stat:
        return None
    return {
        "games": stat.get("gamesPlayed"),
        "wins": stat.get("wins"),
        "losses": stat.get("losses"),
        "era": stat.get("era"),
        "strikeouts": stat.get("strikeOuts"),
        "saves": stat.get("saves"),
        "innings_pitched": stat.get("inningsPitched"),
        "whip": stat.get("whip"),
    }


def extract_probable_pitchers(schedule_game: dict) -> dict:
    """Extrae de un juego del /schedule los pitchers abridores probables (para 'Jugadores Hoy')."""
    probables = schedule_game.get("teams", {})
    return {
        "home_pitcher": probables.get("home", {}).get("probablePitcher", {}).get("fullName"),
        "away_pitcher": probables.get("away", {}).get("probablePitcher", {}).get("fullName"),
    }


def extract_decisions(schedule_game: dict) -> dict:
    """Extrae pitcher ganador/perdedor/salvamento de un juego ya finalizado."""
    decisions = schedule_game.get("decisions", {})
    return {
        "winning_pitcher": decisions.get("winner", {}).get("fullName"),
        "losing_pitcher": decisions.get("loser", {}).get("fullName"),
        "save_pitcher": decisions.get("save", {}).get("fullName"),
    }
