"""
simulate_button.py — Simulador de botão físico para testes sem hardware.

Uso:
    # Modo interativo — cada ENTER = um clique no botão
    python scripts/simulate_button.py

    # Modo automático — publica N eventos com intervalo aleatório
    python scripts/simulate_button.py --auto --count 10 --min-delay 1 --max-delay 5
"""

import argparse
import json
import random
import sys
import time
from pathlib import Path

# Garante que o script funciona tanto de dentro quanto fora da pasta scripts/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import paho.mqtt.client as mqtt

# ── Configuração padrão (lê do .env do backend ou args) ───────────────────────
try:
    from config.settings import settings
    BROKER_HOST = settings.MQTT_BROKER_HOST
    BROKER_PORT = settings.MQTT_BROKER_PORT
    TOPIC = settings.MQTT_TOPIC
except Exception:
    import os
    BROKER_HOST = os.getenv("MQTT_BROKER_HOST", "broker.hivemq.com")
    BROKER_PORT = int(os.getenv("MQTT_BROKER_PORT", "1883"))
    TOPIC = os.getenv("MQTT_TOPIC", "quadra/highlight")


PLAYERS = ["A", "B"]
EVENT_TYPES = ["highlight", "ace", "winner", "error"]
COURT_ID = "court_01"

# ── Cores ANSI ────────────────────────────────────────────────────────────────
_GREEN = "\033[92m"
_YELLOW = "\033[93m"
_CYAN = "\033[96m"
_BOLD = "\033[1m"
_RESET = "\033[0m"


def build_payload(player: str | None = None) -> dict:
    """Gera um payload JSON simulando o botão do ESP32."""
    return {
        "court_id": COURT_ID,
        "player": player or random.choice(PLAYERS),
        "event_type": random.choice(EVENT_TYPES),
        "timestamp": int(time.time()),
    }


def publish_event(client: mqtt.Client, payload: dict) -> None:
    """Publica o payload no tópico MQTT e exibe no terminal."""
    raw = json.dumps(payload)
    result = client.publish(TOPIC, raw, qos=1)
    result.wait_for_publish()

    print(
        f"{_GREEN}📤  Publicado → {_CYAN}{TOPIC}{_RESET}  "
        f"{_BOLD}{raw}{_RESET}"
    )


def interactive_mode(client: mqtt.Client) -> None:
    """Modo interativo: cada ENTER simula um clique no botão."""
    print(f"\n{_YELLOW}{'─'*60}")
    print(f"  🎾  SIMULADOR DE BOTÃO — Quadra Inteligente de Beach Tennis")
    print(f"{'─'*60}{_RESET}")
    print("  Pressione  ENTER  para registrar um highlight.")
    print("  Digite   'A' ou 'B'  + ENTER para escolher o jogador.")
    print(f"  Digite   'q'  para sair.\n")

    while True:
        try:
            entrada = input(f"{_CYAN}[Botão]{_RESET} ").strip().upper()
        except (EOFError, KeyboardInterrupt):
            break

        if entrada == "Q":
            break

        player = entrada if entrada in PLAYERS else None
        payload = build_payload(player=player)
        publish_event(client, payload)


def auto_mode(client: mqtt.Client, count: int, min_delay: float, max_delay: float) -> None:
    """Modo automático: publica `count` eventos com intervalo aleatório."""
    print(f"\n{_YELLOW}🤖  MODO AUTOMÁTICO — {count} eventos ({min_delay}s – {max_delay}s de intervalo){_RESET}\n")
    for i in range(1, count + 1):
        payload = build_payload()
        publish_event(client, payload)
        print(f"   [{i}/{count}]")

        if i < count:
            delay = random.uniform(min_delay, max_delay)
            time.sleep(delay)

    print(f"\n{_GREEN}✅  {count} eventos publicados com sucesso!{_RESET}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Simulador de botão para o projeto Quadra Inteligente"
    )
    parser.add_argument("--auto", action="store_true", help="Modo automático")
    parser.add_argument("--count", type=int, default=5, help="Número de eventos (modo auto)")
    parser.add_argument("--min-delay", type=float, default=1.0, help="Delay mínimo em segundos")
    parser.add_argument("--max-delay", type=float, default=3.0, help="Delay máximo em segundos")
    parser.add_argument("--host", default=BROKER_HOST, help="Host do broker MQTT")
    parser.add_argument("--port", type=int, default=BROKER_PORT, help="Porta do broker MQTT")
    args = parser.parse_args()

    # Conectar ao broker
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id="smart-court-simulator",
    )
    client.connect(args.host, args.port, keepalive=60)
    client.loop_start()

    print(f"{_GREEN}✅  Conectado ao broker MQTT {args.host}:{args.port}{_RESET}")

    try:
        if args.auto:
            auto_mode(client, args.count, args.min_delay, args.max_delay)
        else:
            interactive_mode(client)
    finally:
        client.loop_stop()
        client.disconnect()
        print(f"{_YELLOW}👋  Desconectado.{_RESET}")


if __name__ == "__main__":
    main()
