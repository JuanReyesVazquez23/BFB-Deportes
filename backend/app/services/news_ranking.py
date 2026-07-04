"""
Detección de equipos mencionados en titulares de noticias, y cálculo de
"qué tan caliente" es una noticia según menciones reales — no es una API
de tendencias de terceros, es una métrica propia, explicable y verificable:
entre más noticias recientes hablen del mismo equipo, más "caliente" se
considera el tema.

Se usa para dos cosas:
1. Mostrar el logo del equipo junto a la noticia (si se detecta uno).
2. Ordenar "Noticias Generales" por relevancia real en vez de solo fecha,
   cuando el cliente pide sort=trending.
"""
import re
from collections import Counter

from app.models.sport import NewsArticle, Team

# Nombres muy cortos (ej. "Sox") se excluyen para evitar falsos positivos:
# "Red Sox" y "White Sox" ya vienen completos desde team.short_name, así que
# no hace falta (ni conviene) partirlos más.
MIN_NAME_LENGTH_FOR_MATCH = 4


def _candidate_names(team: Team) -> list[str]:
    """Nombres por los que un titular podría referirse a este equipo, del más específico al más genérico."""
    candidates = [team.short_name, team.name, team.abbreviation]
    return [c for c in candidates if c and len(c) >= MIN_NAME_LENGTH_FOR_MATCH]


def _text_mentions_name(text: str, name: str) -> bool:
    """Coincidencia de palabra completa, sin importar mayúsculas/minúsculas (evita que 'Cubs' matchee 'Cubside')."""
    pattern = r"\b" + re.escape(name) + r"\b"
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


def match_team_for_article(title: str, teams: list[Team]) -> Team | None:
    """Devuelve el primer equipo cuyo nombre aparece en el titular, o None si no se detecta ninguno."""
    for team in teams:
        for name in _candidate_names(team):
            if _text_mentions_name(title, name):
                return team
    return None


def annotate_and_rank(
    articles: list[NewsArticle], teams: list[Team], sort: str
) -> list[dict]:
    """
    Devuelve los artículos como dicts listos para NewsOut, con team_name/
    team_logo_url ya resueltos, y ordenados según 'sort':
    - "recent": más nuevas primero (comportamiento original, sin cambios).
    - "trending": las que comparten equipo/tema con más noticias del lote
      actual aparecen primero (empatando por fecha como criterio secundario).
    """
    matches: dict[int, Team | None] = {a.id: match_team_for_article(a.title, teams) for a in articles}

    mention_counts = Counter(team.id for team in matches.values() if team is not None)

    def heat_score(article: NewsArticle) -> int:
        team = matches[article.id]
        return mention_counts[team.id] if team else 0

    ordered = list(articles)
    if sort == "trending":
        ordered.sort(key=lambda a: (heat_score(a), a.published_at), reverse=True)
    # "recent" no reordena: ya viene ordenado por published_at desde la consulta.

    result = []
    for article in ordered:
        team = matches[article.id]
        result.append(
            {
                "id": article.id,
                "title": article.title,
                "summary": article.summary,
                "image_url": article.image_url,
                "source": article.source,
                "article_url": article.article_url,
                "published_at": article.published_at,
                "team_name": team.short_name or team.name if team else None,
                "team_logo_url": team.logo_url if team else None,
            }
        )
    return result
