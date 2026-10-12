import unittest
from datetime import datetime, timedelta, timezone
from aiot.predictive import assistant_predictions, limit_checks, prediction_facts


class PredictiveFactsTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 12, 12, tzinfo=timezone.utc)

    def summarize(self, health=38, rul=294.8, age=0, status='ready', active=True):
        events = {'compressor_01': {'payload': {
            'status': status, 'health': health, 'rul_hours': rul,
            'source_timestamp': (self.now - timedelta(seconds=age)).isoformat(), 'version': 'test',
        }}}
        alerts = [{'device_id': 'compressor_01', 'active': active,
                   'message': 'Saúde baixa ou RUL abaixo de 48 horas.'}]
        return assistant_predictions(events, alerts, self.now)['compressor_01']

    def test_health_alert_does_not_claim_low_rul(self):
        item = self.summarize()
        self.assertTrue(item['limit_checks']['health_below_limit'])
        self.assertFalse(item['limit_checks']['rul_below_limit'])
        self.assertIn('RUL: 294.80 horas, NÃO abaixo', item['facts'])
        self.assertTrue(item['alert_active'])

    def test_low_rul_does_not_claim_low_health(self):
        item = self.summarize(health=80, rul=24)
        self.assertFalse(item['limit_checks']['health_below_limit'])
        self.assertTrue(item['limit_checks']['rul_below_limit'])

    def test_active_alert_can_have_no_current_violation(self):
        item = self.summarize(health=90, rul=300)
        self.assertTrue(item['alert_active'])
        self.assertFalse(any(item['limit_checks'].values()))
        self.assertIn('dez previsões normais', item['alert_state'])

    def test_stale_or_off_predictions_do_not_supply_current_values(self):
        for args in [{'age': 11}, {'status': 'equipment_off'}]:
            with self.subTest(args=args):
                item = self.summarize(**args)
                self.assertNotIn('limit_checks', item)
                self.assertNotIn('health', item)
                self.assertNotIn('rul_hours', item)

    def test_limits_are_strict_and_display_does_not_hide_violation(self):
        self.assertFalse(any(limit_checks({'health': 40, 'rul_hours': 48}).values()))
        self.assertIn('39.999/100, ABAIXO', prediction_facts({'health': 39.999, 'rul_hours': 300}))


if __name__ == '__main__':
    unittest.main()
