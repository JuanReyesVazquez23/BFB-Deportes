from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Prediction(Base):
    """
    Predicción de un usuario sobre el ganador de un partido que aún no comienza.

    IMPORTANTE (regla de negocio, no es apuesta de dinero real ni de puntos
    en riesgo): el usuario NO arriesga puntos al predecir. Si acierta, gana
    entre BET_MIN_POINTS y BET_MAX_POINTS puntos BFB, calculados según qué
    tan probable era que ese equipo ganara (menos probable = más puntos).
    Si falla, no pierde puntos.
    """

    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), nullable=False)
    predicted_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)

    # Probabilidad del equipo elegido en el momento de hacer la predicción (0-1).
    probability_at_pick: Mapped[float] = mapped_column(Float, nullable=False)

    # pending | correct | incorrect
    status: Mapped[str] = mapped_column(String(15), default="pending", nullable=False)
    points_awarded: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (UniqueConstraint("user_id", "game_id", name="uq_prediction_user_game"),)

    user = relationship("User", back_populates="predictions")
    game = relationship("Game", back_populates="predictions")
    predicted_team = relationship("Team")
