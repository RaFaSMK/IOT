"""
routes.py — Router FastAPI com os endpoints públicos da API.

Endpoints:
    GET /api/highlights          → Lista de eventos recentes
    GET /api/highlights/stats    → Contagem agrupada por intervalo (para gráfico)
    GET /api/health              → Status das conexões (Mosquitto, InfluxDB)
"""

import logging
import socket

from fastapi import APIRouter, Query, HTTPException

from config.settings import settings
from services import influx_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


# ── /api/highlights ───────────────────────────────────────────────────────────

@router.get("/highlights")
def list_highlights(
    start: str = Query(default="-1h", description="Início da janela (ex: '-1h', '-24h')"),
    stop: str = Query(default="now()", description="Fim da janela (padrão: agora)"),
):
    """
    Retorna até 100 highlight events no intervalo [start, stop].
    """
    try:
        events = influx_service.query_highlights(start=start, stop=stop)
        return {"total": len(events), "events": events}
    except Exception as exc:
        logger.exception("Erro ao consultar highlights")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ── /api/highlights/stats ──────────────────────────────────────────────────────

@router.get("/highlights/stats")
def highlight_stats(
    start: str = Query(default="-24h", description="Início da janela"),
    bucket_interval: str = Query(default="1h", description="Intervalo de agregação (ex: '1h', '30m')"),
):
    """
    Retorna a contagem de highlights agrupada por intervalo de tempo.
    Usado para alimentar o gráfico de série temporal no frontend.
    """
    try:
        counts = influx_service.query_highlight_counts(start=start, bucket_interval=bucket_interval)
        return {"series": counts}
    except Exception as exc:
        logger.exception("Erro ao agregar stats")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ── /api/health ───────────────────────────────────────────────────────────────

def _check_mqtt() -> dict:
    """Testa conectividade TCP com o broker MQTT."""
    try:
        with socket.create_connection(
            (settings.MQTT_BROKER_HOST, settings.MQTT_BROKER_PORT), timeout=2
        ):
            return {"status": "ok"}
    except OSError as exc:
        return {"status": "fail", "message": str(exc)}


@router.get("/health")
def health_check():
    """
    Retorna o status das dependências externas.
    """
    mqtt_status = _check_mqtt()
    influx_status = influx_service.check_health()

    overall = "ok" if mqtt_status["status"] == "ok" and influx_status["status"] == "pass" else "degraded"

    return {
        "status": overall,
        "dependencies": {
            "mqtt_broker": mqtt_status,
            "influxdb": influx_status,
        },
    }
