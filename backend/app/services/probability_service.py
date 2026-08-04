"""
Cálculo de probabilidad de victoria y de los puntos BFB otorgados por
predicción acertada.

Regla de negocio (actualizada — antes no se perdían puntos al fallar):
- Cada partido no iniciado muestra una barra de probabilidad de victoria.
- Si el usuario predice correctamente, gana entre BET_MIN_POINTS y
  BET_MAX_POINTS puntos BFB. Entre más probable era que el equipo elegido
  ganara, MENOS puntos se otorgan; entre menos probable era, MÁS puntos.
- Si el usuario predice incorrectamente, PIERDE puntos: al revés que al
  acertar, entre más probable era que el equipo elegido ganara, MÁS puntos
  se pierden (una sorpresa grande sale más cara); entre menos probable era
  (una apuesta arriesgada), MENOS puntos se pierden, ya que perder era lo
  más esperable. Los puntos del usuario nunca bajan de 0.

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
RECENT_FORM_WEIGHT = 0.35  # peso de los últimos partidos frente al récord de temporada (0.65)


def estimate_home_win_probability(
    home_win_pct: float,
    away_win_pct: float,
    home_recent_form: float | None = None,
    away_recent_form: float | None = None,
) -> float:
    """
    Heurística: combina el % de victorias de la TEMPORADA con la forma
    RECIENTE de cada equipo (últimos partidos jugados), y aplica ventaja de
    localía. Devuelve un valor entre 0.05 y 0.95 (nunca 0% ni 100%, para
    evitar barras "imposibles").

    Por qué se agrega la forma reciente: dos equipos con récord de
    temporada parecido pueden estar en momentos muy distintos (uno en
    racha, otro de capa caída) — sin esto, todos los partidos entre
    equipos de nivel similar salían casi 50/50 sin importar cómo estuvieran
    jugando en ese momento. home_recent_form/away_recent_form son opcionales
    (None si el equipo casi no tiene partidos jugados todavía) para no
    fabricar una racha de la nada con muestras muy chicas.
    """
    home_strength = home_win_pct
    if home_recent_form is not None:
        home_strength = (1 - RECENT_FORM_WEIGHT) * home_win_pct + RECENT_FORM_WEIGHT * home_recent_form

    away_strength = away_win_pct
    if away_recent_form is not None:
        away_strength = (1 - RECENT_FORM_WEIGHT) * away_win_pct + RECENT_FORM_WEIGHT * away_recent_form

    total = home_strength + away_strength
    if total <= 0:
        base = 0.5
    else:
        base = home_strength / total

    probability = base + HOME_ADVANTAGE
    return max(0.05, min(0.95, probability))


def implied_probability_from_odds(decimal_odds: float) -> float:
    """Convierte una cuota decimal (ej. 1.80) en probabilidad implícita (0-1)."""
    if decimal_odds <= 1:
        raise ValueError("La cuota decimal debe ser mayor que 1.")
    return 1 / decimal_odds


# >1 separa más los puntos entre ambos equipos cerca del 50/50 (ver
# _skew_probability_for_points); 1.0 = lineal, sin separación extra.
POINTS_CURVE_STRENGTH = 1.8


def _skew_probability_for_points(p: float, strength: float = POINTS_CURVE_STRENGTH) -> float:
    """
    Antes de convertir una probabilidad en puntos, la aleja un poco más de
    su punto medio (0.5). Con la fórmula lineal simple, un partido
    moderadamente parejo (ej. 55%/45%) daba puntos casi idénticos para
    ambos equipos (ej. 10 contra 12) — poca diferencia para que se sienta
    interesante. Con esto, ese mismo partido separa más (ej. ~9 contra
    ~14), y un partido realmente parejo (50/50 exacto) se mantiene igual
    de parejo en puntos, que es lo correcto.

    IMPORTANTE: esto solo afecta el CÁLCULO DE PUNTOS. La probabilidad que
    se le muestra al usuario en la barra del partido (estimate_home_win_probability)
    NUNCA se toca — sigue siendo la estimación real y honesta de quién
    puede ganar; esto solo hace que el premio/castigo se sienta más
    diferenciado entre las dos opciones.
    """
    centered = (p - 0.5) * 2  # -1 (0%) a 1 (100%)
    sign = 1.0 if centered >= 0 else -1.0
    skewed = sign * (abs(centered) ** (1 / strength))
    return max(0.0, min(1.0, skewed / 2 + 0.5))


def points_for_prediction(probability_of_chosen_team: float) -> int:
    """
    Traduce la probabilidad del equipo elegido en puntos BFB otorgados si
    la predicción fue correcta.

    probability = 0.95 (muy probable que gane) -> puntos cercanos al mínimo
    probability = 0.05 (muy improbable que gane) -> puntos cercanos al máximo
    """
    p = _skew_probability_for_points(max(0.0, min(1.0, probability_of_chosen_team)))
    min_pts, max_pts = settings.BET_MIN_POINTS, settings.BET_MAX_POINTS

    points = max_pts - (max_pts - min_pts) * p
    return round(max(min_pts, min(max_pts, points)))


def points_lost_for_prediction(probability_of_chosen_team: float) -> int:
    """
    Puntos que se RESTAN cuando el equipo elegido termina perdiendo.

    Al revés que al acertar (ver points_for_prediction): entre MÁS
    probable era que el equipo elegido ganara, MÁS puntos se pierden si
    termina perdiendo — fue una sorpresa grande, un fallo "más caro".
    Entre MENOS probable era (una apuesta arriesgada a un equipo débil),
    MENOS puntos se pierden, ya que perder era el resultado más esperable.

    probability = 0.95 (muy probable que gane, y aun así pierde) -> pérdida cercana al máximo
    probability = 0.05 (muy improbable que gane, y en efecto pierde) -> pérdida cercana al mínimo
    """
    p = _skew_probability_for_points(max(0.0, min(1.0, probability_of_chosen_team)))
    min_pts, max_pts = settings.BET_MIN_POINTS, settings.BET_MAX_POINTS

    points = min_pts + (max_pts - min_pts) * p
    return round(max(min_pts, min(max_pts, points)))
