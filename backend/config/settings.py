"""
Configurações centralizadas do backend — carregadas via variáveis de ambiente.
Copie .env.example para .env e preencha os valores antes de rodar.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # ── MQTT ─────────────────────────────────────────────────────────────────
    MQTT_BROKER_HOST: str = os.getenv("MQTT_BROKER_HOST", "localhost")
    MQTT_BROKER_PORT: int = int(os.getenv("MQTT_BROKER_PORT", "1883"))
    MQTT_TOPIC: str = os.getenv("MQTT_TOPIC", "quadra/highlight")
    MQTT_CLIENT_ID: str = os.getenv("MQTT_CLIENT_ID", "smart-court-backend")

    # ── InfluxDB 2.x ─────────────────────────────────────────────────────────
    INFLUX_URL: str = os.getenv("INFLUX_URL", "http://localhost:8086")
    INFLUX_TOKEN: str = os.getenv("INFLUX_TOKEN", "")      # obrigatório após setup
    INFLUX_ORG: str = os.getenv("INFLUX_ORG", "smart-court")
    INFLUX_BUCKET: str = os.getenv("INFLUX_BUCKET", "smart_court")

    # ── FastAPI / CORS ────────────────────────────────────────────────────────
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]


settings = Settings()
