import unittest
import numpy as np
from pydantic import ValidationError
from aiot.features import features, latest, WINDOW
from aiot.simulator import Court
from aiot.workers import Hysteresis
from aiot.contracts import LabConfig, Event


class AIoTTests(unittest.TestCase):
    def test_future_does_not_change_features(self):
        readings = np.random.default_rng(7).normal(30, 2, (40, 3))
        readings[4, 0] = np.nan
        original = features(readings)
        readings[30:] = 100
        np.testing.assert_allclose(original[:30 - WINDOW + 1], features(readings)[:30 - WINDOW + 1])

    def test_training_and_live_features_match(self):
        readings = np.random.default_rng(7).normal(30, 2, (40, 3))
        np.testing.assert_allclose(features(readings)[-1], latest(readings[-WINDOW:])[0])

    def test_incomplete_window_has_no_prediction_features(self):
        self.assertIsNone(latest(np.zeros((WINDOW - 1, 3))))

    def test_hysteresis_requires_consecutive_observations(self):
        state = Hysteresis()
        self.assertIsNone(state.update(True))
        self.assertIsNone(state.update(True))
        self.assertTrue(state.update(True))
        for _ in range(9):
            self.assertIsNone(state.update(False))
        self.assertFalse(state.update(False))

    def test_cooling_changes_measured_water_temperature(self):
        off, on = Court(42), Court(42)
        on.command('cooling', {'action': 'set', 'on': True})
        for _ in range(20):
            off_event, on_event = off.sample(), on.sample()
        self.assertLess(on_event.payload['sensors']['water_temperature'], off_event.payload['sensors']['water_temperature'])
        self.assertGreater(on_event.payload['sensors']['compressor_current'], off_event.payload['sensors']['compressor_current'])

    def test_fault_changes_measurements_without_leaking_labels(self):
        court = Court()
        court.command('cooling', {'action': 'set', 'on': True})
        initial = court.sample().payload['sensors']['compressor_vibration']
        court.command('compressor_01', {'action': 'inject_fault'})
        for _ in range(60):
            event = court.sample()
        self.assertGreater(event.payload['sensors']['compressor_vibration'], initial + 3)
        self.assertEqual(set(event.payload), {'court_id', 'sensors', 'actuators'})

    def test_default_lab_reaches_required_volume(self):
        self.assertGreaterEqual(LabConfig().readings, 1_000_000)

    def test_event_rejects_unknown_fields(self):
        with self.assertRaises(ValidationError):
            Event(type='telemetry', device_id='compressor_01', payload={}, health=100)

    def test_labels_cannot_enter_live_telemetry(self):
        data = Court().sample().model_dump()
        data['payload']['rul_hours'] = 10
        with self.assertRaises(ValidationError):
            Event.model_validate(data)


if __name__ == '__main__':
    unittest.main()
