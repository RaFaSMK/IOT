import re
import json
from functools import lru_cache
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from .config import secrets


@lru_cache
def client():
    return InfluxDBClient(url='http://influxdb:8086', token=secrets()['influx_token'], org='smart-court', timeout=10000)


def write(event):
    points = []
    if event.type == 'telemetry':
        for identifier, value in event.payload['sensors'].items():
            if isinstance(value, bool) or not isinstance(value, (float, int)):
                raise ValueError('Leitura de sensor deve ser numérica.')
            points.append(Point('sensor_readings').tag('court_id', 'court_01').tag('device_id', identifier).field('value', float(value)).field('event_id', event.id).time(event.timestamp, WritePrecision.NS))
        equipment = Point('equipment_telemetry').tag('device_id', event.device_id).field('event_id', event.id).time(event.timestamp, WritePrecision.NS)
        for name, value in event.payload['sensors'].items():
            equipment.field(name, float(value))
        for name, value in event.payload['actuators'].items():
            equipment.field(name, bool(value))
        for name, value in event.payload.get('simulation', {}).items():
            equipment.field('simulation_' + name, float(value))
        points.append(equipment)
    elif event.type == 'highlight':
        data = event.payload
        points.append(Point('highlight_events').tag('court_id', 'court_01').tag('event_id', event.id).field('player', data['player']).field('event_type', data['event_type']).time(event.timestamp, WritePrecision.NS))
    client().write_api(write_options=SYNCHRONOUS).write(bucket='smart_court', record=points)


def duration(value):
    if not re.fullmatch(r'-?[1-9][0-9]{0,3}[mhdw]', value):
        raise ValueError('Use duração relativa, por exemplo -1h ou -7d.')
    return value if value.startswith('-') else '-' + value


def history(device_id, start='-1h', limit=300):
    start = duration(start)
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', device_id):
        raise ValueError('Dispositivo inválido.')
    flux = f'''from(bucket: "smart_court") |> range(start: {start})
      |> filter(fn: (r) => r._measurement == "sensor_readings" and r.device_id == {json.dumps(device_id)} and r._field == "value")
      |> aggregateWindow(every: 10s, fn: mean, createEmpty: false)
      |> group() |> sort(columns: ["_time"], desc: true) |> limit(n: {min(max(limit, 1), 1000)})'''
    results = [{'time': row.get_time().isoformat(), 'value': row.get_value()} for table in client().query_api().query(flux) for row in table.records]
    return sorted(results, key=lambda row: row['time'])


def highlights(start='-1h', limit=100):
    start = duration(start)
    flux = f'''from(bucket: "smart_court") |> range(start: {start})
      |> filter(fn: (r) => r._measurement == "highlight_events")
      |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
      |> group() |> sort(columns: ["_time"], desc: true) |> limit(n: {min(max(limit, 1), 1000)})'''
    return [{'id': row.values.get('event_id', ''), 'time': row.get_time().isoformat(), 'court_id': row.values.get('court_id', ''), 'player': row.values.get('player', ''), 'event_type': row.values.get('event_type', '')} for table in client().query_api().query(flux) for row in table.records]


def stats(start='-24h', interval='1h'):
    start = duration(start)
    interval = duration(interval).lstrip('-')
    flux = f'''from(bucket: "smart_court") |> range(start: {start})
      |> filter(fn: (r) => r._measurement == "highlight_events" and r._field == "player")
      |> group() |> aggregateWindow(every: {interval}, fn: count, createEmpty: true)'''
    return [{'time': row.get_time().isoformat(), 'count': row.get_value() or 0} for table in client().query_api().query(flux) for row in table.records]
