"""
Estadísticas reales de jugadores de NBA vía stats.nba.com.

Investigado y confirmado antes de escribir esto: balldontlie (el
proveedor que ya se usa para equipos/jugadores/partidos de NBA) NO
incluye estadísticas de jugador en su plan gratuito — eso requiere un
plan de pago (ALL-STAR o GOAT, ver balldontlie.io/pricing). stats.nba.com
sí las tiene gratis, pero con una salvedad importante:

IMPORTANTE — es una API NO OFICIAL:
- La NBA no publica documentación de este endpoint ni ofrece un sistema
  de llaves; lo usa el propio sitio nba.com/stats internamente.
- No hay un límite de uso publicado, pero tampoco ninguna garantía: puede
  cambiar de forma o bloquear solicitudes sin aviso.
- Por eso se consulta solo EN VIVO cuando alguien busca a un jugador
  específico (nunca en la sincronización periódica) — el mismo patrón que
  ya existe para MLB Stats API. Si stats.nba.com no responde, el perfil
  del jugador se muestra igual, solo sin números, en vez de fallar la
  petición completa.

Un solo llamado a /stats/playercareerstats trae TODO lo que se necesita:
totales de carrera Y el desglose temporada por temporada (de ahí se toma
la última fila como "temporada actual") — no hacen falta dos llamadas.
"""
import re
import unicodedata

import httpx

NBA_STATS_BASE = "https://stats.nba.com/stats"
TIMEOUT = 10.0

# Headers requeridos para que stats.nba.com no rechace la solicitud (no
# es autenticación real, solo simula que la petición viene de un
# navegador visitando nba.com/stats — confirmado contra reportes de la
# comunidad que mantiene el paquete nba_api, la referencia más completa
# que existe sobre este endpoint no oficial).
_HEADERS = {
    "Host": "stats.nba.com",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:61.0) Gecko/20100101 Firefox/61.0",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": "https://stats.nba.com/",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "x-nba-stats-origin": "stats",
    "x-nba-stats-token": "true",
}


async def get_player_career_stats(player_id: int) -> dict:
    """PerMode=PerGame: promedios por partido (más fácil de leer que totales acumulados)."""
    params = {"PlayerID": player_id, "PerMode": "PerGame", "LeagueID": "00"}
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(f"{NBA_STATS_BASE}/playercareerstats", params=params, headers=_HEADERS)
        resp.raise_for_status()
        return resp.json()


async def get_all_players_index() -> dict:
    """
    Lista de TODOS los jugadores que ha tenido la NBA (con su PERSON_ID
    oficial de stats.nba.com), no solo los de la temporada actual — así no
    hay que calcular bien el nombre de temporada de la NBA ("2025-26") ni
    preocuparse por si se está en receso. Se usa una sola vez por
    sincronización para emparejar por nombre contra el roster ya
    sincronizado desde balldontlie (que usa un ID interno propio, distinto
    a este). Season="2000-01" es solo un valor requerido por el endpoint;
    con IsOnlyCurrentSeason=0 no restringe el resultado a esa temporada.
    """
    params = {"IsOnlyCurrentSeason": 0, "LeagueID": "00", "Season": "2000-01"}
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(f"{NBA_STATS_BASE}/commonallplayers", params=params, headers=_HEADERS)
        resp.raise_for_status()
        return resp.json()


def normalize_player_name(name: str) -> str:
    """
    Normaliza un nombre para comparar de forma confiable entre dos fuentes
    de datos distintas (acentos, mayúsculas, puntuación, sufijos como
    "Jr."/"III" que una fuente incluye y la otra no).
    """
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    name = name.lower()
    name = re.sub(r"\b(jr|sr|ii|iii|iv)\b\.?", "", name)
    name = re.sub(r"[^a-z\s]", "", name)
    return re.sub(r"\s+", " ", name).strip()


def build_name_to_id_map(raw_index: dict) -> dict[str, str]:
    """A partir de get_all_players_index(), arma {nombre_normalizado: PERSON_ID}."""
    rows = _extract_dataset(raw_index, "CommonAllPlayers")
    mapping: dict[str, str] = {}
    for row in rows:
        name = row.get("DISPLAY_FIRST_LAST")
        person_id = row.get("PERSON_ID")
        if name and person_id is not None:
            mapping[normalize_player_name(name)] = str(person_id)
    return mapping


def _extract_dataset(raw: dict, name: str) -> list[dict]:
    """Convierte un data_set de la respuesta (headers + filas) en una lista de diccionarios."""
    for result_set in raw.get("resultSets", []):
        if result_set.get("name") == name:
            headers = result_set["headers"]
            return [dict(zip(headers, row)) for row in result_set.get("rowSet", [])]
    return []


def _format_row(row: dict) -> dict:
    return {
        "games_played": row.get("GP"),
        "points": row.get("PTS"),
        "rebounds": row.get("REB"),
        "assists": row.get("AST"),
        "steals": row.get("STL"),
        "blocks": row.get("BLK"),
        "fg_pct": row.get("FG_PCT"),
        "fg3_pct": row.get("FG3_PCT"),
        "ft_pct": row.get("FT_PCT"),
    }


def extract_career_and_season_stats(raw: dict) -> tuple[dict | None, dict | None]:
    """
    Devuelve (estadísticas_de_carrera, estadísticas_de_temporada_actual),
    ya en formato simple listo para mostrar. None en cualquiera de los dos
    si el jugador no tiene datos todavía (ej. un rookie sin partidos).
    """
    career_rows = _extract_dataset(raw, "CareerTotalsRegularSeason")
    season_rows = _extract_dataset(raw, "SeasonTotalsRegularSeason")

    career = _format_row(career_rows[0]) if career_rows else None
    current_season = _format_row(season_rows[-1]) if season_rows else None
    return career, current_season
