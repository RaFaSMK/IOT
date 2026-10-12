import unittest
from aiot.assistant_facts import sections, selected_sections, validate_selection


class AssistantFactsTests(unittest.TestCase):
    def setUp(self):
        self.data = {'predictions': {'compressor_01': {
            'facts': 'Saúde: 38.00/100, ABAIXO do limite 40. RUL: 294.80 horas, NÃO abaixo do limite 48 horas.',
            'source_timestamp': '2026-10-12T12:00:00Z', 'alert_active': True,
            'limit_checks': {'health_below_limit': True, 'rul_below_limit': False},
            'alert_state': 'Alerta ativo. São necessárias dez previsões normais para resolver.',
        }}, 'alerts': [], 'telemetry': {}, 'models': []}

    def test_low_health_has_only_health_as_current_alert_reason(self):
        facts = sections(self.data)
        self.assertIn('RUL: 294.80 horas, NÃO abaixo', facts['predictions'])
        self.assertIn('Limites violados nesta previsão: saúde abaixo de 40.', facts['alerts'])
        self.assertNotIn('RUL abaixo de 48', facts['alerts'])

    def test_recovery_does_not_reinterpret_a_persisted_alert(self):
        self.data['predictions']['compressor_01']['limit_checks'] = {
            'health_below_limit': False, 'rul_below_limit': False}
        self.assertIn('Limites violados nesta previsão: nenhum.', sections(self.data)['alerts'])

    def test_untrusted_model_text_cannot_be_rendered_as_fact(self):
        facts = sections(self.data)
        raw = '{"sections":["invented"],"text":"A RUL está abaixo de 48 horas"}'
        self.assertEqual(selected_sections(raw, facts, set()), [])
        with self.assertRaises(ValueError):
            validate_selection(raw, facts)

    def test_partial_stream_does_not_emit_unfinished_or_duplicate_sections(self):
        facts = sections(self.data)
        self.assertEqual(selected_sections('{"sections":["predict', facts, set()), [])
        self.assertEqual(selected_sections('{"sections":["predictions","predictions"]}', facts, set()), ['predictions'])
        self.assertEqual(selected_sections('{"sections":["predictions"]}', facts, {'predictions'}), [])

    def test_selection_must_use_known_identifiers(self):
        facts = sections(self.data)
        self.assertEqual(validate_selection('{"sections":["predictions","alerts"]}', facts), ['predictions', 'alerts'])
        for raw in ['{}', '{"sections":[]}', '{"sections":[1]}']:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                validate_selection(raw, facts)


if __name__ == '__main__':
    unittest.main()
