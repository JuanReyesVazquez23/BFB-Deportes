"""
Obtención de noticias deportivas reales vía RSS de ESPN.

Términos de uso de ESPN RSS (obligatorio cumplir):
- Solo se muestra el contenido tal cual viene en el feed (título + resumen),
  sin modificarlo.
- Siempre se debe enlazar al artículo completo en espn.com.
- Siempre se debe indicar que el contenido proviene de ESPN.
- No se debe incluir publicidad dentro del contenido del feed.

Esta función NO reproduce el artículo completo, solo el resumen que ESPN
distribuye en su propio feed público para ese fin.
"""
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import feedparser
import httpx

from app.core.config import settings

from app.services.http_client import DEFAULT_HTTP_TIMEOUT as TIMEOUT

FEEDS_BY_SPORT = {
    "baseball": settings.NEWS_RSS_MLB,
    "basketball": settings.NEWS_RSS_NBA,
    "football": settings.NEWS_RSS_SOCCER,
}

# Busca el primer <img src="..."> dentro de HTML (algunos feeds de ESPN
# incrustan la imagen directamente en el resumen en vez de usar una etiqueta
# de imagen aparte).
_IMG_TAG_PATTERN = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)


def _extract_image(entry: dict) -> str | None:
    """
    Busca la imagen real del artículo, probando las distintas formas en que
    un feed RSS puede exponerla, de la más específica a la más genérica:
    1) media:content / media:thumbnail (extensión Media RSS)
    2) <enclosure> (método clásico de RSS, común en varios feeds de ESPN)
    3) una etiqueta <img> incrustada dentro del HTML del resumen
    """
    if entry.get("media_content"):
        return entry["media_content"][0].get("url")
    if entry.get("media_thumbnail"):
        return entry["media_thumbnail"][0].get("url")

    for enclosure in entry.get("enclosures", []):
        if enclosure.get("type", "").startswith("image") or enclosure.get("href", "").lower().endswith(
            (".jpg", ".jpeg", ".png", ".webp")
        ):
            return enclosure.get("href")

    for link in entry.get("links", []):
        if link.get("type", "").startswith("image"):
            return link.get("href")

    summary_html = entry.get("summary", "")
    match = _IMG_TAG_PATTERN.search(summary_html)
    if match:
        return match.group(1)

    return None


def _strip_html(html_text: str) -> str:
    """Deja solo texto legible, sin etiquetas HTML. Nunca se inserta HTML de terceros sin sanear."""
    text = re.sub(r"<[^>]+>", " ", html_text)
    return re.sub(r"\s+", " ", text).strip()


def _parse_date(entry: dict) -> datetime:
    published = entry.get("published")
    if published:
        try:
            return parsedate_to_datetime(published)
        except (TypeError, ValueError):
            pass
    return datetime.now(timezone.utc)


async def fetch_rss_news(feed_url: str, limit: int = 15) -> list[dict]:
    """Descarga y parsea un feed RSS, devolviendo una lista de artículos normalizados."""
    async with httpx.AsyncClient(timeout=TIMEOUT, headers={"User-Agent": "BFBDeportes/1.0"}) as client:
        resp = await client.get(feed_url)
        resp.raise_for_status()
        raw = resp.content

    parsed = feedparser.parse(raw)
    articles = []
    for entry in parsed.entries[:limit]:
        articles.append(
            {
                "title": entry.get("title", "").strip(),
                "summary": _strip_html(entry.get("summary", "")).strip() or None,
                "image_url": _extract_image(entry),
                "source": "ESPN",
                "article_url": entry.get("link"),
                "published_at": _parse_date(entry),
            }
        )
    return articles


async def fetch_general_baseball_news(limit: int = 10) -> list[dict]:
    return await fetch_rss_news(settings.NEWS_RSS_MLB, limit=limit)


async def fetch_general_news(sport_key: str, limit: int = 10) -> list[dict]:
    feed_url = FEEDS_BY_SPORT.get(sport_key, settings.NEWS_RSS_GENERAL)
    return await fetch_rss_news(feed_url, limit=limit)
