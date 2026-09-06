"""
subscriber.py — MQTT subscriber usando Paho-MQTT 2.x.

Conecta ao Mosquitto, subscreve ao tópico configurado e delega o
processamento de cada mensagem ao highlight_service.
"""

import json
import logging
import threading

import paho.mqtt.client as mqtt

from config.settings import settings
from services import highlight_service

logger = logging.getLogger(__name__)

# ── Cores ANSI para log colorido no terminal ─────────────────────────────────
_GREEN = "\033[92m"
_YELLOW = "\033[93m"
_RED = "\033[91m"
_CYAN = "\033[96m"
_RESET = "\033[0m"


def _on_connect(client: mqtt.Client, userdata, flags, reason_code, properties):
    """Callback chamado quando a conexão com o broker é estabelecida."""
    if reason_code == 0:
        logger.info("%s📡  MQTT conectado ao broker %s:%s%s",
                    _GREEN, settings.MQTT_BROKER_HOST, settings.MQTT_BROKER_PORT, _RESET)
        client.subscribe(settings.MQTT_TOPIC)
        logger.info("%s📌  Subscrito ao tópico: %s%s", _CYAN, settings.MQTT_TOPIC, _RESET)
    else:
        logger.error("%s❌  Falha ao conectar ao MQTT broker — reason_code=%s%s",
                     _RED, reason_code, _RESET)


def _on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
    """Callback chamado quando a conexão é perdida."""
    if reason_code != 0:
        logger.warning("%s⚠️   Desconectado do MQTT broker (reason=%s). Reconectando...%s",
                       _YELLOW, reason_code, _RESET)


def _on_message(client: mqtt.Client, userdata, message: mqtt.MQTTMessage):
    """Callback chamado para cada mensagem recebida."""
    raw = message.payload.decode("utf-8")
    logger.info("%s📨  MQTT [%s] → %s%s", _CYAN, message.topic, raw, _RESET)

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.error("%s❌  Payload inválido (não é JSON): %s%s", _RED, exc, _RESET)
        return

    try:
        result = highlight_service.process_event(payload)
        logger.info("%s✅  Evento processado: %s%s", _GREEN, result["event"], _RESET)
    except ValueError as exc:
        logger.error("%s❌  Payload rejeitado: %s%s", _RED, exc, _RESET)
    except Exception as exc:
        logger.exception("%s💥  Erro inesperado ao processar evento: %s%s", _RED, exc, _RESET)


def start_subscriber() -> threading.Thread:
    """
    Cria e inicia o cliente MQTT em uma thread daemon.

    Returns:
        Thread que executa o loop MQTT (já iniciada).
    """
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=settings.MQTT_CLIENT_ID,
    )

    client.on_connect = _on_connect
    client.on_disconnect = _on_disconnect
    client.on_message = _on_message

    client.connect(
        host=settings.MQTT_BROKER_HOST,
        port=settings.MQTT_BROKER_PORT,
        keepalive=60,
    )

    thread = threading.Thread(target=client.loop_forever, daemon=True, name="mqtt-subscriber")
    thread.start()
    logger.info("🚀  MQTT subscriber iniciado em thread daemon.")
    return thread
