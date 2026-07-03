"""
Cálculo de probabilidad de victoria y de los puntos BFB otorgados por
predicción acertada.

Regla de negocio (definida en la especificación del proyecto):
- Cada partido no iniciado muestra una barra de probabilidad de victoria.
- Si el usuario predice correctamente, gana entre BET_MIN_POINTS y
  BET_MAX_POINTS puntos BFB.
- Entre más probable era que el equipo elegido ganara, MENOS puntos se
  otorgan; entre menos probable era, MÁS puntos se otorgan.
- No hay pérdida de puntos por fallar (no es una apuesta con riesgo real).

Fuente de la probabilidad:
1) Si el proveedor de datos ofrece cuotas/odds reales (ej. balldontlie en
   sus planes con datos extendidos), se debe preferir esa probabilidad
   implícita real.
2) Si no hay cuotas disponibles (caso por defecto, ej. MLB Stats API no
   expone odds), se usa una heurística basada en el porcentaje de
   victorias de cada equipo más una ventaja de localía. Esto es una
   ESTIMACIÓN, no una probabilidad de casa de apuestas real, y así debe
   comunicarse en la interfaz ("probabilidad estimada").
"""
from app.core.config import settings

HOME_ADVANTAGE = 0.035  # 3.5 puntos porcentuales de ventaja para el equipo local


def estimate_home_win_probability(home_win_pct: float, away_win_pct: float) -> float:
    """
    Heurística simple: convierte la diferencia de % de victorias en una
    probabilidad, aplicando ventaja de local. Devuelve un valor entre
    0.05 y 0.95 (nunca 0% ni 100%, para evitar barras "imposibles").
    """
    total = home_win_pct + away_win_pct
    if total <= 0:
        base = 0.5
    else:
        base = home_win_pct / total

    probability = base + HOME_ADVANTAGE
    return max(0.05, min(0.95, probability))


def implied_probability_from_odds(decimal_odds: float) -> float:
    """Convierte una cuota decimal (ej. 1.80) en probabilidad implícita (0-1)."""
    if decimal_odds <= 1:
        raise ValueError("La cuota decimal debe ser mayor que 1.")
    return 1 / decimal_odds


def points_for_prediction(probability_of_chosen_team: float) -> int:
    """
    Traduce la probabilidad del equipo elegido en puntos BFB otorgados.

    probability = 0.95 (muy probable que gane) -> puntos cercanos al mínimo
    probability = 0.05 (muy improbable que gane) -> puntos cercanos al máximo
    """
    p = max(0.0, min(1.0, probability_of_chosen_team))
    min_pts, max_pts = settings.BET_MIN_POINTS, settings.BET_MAX_POINTS

    points = max_pts - (max_pts - min_pts) * p
    return round(max(min_pts, min(max_pts, points)))
