"""Configuración HTTP compartida entre los distintos clientes de APIs externas."""
import httpx

# Timeout usado por todos los servicios que llaman APIs externas
# (MLB Stats API, RSS de noticias de ESPN).
DEFAULT_HTTP_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
