"""Mesmo cálculo causal de features para treino e inferência."""
import numpy as np
from .equipment import STEP_HOURS

CHANNELS = ['compressor_temperature', 'compressor_current', 'compressor_vibration']
INPUT_CHANNELS = CHANNELS + ['ambient_temperature']
WINDOW = 12
FEATURE_NAMES = [f'{channel}_{stat}' for channel in ['temperature_rise', 'compressor_current', 'compressor_vibration'] for stat in ['last', 'mean', 'std', 'max', 'trend_per_hour']]


def features(values, window=WINDOW, sample_hours=STEP_HOURS):
    values = np.asarray(values, dtype=np.float64)
    if values.ndim != 2 or values.shape[1] != 4:
        raise ValueError('Esperadas três variáveis do compressor e temperatura ambiente.')
    if not np.isfinite(sample_hours) or sample_hours <= 0:
        raise ValueError('Intervalo de amostragem deve ser positivo.')
    # Ausência: valor anterior; nunca interpolar com observações futuras.
    cleaned = values.copy()
    defaults = [35., 2.5, 1., 25.]
    bounds = [(0, 160), (0, 30), (0, 40), (-20, 65)]
    for col in range(4):
        valid = np.isfinite(cleaned[:, col])
        indices = np.maximum.accumulate(np.where(valid, np.arange(len(cleaned)), -1))
        filled = np.where(indices >= 0, cleaned[np.maximum(indices, 0), col], defaults[col])
        cleaned[:, col] = np.clip(filled, *bounds[col])
    # Compensação por uma medição observável, sem acesso ao desgaste interno.
    cleaned[:, 0] -= cleaned[:, 3]
    cleaned = cleaned[:, :3]
    required = int(np.ceil((window - 1) * STEP_HOURS / sample_hours))
    if len(cleaned) <= required:
        return np.empty((0, len(FEATURE_NAMES)))
    # Janela temporal fixa (55 min), mesmo se o laboratório mudar a cadência.
    # Interpolação usa somente leituras já observadas no instante da previsão.
    positions = np.arange(required, len(cleaned))[:, None] - np.arange(window - 1, -1, -1) * STEP_HOURS / sample_hours
    lower = np.floor(positions + 1e-9).astype(int)
    upper = np.minimum(lower + 1, np.arange(required, len(cleaned))[:, None])
    fraction = (positions - lower)[..., None]
    windows = (cleaned[lower] * (1 - fraction) + cleaned[upper] * fraction).transpose(0, 2, 1)
    centered = (np.arange(window) - (window - 1) / 2) * STEP_HOURS
    slope = (windows * centered).sum(axis=2) / (centered ** 2).sum()
    output = np.stack([windows[:, :, -1], windows.mean(axis=2), windows.std(axis=2), windows.max(axis=2), slope], axis=2)
    return output.reshape(len(output), -1).astype(np.float32)


def latest(history):
    output = features(history)
    return output[-1:] if len(output) else None
