"""
Configuración central de BFB Deportes.

Todas las variables sensibles (contraseñas, claves de API, secretos JWT)
se leen desde el entorno (.env) y NUNCA se escriben directamente en el código.
"""
from functools import lru_cache
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- General ---
    PROJECT_NAME: str = "BFB Deportes"
    API_V1_PREFIX: str = "/api/v1"
    ENV: str = "development"  # development | production

    # --- Base de datos ---
    # Ejemplo: postgresql+psycopg2://usuario:password@localhost:5432/bfb_deportes
    DATABASE_URL: str = "postgresql+psycopg2://bfb_user:bfb_password@localhost:5432/bfb_deportes"

    @field_validator("DATABASE_URL")
    @classmethod
    def _normalize_database_url(cls, v: str) -> str:
        """
        Algunas plataformas (Railway, Heroku) entregan la URL de Postgres con
        el prefijo antiguo 'postgres://', que SQLAlchemy 2.0 ya no acepta.
        Se normaliza automáticamente a 'postgresql://' para evitar un error
        de arranque difícil de diagnosticar.
        """
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql://", 1)
        return v

    # --- Seguridad / JWT ---
    # SECRET_KEY debe generarse único por instalación. Nunca usar el valor por defecto en producción.
    SECRET_KEY: str = "CAMBIA_ESTA_CLAVE_POR_UNA_ALEATORIA_Y_SECRETA"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 días
    COOKIE_NAME: str = "bfb_session"

    # --- CORS ---
    # Lista de orígenes permitidos. En producción NUNCA usar "*".
    CORS_ORIGINS: List[str] = [
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]

    # --- APIs externas de datos deportivos ---
    # MLB Stats API es oficial, gratuita y no requiere API key.
    MLB_STATS_API_BASE: str = "https://statsapi.mlb.com/api/v1"

    # balldontlie.io cubre NBA, WNBA, NCAAB, NFL, NHL y varias ligas de fútbol
    # (EPL, La Liga, Serie A, Bundesliga, Ligue 1, MLS, Champions League, Mundial).
    # Requiere API key propia (nivel gratuito disponible). Se obtiene en https://balldontlie.io
    BALLDONTLIE_API_BASE: str = "https://api.balldontlie.io"
    BALLDONTLIE_API_KEY: str = ""

    # football-data.org: fútbol (EPL, La Liga, Serie A, Bundesliga, Ligue 1,
    # Champions League, Mundial). Gratis para siempre según su propio creador,
    # 10 peticiones/minuto. Se obtiene en https://www.football-data.org/client/register
    FOOTBALL_DATA_API_BASE: str = "https://api.football-data.org/v4"
    FOOTBALL_DATA_API_KEY: str = ""

    # --- Noticias (RSS oficiales, gratuitos, con imagen) ---
    NEWS_RSS_GENERAL: str = "https://www.espn.com/espn/rss/news"
    NEWS_RSS_MLB: str = "https://www.espn.com/espn/rss/mlb/news"
    NEWS_RSS_NBA: str = "https://www.espn.com/espn/rss/nba/news"
    NEWS_RSS_SOCCER: str = "https://www.espn.com/espn/rss/soccer/news"
    # Frecuencia mínima (minutos) entre refrescos de noticias por sección, para no saturar la fuente.
    NEWS_REFRESH_MINUTES: int = 15

    # --- Sistema de puntos BFB (predicciones) ---
    BET_MIN_POINTS: int = 2
    BET_MAX_POINTS: int = 20
    NEW_USER_STARTING_POINTS: int = 100

    # --- Rate limiting básico (login/registro) ---
    LOGIN_RATE_LIMIT_ATTEMPTS: int = 8
    LOGIN_RATE_LIMIT_WINDOW_SECONDS: int = 300

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """Cachea la instancia de configuración para no releer el .env en cada request."""
    return Settings()


settings = get_settings()
