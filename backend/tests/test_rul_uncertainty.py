import unittest

import numpy as np

from aiot.ml import qualify_rul, calibrate_rul
from aiot.predictive import limit_checks, prediction_facts


class RulUncertaintyTests(unittest.TestCase):
    def calibration(self, radius=100):
        return {'bins': [{'health_min': 0, 'health_max': 101, 'radius_hours': radius}]}

    def test_healthy_signals_do_not_identify_a_failure_deadline(self):
        for estimate in [1500, 2500]:
            result = qualify_rul(estimate, 99.8, self.calibration())
            self.assertIsNone(result['rul_hours'])
            self.assertEqual(result['rul_status'], 'not_identifiable')
            self.assertEqual(result['rul_estimate_hours'], estimate)
            self.assertNotIn('rul_interval', result)
            self.assertFalse(limit_checks({'health': 99.8, **result})['rul_below_limit'])

    def test_large_validation_error_is_visible_with_low_confidence(self):
        result = qualify_rul(500, 65, self.calibration(400))
        self.assertEqual(result['rul_hours'], 500)
        self.assertEqual(result['rul_status'], 'low_confidence')
        self.assertEqual(result['rul_interval'], [100, 900])

    def test_healthy_reference_is_natural_wear_scenario_not_failure_prediction(self):
        result = qualify_rul(17, 99, self.calibration())
        self.assertEqual(result['rul_reference_hours'], 16500)
        self.assertIsNone(result['rul_hours'])
        self.assertFalse(limit_checks({'health': 99, **result})['rul_below_limit'])
        self.assertNotIn('rul_reference_hours', qualify_rul(17, 89, self.calibration()))
        self.assertNotIn('rul_reference_hours', qualify_rul(17, 99, None))

    def test_published_low_point_does_not_override_interval_for_alerts(self):
        result = qualify_rul(24, 80, self.calibration(50))
        self.assertEqual(result['rul_hours'], 24)
        self.assertEqual(result['rul_status'], 'low_confidence')
        self.assertFalse(limit_checks({'health': 80, **result})['rul_below_limit'])
        self.assertIn('BAIXA CONFIANÇA', prediction_facts({'health': 80, **result}))

    def test_simulated_error_threshold_changes_label_instead_of_hiding_value(self):
        for estimate, radius, status in [(1, .5, 'estimated'), (1, .51, 'low_confidence'), (4, 1, 'estimated'), (4, 1.01, 'low_confidence')]:
            calibration = self.calibration(radius)
            calibration['unit'] = 'simulated_operating_hours'
            result = qualify_rul(estimate, 60, calibration)
            self.assertEqual(result['rul_hours'], estimate)
            self.assertEqual(result['rul_status'], status)

    def test_precise_enough_degraded_estimate_is_retained(self):
        result = qualify_rul(200, 50, self.calibration(40))
        self.assertEqual(result['rul_hours'], 200)
        self.assertEqual(result['rul_status'], 'estimated')

    def test_old_model_requires_calibration(self):
        self.assertIsNone(qualify_rul(2000, 99, None)['rul_hours'])

    def test_alert_requires_entire_interval_below_limit(self):
        prediction = {'health': 80, **qualify_rul(24, 80, self.calibration(40))}
        self.assertFalse(limit_checks(prediction)['rul_below_limit'])
        prediction = {'health': 80, **qualify_rul(24, 80, self.calibration(10))}
        self.assertTrue(limit_checks(prediction)['rul_below_limit'])

    def test_uncertain_rul_cannot_be_reported_as_safe(self):
        result = {'health': 99, **qualify_rul(2000, 99, self.calibration(1200))}
        facts = prediction_facts(result)
        self.assertIn('RUL inconclusiva', facts)
        self.assertNotIn('NÃO abaixo', facts.split('RUL')[1])

    def test_test_labels_cannot_change_validation_interval(self):
        class FixedModel:
            def __init__(self, value):
                self.value = value

            def predict(self, x):
                return np.full(len(x), self.value)

        models = {'health': FixedModel(99), 'rul_hours': FixedModel(2000)}
        x = np.zeros((400, 15))
        y = np.zeros((400, 2))
        y[:200, 1] = np.linspace(500, 3500, 200)
        first = calibrate_rul(models, x, y, np.arange(200), np.arange(200, 400))
        y[200:, 1] = 2000
        second = calibrate_rul(models, x, y, np.arange(200), np.arange(200, 400))
        self.assertEqual(first['bins'][-1]['radius_hours'], second['bins'][-1]['radius_hours'])
        self.assertNotEqual(first['bins'][-1]['test_coverage'], second['bins'][-1]['test_coverage'])
