from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Prediction(Base):
    """
    Predicción de un usuario sobre el ganador de un partido que aún no comienza.

    Regla de negocio: el usuario NO arriesga puntos por adelantado al
    predecir. Si acierta, gana entre BET_MIN_POINTS y BET_MAX_POINTS puntos
    BFB (menos probable el ganador = más puntos). Si falla, PIERDE puntos
    (ver probability_service.points_lost_for_prediction) — más probable era
    que ganara el equipo elegido, más puntos se pierden al fallar. Los
    puntos del usuario nunca bajan de 0.
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

    # True por defecto (nada que avisar al crearla). resolve_finished_predictions
    # la pone en False al resolverse, para que el frontend sepa que hay un
    # resultado nuevo que el usuario todavía no vio; se marca True de nuevo
    # cuando el frontend lo muestra (ver /predictions/me/mark-seen).
    seen: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (UniqueConstraint("user_id", "game_id", name="uq_prediction_user_game"),)

    user = relationship("User", back_populates="predictions")
    game = relationship("Game", back_populates="predictions")
    predicted_team = relationship("Team")
