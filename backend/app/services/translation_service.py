"""
Traducción automática de contenido (noticias, jugadas en vivo) al español.

Se usa deep-translator con CADENA DE MOTORES (Google -> MyMemory): el
endpoint gratuito de Google Translate suele bloquear IPs de datacenters
(Render/Railway) con 429, lo que dejaba TODAS las noticias en inglés. Con
el respaldo, si Google falla se intenta MyMemory (gratis, sin key) antes
de rendirse al original en inglés.

REGLA IMPORTANTE: nunca se traducen nombres propios (equipos, jugadores,
ciudades, estadios) — nada de eso pasa por aquí. Solo texto libre como
titulares y resúmenes de noticias, o descripciones de jugadas.
"""
import logging

from deep_translator import GoogleTranslator, MyMemoryTranslator

logger = logging.getLogger("bfb.translation")

# Límite práctico por texto: motores gratuitos de traducción suelen tener
# un límite de caracteres por request (ej. 5000). Un titular o resumen de
# noticia nunca se acerca a esto, es solo una salvaguarda.
_MAX_CHARS = 4500


def _via_google(text: str) -> str | None:
    return GoogleTranslator(source="en", target="es").translate(text)


def _via_mymemory(text: str) -> str | None:
    return MyMemoryTranslator(source="en", target="es").translate(text)


def translate_to_spanish(text: str | None) -> str | None:
    """
    Traduce un texto de inglés a español probando Google primero y MyMemory
    como respaldo. Si todo falla (motores caídos, límites excedidos, sin
    conexión), devuelve None en vez de lanzar una excepción — así un fallo
    de traducción nunca rompe la sincronización de noticias ni la consulta
    de un partido en vivo. El código que llama a esto debe usar el texto
    original en inglés como respaldo cuando esto devuelve None.
    """
    if not text:
        return None
    clean = text[:_MAX_CHARS]
    for engine_name, engine in (("google", _via_google), ("mymemory", _via_mymemory)):
        try:
            out = engine(clean)
            if out and out.strip() and out.strip().lower() != clean.strip().lower():
                return out
        except Exception:
            logger.info("Motor de traducción '%s' falló; probando el siguiente.", engine_name)
            continue
    logger.warning("No se pudo traducir un texto al español; se usará el original en inglés como respaldo.")
    return None
