"""Verificação contra os serviços reais. Executar dentro do container api."""
import asyncio
import json
import time
import httpx
from websockets.asyncio.client import connect
from aiot.config import secrets

BASE = 'http://frontend:8080'


async def main():
    async with httpx.AsyncClient(base_url=BASE, timeout=30) as http:
        tokens = {}
        for role, credentials in secrets()['demo_users'].items():
            response = await http.post('/api/login', json=credentials)
            response.raise_for_status()
            tokens[role] = response.json()['token']
        viewer = {'Authorization': 'Bearer ' + tokens['viewer']}
        operator = {'Authorization': 'Bearer ' + tokens['operator']}
        admin = {'Authorization': 'Bearer ' + tokens['admin']}
        assert (await http.post('/api/devices/floodlights/command', headers=viewer, json={'action': 'set', 'on': True})).status_code == 403
        assert (await http.post('/api/lab/generate', headers=operator, json={})).status_code == 403
        assert (await http.get('/api/audit', headers=viewer)).status_code == 403
        print('Login e isolamento dos três papéis: OK', flush=True)
        response = await http.post('/api/ws-ticket', headers=viewer)
        response.raise_for_status()
        ticket = response.json()['ticket']
        async with connect('ws://frontend:8080/api/ws?ticket=' + ticket) as ws:
            snapshot = json.loads(await ws.recv())
            assert snapshot['type'] == 'snapshot'
            response = await http.post('/api/devices/floodlights/command', headers=operator, json={'action': 'set', 'on': True})
            response.raise_for_status()
            command_id = response.json()['command_id']
            ack, reflected = False, False
            end = time.monotonic() + 30
            while time.monotonic() < end and not (ack and reflected):
                event = json.loads(await asyncio.wait_for(ws.recv(), 15))
                if event['type'] == 'ack' and event.get('correlation_id') == command_id:
                    ack = True
                if event['type'] == 'telemetry' and event['payload']['actuators']['floodlights']:
                    reflected = True
            assert ack and reflected
        try:
            async with connect('ws://frontend:8080/api/ws?ticket=' + ticket):
                raise AssertionError('Ticket reutilizado foi aceito')
        except Exception as exc:
            assert '403' in str(exc)
        print('Web → AMQP → MQTT → atuador → telemetria → WebSocket e ticket único: OK', flush=True)
        response = await http.post('/api/devices/highlight_button/command', headers=operator, json={'action': 'highlight', 'player': 'A'})
        response.raise_for_status()
        await asyncio.sleep(4)
        response = await http.get('/api/highlights', headers=viewer)
        response.raise_for_status()
        assert response.json()['events']
        response = await http.get('/api/devices/ambient_temperature/history', headers=viewer)
        response.raise_for_status()
        assert response.json()
        print('Persistência dos highlights e histórico de sensores no InfluxDB: OK', flush=True)
        response = await http.get('/api/messaging', headers=viewer)
        response.raise_for_status()
        queues = response.json()['queues']
        assert len(queues) >= 8
        assert all(q['consumers'] >= 1 for q in queues if q['name'] != 'court.dlq')
        print('Filas e consumidores reais no RabbitMQ: OK', flush=True)
        response = await http.post('/api/lab/generate', headers=admin, json={})
        response.raise_for_status()
        dataset = response.json()['job_id']
        await wait_job(http, admin, dataset)
        response = await http.post('/api/models/train', headers=admin, json={'dataset_id': dataset})
        response.raise_for_status()
        training = response.json()['job_id']
        job = await wait_job(http, admin, training)
        result = job['result']
        print('Modelos:', json.dumps({key: value['test'] | {'beats_baseline': value['beats_baseline']} for key, value in result['metrics'].items()}), flush=True)
        assert result['accepted']
        split = result['split']
        assert not set(split['train']) & set(split['test'])
        assert not set(split['train']) & set(split['validation'])
        print('Geração massiva, treino por equipamento e dois modelos superiores à base: OK', flush=True)
        print('INTEGRAÇÃO APROVADA', flush=True)


async def wait_job(http, headers, identifier):
    end = time.monotonic() + 600
    previous = None
    while time.monotonic() < end:
        response = await http.get('/api/jobs', headers=headers)
        response.raise_for_status()
        job = next(j for j in response.json() if j['id'] == identifier)
        status = (job['status'], job['progress'])
        if status != previous:
            print(job['kind'], status, flush=True)
            previous = status
        if job['status'] == 'failed':
            raise AssertionError(job['result'])
        if job['status'] == 'completed':
            return job
        await asyncio.sleep(3)
    raise TimeoutError('Job não concluiu em 10 minutos')


if __name__ == '__main__':
    asyncio.run(main())
