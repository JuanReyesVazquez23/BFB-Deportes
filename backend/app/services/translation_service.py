"""
Traducción automática de contenido (noticias, jugadas en vivo) al español.

Se eligió deep-translator en vez de la librería "googletrans" porque esta
última usa un endpoint no oficial de Google Translate que su propio autor
advierte explícitamente: "no garantiza que la librería funcione en todo
momento" y puede bloquearse sin aviso. deep-translator envuelve varios
motores de traducción con una interfaz más estable, y es más fácil
cambiar de motor si uno falla.

REGLA IMPORTANTE: nunca se traducen nombres propios (equipos, jugadores,
ciudades, estadios) — nada de eso pasa por aquí. Solo texto libre como
titulares y resúmenes de noticias, o descripciones de jugadas.
"""
import logging

from deep_translator import GoogleTranslator

logger = logging.getLogger("bfb.translation")

# Límite práctico por texto: motores gratuitos de traducción suelen tener
# un límite de caracteres por request (ej. 5000). Un titular o resumen de
# noticia nunca se acerca a esto, es solo una salvaguarda.
_MAX_CHARS = 4500


def translate_to_spanish(text: str | None) -> str | None:
    """
    Traduce un texto de inglés a español. Si la traducción falla por
    cualquier motivo (motor caído, límite excedido, sin conexión), devuelve
    None en vez de lanzar una excepción — así un fallo de traducción nunca
    rompe la sincronización de noticias ni la consulta de un partido en vivo.
    El código que llama a esto debe usar el texto original en inglés como
    respaldo cuando esto devuelve None.
    """
    if not text:
        return None
    try:
        return GoogleTranslator(source="en", target="es").translate(text[:_MAX_CHARS])
    except Exception:
        logger.warning("No se pudo traducir un texto al español; se usará el original en inglés como respaldo.")
        return None
