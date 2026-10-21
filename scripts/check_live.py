"""Verifica inferência, regra automática, DLQ e LLM nos containers reais."""
import asyncio
import json
import sys
import time
import httpx
import aio_pika
from websockets.asyncio.client import connect
from aiot.config import secrets
from aiot.bus import Bus
from aiot.predictive import limit_checks


async def main(mode='live'):
    async with httpx.AsyncClient(base_url='http://frontend:8080', timeout=300) as http:
        response = await http.post('/api/login', json=secrets()['demo_users']['admin'])
        response.raise_for_status()
        headers = {'Authorization': 'Bearer ' + response.json()['token']}
        async def get(path):
            result = await http.get('/api/' + path, headers=headers)
            result.raise_for_status()
            return result.json()
        async def command(identifier, action, **kwargs):
            result = await http.post('/api/devices/' + identifier + '/command', headers=headers, json={'action': action, **kwargs})
            result.raise_for_status()
        if mode == 'queues':
            print(json.dumps((await get('messaging'))['queues']), flush=True)
            return
        if mode == 'dlq':
            bus = Bus('api')
            await bus.connect()
            try:
                await bus.exchange.publish(aio_pika.Message(b'{"qa":"invalid-contract"}', delivery_mode=2), routing_key='command.court_01.qa')
            finally:
                await bus.close()
            await asyncio.sleep(3)
            first, second = await get('messaging/dlq'), await get('messaging/dlq')
            assert any('invalid-contract' in row['payload'] for row in first)
            assert len(second) == len(first)
            print('DLQ preserva a mensagem e a consulta não a remove: OK', flush=True)
            return
        ticket = (await http.post('/api/ws-ticket', headers=headers)).json()['ticket']
        original_rule = (await get('rules'))[0]
        # O ensaio fica aguardando o HTTP/LLM enquanto a telemetria continua.
        # A fila padrão de 16 frames bloquearia leitura de ping/pong nesse período.
        async with connect('ws://frontend:8080/api/ws?ticket=' + ticket, max_queue=None, ping_timeout=60) as ws:
            snapshot = json.loads(await ws.recv())
            assert snapshot['type'] == 'snapshot'
            try:
                rule = {'enabled': True, 'on_above': 5, 'off_below': 2}
                (await http.put('/api/rules/water_cooling', headers=headers, json=rule)).raise_for_status()
                await command('compressor_01', 'reset_fault')
                await command('cooling', 'set', on=False)
                end = time.monotonic() + 90
                ready = None
                normal_ready = 0
                while time.monotonic() < end:
                    event = json.loads(await asyncio.wait_for(ws.recv(), 20))
                    if event['type'] == 'prediction' and event['payload']['status'] == 'ready':
                        ready = event['payload']
                        assert ready['health'] >= 90 and not any(limit_checks(ready).values()), ready
                        assert ready['rul_hours'] is None and 'rul_interval' not in ready, ready
                        normal_ready += 1
                        if normal_ready >= 12 and not any(row['active'] for row in await get('alerts')):
                            break
                assert ready and normal_ready >= 12, 'Inferência não carregou o modelo ou regra não ligou o compressor'
                assert not any(row['active'] for row in await get('alerts')), 'Alertas não foram limpos na condição saudável'
                print('Regra automática e carregamento do modelo sem reinício: OK', flush=True)
                print('Previsão saudável:', json.dumps(ready), flush=True)
                await command('compressor_01', 'inject_fault')
                opened = False
                end = time.monotonic() + 240
                while time.monotonic() < end:
                    event = json.loads(await asyncio.wait_for(ws.recv(), 20))
                    if event['type'] == 'alert' and event['payload']['active']:
                        opened = True
                        break
                assert opened, 'A falha não produziu alerta preditivo'
                assert any(row['active'] for row in await get('alerts'))
                print('Falha → medições → regressão → alerta persistido e WebSocket: OK', flush=True)
                rul_points = []
                end = time.monotonic() + 120
                while time.monotonic() < end and len(rul_points) < 8:
                    event = json.loads(await asyncio.wait_for(ws.recv(), 20))
                    data = event.get('payload', {})
                    if event['type'] == 'prediction' and data.get('status') == 'ready' and data.get('rul_hours') is not None:
                        assert data.get('rul_unit') == 'simulated_operating_hours', data
                        rul_points.append(data['rul_hours'])
                assert len(rul_points) == 8, 'RUL permaneceu inconclusiva durante toda a falha'
                assert sum(rul_points[:3]) > sum(rul_points[-3:]), 'RUL não acompanhou a degradação'
                print('RUL numérica durante falha (h de operação simuladas):', json.dumps(rul_points), flush=True)
                async with http.stream('POST', '/api/assistant', headers=headers, json={'question': 'Qual equipamento está com alerta e o que significa? Responda em duas frases.'}) as response:
                    response.raise_for_status()
                    chunks = []
                    done = False
                    async for line in response.aiter_lines():
                        if line.startswith('data: '):
                            item = json.loads(line[6:])
                            assert not item.get('error'), item
                            if not item.get('status'):
                                chunks.append(item.get('text', ''))
                            done = done or item.get('done', False)
                    assert done and ''.join(chunks).strip()
                    print('LLM local em streaming:', ''.join(chunks), flush=True)
                await command('compressor_01', 'reset_fault')
                resolved = False
                end = time.monotonic() + 100
                while time.monotonic() < end:
                    event = json.loads(await asyncio.wait_for(ws.recv(), 20))
                    if event['type'] == 'alert' and not event['payload']['active']:
                        resolved = True
                        break
                assert resolved, 'Histerese não resolveu o alerta após recuperação'
                print('Recuperação e limpeza do alerta por histerese: OK', flush=True)
            finally:
                await command('compressor_01', 'reset_fault')
                config = original_rule['config']
                (await http.put('/api/rules/water_cooling', headers=headers, json={'enabled': original_rule['enabled'], 'on_above': config['on_above'], 'off_below': config['off_below']})).raise_for_status()


if __name__ == '__main__':
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else 'live'))
