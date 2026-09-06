"""
highlight_service.py — Ponto único de lógica de negócio para highlight events.

Tanto o MQTT subscriber quanto (no 2º bi) endpoints REST chamam este módulo.
"""

import logging
import time

from services import influx_service
from services import video_stub

logger = logging.getLogger(__name__)

# Campos obrigatórios no payload de um evento
REQUIRED_FIELDS = {"court_id", "player", "event_type"}


def process_event(payload: dict) -> dict:
    """
    Orquestra o processamento de um highlight event recebido via MQTT (ou API).

    Etapas:
        1. Validação do payload
        2. Gravação no InfluxDB
        3. Chamada ao video_stub (simulação de captura)
        4. Log de sucesso

    Args:
        payload: Dicionário com os dados do evento MQTT.

    Returns:
        Dicionário com resultado do processamento.

    Raises:
        ValueError: Se o payload for inválido.
    """
    # ── 1. Validação ─────────────────────────────────────────────────────────
    missing = REQUIRED_FIELDS - payload.keys()
    if missing:
        raise ValueError(f"Payload inválido — campos faltando: {missing}")

    # Garante timestamp
    if "timestamp" not in payload:
        payload["timestamp"] = time.time()

    # ── 2. Gravar no InfluxDB ─────────────────────────────────────────────────
    influx_service.write_highlight(payload)

    # ── 3. Video stub ────────────────────────────────────────────────────────
    video_meta = video_stub.capture_highlight_clip(payload)

    # ── 4. Log de sucesso ─────────────────────────────────────────────────────
    logger.info(
        "🎾  Highlight processado | Quadra: %s | Jogador: %s | Tipo: %s",
        payload.get("court_id"),
        payload.get("player"),
        payload.get("event_type"),
    )

    return {
        "status": "ok",
        "event": payload,
        "video": video_meta,
    }
