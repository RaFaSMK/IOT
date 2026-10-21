import unittest
from datetime import datetime, timedelta, timezone

from aiot.simulator import Court
from aiot.workers import Workers
from aiot.features import WINDOW


class InferenceGapTests(unittest.IsolatedAsyncioTestCase):
    async def test_pause_requires_a_new_complete_window(self):
        class Bus:
            async def publish(self, *args):
                pass

        class Predictor:
            version = 'test'

            def predict(self, history):
                return {'status': 'ready' if len(history) == WINDOW else 'warming_up'}

        worker = Workers(Bus())
        worker.predictor = Predictor()
        court = Court()
        court.cooling = True
        start = datetime.now(timezone.utc)
        for i in range(WINDOW):
            event = court.sample()
            event.timestamp = start + timedelta(seconds=i * 2)
            await worker.inference(event)
        self.assertEqual(len(worker.histories['compressor_01']), WINDOW)
        event = court.sample()
        event.timestamp = start + timedelta(seconds=120)
        await worker.inference(event)
        self.assertEqual(len(worker.histories['compressor_01']), 1)
