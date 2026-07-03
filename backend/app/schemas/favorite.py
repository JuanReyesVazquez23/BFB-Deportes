from pydantic import BaseModel, field_validator


class FavoriteCreate(BaseModel):
    favorite_type: str  # team | player | league
    target_id: int

    @field_validator("favorite_type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in ("team", "player", "league"):
            raise ValueError("favorite_type debe ser 'team', 'player' o 'league'.")
        return v


class FavoriteOut(BaseModel):
    id: int
    favorite_type: str
    team_id: int | None
    player_id: int | None
    league_id: int | None

    class Config:
        from_attributes = True
