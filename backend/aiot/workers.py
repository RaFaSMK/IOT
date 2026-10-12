import asyncio
import logging
import sys
from collections import defaultdict, deque
from sqlalchemy import select
from .bus import Bus
from .contracts import Event, LabConfig
from .database import session, Job, ModelVersion, Rule, Alert, audit
from .features import CHANNELS, WINDOW
from .ml import Predictor, generate, train, activate
from .predictive import limit_checks, prediction_facts
from . import storage

log = logging.getLogger(__name__)


class Hysteresis:
    def __init__(self, active=False):
        self.active = active
        self.bad = 0
        self.good = 0

    def update(self, critical):
        previous = self.active
        if critical:
            self.bad += 1
            self.good = 0
            if self.bad >= 3:
                self.active = True
        else:
            self.good += 1
            self.bad = 0
            if self.good >= 10:
                self.active = False
        return self.active if previous != self.active else None


class Workers:
    def __init__(self, bus):
        self.bus = bus
        self.histories = defaultdict(lambda: deque(maxlen=WINDOW))
        self.predictor = Predictor()
        self.hysteresis = {}
        self.seen = deque(maxlen=5000)
        self.lock = asyncio.Lock()

    async def writer(self, event):
        if event.id in self.seen:
            return
        await asyncio.to_thread(storage.write, event)
        self.seen.append(event.id)

    async def inference(self, event):
        if event.type == 'model':
            await asyncio.to_thread(self.predictor.reload)
            return
        if event.id in self.seen:
            return
        self.seen.append(event.id)
        history = self.histories[event.device_id]
        if event.payload['actuators']['cooling']:
            history.append([event.payload['sensors'][name] for name in CHANNELS])
            prediction = await asyncio.to_thread(self.predictor.predict, list(history))
        else:
            history.clear()
            prediction = {'status': 'equipment_off', 'version': self.predictor.version}
        prediction['source_timestamp'] = event.timestamp.isoformat()
        await self.bus.publish(f'prediction.court_01.{event.device_id}', Event(type='prediction', device_id=event.device_id, correlation_id=event.id, payload=prediction))

    async def rules(self, event):
        if event.id in self.seen:
            return
        self.seen.append(event.id)
        if event.type == 'telemetry':
            def load_rule():
                with session() as db:
                    row = db.get(Rule, 'water_cooling')
                    return row.config if row and row.enabled else None
            rule = await asyncio.to_thread(load_rule)
            if not rule:
                return
            value = event.payload['sensors'][rule['sensor']]
            state = event.payload['actuators'][rule['actuator']]
            desired = True if value > rule['on_above'] else False if value < rule['off_below'] else state
            if desired != state:
                command = Event(type='command', device_id=rule['actuator'], correlation_id=event.id, payload={'action': 'set', 'on': desired})
                await self.bus.publish(f'command.court_01.{rule["actuator"]}', command)
                await asyncio.to_thread(audit, 'rule:water_cooling', 'automatic_command', {'command_id': command.id, 'on': desired, 'water_temperature': value})
        elif event.type == 'prediction' and event.payload.get('status') == 'ready':
            alert_id = event.device_id + ':predictive'
            if alert_id not in self.hysteresis:
                def load_state():
                    with session() as db:
                        row = db.get(Alert, alert_id)
                        return bool(row and row.active)
                self.hysteresis[alert_id] = Hysteresis(await asyncio.to_thread(load_state))
            data = event.payload
            transition = self.hysteresis[alert_id].update(any(limit_checks(data).values()))
            if transition is None:
                return
            message = ('Alerta do compressor. ' if transition else 'Compressor recuperado. ') + prediction_facts(data)
            if transition:
                message += ' Inspecione o equipamento.'
            def persist():
                with session() as db:
                    row = db.get(Alert, alert_id)
                    if not row:
                        row = Alert(id=alert_id, device_id=event.device_id, message=message)
                        db.add(row)
                    row.active = transition
                    row.message = message
                    db.commit()
            await asyncio.to_thread(persist)
            await self.bus.publish(f'alert.court_01.{event.device_id}', Event(type='alert', device_id=event.device_id, payload={'id': alert_id, 'active': transition, 'message': message}))

    async def job(self, event, kind):
        async with self.lock:
            identifier = event.payload['job_id']
            loop = asyncio.get_running_loop()
            def status(value, message, state='running', result=None):
                with session() as db:
                    job = db.get(Job, identifier)
                    job.progress = value
                    job.status = state
                    if result is not None:
                        job.result = result
                    db.commit()
                update = Event(type='job', device_id='laboratory', correlation_id=event.id, payload={'job_id': identifier, 'progress': value, 'status': state, 'message': message})
                asyncio.run_coroutine_threadsafe(self.bus.publish(f'job.{kind}.{identifier}', update), loop).result(timeout=30)
            def run():
                with session() as db:
                    job = db.get(Job, identifier)
                    if job.status == 'completed':
                        return
                    config = job.config
                try:
                    status(0, 'Iniciando job')
                    if kind == 'generate':
                        result = generate(identifier, LabConfig.model_validate(config), status)
                    else:
                        result = train(identifier, config['dataset_id'], status)
                        with session() as db:
                            if not db.get(ModelVersion, identifier):
                                db.add(ModelVersion(id=identifier, dataset_id=config['dataset_id'], metrics=result, active=False))
                            db.commit()
                        if result['accepted']:
                            activate(identifier)
                            with session() as db:
                                for model in db.scalars(select(ModelVersion)):
                                    model.active = model.id == identifier
                                db.commit()
                            asyncio.run_coroutine_threadsafe(self.bus.publish('model.activated', Event(type='model', device_id='compressor_01', payload={'version': identifier})), loop).result(timeout=30)
                    status(100, 'Concluído', 'completed', result)
                except Exception as exc:
                    status(0, str(exc), 'failed', {'error': str(exc)})
                    raise
            await asyncio.to_thread(run)


async def main(service):
    logging.basicConfig(level=logging.INFO)
    bus = Bus(service)
    await bus.connect()
    worker = Workers(bus)
    callback = (lambda event: worker.job(event, 'generate' if service == 'generator' else 'train')) if service in ['generator', 'trainer'] else getattr(worker, service)
    await bus.consume(callback)
    try:
        await bus.heartbeat()
    finally:
        await bus.close()


if __name__ == '__main__':
    asyncio.run(main(sys.argv[1]))
