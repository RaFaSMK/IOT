import json
import logging
import queue
import time
from collections import deque
from datetime import datetime
from pathlib import Path
import numpy as np
import paho.mqtt.client as mqtt
from .config import credential
from .contracts import Event, Command
from .equipment import STEP_HOURS, PUBLISH_SECONDS, NATURAL_RATE, compressor_signals, load_at, ambient_at

log = logging.getLogger(__name__)


class Court:
    def __init__(self, seed=42):
        self.rng = np.random.default_rng(seed)
        self.cooling = False
        self.floodlights = False
        self.paused = False
        self.water = 19.
        self.wear = 0.
        self.fault = False
        self.tick = 0
        self.offsets = self.rng.normal(0, [.6, .04, .05])
        self.mode = 'bearing'
        self.fault_duration = 6.
        self.fault_rate = 1 / self.fault_duration

    def command(self, device, payload):
        command = Command.model_validate(payload)
        if command.action == 'set':
            if device not in ['cooling', 'floodlights'] or command.on is None:
                raise ValueError('Atuador ou estado inválido.')
            setattr(self, device, command.on)
        elif command.action in ['inject_fault', 'reset_fault']:
            if device != 'compressor_01':
                raise ValueError('Falha só pode ser injetada no compressor.')
            self.fault = command.action == 'inject_fault'
            if self.fault:
                self.fault_rate = (1 - self.wear) / self.fault_duration
            if not self.fault:
                self.wear = 0
        elif command.action in ['pause', 'resume']:
            if device != 'simulator':
                raise ValueError('Controle destinado ao simulador.')
            self.paused = command.action == 'pause'
        elif command.action == 'highlight':
            if device != 'highlight_button':
                raise ValueError('Comando destinado ao botão de highlight.')
            return Event(type='highlight', device_id=device, payload={'court_id': 'court_01', 'player': command.player, 'event_type': 'highlight'})
        return None

    def sample(self):
        self.tick += 1
        # Ciclo virtual acelerado para a demonstração; não revela desgaste nos dados.
        hours = self.tick * STEP_HOURS
        hour = hours % 24
        daylight = max(0, np.sin((hour - 6) * np.pi / 12))
        ambient = float(ambient_at(hours)) + self.rng.normal(0, .25)
        humidity = 72 - 23 * daylight + self.rng.normal(0, 1)
        luminosity = 60000 * daylight + self.rng.uniform(0, 50)
        if self.cooling:
            self.wear = min(1., self.wear + STEP_HOURS * (self.fault_rate if self.fault else NATURAL_RATE))
            self.water += .10 + self.wear * .22 - .35
        else:
            self.water += (ambient - self.water) * .018
        self.water = float(np.clip(self.water, 5, ambient))
        temperature, current, vibration = compressor_signals(ambient, load_at(hours), self.wear, self.cooling, self.mode, self.offsets, self.rng)
        return Event(type='telemetry', device_id='compressor_01', payload={
            'court_id': 'court_01',
            'sensors': {'ambient_temperature': round(float(ambient), 2), 'humidity': round(float(humidity), 2), 'luminosity': round(float(luminosity), 1), 'water_temperature': round(self.water, 2), 'compressor_temperature': round(float(temperature), 2), 'compressor_current': round(float(current), 3), 'compressor_vibration': round(float(vibration), 3)},
            'actuators': {'cooling': self.cooling, 'floodlights': self.floodlights},
            'simulation': {'step_hours': STEP_HOURS, 'elapsed_hours': hours},
        })


def main():
    logging.basicConfig(level=logging.INFO)
    court = Court()
    inbox = queue.Queue(maxsize=100)
    seen = deque(maxlen=1000)
    connected = False
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id='court-simulator')
    cred = credential('simulator')
    client.username_pw_set(cred['user'], cred['password'])

    def connect(c, _, flags, reason, properties):
        nonlocal connected
        connected = reason == 0
        if connected:
            c.subscribe('court/court_01/command/#', qos=1)

    def disconnect(*args):
        nonlocal connected
        connected = False

    def message(c, _, msg):
        try:
            inbox.put_nowait(Event.model_validate_json(msg.payload))
        except Exception:
            log.exception('Comando inválido')

    client.on_connect = connect
    client.on_disconnect = disconnect
    client.on_message = message
    client.connect_async('mosquitto', 1883)
    client.loop_start()
    try:
        while True:
            while not inbox.empty():
                event = inbox.get_nowait()
                if event.id in seen:
                    continue
                try:
                    result = court.command(event.device_id, event.payload)
                    seen.append(event.id)
                    if result:
                        client.publish('court/court_01/highlight/highlight_button', result.model_dump_json(), qos=1).wait_for_publish(timeout=5)
                    ack = Event(type='ack', device_id=event.device_id, correlation_id=event.id, payload={'executed': True, 'action': event.payload['action']})
                    client.publish(f'court/court_01/ack/{event.device_id}', ack.model_dump_json(), qos=1)
                except Exception:
                    log.exception('Falha ao executar comando')
            if connected:
                Path('/tmp/worker.healthy').touch()
                if not court.paused:
                    event = court.sample()
                    client.publish('court/court_01/telemetry/compressor_01', event.model_dump_json(), qos=1).wait_for_publish(timeout=5)
            time.sleep(PUBLISH_SECONDS)
    finally:
        client.disconnect()
        client.loop_stop()


if __name__ == '__main__':
    main()
