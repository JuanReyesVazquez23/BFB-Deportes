from datetime import datetime

from pydantic import BaseModel


class SportOut(BaseModel):
    id: int
    key: str
    name_es: str
    name_en: str

    class Config:
        from_attributes = True


class LeagueOut(BaseModel):
    id: int
    key: str
    name: str
    country: str | None
    logo_url: str | None
    is_primary: bool

    class Config:
        from_attributes = True


class TeamOut(BaseModel):
    id: int
    name: str
    abbreviation: str | None
    city: str | None
    logo_url: str | None
    wins: int
    losses: int
    ties: int
    win_pct: float
    division: str | None
    conference: str | None

    class Config:
        from_attributes = True


class PlayerOut(BaseModel):
    id: int
    full_name: str
    position: str | None
    jersey_number: str | None
    photo_url: str | None
    team_id: int

    class Config:
        from_attributes = True


class GameOut(BaseModel):
    id: int
    external_id: str
    start_time: datetime
    status: str
    home_team: TeamOut
    away_team: TeamOut
    home_score: int | None
    away_score: int | None
    home_win_probability: float | None
    venue: str | None
    period_status: str | None

    class Config:
        from_attributes = True


class GameDetailOut(GameOut):
    """Incluye el detalle específico del deporte (pitcher ganador, boxscore, goleadores...)."""

    details: dict | None

    class Config:
        from_attributes = True


class NewsOut(BaseModel):
    id: int
    title: str
    summary: str | None
    image_url: str | None
    source: str
    article_url: str
    published_at: datetime

    class Config:
        from_attributes = True
