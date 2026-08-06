"""
Estadísticas detalladas de jugadores de fútbol vía API-Football
(api-sports.io, endpoint directo — no RapidAPI).

Por qué existe: football-data.org (ya usado para equipos/posiciones/
goleadores) en su plan gratuito solo da goles/asistencias de los
goleadores destacados de cada liga — no la plantilla completa ni
estadísticas detalladas (tarjetas, minutos, calificación del partido).
API-Football sí las da en su plan gratuito.

LÍMITES REALES a tener en cuenta:
- Plan gratuito: 100 peticiones/día, 10/minuto. Por eso esto se consulta
  SOLO en vivo, al buscar un jugador específico — nunca en la
  sincronización periódica (eso agotaría el límite diario de inmediato).
- "Limitado en temporadas disponibles" según la propia documentación: no
  se pudo confirmar hasta cuántas temporadas atrás alcanza el plan
  gratuito. Por eso aquí solo se pide la temporada actual y, si no hay
  datos, la anterior como respaldo — un total de "carrera" de muchos años
  (como sí se logra con NBA vía stats.nba.com) no es viable de forma
  confiable en este plan.

NOTA DE HONESTIDAD: este archivo se escribió sin poder probarlo contra
una key real (no hay una configurada en este entorno) — se revisó a
fondo contra la documentación oficial de api-football.com, pero es
posible que algún nombre de campo necesite un ajuste la primera vez que
corra de verdad. Si el perfil de un jugador de fútbol se queda sin
number, revisa los logs del servidor para ver el error exacto.
"""
import httpx

from app.core.config import settings

TIMEOUT = 10.0


def _headers() -> dict:
    return {"x-apisports-key": settings.API_FOOTBALL_KEY}


async def search_player_season_stats(name: str, season: int) -> dict:
    """
    Busca por nombre (mínimo 3 caracteres, límite de la API) y devuelve,
    para cada jugador que coincida, sus estadísticas de esa temporada en
    cada competencia en la que jugó (liga, copas, etc. — ver
    extract_best_match_stats para cómo se combinan en un solo total).
    """
    params = {"search": name, "season": season}
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(f"{settings.API_FOOTBALL_API_BASE}/players", params=params, headers=_headers())
        resp.raise_for_status()
        return resp.json()


def extract_best_match_stats(raw: dict, team_name: str | None = None) -> dict | None:
    """
    De los jugadores que devolvió la búsqueda por nombre (puede haber
    homónimos), se prioriza el que tenga a team_name entre sus equipos de
    esa temporada; si no se puede confirmar, se usa el primer resultado.
    Sus estadísticas de todas las competencias de esa temporada (liga +
    copas) se suman en un solo total, en vez de mostrarlas repetidas por
    competencia.

    Devuelve None si la búsqueda no encontró a nadie (ej. la temporada
    pedida no está disponible en el plan gratuito).
    """
    results = raw.get("response", [])
    if not results:
        return None

    chosen = results[0]
    if team_name:
        for entry in results:
            teams_played = {(s.get("team") or {}).get("name") for s in entry.get("statistics", [])}
            if team_name in teams_played:
                chosen = entry
                break

    totals = {"appearances": 0, "goals": 0, "assists": 0, "yellow_cards": 0, "red_cards": 0, "minutes": 0}
    rating_sum = 0.0
    rating_count = 0

    for stat in chosen.get("statistics", []):
        games = stat.get("games") or {}
        goals = stat.get("goals") or {}
        cards = stat.get("cards") or {}

        totals["appearances"] += games.get("appearences") or 0
        totals["minutes"] += games.get("minutes") or 0
        totals["goals"] += goals.get("total") or 0
        totals["assists"] += goals.get("assists") or 0
        totals["yellow_cards"] += cards.get("yellow") or 0
        totals["red_cards"] += cards.get("red") or 0

        rating = games.get("rating")
        if rating:
            try:
                rating_sum += float(rating)
                rating_count += 1
            except (TypeError, ValueError):
                pass

    totals["avg_rating"] = round(rating_sum / rating_count, 2) if rating_count else None
    return totals
