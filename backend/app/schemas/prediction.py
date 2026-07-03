from datetime import datetime

from pydantic import BaseModel


class PredictionCreate(BaseModel):
    game_id: int
    predicted_team_id: int


class PredictionOut(BaseModel):
    id: int
    game_id: int
    predicted_team_id: int
    probability_at_pick: float
    status: str
    points_awarded: int
    created_at: datetime
    resolved_at: datetime | None

    class Config:
        from_attributes = True
