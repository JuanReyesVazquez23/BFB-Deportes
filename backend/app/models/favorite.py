from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Favorite(Base):
    """
    Favorito genérico: un usuario puede marcar como favorito un equipo,
    un jugador o una liga. Solo uno de team_id/player_id/league_id estará
    definido según favorite_type.
    """

    __tablename__ = "favorites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    favorite_type: Mapped[str] = mapped_column(String(10), nullable=False)  # team | player | league

    team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"), nullable=True)
    player_id: Mapped[int | None] = mapped_column(ForeignKey("players.id"), nullable=True)
    league_id: Mapped[int | None] = mapped_column(ForeignKey("leagues.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        UniqueConstraint("user_id", "favorite_type", "team_id", "player_id", "league_id", name="uq_favorite"),
    )

    user = relationship("User", back_populates="favorites")
    team = relationship("Team")
    player = relationship("Player")
    league = relationship("League")
