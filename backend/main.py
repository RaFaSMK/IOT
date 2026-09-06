"""
main.py — Entrypoint do backend FastAPI.

Responsabilidades:
    1. Configura logging colorido
    2. Cria a app FastAPI com CORS middleware
    3. Inclui o router de api/routes.py
    4. No evento `startup`, inicia o MQTT subscriber em uma thread daemon
    5. Roda via uvicorn na porta 8000
"""

import logging
import sys
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.settings import settings

# ── Logging ───────────────────────────────────────────────────────────────────

# Força UTF-8 no terminal Windows (evita crash com emojis nos logs)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)

logger = logging.getLogger(__name__)


# ── Lifespan (startup / shutdown) ─────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa recursos assíncronos na subida do servidor."""
    logger.info("🚀  Iniciando Smart Court Backend...")

    # Importação tardia para evitar ciclos e erros antes de logging estar pronto
    from mqtt.subscriber import start_subscriber
    start_subscriber()

    logger.info("✅  Backend pronto. Acesse: http://localhost:%s/docs", settings.API_PORT)
    yield

    # Cleanup (se necessário no futuro)
    logger.info("🛑  Backend encerrado.")


# ── App FastAPI ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="🎾 Quadra Inteligente de Beach Tennis — API",
    description=(
        "Backend IoT para captura e visualização de highlights em tempo real. "
        "Fluxo: Botão → MQTT → Mosquitto → FastAPI → InfluxDB → Vue Dashboard."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — permite o frontend Vue (dev server na 5173) acessar a API
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
from api.routes import router as api_router  # noqa: E402
app.include_router(api_router)


# ── Entrypoint ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=False,
        log_level="info",
    )
