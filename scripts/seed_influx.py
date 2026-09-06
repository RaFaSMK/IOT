"""
seed_influx.py — Popula o InfluxDB com ~50 eventos de teste espalhados nas últimas 24h.

Uso (após configurar INFLUX_TOKEN no .env ou variável de ambiente):
    python scripts/seed_influx.py

O script é idempotente — pode ser rodado múltiplas vezes (cria novos pontos,
mas não apaga dados existentes, pois cada ponto tem timestamp único).
"""

import random
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Garante acesso às configurações do backend
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from config.settings import settings  # noqa: E402 (import após sys.path)
from influxdb_client import InfluxDBClient, Point, WritePrecision  # noqa: E402
from influxdb_client.client.write_api import SYNCHRONOUS  # noqa: E402

# ── Parâmetros do seed ────────────────────────────────────────────────────────
NUM_EVENTS = 50
HOURS_BACK = 24
PLAYERS = ["A", "B"]
EVENT_TYPES = ["highlight", "ace", "winner", "error"]
COURT_IDS = ["court_01"]

# Cores ANSI
_GREEN = "\033[92m"
_CYAN = "\033[96m"
_YELLOW = "\033[93m"
_RESET = "\033[0m"


def generate_events(n: int = NUM_EVENTS) -> list[dict]:
    """Gera N eventos aleatórios espalhados nas últimas HOURS_BACK horas."""
    now = datetime.now(tz=timezone.utc)
    window_seconds = HOURS_BACK * 3600
    events = []

    for _ in range(n):
        offset = random.uniform(0, window_seconds)
        event_time = now - timedelta(seconds=offset)
        events.append({
            "time": event_time,
            "court_id": random.choice(COURT_IDS),
            "player": random.choice(PLAYERS),
            "event_type": random.choice(EVENT_TYPES),
        })

    # Ordenar cronologicamente para melhor visualização nos logs
    return sorted(events, key=lambda e: e["time"])


def seed():
    if not settings.INFLUX_TOKEN:
        print(f"{_YELLOW}⚠️  INFLUX_TOKEN não definido! Configure no .env ou variável de ambiente.{_RESET}")
        sys.exit(1)

    client = InfluxDBClient(
        url=settings.INFLUX_URL,
        token=settings.INFLUX_TOKEN,
        org=settings.INFLUX_ORG,
    )
    write_api = client.write_api(write_options=SYNCHRONOUS)

    print(f"\n{_CYAN}🌱  Gerando {NUM_EVENTS} eventos de seed nas últimas {HOURS_BACK}h...{_RESET}\n")

    events = generate_events(NUM_EVENTS)
    points = []

    for ev in events:
        point = (
            Point("highlight_events")
            .tag("court_id", ev["court_id"])
            .field("player", ev["player"])
            .field("event_type", ev["event_type"])
            .time(ev["time"], WritePrecision.S)
        )
        points.append(point)

        ts_str = ev["time"].strftime("%d/%m %H:%M:%S")
        print(f"  {_GREEN}•{_RESET} [{ts_str}] {ev['court_id']} | Jogador {ev['player']} | {ev['event_type']}")

    write_api.write(bucket=settings.INFLUX_BUCKET, org=settings.INFLUX_ORG, record=points)
    client.close()

    print(f"\n{_GREEN}✅  {NUM_EVENTS} eventos gravados no bucket '{settings.INFLUX_BUCKET}' com sucesso!{_RESET}")
    print(f"   Abra o dashboard em http://localhost:5173 ou a UI do InfluxDB em {settings.INFLUX_URL}\n")


if __name__ == "__main__":
    seed()
