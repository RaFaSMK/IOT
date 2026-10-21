import unittest
import numpy as np

from aiot.equipment import STEP_HOURS
from aiot.features import features
from aiot.simulator import Court
from aiot.contracts import Event
from pydantic import ValidationError


class SimulatedTimeTests(unittest.TestCase):
    def test_live_clock_matches_feature_period(self):
        event = Court().sample()
        self.assertEqual(event.payload['simulation']['step_hours'], STEP_HOURS)

    def test_fixed_time_features_match_at_different_cadences(self):
        def measured(hours):
            return np.column_stack([30 + hours * 3, 2 + hours, .5 + hours, np.full(len(hours), 25)])
        dense = features(measured(np.arange(0, 2.01, 1 / 60)), sample_hours=1 / 60)[-1]
        sparse = features(measured(np.arange(0, 2.01, STEP_HOURS)))[-1]
        np.testing.assert_allclose(dense, sparse, atol=1e-5)

    def test_ambient_variation_alone_does_not_imply_degradation(self):
        hours = np.arange(30) * STEP_HOURS
        ambient = 25 + hours * 4
        inputs = np.column_stack([ambient + 10, np.full(30, 2.7), np.full(30, .9), ambient])
        result = features(inputs)
        self.assertAlmostEqual(float(result[-1, 0]), 10.)
        self.assertAlmostEqual(float(result[-1, 4]), 0., places=5)

    def test_clock_cannot_smuggle_truth_labels(self):
        event = Court().sample().model_dump()
        event['payload']['simulation']['wear'] = .5
        with self.assertRaises(ValidationError):
            Event.model_validate(event)
