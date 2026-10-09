import asyncio
import logging
from pathlib import Path
import paho.mqtt.client as mqtt
from .bus import Bus
from .config import credential
from .contracts import Event


async def main():
    logging.basicConfig(level=logging.INFO)
    bus = Bus('gateway')
    await bus.connect()
    loop = asyncio.get_running_loop()
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id='court-gateway')
    cred = credential('gateway')
    client.username_pw_set(cred['user'], cred['password'])
    connected = asyncio.Event()

    def on_connect(c, _, flags, reason, properties):
        if reason == 0:
            c.subscribe([('court/+/telemetry/#', 1), ('court/+/highlight/#', 1), ('court/+/ack/#', 1)])
            loop.call_soon_threadsafe(connected.set)

    def on_disconnect(*args):
        loop.call_soon_threadsafe(connected.clear)

    def on_message(c, _, msg):
        # Aguarda confirmação AMQP antes de confirmar MQTT QoS 1.
        async def forward():
            event = Event.model_validate_json(msg.payload)
            expected = msg.topic.split('/')[2]
            if event.type != expected:
                raise ValueError('Tipo não corresponde ao tópico MQTT.')
            if event.type == 'telemetry' and any(k in event.payload for k in ['health', 'rul_hours', 'wear', 'labels']):
                raise ValueError('Rótulos de treino proibidos na telemetria.')
            await bus.publish(f'{event.type}.court_01.{event.device_id}', event)
        try:
            asyncio.run_coroutine_threadsafe(forward(), loop).result(timeout=15)
            c.ack(msg.mid, msg.qos)
        except Exception:
            logging.exception('Falha no encaminhamento MQTT/AMQP; mensagem não confirmada')
            c.disconnect()
            c.reconnect()

    client.manual_ack_set(True)
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    client.connect_async('mosquitto', 1883)
    client.loop_start()

    async def command(event):
        if event.type != 'command':
            raise ValueError('Mensagem não é um comando.')
        await asyncio.wait_for(connected.wait(), timeout=10)
        result = client.publish(f'court/court_01/command/{event.device_id}', event.model_dump_json(), qos=1)
        await asyncio.to_thread(result.wait_for_publish, 10)
        if not result.is_published():
            raise RuntimeError('MQTT não confirmou a publicação do comando.')

    await bus.consume(command)
    try:
        while True:
            if connected.is_set() and not bus.connection.is_closed:
                await bus.touch()
            await asyncio.sleep(10)
    finally:
        client.disconnect()
        client.loop_stop()
        await bus.close()


if __name__ == '__main__':
    asyncio.run(main())
