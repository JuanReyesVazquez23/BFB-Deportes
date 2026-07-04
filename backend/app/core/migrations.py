"""
Migraciones ligeras para columnas nuevas en tablas que YA existen en la
base de datos (por ejemplo, en producción/Railway).

Por qué existe este archivo: Base.metadata.create_all() (usado en el
arranque de la app) solo crea tablas que todavía no existen — nunca
modifica una tabla que ya está creada. Si agregamos una columna nueva a un
modelo (ej. Team.short_name) y la base de datos ya tiene la tabla "teams"
creada de antes, create_all() la ignora y la app fallaría al intentar leer
o escribir esa columna inexistente.

Cada sentencia usa "ADD COLUMN IF NOT EXISTS", así que:
- Es segura de ejecutar en cada arranque (no falla si la columna ya existe).
- No borra ni modifica datos existentes.
- En una base de datos nueva (recién creada), create_all() ya incluye estas
  columnas desde el principio, así que aquí simplemente no habría nada que
  hacer (la sentencia es un no-op).

Nota: para un proyecto que crezca más, lo correcto a mediano plazo es migrar
a Alembic (ya lo señala el README como próximo paso). Esto es un puente
seguro mientras tanto, no un reemplazo definitivo de Alembic.
"""
import logging

from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger("bfb.migrations")

# Cada entrada es una sentencia SQL idempotente. Se agregan aquí a futuro
# nuevas columnas que necesiten "parchear" tablas ya existentes.
_LIGHTWEIGHT_MIGRATIONS = [
    "ALTER TABLE teams ADD COLUMN IF NOT EXISTS short_name VARCHAR(60)",
]


def run_lightweight_migrations(engine: Engine) -> None:
    with engine.begin() as conn:
        for statement in _LIGHTWEIGHT_MIGRATIONS:
            conn.execute(text(statement))
    logger.info("Migraciones ligeras aplicadas correctamente (%d sentencias).", len(_LIGHTWEIGHT_MIGRATIONS))
