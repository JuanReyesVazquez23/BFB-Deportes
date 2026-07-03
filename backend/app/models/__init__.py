"""
Importa todos los modelos para que SQLAlchemy los registre en Base.metadata
antes de llamar a create_all(). Si se agrega un modelo nuevo, debe importarse aquí.
"""
from app.models.user import User  # noqa: F401
from app.models.sport import Sport, League, Team, Player, Game, NewsArticle  # noqa: F401
from app.models.favorite import Favorite  # noqa: F401
from app.models.prediction import Prediction  # noqa: F401
