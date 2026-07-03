import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import auth, favorites, games, leagues, news, predictions, stats
from app.core.config import settings
from app.core.database import Base, SessionLocal, engine
from app.services.sync_service import ensure_base_catalog, run_full_sync

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bfb.main")

BACKGROUND_SYNC_INTERVAL_SECONDS = 300  # 5 minutos

# Ruta absoluta a la carpeta frontend/, calculada desde la ubicación de este
# archivo (backend/app/main.py -> sube 2 niveles -> backend/ -> frontend/).
# frontend/ vive DENTRO de backend/ a propósito: en Railway, el servicio está
# configurado con Root Directory=backend, así que solo lo que esté dentro de
# esa carpeta llega al build. Si frontend/ estuviera al lado de backend/
# (como estaba antes), Railway la excluiría del despliegue.
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


async def _background_sync_loop() -> None:
    """Refresca los datos deportivos periódicamente sin bloquear las peticiones HTTP."""
    while True:
        try:
            await run_full_sync()
        except Exception:  # noqa: BLE001 - un fallo de sync no debe tumbar el servidor
            logger.exception("Error durante la sincronización periódica.")
        await asyncio.sleep(BACKGROUND_SYNC_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # NOTA: create_all() es adecuado para desarrollo. En producción se
    # recomienda usar Alembic para migraciones versionadas del esquema.
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        ensure_base_catalog(db)
    finally:
        db.close()

    sync_task = asyncio.create_task(_background_sync_loop())
    yield
    sync_task.cancel()


app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,  # nunca "*" en producción cuando se usan cookies
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type"],
)

app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(leagues.router, prefix=settings.API_V1_PREFIX)
app.include_router(games.router, prefix=settings.API_V1_PREFIX)
app.include_router(news.router, prefix=settings.API_V1_PREFIX)
app.include_router(favorites.router, prefix=settings.API_V1_PREFIX)
app.include_router(predictions.router, prefix=settings.API_V1_PREFIX)
app.include_router(stats.router, prefix=settings.API_V1_PREFIX)


@app.get("/api/health")
def health_check():
    return {"status": "ok", "project": settings.PROJECT_NAME}


# Sirve el frontend estático (HTML/CSS/JS) desde el mismo servidor.
# Si la carpeta no existe (ej. estructura de despliegue distinta), se avisa
# claramente en los logs en vez de fallar con un error críptico de FastAPI.
if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
else:
    logger.warning(
        "No se encontró la carpeta frontend en %s; el sitio no se servirá "
        "desde este proceso (la API seguirá funcionando en %s).",
        FRONTEND_DIR,
        settings.API_V1_PREFIX,
    )
