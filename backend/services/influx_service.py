"""
influx_service.py — Integração com InfluxDB 2.x.
Expõe funções para escrever e consultar highlight events.
"""

import logging
from datetime import datetime, timezone, timedelta
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

from config.settings import settings

logger = logging.getLogger(__name__)

# Cliente global (inicializado na primeira chamada ou no startup)
_client: InfluxDBClient | None = None
_write_api = None
_query_api = None


def get_client() -> InfluxDBClient:
    """Retorna (ou inicializa) o cliente InfluxDB."""
    global _client, _write_api, _query_api
    if _client is None:
        _client = InfluxDBClient(
            url=settings.INFLUX_URL,
            token=settings.INFLUX_TOKEN,
            org=settings.INFLUX_ORG,
        )
        _write_api = _client.write_api(write_options=SYNCHRONOUS)
        _query_api = _client.query_api()
        logger.info("✅  InfluxDB client inicializado → %s", settings.INFLUX_URL)
    return _client


def write_highlight(event_data: dict) -> None:
    """
    Escreve um highlight event como Point no InfluxDB.

    Esquema:
        measurement : highlight_events
        tags        : court_id
        fields      : player (str), event_type (str)
        time        : timestamp do evento (epoch seconds)
    """
    get_client()

    ts_raw = event_data.get("timestamp")
    if ts_raw:
        event_time = datetime.fromtimestamp(float(ts_raw), tz=timezone.utc)
    else:
        event_time = datetime.now(tz=timezone.utc)

    point = (
        Point("highlight_events")
        .tag("court_id", event_data.get("court_id", "unknown"))
        .field("player", event_data.get("player", "unknown"))
        .field("event_type", event_data.get("event_type", "highlight"))
        .time(event_time, WritePrecision.S)
    )

    _write_api.write(bucket=settings.INFLUX_BUCKET, org=settings.INFLUX_ORG, record=point)
    logger.info("💾  Highlight gravado no InfluxDB: %s", event_data)


def query_highlights(start: str = "-1h", stop: str = "now()") -> list[dict]:
    """
    Consulta eventos de highlight no intervalo [start, stop].

    Args:
        start: Offset relativo (ex: '-1h', '-24h') ou timestamp RFC3339.
        stop:  'now()' ou timestamp RFC3339.

    Returns:
        Lista de dicionários com os campos do evento.
    """
    get_client()

    flux = f"""
from(bucket: "{settings.INFLUX_BUCKET}")
  |> range(start: {start}, stop: {stop})
  |> filter(fn: (r) => r._measurement == "highlight_events")
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> sort(columns: ["_time"], desc: true)
  |> limit(n: 100)
"""
    tables = _query_api.query(flux, org=settings.INFLUX_ORG)

    results = []
    for table in tables:
        for record in table.records:
            results.append({
                "time": record.get_time().isoformat(),
                "court_id": record.values.get("court_id", ""),
                "player": record.values.get("player", ""),
                "event_type": record.values.get("event_type", ""),
            })
    return results


def query_highlight_counts(start: str = "-24h", bucket_interval: str = "1h") -> list[dict]:
    """
    Agrega a contagem de highlights por intervalo de tempo (para alimentar gráficos).

    Args:
        start:           Offset relativo do início da janela (ex: '-24h').
        bucket_interval: Tamanho do bucket de agregação (ex: '1h', '30m').

    Returns:
        Lista de dicionários com {time, count}.
    """
    get_client()

    flux = f"""
from(bucket: "{settings.INFLUX_BUCKET}")
  |> range(start: {start})
  |> filter(fn: (r) => r._measurement == "highlight_events" and r._field == "player")
  |> aggregateWindow(every: {bucket_interval}, fn: count, createEmpty: true)
  |> yield(name: "highlight_counts")
"""
    tables = _query_api.query(flux, org=settings.INFLUX_ORG)

    results = []
    for table in tables:
        for record in table.records:
            results.append({
                "time": record.get_time().isoformat(),
                "count": record.get_value() or 0,
            })
    return results


def check_health() -> dict:
    """Verifica se o InfluxDB está respondendo."""
    try:
        client = get_client()
        health = client.health()
        return {"status": health.status, "message": health.message}
    except Exception as exc:
        return {"status": "fail", "message": str(exc)}
