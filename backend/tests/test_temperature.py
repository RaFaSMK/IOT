import unittest

import numpy as np

from aiot.equipment import thermal_response
from aiot.simulator import Court


class TemperatureTests(unittest.TestCase):
    def test_batch_and_live_thermal_response_match_at_multiple_cadences(self):
        targets = np.concatenate([np.full(10, 25.), np.full(20, 50.), np.full(20, 25.)])
        for step in [1 / 60, 5 / 60, 30 / 60]:
            batch = thermal_response(targets, previous=25, sample_hours=step)
            previous = 25
            live = []
            for target in targets:
                previous = thermal_response(target, previous, step)
                live.append(previous)
            np.testing.assert_allclose(batch, live, atol=1e-12)

    def test_thermal_response_is_causal_and_does_not_jump_to_target(self):
        targets = np.concatenate([np.full(10, 25.), np.full(30, 50.)])
        response = thermal_response(targets)
        self.assertGreater(response[10], 25)
        self.assertLess(response[10], 35)
        self.assertGreater(response[-1], 49)
        targets[20:] = 0
        np.testing.assert_allclose(thermal_response(targets)[:20], response[:20])

    def test_compressor_cools_gradually_after_switching_off(self):
        court = Court(42)
        court.cooling = True
        for _ in range(30):
            before = court.sample().payload['sensors']['compressor_temperature']
        court.cooling = False
        after = court.sample().payload['sensors']['compressor_temperature']
        self.assertGreater(before, after)
        self.assertLess(before - after, 4)

    def test_water_cooling_and_ambient_changes_are_less_abrupt(self):
        court = Court(42)
        court.cooling = True
        water = [court.water]
        ambient = []
        for _ in range(100):
            sensors = court.sample().payload['sensors']
            water.append(sensors['water_temperature'])
            ambient.append(sensors['ambient_temperature'])
        self.assertLess(max(abs(np.diff(water))), .08)
        self.assertLess(max(abs(np.diff(ambient))), .4)
