"""Dinâmica sintética compartilhada por laboratório e dispositivo.

RUL é expressa em horas de operação simuladas, supondo a continuação da
degradação atual. Não é uma previsão de data no calendário nem de máquina real.
"""
import numpy as np
from scipy.signal import lfilter

PHYSICS_VERSION = 'compressor-v2'
STEP_HOURS = 5 / 60
PUBLISH_SECONDS = 2
NATURAL_RATE = .00006
AMBIENT_NOISE = .05
THERMAL_HOURS = 20 / 60
TEMPERATURE_PROFILE = 'thermal-20min-v1'
MODES = {'bearing': (1., 1., 1.3), 'overheating': (1.4, 1.1, .8), 'imbalance': (.85, 1., 1.4)}


def thermal_response(values, previous=None, sample_hours=STEP_HOURS):
    """Inércia térmica causal, idêntica para blocos de treino e passos ao vivo."""
    values = np.asarray(values, dtype=float)
    alpha = -np.expm1(-sample_hours / THERMAL_HOURS)
    if values.ndim == 0:
        initial = float(values) if previous is None else previous
        return float(initial + alpha * (values - initial))
    if not len(values):
        return values.copy()
    initial = values[0] if previous is None else previous
    return lfilter([alpha], [1, -(1 - alpha)], values, zi=[(1 - alpha) * initial])[0]


def compressor_signals(ambient, load, wear, cooling, mode, offsets, rng, noise=.6, previous_temperature=None, sample_hours=STEP_HOURS):
    """Aceita escalares ou blocos NumPy; nenhum rótulo é parte da saída."""
    ambient, load, wear, cooling = np.broadcast_arrays(ambient, load, wear, cooling)
    multipliers = MODES[mode]
    temperature = np.where(cooling, ambient + 12 * load + 38 * wear * multipliers[0] + offsets[0], ambient + 1)
    current = np.where(cooling, 1.9 + 1.1 * load + 3.8 * wear * multipliers[1] + offsets[1], 0)
    vibration = np.where(cooling, .65 + .4 * load + 6 * wear * multipliers[2] + offsets[2], 0)
    signals = np.stack([temperature, current, vibration], axis=-1)
    signals += rng.normal(0, np.array([1.3, .2, .3]) * noise, signals.shape)
    signals[..., 0] = thermal_response(signals[..., 0], previous_temperature, sample_hours)
    signals[..., 1:] = np.maximum(signals[..., 1:], 0)
    return signals


def load_at(hours, phase=0):
    return .7 + .22 * np.sin(2 * np.pi * np.asarray(hours) / 24 + phase) + .1 * np.sin(2 * np.pi * np.asarray(hours) / (24 * 7))


def ambient_at(hours, phase=0):
    return 27 + 6 * np.sin(2 * np.pi * np.asarray(hours) / 24 + phase) + 2 * np.sin(2 * np.pi * np.asarray(hours) / (24 * 365))
