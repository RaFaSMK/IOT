"""
video_stub.py — Simula captura de vídeo de um highlight.
No 2º bimestre, este módulo será substituído por integração real.
"""

import logging
import time
from datetime import datetime

logger = logging.getLogger(__name__)

# Pasta onde os stubs de vídeo seriam salvos (apenas log/arquivo dummy)
VIDEO_OUTPUT_DIR = "videos"


def capture_highlight_clip(event_data: dict) -> dict:
    """
    Simula a captura de 10 segundos de vídeo ao redor de um highlight.

    Args:
        event_data: Dicionário com dados do evento (court_id, player, timestamp, etc.)

    Returns:
        Dicionário com metadados do vídeo stub.
    """
    court_id = event_data.get("court_id", "unknown")
    player = event_data.get("player", "unknown")
    ts = event_data.get("timestamp", time.time())
    dt = datetime.fromtimestamp(float(ts))

    clip_filename = f"highlight_{court_id}_{player}_{int(ts)}.mp4"
    clip_path = f"{VIDEO_OUTPUT_DIR}/{clip_filename}"

    logger.info("🎬  [VIDEO STUB] Iniciando captura de highlight...")
    logger.info("🎬  [VIDEO STUB] Quadra: %s | Jogador: %s | Horário: %s",
                court_id, player, dt.strftime("%H:%M:%S"))
    logger.info("🎬  [VIDEO STUB] Gravando 10s de vídeo → %s", clip_path)
    logger.info("🎬  [VIDEO STUB] Captura concluída (simulado). "
                "Integração real prevista para o 2º bimestre.")

    return {
        "status": "stub",
        "clip_filename": clip_filename,
        "clip_path": clip_path,
        "duration_seconds": 10,
        "note": "Video capture is simulated. Real integration planned for 2nd semester.",
    }
