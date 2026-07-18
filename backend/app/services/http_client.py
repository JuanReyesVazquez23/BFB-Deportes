"""Configuración HTTP compartida entre los distintos clientes de APIs externas."""
import httpx

# Timeout usado por todos los servicios que llaman APIs externas
# (MLB Stats API, balldontlie, football-data.org, RSS de noticias).
DEFAULT_HTTP_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
