import asyncio
import json
import logging
from collections import deque
from contextlib import asynccontextmanager
from uuid import uuid4
from datetime import datetime, timezone
import httpx
from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, ConfigDict, model_validator
from sqlalchemy import select, text
from . import storage
from .auth import current_user, require, login, issue_ticket, consume_ticket, rate_limit
from .bus import Bus
from .config import credential, MODEL
from .contracts import Event, Command, LabConfig
from .database import session, User, Device, Job, Rule, Alert, Audit, ModelVersion, audit, as_dict
from .predictive import assistant_predictions
from .assistant_facts import sections, selection_prompt, selection_schema, selected_sections, validate_selection

log = logging.getLogger(__name__)
bus = Bus('api')
latest = {}
predictions = {}
recent = deque(maxlen=100)
sockets = set()


async def receive(event):
    data = event.model_dump(mode='json')
    if event.type == 'telemetry':
        latest[event.device_id] = data
    elif event.type == 'prediction':
        predictions[event.device_id] = data
    recent.appendleft(data)
    for queue in tuple(sockets):
        if queue.full():
            queue.get_nowait()
        queue.put_nowait(data)


@asynccontextmanager
async def lifespan(app):
    await bus.connect()
    await bus.consume(receive)
    heartbeat = asyncio.create_task(bus.heartbeat())
    yield
    heartbeat.cancel()
    await bus.close()


app = FastAPI(title='Quadra Inteligente — AIoT', version='2.0.0', lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:5173', 'http://localhost:8080'], allow_methods=['*'], allow_headers=['Authorization', 'Content-Type'])


class LoginBody(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=72)


@app.post('/api/login')
def sign_in(body: LoginBody, request: Request):
    try:
        result = login(body.username, body.password, request.client.host)
    except HTTPException:
        audit(body.username, 'login_failed')
        raise
    audit(body.username, 'login')
    return result


@app.get('/api/me')
def me(user=Depends(current_user)):
    return user


@app.get('/api/ready')
async def ready():
    if bus.connection is None or bus.connection.is_closed:
        raise HTTPException(503, 'RabbitMQ indisponível')
    return {'status': 'ok'}


@app.get('/api/health')
def health(user=Depends(current_user)):
    checks = {}
    try:
        with session() as db:
            db.execute(text('SELECT 1'))
        checks['postgresql'] = {'status': 'ok'}
    except Exception:
        checks['postgresql'] = {'status': 'fail'}
    try:
        response = storage.client().health()
        checks['influxdb'] = {'status': response.status}
    except Exception:
        checks['influxdb'] = {'status': 'fail'}
    checks['rabbitmq'] = {'status': 'ok' if bus.connection and not bus.connection.is_closed else 'fail'}
    source = latest.get('compressor_01')
    fresh = source and (datetime.now(timezone.utc) - datetime.fromisoformat(source['timestamp'])).total_seconds() < 10
    checks['simulator'] = {'status': 'ok' if fresh else 'no_data'}
    return {'status': 'ok' if all(check['status'] in ['ok', 'pass'] for check in checks.values()) else 'degraded', 'dependencies': checks}


@app.post('/api/ws-ticket')
def ws_ticket(user=Depends(current_user)):
    rate_limit('ws:' + user['username'], 30)
    return {'ticket': issue_ticket(user), 'expires_in': 20}


@app.websocket('/api/ws')
async def websocket(ws: WebSocket):
    token = ws.query_params.get('ticket', '')
    user = consume_ticket(token)
    if not user:
        await ws.close(code=4401)
        return
    await ws.accept()
    queue = asyncio.Queue(maxsize=100)
    sockets.add(queue)
    try:
        def alert_snapshot():
            with session() as db:
                return [Event(type='alert', device_id=row.device_id, payload={'id': row.id, 'active': row.active, 'message': row.message}).model_dump(mode='json') for row in db.scalars(select(Alert))]
        saved_alerts = await asyncio.to_thread(alert_snapshot)
        await ws.send_json({'type': 'snapshot', 'payload': {'telemetry': list(latest.values()), 'predictions': list(predictions.values()), 'alerts': saved_alerts}})
        while True:
            try:
                data = await asyncio.wait_for(queue.get(), timeout=15)
                await ws.send_json(data)
            except asyncio.TimeoutError:
                await ws.send_json({'type': 'heartbeat'})
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        sockets.discard(queue)


class DeviceBody(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,80}$')
    name: str = Field(min_length=1, max_length=120)
    kind: str = Field(pattern=r'^(sensor|actuator|equipment|button|simulator)$')
    unit: str = Field(default='', max_length=20)
    config: dict = Field(default_factory=dict)
    enabled: bool = True

    @model_validator(mode='after')
    def normal_range(self):
        import math
        if any(key not in ['min', 'max'] for key in self.config):
            raise ValueError('Configuração aceita somente min e max.')
        for value in self.config.values():
            if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
                raise ValueError('Limites devem ser números finitos.')
        if 'min' in self.config and 'max' in self.config and self.config['min'] >= self.config['max']:
            raise ValueError('A faixa mínima deve ser menor que a máxima.')
        return self


@app.get('/api/devices')
def devices(user=Depends(current_user)):
    with session() as db:
        return [as_dict(device) for device in db.scalars(select(Device).order_by(Device.kind, Device.name))]


@app.put('/api/devices/{identifier}')
def save_device(identifier: str, body: DeviceBody, user=Depends(require('admin'))):
    if identifier != body.id:
        raise HTTPException(400, 'IDs não correspondem.')
    with session() as db:
        row = db.get(Device, identifier)
        if not row:
            row = Device(**body.model_dump())
            db.add(row)
        else:
            for key, value in body.model_dump().items():
                setattr(row, key, value)
        db.commit()
        result = as_dict(row)
    audit(user['username'], 'device_saved', {'device_id': identifier})
    return result


@app.delete('/api/devices/{identifier}')
def disable_device(identifier: str, user=Depends(require('admin'))):
    with session() as db:
        row = db.get(Device, identifier)
        if not row:
            raise HTTPException(404, 'Dispositivo não encontrado.')
        row.enabled = False
        db.commit()
    audit(user['username'], 'device_disabled', {'device_id': identifier})
    return {'disabled': True}


@app.post('/api/devices/{identifier}/command')
async def command(identifier: str, body: Command, user=Depends(require('operator', 'admin'))):
    allowed = {'cooling': ['set'], 'floodlights': ['set'], 'compressor_01': ['inject_fault', 'reset_fault'], 'highlight_button': ['highlight'], 'simulator': ['pause', 'resume']}
    if body.action not in allowed.get(identifier, []) or (body.action == 'set' and body.on is None):
        raise HTTPException(400, 'Comando incompatível com o dispositivo.')
    def enabled():
        with session() as db:
            row = db.get(Device, identifier)
            return row and row.enabled
    if not await asyncio.to_thread(enabled):
        raise HTTPException(404, 'Dispositivo indisponível.')
    rate_limit('command:' + user['username'], 60)
    event = Event(type='command', device_id=identifier, payload=body.model_dump(exclude_none=True))
    await bus.publish(f'command.court_01.{identifier}', event)
    await asyncio.to_thread(audit, user['username'], 'command_sent', {'device_id': identifier, 'command_id': event.id, 'command': event.payload})
    return {'command_id': event.id, 'status': 'sent'}


@app.get('/api/devices/{identifier}/history')
def device_history(identifier: str, start: str = '-1h', user=Depends(current_user)):
    try:
        return storage.history(identifier, start)
    except ValueError as exc:
        raise HTTPException(422, str(exc))


@app.get('/api/highlights')
def highlights(start: str = '-1h', limit: int = 100, user=Depends(current_user)):
    try:
        events = storage.highlights(start, limit)
        return {'events': events, 'total': len(events)}
    except ValueError as exc:
        raise HTTPException(422, str(exc))


@app.get('/api/highlights/stats')
def highlights_stats(start: str = '-24h', bucket_interval: str = '1h', user=Depends(current_user)):
    try:
        return {'series': storage.stats(start, bucket_interval)}
    except ValueError as exc:
        raise HTTPException(422, str(exc))


@app.get('/api/alerts')
def alerts(user=Depends(current_user)):
    with session() as db:
        return [as_dict(alert) for alert in db.scalars(select(Alert).order_by(Alert.timestamp.desc()))]


@app.get('/api/rules')
def rules(user=Depends(current_user)):
    with session() as db:
        return [as_dict(rule) for rule in db.scalars(select(Rule))]


class RuleBody(BaseModel):
    enabled: bool
    on_above: float = Field(ge=5, le=30)
    off_below: float = Field(ge=2, le=25)

    @model_validator(mode='after')
    def hysteresis(self):
        if self.off_below >= self.on_above:
            raise ValueError('O limite de desligamento deve ser menor que o de acionamento.')
        return self


@app.put('/api/rules/water_cooling')
def save_rule(body: RuleBody, user=Depends(require('admin'))):
    with session() as db:
        row = db.get(Rule, 'water_cooling')
        row.enabled = body.enabled
        row.config = {**row.config, 'on_above': body.on_above, 'off_below': body.off_below}
        db.commit()
    audit(user['username'], 'rule_changed', body.model_dump())
    return {'saved': True}


@app.get('/api/jobs')
def jobs(user=Depends(current_user)):
    with session() as db:
        return [as_dict(job) for job in db.scalars(select(Job).order_by(Job.timestamp.desc()).limit(100))]


async def create_job(kind, config, user):
    identifier = str(uuid4())
    def persist():
        with session() as db:
            # Serialize a admissão de jobs para impedir dois treinos concorrentes.
            db.execute(text('SELECT pg_advisory_xact_lock(20261008)'))
            active = db.scalar(select(Job).where(Job.kind == kind, Job.status.in_(['queued', 'running'])))
            if active:
                raise HTTPException(409, 'Já existe um job deste tipo em execução.')
            db.add(Job(id=identifier, kind=kind, config=config))
            db.commit()
    await asyncio.to_thread(persist)
    try:
        await bus.publish(f'task.{kind}', Event(type='task', device_id='laboratory', payload={'job_id': identifier}))
    except Exception:
        def failed():
            with session() as db:
                db.get(Job, identifier).status = 'failed'
                db.commit()
        await asyncio.to_thread(failed)
        raise HTTPException(503, 'Falha ao enfileirar o job.')
    await asyncio.to_thread(audit, user['username'], 'job_created', {'job_id': identifier, 'kind': kind, 'config': config})
    return {'job_id': identifier, 'status': 'queued'}


@app.post('/api/lab/generate', status_code=202)
async def generate_data(body: LabConfig, user=Depends(require('admin'))):
    if not 1_000_000 <= body.readings <= 20_000_000 or body.rows > 2_000_000:
        raise HTTPException(422, 'Configure de 1 a 20 milhões de leituras e até 2 milhões de amostras.')
    return await create_job('generate', body.model_dump(), user)


class TrainBody(BaseModel):
    dataset_id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,80}$')


@app.post('/api/models/train', status_code=202)
async def train_model(body: TrainBody, user=Depends(require('admin'))):
    def valid():
        with session() as db:
            job = db.get(Job, body.dataset_id)
            return job and job.kind == 'generate' and job.status == 'completed'
    if not await asyncio.to_thread(valid):
        raise HTTPException(422, 'Selecione um dataset concluído.')
    return await create_job('train', body.model_dump(), user)


@app.get('/api/models')
def models(user=Depends(current_user)):
    with session() as db:
        return [as_dict(model) for model in db.scalars(select(ModelVersion).order_by(ModelVersion.timestamp.desc()))]


@app.get('/api/messaging')
async def messaging(user=Depends(current_user)):
    cred = credential('monitor')
    try:
        async with httpx.AsyncClient(base_url='http://rabbitmq:15672', auth=(cred['user'], cred['password']), timeout=5) as http:
            response = await http.get('/api/queues/court')
            response.raise_for_status()
            queues = response.json()
        return {'queues': [{'name': q['name'], 'messages': q.get('messages', 0), 'ready': q.get('messages_ready', 0), 'unacked': q.get('messages_unacknowledged', 0), 'consumers': q.get('consumers', 0), 'publish_rate': q.get('message_stats', {}).get('publish_details', {}).get('rate', 0), 'deliver_rate': q.get('message_stats', {}).get('deliver_get_details', {}).get('rate', 0)} for q in queues], 'recent': list(recent)}
    except httpx.HTTPError:
        raise HTTPException(503, 'Gerenciamento do RabbitMQ indisponível.')


@app.get('/api/messaging/dlq')
async def dlq(user=Depends(require('admin'))):
    cred = credential('monitor')
    async with httpx.AsyncClient(base_url='http://rabbitmq:15672', auth=(cred['user'], cred['password']), timeout=5) as http:
        response = await http.post('/api/queues/court/court.dlq/get', json={'count': 20, 'ackmode': 'ack_requeue_true', 'encoding': 'auto', 'truncate': 20000})
        response.raise_for_status()
        return response.json()


@app.get('/api/audit')
def audit_log(user=Depends(require('admin'))):
    with session() as db:
        return [as_dict(item) for item in db.scalars(select(Audit).order_by(Audit.id.desc()).limit(200))]


@app.get('/api/admin-links')
def admin_links(user=Depends(current_user)):
    return [{'name': 'InfluxDB', 'url': 'http://127.0.0.1:18086'}, {'name': 'RabbitMQ', 'url': 'http://127.0.0.1:15672'}, {'name': 'API / Swagger', 'url': '/docs'}]


class ChatBody(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


@app.post('/api/assistant')
async def assistant(body: ChatBody, user=Depends(current_user)):
    rate_limit('chat:' + user['username'], 5)
    await asyncio.to_thread(audit, user['username'], 'assistant_question', {'question': body.question})
    def context():
        with session() as db:
            alerts = [as_dict(row) for row in db.scalars(select(Alert).where(Alert.active.is_(True)))]
            current_models = list(db.scalars(select(ModelVersion).where(ModelVersion.active.is_(True))))
            last_model = db.scalar(select(ModelVersion).order_by(ModelVersion.timestamp.desc()).limit(1))
            if last_model and all(row.id != last_model.id for row in current_models):
                current_models.append(last_model)
            models = [as_dict(row) for row in current_models]
        summaries = [{'version': row['id'], 'active': row['active'], 'metrics': {target: {name: values for name, values in metrics.items() if name in ['test', 'validation', 'baseline', 'beats_baseline']} for target, metrics in row['metrics'].get('metrics', {}).items()}} for row in models]
        predictive_summary = assistant_predictions(predictions, alerts)
        # Mensagens antigas/genéricas da auditoria não descrevem os limites atuais.
        # O contexto separa o estado persistido dos fatos da previsão recente.
        alert_states = [{'id': row['id'], 'device_id': row['device_id'], 'active': row['active'],
                         'timestamp': row['timestamp']} for row in alerts]
        return {'telemetry': latest, 'predictions': predictive_summary, 'alerts': alert_states, 'models': summaries}
    data = await asyncio.to_thread(context)
    facts = sections(data)
    system = selection_prompt(facts)
    async def stream():
        yield 'data: ' + json.dumps({'status': 'preparing', 'text': 'Preparando a consulta…'}) + '\n\n'
        try:
            buffer = ''
            sent = set()
            done = False
            async with httpx.AsyncClient(timeout=httpx.Timeout(300, connect=10)) as http:
                loaded = await http.get('http://ollama:11434/api/ps')
                loaded.raise_for_status()
                if not any(model.get('name') == MODEL or model.get('model') == MODEL for model in loaded.json().get('models', [])):
                    yield 'data: ' + json.dumps({'status': 'loading', 'text': 'Carregando o modelo local…'}) + '\n\n'
                    warmup = await http.post('http://ollama:11434/api/generate', json={'model': MODEL, 'stream': False, 'keep_alive': '30m'})
                    warmup.raise_for_status()
                    if warmup.json().get('error'):
                        raise RuntimeError(warmup.json()['error'])
                yield 'data: ' + json.dumps({'status': 'processing', 'text': 'Analisando sua pergunta…'}) + '\n\n'
                async with http.stream('POST', 'http://ollama:11434/api/chat', json={'model': MODEL, 'stream': True, 'format': selection_schema(facts), 'keep_alive': '30m', 'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': body.question}], 'options': {'temperature': 0, 'num_predict': 200}}) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if line:
                            item = json.loads(line)
                            if item.get('error'):
                                raise RuntimeError(item['error'])
                            buffer += item.get('message', {}).get('content', '')
                            for identifier in selected_sections(buffer, facts, sent):
                                prefix = '\n\n' if sent else ''
                                sent.add(identifier)
                                for word in (prefix + facts[identifier]).split(' '):
                                    yield 'data: ' + json.dumps({'text': word + ' ', 'done': False}) + '\n\n'
                            if item.get('done'):
                                validate_selection(buffer, facts)
                                done = True
            if not done or not sent:
                raise RuntimeError('O modelo não concluiu a seleção de fatos.')
            yield 'data: ' + json.dumps({'text': '', 'done': True}) + '\n\n'
        except (httpx.HTTPError, RuntimeError, ValueError) as exc:
            log.warning('Assistente indisponível: %s', type(exc).__name__)
            yield 'data: ' + json.dumps({'error': 'Modelo local indisponível. Verifique o serviço ollama e o download em model-init.'}) + '\n\n'
    return StreamingResponse(stream(), media_type='text/event-stream', headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})
