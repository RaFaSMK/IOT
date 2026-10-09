import asyncio
import json
import logging
import os
from pathlib import Path
from urllib.parse import quote
import aio_pika
from .config import credential, EXCHANGE, QUEUES
from .contracts import Event

log = logging.getLogger(__name__)


class Bus:
    def __init__(self, service=None):
        self.service = service or os.getenv('SERVICE_NAME', 'api')
        self.connection = None
        self.exchange = None

    async def connect(self):
        creds = credential(self.service)
        url = f"amqp://{quote(creds['user'], safe='')}:{quote(creds['password'], safe='')}@rabbitmq:5672/court"
        self.connection = await aio_pika.connect_robust(url, fail_fast=False, reconnect_interval=3)
        self.channel = await self.connection.channel(publisher_confirms=True)
        await self.channel.set_qos(prefetch_count=16 if self.service != 'writer' else 64)
        self.exchange = await self.channel.get_exchange(EXCHANGE, ensure=False)
        await self.touch()

    async def touch(self):
        path = Path('/tmp/worker.healthy')
        path.touch()

    async def publish(self, key, event):
        if isinstance(event, Event):
            body = event.model_dump_json().encode()
            identifier = event.id
        else:
            checked = Event.model_validate(event)
            body = checked.model_dump_json().encode()
            identifier = checked.id
        await self.exchange.publish(aio_pika.Message(body, content_type='application/json', message_id=identifier, delivery_mode=aio_pika.DeliveryMode.PERSISTENT), routing_key=key, mandatory=True)

    async def consume(self, callback):
        queue = await self.channel.get_queue(f'court.{self.service}', ensure=False)

        async def receive(message):
            try:
                event = Event.model_validate_json(message.body)
                await callback(event)
            except asyncio.CancelledError:
                await message.nack(requeue=True)
                raise
            except Exception:
                log.exception('Mensagem rejeitada; conteúdo preservado na DLQ')
                await message.reject(requeue=False)
            else:
                await message.ack()
            await self.touch()

        await queue.consume(receive)

    async def close(self):
        if self.connection:
            await self.connection.close()

    async def heartbeat(self):
        while True:
            if self.connection and not self.connection.is_closed:
                await self.touch()
            await asyncio.sleep(10)
