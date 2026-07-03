from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.sport import NewsArticle, Sport
from app.schemas.sport import NewsOut

router = APIRouter(prefix="/news", tags=["news"])


@router.get("/{sport_key}", response_model=list[NewsOut])
def get_sport_news(sport_key: str, limit: int = 15, db: Session = Depends(get_db)):
    """
    Noticias generales del deporte (ej. todo lo relacionado a béisbol,
    no solo de una liga). Se guardan en BD por el proceso de sincronización
    periódica y se sirven desde ahí para no golpear el feed RSS en cada visita.
    """
    sport = db.query(Sport).filter(Sport.key == sport_key).first()
    if not sport:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deporte no encontrado.")

    return (
        db.query(NewsArticle)
        .filter(NewsArticle.sport_id == sport.id)
        .order_by(NewsArticle.published_at.desc())
        .limit(limit)
        .all()
    )
