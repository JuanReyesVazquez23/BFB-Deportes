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
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.prediction import Prediction
from app.models.sport import Game, League, NewsArticle, Sport, Team
from app.models.user import User
from app.services import mlb_service, news_service
from app.services.probability_service import estimate_home_win_probability, points_for_prediction

logger = logging.getLogger("bfb.sync")

CURRENT_MLB_SEASON = datetime.now(timezone.utc).year


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
    return league


def ensure_base_catalog(db: Session) -> None:
    """Crea los deportes y la liga MLB si todavía no existen (idempotente)."""
    baseball = _get_or_create_sport(db, "baseball", "Béisbol", "Baseball")
    _get_or_create_sport(db, "football", "Fútbol", "Football")
    _get_or_create_sport(db, "basketball", "Basketball", "Basketball")

    _get_or_create_league(db, baseball, "mlb", "MLB", provider="mlb_stats_api", is_primary=True)


async def sync_mlb_teams_and_standings() -> None:
    db = SessionLocal()
    try:
        league = db.query(League).filter(League.key == "mlb").first()
        if not league:
            logger.warning("Liga MLB no existe todavía en la BD; ejecuta ensure_base_catalog primero.")
            return

        standings_data = await mlb_service.get_standings(CURRENT_MLB_SEASON)
        for record in standings_data.get("records", []):
            for team_record in record.get("teamRecords", []):
                team_info = team_record["team"]
                external_id = str(team_info["id"])

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
                team.wins = wins
                team.losses = losses
                team.win_pct = round(wins / total, 3) if total else 0.0
                team.division = record.get("division", {}).get("name")
                team.standings_updated_at = datetime.now(timezone.utc)

        db.commit()
        logger.info("Posiciones de MLB sincronizadas correctamente.")
    finally:
        db.close()


async def sync_mlb_games(target_date: date | None = None) -> None:
    db = SessionLocal()
    try:
        league = db.query(League).filter(League.key == "mlb").first()
        if not league:
            return

        target_date = target_date or datetime.now(timezone.utc).date()
        schedule = await mlb_service.get_schedule(target_date)

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

                game.home_score = game_data["teams"]["home"].get("score")
                game.away_score = game_data["teams"]["away"].get("score")
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

        db.commit()
        logger.info("Calendario de MLB sincronizado para %s.", target_date)
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
        baseball = db.query(Sport).filter(Sport.key == "baseball").first()
        if not baseball:
            return

        articles = await news_service.fetch_general_baseball_news(limit=15)
        for article in articles:
            exists = db.query(NewsArticle).filter(NewsArticle.article_url == article["article_url"]).first()
            if exists or not article["article_url"]:
                continue
            db.add(
                NewsArticle(
                    sport_id=baseball.id,
                    title=article["title"],
                    summary=article["summary"],
                    image_url=article["image_url"],
                    source=article["source"],
                    article_url=article["article_url"],
                    published_at=article["published_at"],
                )
            )
        db.commit()
        logger.info("Noticias de béisbol sincronizadas.")
    finally:
        db.close()


async def run_full_sync() -> None:
    """Punto de entrada único para refrescar todo lo relacionado a MLB + noticias."""
    db = SessionLocal()
    try:
        ensure_base_catalog(db)
    finally:
        db.close()

    await sync_mlb_teams_and_standings()
    await sync_mlb_games()
    await sync_news()
    resolve_finished_predictions()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_full_sync())
