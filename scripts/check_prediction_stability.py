"""Reproduz ciclos normais/falha sem alterar o simulador ou os bancos em uso."""
import json
import sys
from collections import deque

import joblib
import numpy as np

from aiot.config import DATA_DIR
from aiot.features import INPUT_CHANNELS, FEATURE_NAMES, WINDOW, latest
from aiot.simulator import Court
from aiot.ml import qualify_rul


def scenario(model, seed, fault=False, mode='bearing', duration=6.):
    court = Court(seed)
    court.mode = mode
    court.fault_duration = duration
    if fault:
        court.command('compressor_01', {'action': 'inject_fault'})
    history = deque(maxlen=WINDOW)
    windows = []
    truth = []
    for step in range(960 if not fault else int(duration * 12) + 1):
        if court.water > 16:
            court.cooling = True
        elif court.water < 10:
            court.cooling = False
        if fault:
            court.cooling = True
        event = court.sample()
        if not court.cooling:
            history.clear()
            continue
        history.append([event.payload['sensors'][name] for name in INPUT_CHANNELS])
        vector = latest(list(history))
        if vector is not None:
            windows.append(vector[0])
            truth.append(max(0., (1 - court.wear) / court.fault_rate))
    x = np.asarray(windows)
    health = model['models']['health'].predict(x)
    rul = model['models']['rul_hours'].predict(x)
    qualified = [qualify_rul(float(r), float(h), model['metadata'].get('rul_calibration'))
                 for h, r in zip(health, rul)]
    reported = np.array([i for i, item in enumerate(qualified) if item['rul_hours'] is not None])
    if not fault:
        assert all(item['rul_hours'] is None for item in qualified), 'Prazo indevido em cenário saudável'
        assert float(health.min()) > 90, 'Falso desgaste em cenário saudável'
    else:
        assert health[-1] < 40, 'Falha não detectada pela saúde'
        assert sum(item['rul_hours'] is not None for item in qualified) >= 5, 'RUL não se tornou demonstrável durante falha'
        assert np.mean(np.abs(rul - truth)) < 2., 'Erro de RUL no cenário completo maior que 2 h'
        assert np.median(rul[reported[:3]]) > np.median(rul[reported[-3:]]), 'RUL publicada não acompanha a degradação'
    return {'seed': seed, 'fault': fault, 'samples': len(x),
            'mode': mode, 'duration_hours': duration,
            'rul_mae_hours': float(np.mean(np.abs(rul - truth))) if fault else None,
            'reported_rul_mae_hours': float(np.mean(np.abs(rul[reported] - np.asarray(truth)[reported]))) if len(reported) and fault else None,
            'reported_first_hours': float(rul[reported[0]]) if len(reported) else None,
            'reported_last_hours': float(rul[reported[-1]]) if len(reported) else None,
            'qualified_deadlines': sum(item['rul_hours'] is not None for item in qualified),
            'health_min': float(health.min()), 'health_max': float(health.max()),
            'rul_min': float(rul.min()), 'rul_max': float(rul.max()),
            'rul_span': float(np.ptp(rul)), 'final_health': float(health[-1]),
            'final_rul': float(rul[-1])}


def main():
    active = sys.argv[1] if len(sys.argv) > 1 else json.loads((DATA_DIR / 'models/active.json').read_text())['version']
    model = joblib.load(DATA_DIR / 'models' / active / 'model.joblib')
    assert model['metadata']['features'] == FEATURE_NAMES, 'Modelo antigo: preserve como baseline e gere/treine a nova dinâmica.'
    print(json.dumps({'version': active, 'metrics': {
        key: value['test'] for key, value in model['metadata']['metrics'].items()}}), flush=True)
    for seed in [42, 7, 123]:
        print(json.dumps(scenario(model, seed)), flush=True)
    for seed, mode, duration in [(99, 'bearing', 6.), (2026, 'overheating', 10.), (314, 'imbalance', 4.)]:
        print(json.dumps(scenario(model, seed, True, mode, duration)), flush=True)
    # Sementes adicionais reservadas ao ensaio final, fora dos pilotos iniciais.
    for seed, mode, duration in [(13579, 'bearing', 6.), (24680, 'overheating', 10.), (97531, 'imbalance', 4.)]:
        print(json.dumps(scenario(model, seed, True, mode, duration)), flush=True)


if __name__ == '__main__':
    main()
