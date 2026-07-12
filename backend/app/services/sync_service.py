"""
Sincronización periódica: trae datos reales de las APIs externas y los
guarda en PostgreSQL. Separar "sincronizar" de "servir" es lo que permite:

1) Respetar los límites de peticiones por minuto de las APIs externas.
2) Servir las páginas rápido (lectura local en vez de esperar a un tercero).
3) Resolver predicciones y otorgar puntos BFB cuando un partido termina.

Este archivo se ejecuta desde un scheduler (ver app/main.py, tarea en
background) o manualmente con `python -m app.services.sync_service`.
"""
import asyncio
import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.prediction import Prediction
from app.models.sport import Game, League, NewsArticle, Player, Sport, Team
from app.models.user import User
from app.services import balldontlie_service, football_data_service, mlb_service, news_service, translation_service
from app.services.probability_service import estimate_home_win_probability, points_for_prediction

logger = logging.getLogger("bfb.sync")

CURRENT_MLB_SEASON = datetime.now(timezone.utc).year

# El plan gratuito de balldontlie permite 5 peticiones/minuto. Con 13s de
# espaciado SOLO entre ligas (y las 2 llamadas de cada liga seguidas), el
# cálculo real daba ~9 llamadas/minuto -> se pasaba del límite y fallaba en
# silencio. Ahora se espacia CADA llamada individual (dentro de cada liga
# también), y 20s de espaciado da ~3-4 llamadas/minuto: dentro del límite
# con margen real, no al filo.
BALLDONTLIE_CALL_SPACING_SECONDS = 20

# football-data.org permite 10 peticiones/minuto en su plan gratuito.
# 7s de espaciado entre CADA llamada da ~8-9/min: dentro del límite con margen.
FOOTBALL_DATA_CALL_SPACING_SECONDS = 7


def _get_or_create_sport(db: Session, key: str, name_es: str, name_en: str) -> Sport:
    sport = db.query(Sport).filter(Sport.key == key).first()
    if not sport:
        sport = Sport(key=key, name_es=name_es, name_en=name_en)
        db.add(sport)
        db.commit()
        db.refresh(sport)
    return sport


def _get_or_create_league(db: Session, sport: Sport, key: str, name: str, provider: str, is_primary=False) -> League:
    league = db.query(League).filter(League.key == key).first()
    if not league:
        league = League(
            sport_id=sport.id, key=key, name=name, is_primary=is_primary, data_provider=provider
        )
        db.add(league)
        db.commit()
        db.refresh(league)
    elif league.data_provider != provider:
        # Se actualiza aunque ya exista: si cambiamos de proveedor en el
        # código (ej. de balldontlie a football-data.org), sin esto la BD
        # de producción se quedaría con el proveedor viejo para siempre.
        league.data_provider = provider
        db.commit()
    return league


def ensure_base_catalog(db: Session) -> None:
    """Crea los deportes y las ligas si todavía no existen (idempotente)."""
    baseball = _get_or_create_sport(db, "baseball", "Béisbol", "Baseball")
    football = _get_or_create_sport(db, "football", "Fútbol", "Football")
    basketball = _get_or_create_sport(db, "basketball", "Basketball", "Basketball")

    _get_or_create_league(db, baseball, "mlb", "MLB", provider="mlb_stats_api", is_primary=True)

    _get_or_create_league(db, basketball, "nba", "NBA", provider="balldontlie", is_primary=True)
    _get_or_create_league(db, basketball, "wnba", "WNBA", provider="balldontlie")
    _get_or_create_league(db, basketball, "ncaab", "NCAA Basketball", provider="balldontlie")

    # El Mundial vive aquí, como una liga más de fútbol (igual que en
    # SofaScore/OneFootball), no como una pestaña de deporte aparte.
    # Proveedor: football-data.org (no balldontlie) porque su nivel gratis
    # sí cubre estas competencias sin plan de pago por deporte.
    _get_or_create_league(db, football, "epl", "Premier League", provider="football_data_org", is_primary=True)
    _get_or_create_league(db, football, "laliga", "La Liga", provider="football_data_org")
    _get_or_create_league(db, football, "seriea", "Serie A", provider="football_data_org")
    _get_or_create_league(db, football, "bundesliga", "Bundesliga", provider="football_data_org")
    _get_or_create_league(db, football, "ligue1", "Ligue 1", provider="football_data_org")
    _get_or_create_league(db, football, "champions_league", "Champions League", provider="football_data_org")
    _get_or_create_league(db, football, "world_cup", "Mundial 2026", provider="football_data_org")


async def sync_mlb_teams_and_standings() -> None:
    db = SessionLocal()
    try:
        league = db.query(League).filter(League.key == "mlb").first()
        if not league:
            logger.warning("Liga MLB no existe todavía en la BD; ejecuta ensure_base_catalog primero.")
            return

        standings_data = await mlb_service.get_standings(CURRENT_MLB_SEASON)

        # El endpoint de standings solo trae "name" (nombre completo, ej.
        # "New York Yankees"). Para el nombre corto ("Yankees"), la
        # abreviación ("NYY") y la ciudad, se necesita el endpoint /teams.
        teams_data = await mlb_service.get_teams(CURRENT_MLB_SEASON)
        team_details_by_id = {str(t["id"]): t for t in teams_data.get("teams", [])}

        for record in standings_data.get("records", []):
            division_id = record.get("division", {}).get("id")
            division_name = mlb_service.MLB_DIVISION_NAMES.get(division_id)

            for team_record in record.get("teamRecords", []):
                team_info = team_record["team"]
                external_id = str(team_info["id"])
                details = team_details_by_id.get(external_id, {})

                team = (
                    db.query(Team)
                    .filter(Team.league_id == league.id, Team.external_id == external_id)
                    .first()
                )
                if not team:
                    team = Team(league_id=league.id, external_id=external_id, name=team_info["name"])
                    db.add(team)

                wins = team_record.get("wins", 0)
                losses = team_record.get("losses", 0)
                total = wins + losses
                team.name = team_info["name"]
                team.short_name = details.get("teamName")  # ej. "Yankees"
                team.abbreviation = details.get("abbreviation")  # ej. "NYY"
                team.city = details.get("locationName")  # ej. "New York"
                # Logo oficial de MLB: patrón de CDN público y estable, confirmado
                # contra datos reales usados por la propia comunidad de MLB.
                team.logo_url = f"https://www.mlbstatic.com/team-logos/{external_id}.svg"
                team.wins = wins
                team.losses = losses
                team.win_pct = round(wins / total, 3) if total else 0.0
                team.division = division_name
                team.standings_updated_at = datetime.now(timezone.utc)

        db.commit()
        logger.info("Posiciones de MLB sincronizadas correctamente.")
    finally:
        db.close()


def _extract_mlb_score(game_data: dict, side: str) -> int | None:
    """
    Extrae el marcador real de un lado ("home" o "away") de un juego de MLB.

    Se prioriza linescore.teams.{side}.runs, confirmado como la fuente que
    sí se actualiza mientras el partido está EN VIVO. teams.{side}.score
    se usa como respaldo (es la fuente que ya se usaba antes; funciona bien
    para partidos finalizados, pero se quedaba en 0 durante partidos en vivo,
    que era la causa del bug reportado de "siempre 0-0").
    """
    linescore_teams = (game_data.get("linescore") or {}).get("teams") or {}
    runs = linescore_teams.get(side, {}).get("runs")
    if runs is not None:
        return runs
    return game_data.get("teams", {}).get(side, {}).get("score")


async def sync_mlb_games(target_date: date | None = None) -> None:
    db = SessionLocal()
    try:
        league = db.query(League).filter(League.key == "mlb").first()
        if not league:
            return

        base_date = target_date or datetime.now(timezone.utc).date()
        # Se sincroniza "ayer" y "hoy" (no solo hoy): un juego de la Costa Oeste
        # que empieza tarde en hora local puede caer en el día siguiente en UTC,
        # y sin esto ese juego nunca se guardaba en la base de datos.
        dates_to_sync = {base_date - timedelta(days=1), base_date}

        # Auto-corrección: cualquier juego que sigue marcado "live" en la BD
        # pero es de una fecha que ya no cae en la ventana de arriba nunca se
        # vuelve a tocar, y se queda "en vivo" para siempre aunque ya haya
        # terminado hace días. Se agregan esas fechas para forzar su corrección.
        stale_live_dates = {
            g.start_time.date()
            for g in db.query(Game).filter(Game.league_id == league.id, Game.status == "live").all()
        }
        dates_to_sync |= stale_live_dates

        for sync_date in sorted(dates_to_sync):
            schedule = await mlb_service.get_schedule(sync_date)
            _process_mlb_schedule(db, league, schedule)

        db.commit()
        logger.info("Calendario de MLB sincronizado (%d fecha(s)).", len(dates_to_sync))
    finally:
        db.close()


def _process_mlb_schedule(db, league, schedule: dict) -> None:
    """Procesa un calendario (un solo día) de la MLB Stats API y actualiza/crea los juegos en BD."""
    for day in schedule.get("dates", []):
        for game_data in day.get("games", []):
            external_id = str(game_data["gamePk"])
            home_info = game_data["teams"]["home"]["team"]
            away_info = game_data["teams"]["away"]["team"]

            home_team = (
                db.query(Team)
                .filter(Team.league_id == league.id, Team.external_id == str(home_info["id"]))
                .first()
            )
            away_team = (
                db.query(Team)
                .filter(Team.league_id == league.id, Team.external_id == str(away_info["id"]))
                .first()
            )
            if not home_team or not away_team:
                # Los equipos deberían existir tras sync_mlb_teams_and_standings; si no, se omite.
                continue

            game = (
                db.query(Game)
                .filter(Game.league_id == league.id, Game.external_id == external_id)
                .first()
            )
            if not game:
                game = Game(
                    league_id=league.id,
                    external_id=external_id,
                    home_team_id=home_team.id,
                    away_team_id=away_team.id,
                    start_time=datetime.fromisoformat(game_data["gameDate"].replace("Z", "+00:00")),
                )
                db.add(game)

            raw_status = game_data.get("status", {}).get("abstractGameState", "Preview")
            status_map = {"Preview": "scheduled", "Live": "live", "Final": "final"}
            game.status = status_map.get(raw_status, "scheduled")

            game.home_score = _extract_mlb_score(game_data, "home")
            game.away_score = _extract_mlb_score(game_data, "away")
            game.venue = game_data.get("venue", {}).get("name")

            if game.status == "scheduled" and game.home_win_probability is None:
                game.home_win_probability = estimate_home_win_probability(
                    home_team.win_pct or 0.5, away_team.win_pct or 0.5
                )

            details = game.details or {}
            if game.status == "scheduled":
                details.update(mlb_service.extract_probable_pitchers(game_data))
            elif game.status == "final":
                details.update(mlb_service.extract_decisions(game_data))
                linescore = game_data.get("linescore", {})
                details["innings_played"] = linescore.get("currentInning")
            elif game.status == "live":
                linescore = game_data.get("linescore", {})
                game.period_status = f"Inning {linescore.get('currentInning', '?')}"
            game.details = details
            game.last_synced_at = datetime.now(timezone.utc)


def _interpret_basketball_status(raw_status: str) -> tuple[str, str | None]:
    """
    Traduce el campo "status" de balldontlie (NBA/WNBA/NCAAB) a nuestro
    estado interno. Confirmado con ejemplos reales de su documentación:
    - "Final" -> partido terminado.
    - Una fecha/hora ISO (ej. "2025-12-08T00:00:00Z") -> el partido no ha
      empezado; ese valor es la hora de inicio, no un estado.
    - Cualquier otro texto (ej. "2nd Qtr", "Halftime") -> en vivo, y ya
      viene en formato legible para mostrarlo tal cual.
    """
    if raw_status == "Final":
        return "final", None
    try:
        datetime.fromisoformat(raw_status.replace("Z", "+00:00"))
        return "scheduled", None
    except (ValueError, AttributeError):
        return "live", raw_status


def _interpret_soccer_status(raw_status: str, status_detail: str | None) -> tuple[str, str | None]:
    """
    Traduce el campo "status" de balldontlie (fútbol) a nuestro estado
    interno. Confirmado: "STATUS_FULL_TIME" -> terminado. Los valores para
    "programado" y "en vivo" no están 100% confirmados en la documentación
    pública, así que se usa una coincidencia por texto tolerante: cualquier
    estado que no sea claramente "final" ni "programado" se trata como en
    vivo, mostrando status_detail (ej. "45'", "HT") si viene disponible.
    """
    if "FULL_TIME" in raw_status or "FINAL" in raw_status:
        return "final", None
    if "SCHEDULED" in raw_status or not raw_status:
        return "scheduled", None
    return "live", status_detail or raw_status


async def sync_basketball_league(league_key: str) -> None:
    """
    Sincroniza equipos y partidos de hoy de una liga de basketball vía
    balldontlie (NBA confirmado con alta confianza contra ejemplos reales
    de su documentación; WNBA/NCAAB deberían compartir la misma forma de
    respuesta al ser productos de la misma familia).

    Nota: no se sincronizan posiciones de temporada completa todavía (el
    endpoint /standings de balldontlie no se pudo confirmar con la misma
    certeza). Mientras tanto, la probabilidad de victoria usa 50/50 por
    defecto para estos equipos, igual que si no hubiera historial.
    """
    db = SessionLocal()
    try:
        league = db.query(League).filter(League.key == league_key).first()
        if not league:
            logger.warning("Liga '%s' no existe en la BD; ejecuta ensure_base_catalog primero.", league_key)
            return

        try:
            teams_data = await balldontlie_service.get_teams(league_key)
            for team_info in teams_data.get("data", []):
                external_id = str(team_info["id"])
                team = (
                    db.query(Team)
                    .filter(Team.league_id == league.id, Team.external_id == external_id)
                    .first()
                )
                if not team:
                    team = Team(
                        league_id=league.id,
                        external_id=external_id,
                        name=team_info.get("full_name") or team_info.get("name", ""),
                    )
                    db.add(team)
                team.name = team_info.get("full_name") or team.name
                team.short_name = team_info.get("name")  # ej. "Knicks"
                team.abbreviation = team_info.get("abbreviation")
                team.city = team_info.get("city")
                team.conference = team_info.get("conference")
                team.division = team_info.get("division")
                # Logo: CDN de ESPN, confirmado en vivo SOLO para NBA usando
                # la abreviación en minúsculas (ej. "nyk" para los Knicks).
                # WNBA/NCAAB usan un slug de ESPN distinto que no está
                # confirmado, así que se dejan sin logo en vez de arriesgar
                # una URL equivocada.
                if league_key == "nba" and team.abbreviation:
                    team.logo_url = f"https://a.espncdn.com/i/teamlogos/nba/500/{team.abbreviation.lower()}.png"
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("No se pudieron sincronizar equipos de '%s'.", league_key)

        try:
            # Pausa entre esta llamada y la de equipos de arriba: balldontlie
            # gratis permite 5 peticiones/minuto: espaciar solo entre ligas
            # (y no entre las 2 llamadas de cada liga) no alcanzaba.
            await asyncio.sleep(BALLDONTLIE_CALL_SPACING_SECONDS)
            target_date = datetime.now(timezone.utc).date()
            games_data = await balldontlie_service.get_games(league_key, target_date)
            for game_data in games_data.get("data", []):
                external_id = str(game_data["id"])
                home_info = game_data["home_team"]
                away_info = game_data["visitor_team"]

                home_team = (
                    db.query(Team)
                    .filter(Team.league_id == league.id, Team.external_id == str(home_info["id"]))
                    .first()
                )
                away_team = (
                    db.query(Team)
                    .filter(Team.league_id == league.id, Team.external_id == str(away_info["id"]))
                    .first()
                )
                if not home_team or not away_team:
                    continue

                game = (
                    db.query(Game)
                    .filter(Game.league_id == league.id, Game.external_id == external_id)
                    .first()
                )
                raw_datetime = game_data.get("datetime") or game_data.get("date", "")
                try:
                    start_time = datetime.fromisoformat(raw_datetime.replace("Z", "+00:00"))
                except ValueError:
                    start_time = datetime.now(timezone.utc)

                if not game:
                    game = Game(
                        league_id=league.id,
                        external_id=external_id,
                        home_team_id=home_team.id,
                        away_team_id=away_team.id,
                        start_time=start_time,
                    )
                    db.add(game)

                status, period_status = _interpret_basketball_status(str(game_data.get("status", "")))
                game.status = status
                game.period_status = period_status
                game.home_score = game_data.get("home_team_score")
                game.away_score = game_data.get("visitor_team_score")

                if game.status == "scheduled" and game.home_win_probability is None:
                    game.home_win_probability = estimate_home_win_probability(
                        home_team.win_pct or 0.5, away_team.win_pct or 0.5
                    )
                game.last_synced_at = datetime.now(timezone.utc)

            db.commit()
            logger.info("Partidos de '%s' sincronizados.", league_key)
        except Exception:
            db.rollback()
            logger.exception("No se pudieron sincronizar partidos de '%s'.", league_key)
    finally:
        db.close()


FOOTBALL_DATA_STATUS_MAP = {
    "FINISHED": "final",
    "IN_PLAY": "live",
    "PAUSED": "live",
    "SCHEDULED": "scheduled",
    "TIMED": "scheduled",
    # POSTPONED / SUSPENDED / CANCELLED: no se procesan (ver abajo, se omiten).
}


async def sync_football_data_league(league_key: str) -> None:
    """
    Sincroniza equipos, partidos y posiciones de una liga de fútbol vía
    football-data.org. A diferencia de balldontlie, esta API SÍ incluye el
    logo real de cada equipo en el campo "crest" — no hay que adivinar
    ningún patrón de CDN.

    Las posiciones se omiten para el Mundial a propósito (pedido explícito):
    es una competencia por grupos, no una tabla de liga tradicional, y
    football-data.org tampoco las expone igual para este tipo de torneo.
    """
    db = SessionLocal()
    try:
        league = db.query(League).filter(League.key == league_key).first()
        if not league:
            logger.warning("Liga '%s' no existe en la BD; ejecuta ensure_base_catalog primero.", league_key)
            return

        try:
            teams_data = await football_data_service.get_teams(league_key)
            for team_info in teams_data.get("teams", []):
                external_id = str(team_info["id"])
                team = (
                    db.query(Team)
                    .filter(Team.league_id == league.id, Team.external_id == external_id)
                    .first()
                )
                if not team:
                    team = Team(league_id=league.id, external_id=external_id, name=team_info.get("name", ""))
                    db.add(team)
                team.name = team_info.get("name") or team.name
                team.short_name = team_info.get("shortName")
                team.abbreviation = team_info.get("tla")
                team.logo_url = team_info.get("crest")  # logo real, confirmado en la documentación oficial
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("No se pudieron sincronizar equipos de '%s' (football-data.org).", league_key)

        await asyncio.sleep(FOOTBALL_DATA_CALL_SPACING_SECONDS)

        try:
            matches_data = await football_data_service.get_matches(league_key)
            for match in matches_data.get("matches", []):
                raw_status = match.get("status")
                if raw_status not in FOOTBALL_DATA_STATUS_MAP:
                    continue  # postergado/suspendido/cancelado: se omite

                external_id = str(match["id"])
                home_info = match.get("homeTeam") or {}
                away_info = match.get("awayTeam") or {}
                if not home_info.get("id") or not away_info.get("id"):
                    continue  # partido de eliminatoria cuyos equipos aún no se determinan

                home_team = (
                    db.query(Team)
                    .filter(Team.league_id == league.id, Team.external_id == str(home_info["id"]))
                    .first()
                )
                away_team = (
                    db.query(Team)
                    .filter(Team.league_id == league.id, Team.external_id == str(away_info["id"]))
                    .first()
                )
                if not home_team or not away_team:
                    continue

                game = (
                    db.query(Game)
                    .filter(Game.league_id == league.id, Game.external_id == external_id)
                    .first()
                )
                if not game:
                    game = Game(
                        league_id=league.id,
                        external_id=external_id,
                        home_team_id=home_team.id,
                        away_team_id=away_team.id,
                        start_time=datetime.fromisoformat(match["utcDate"].replace("Z", "+00:00")),
                    )
                    db.add(game)

                game.status = FOOTBALL_DATA_STATUS_MAP[raw_status]
                full_time = (match.get("score") or {}).get("fullTime") or {}
                game.home_score = full_time.get("home")
                game.away_score = full_time.get("away")
                game.venue = match.get("venue")

                if game.status == "live":
                    minute = match.get("minute")
                    game.period_status = f"{minute}'" if minute else None

                if game.status == "scheduled" and game.home_win_probability is None:
                    game.home_win_probability = estimate_home_win_probability(
                        home_team.win_pct or 0.5, away_team.win_pct or 0.5
                    )
                game.last_synced_at = datetime.now(timezone.utc)

            db.commit()
            logger.info("Partidos de '%s' sincronizados (football-data.org).", league_key)
        except Exception:
            db.rollback()
            logger.exception("No se pudieron sincronizar partidos de '%s' (football-data.org).", league_key)

        if league_key != "world_cup":
            # Posiciones: se omiten para el Mundial a propósito (ver
            # docstring). Para las demás ligas, se intenta de forma segura:
            # si football-data.org devuelve un formato distinto al esperado
            # para alguna, se registra el error sin tumbar el resto del sync.
            await asyncio.sleep(FOOTBALL_DATA_CALL_SPACING_SECONDS)
            try:
                standings_data = await football_data_service.get_standings(league_key)
                tables = standings_data.get("standings", [])
                total_table = next((t for t in tables if t.get("type") == "TOTAL"), tables[0] if tables else None)
                for entry in (total_table or {}).get("table", []):
                    team_info = entry.get("team", {})
                    external_id = str(team_info.get("id", ""))
                    team = (
                        db.query(Team)
                        .filter(Team.league_id == league.id, Team.external_id == external_id)
                        .first()
                    )
                    if not team:
                        continue
                    played = entry.get("playedGames", 0)
                    team.wins = entry.get("won", 0)
                    team.losses = entry.get("lost", 0)
                    team.ties = entry.get("draw", 0)
                    team.win_pct = round(team.wins / played, 3) if played else 0.0
                    team.standings_updated_at = datetime.now(timezone.utc)
                db.commit()
                logger.info("Posiciones de '%s' sincronizadas (football-data.org).", league_key)
            except Exception:
                db.rollback()
                logger.warning("No se pudieron sincronizar posiciones de '%s' (football-data.org).", league_key)
    finally:
        db.close()


async def sync_soccer_league(league_key: str) -> None:
    """
    Sincroniza equipos y partidos ("matches") de hoy de una liga de fútbol
    vía balldontlie. A diferencia de basketball, los partidos solo traen
    home_team_id/away_team_id (sin el equipo embebido), por eso los
    equipos deben sincronizarse primero para poder resolverlos.

    Misma nota que en basketball: posiciones de temporada completa no se
    sincronizan todavía (endpoint no confirmado con certeza), así que la
    probabilidad usa 50/50 por defecto para estos equipos por ahora.
    """
    db = SessionLocal()
    try:
        league = db.query(League).filter(League.key == league_key).first()
        if not league:
            logger.warning("Liga '%s' no existe en la BD; ejecuta ensure_base_catalog primero.", league_key)
            return

        try:
            teams_data = await balldontlie_service.get_teams(league_key)
            for team_info in teams_data.get("data", []):
                external_id = str(team_info["id"])
                team = (
                    db.query(Team)
                    .filter(Team.league_id == league.id, Team.external_id == external_id)
                    .first()
                )
                if not team:
                    team = Team(league_id=league.id, external_id=external_id, name=team_info.get("name", ""))
                    db.add(team)
                team.name = team_info.get("name") or team.name
                team.short_name = team_info.get("short_name") or team_info.get("name")
                team.abbreviation = team_info.get("abbreviation")
                team.city = team_info.get("city")
                # Logo: sin CDN confirmado todavía para esta liga; se deja sin definir a propósito.
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("No se pudieron sincronizar equipos de '%s'.", league_key)

        try:
            # Misma razón que en basketball: espaciar solo entre ligas no alcanzaba.
            await asyncio.sleep(BALLDONTLIE_CALL_SPACING_SECONDS)
            target_date = datetime.now(timezone.utc).date()
            matches_data = await balldontlie_service.get_games(league_key, target_date)
            for match_data in matches_data.get("data", []):
                external_id = str(match_data["id"])
                home_team = (
                    db.query(Team)
                    .filter(Team.league_id == league.id, Team.external_id == str(match_data["home_team_id"]))
                    .first()
                )
                away_team = (
                    db.query(Team)
                    .filter(Team.league_id == league.id, Team.external_id == str(match_data["away_team_id"]))
                    .first()
                )
                if not home_team or not away_team:
                    continue

                game = (
                    db.query(Game)
                    .filter(Game.league_id == league.id, Game.external_id == external_id)
                    .first()
                )
                if not game:
                    game = Game(
                        league_id=league.id,
                        external_id=external_id,
                        home_team_id=home_team.id,
                        away_team_id=away_team.id,
                        start_time=datetime.fromisoformat(match_data["date"].replace("Z", "+00:00")),
                    )
                    db.add(game)

                status, period_status = _interpret_soccer_status(
                    str(match_data.get("status", "")), match_data.get("status_detail")
                )
                game.status = status
                game.period_status = period_status
                game.home_score = match_data.get("home_score")
                game.away_score = match_data.get("away_score")
                game.venue = match_data.get("venue_name")

                if game.status == "scheduled" and game.home_win_probability is None:
                    game.home_win_probability = estimate_home_win_probability(
                        home_team.win_pct or 0.5, away_team.win_pct or 0.5
                    )
                game.last_synced_at = datetime.now(timezone.utc)

            db.commit()
            logger.info("Partidos de '%s' sincronizados.", league_key)
        except Exception:
            db.rollback()
            logger.exception("No se pudieron sincronizar partidos de '%s'.", league_key)
    finally:
        db.close()


async def sync_mlb_rosters() -> None:
    """
    Sincroniza los jugadores (roster) de cada equipo de MLB. Es lo que
    permite que el buscador de estadísticas encuentre jugadores reales por
    nombre, no solo por ID.
    """
    db = SessionLocal()
    try:
        league = db.query(League).filter(League.key == "mlb").first()
        if not league:
            return

        teams = db.query(Team).filter(Team.league_id == league.id).all()
        for team in teams:
            try:
                roster_data = await mlb_service.get_team_roster(int(team.external_id), CURRENT_MLB_SEASON)
            except Exception:
                logger.exception("No se pudo obtener el roster del equipo '%s'.", team.name)
                continue

            for entry in roster_data.get("roster", []):
                person = entry.get("person", {})
                external_id = str(person.get("id", ""))
                if not external_id:
                    continue

                player = (
                    db.query(Player)
                    .filter(Player.team_id == team.id, Player.external_id == external_id)
                    .first()
                )
                if not player:
                    player = Player(team_id=team.id, external_id=external_id, full_name=person.get("fullName", ""))
                    db.add(player)

                player.full_name = person.get("fullName") or player.full_name
                player.position = entry.get("position", {}).get("abbreviation")
                player.jersey_number = entry.get("jerseyNumber")

        db.commit()
        logger.info("Roster de MLB sincronizado (%d equipos).", len(teams))
    finally:
        db.close()


def resolve_finished_predictions() -> None:
    """
    Recorre juegos finalizados con predicciones pendientes, determina si el
    usuario acertó y otorga puntos BFB según la probabilidad al momento de
    predecir. Se debe llamar después de sync_mlb_games.
    """
    db = SessionLocal()
    try:
        pending = (
            db.query(Prediction)
            .join(Game, Prediction.game_id == Game.id)
            .filter(Prediction.status == "pending", Game.status == "final")
            .all()
        )
        for prediction in pending:
            game = prediction.game
            winner_team_id = None
            if game.home_score is not None and game.away_score is not None:
                if game.home_score > game.away_score:
                    winner_team_id = game.home_team_id
                elif game.away_score > game.home_score:
                    winner_team_id = game.away_team_id

            if winner_team_id is None:
                continue  # empate u datos incompletos: se deja pendiente

            user = db.get(User, prediction.user_id)
            if prediction.predicted_team_id == winner_team_id:
                points = points_for_prediction(prediction.probability_at_pick)
                prediction.status = "correct"
                prediction.points_awarded = points
                user.bfb_points += points
            else:
                prediction.status = "incorrect"
                prediction.points_awarded = 0

            prediction.resolved_at = datetime.now(timezone.utc)

        db.commit()
        logger.info("Predicciones resueltas: %d", len(pending))
    finally:
        db.close()


async def sync_news() -> None:
    db = SessionLocal()
    try:
        sports = db.query(Sport).all()
        for sport in sports:
            try:
                articles = await news_service.fetch_general_news(sport.key, limit=15)
            except Exception:
                logger.exception("No se pudieron obtener noticias de '%s'.", sport.key)
                continue

            for article in articles:
                if not article["article_url"]:
                    continue

                existing = (
                    db.query(NewsArticle).filter(NewsArticle.article_url == article["article_url"]).first()
                )
                if existing:
                    # Se actualiza la imagen y el resumen aunque el artículo ya
                    # exista: si el artículo se guardó antes de una mejora en
                    # la extracción de imagen, esto permite que se "autocorrija"
                    # en el siguiente ciclo en vez de quedarse sin imagen para siempre.
                    existing.image_url = article["image_url"] or existing.image_url
                    if article["summary"] and article["summary"] != existing.summary:
                        existing.summary = article["summary"]
                        existing.summary_es = None  # el resumen cambió: se re-traduce abajo

                    # Solo se traduce si todavía no hay traducción (evita
                    # volver a traducir lo mismo cada 5 minutos sin necesidad).
                    if not existing.title_es:
                        existing.title_es = translation_service.translate_to_spanish(existing.title)
                    if not existing.summary_es and existing.summary:
                        existing.summary_es = translation_service.translate_to_spanish(existing.summary)
                    continue

                db.add(
                    NewsArticle(
                        sport_id=sport.id,
                        title=article["title"],
                        title_es=translation_service.translate_to_spanish(article["title"]),
                        summary=article["summary"],
                        summary_es=translation_service.translate_to_spanish(article["summary"]),
                        image_url=article["image_url"],
                        source=article["source"],
                        article_url=article["article_url"],
                        published_at=article["published_at"],
                    )
                )
            db.commit()
        logger.info("Noticias sincronizadas para %d deporte(s).", len(sports))
    finally:
        db.close()


async def run_full_sync() -> None:
    """Punto de entrada único para refrescar todo lo relacionado a todas las ligas + noticias."""
    db = SessionLocal()
    try:
        ensure_base_catalog(db)
    finally:
        db.close()

    await sync_mlb_teams_and_standings()
    await sync_mlb_games()
    await sync_mlb_rosters()

    if settings.BALLDONTLIE_API_KEY:
        for league_key in ("nba", "wnba", "ncaab"):
            try:
                await sync_basketball_league(league_key)
            except Exception:
                logger.exception("Fallo sincronizando la liga de basketball '%s'.", league_key)
            await asyncio.sleep(BALLDONTLIE_CALL_SPACING_SECONDS)
    else:
        logger.info("BALLDONTLIE_API_KEY no configurada: se omite la sincronización de basketball.")

    if settings.FOOTBALL_DATA_API_KEY:
        for league_key in ("epl", "laliga", "seriea", "bundesliga", "ligue1", "champions_league", "world_cup"):
            try:
                await sync_football_data_league(league_key)
            except Exception:
                logger.exception("Fallo sincronizando la liga de fútbol '%s' (football-data.org).", league_key)
            await asyncio.sleep(FOOTBALL_DATA_CALL_SPACING_SECONDS)
    else:
        logger.info("FOOTBALL_DATA_API_KEY no configurada: se omite la sincronización de fútbol/Mundial.")

    await sync_news()
    resolve_finished_predictions()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_full_sync())
