"""Mesmo cálculo causal de features para treino e inferência."""
import numpy as np

CHANNELS = ['compressor_temperature', 'compressor_current', 'compressor_vibration']
WINDOW = 12
FEATURE_NAMES = [f'{channel}_{stat}' for channel in CHANNELS for stat in ['last', 'mean', 'std', 'max', 'trend']]


def features(values, window=WINDOW):
    values = np.asarray(values, dtype=np.float64)
    if values.ndim != 2 or values.shape[1] != 3:
        raise ValueError('Esperadas três variáveis medidas do compressor.')
    # Ausência: valor anterior; nunca interpolar com observações futuras.
    cleaned = values.copy()
    defaults = [35., 2.5, 1.]
    bounds = [(0, 160), (0, 30), (0, 40)]
    for col in range(3):
        valid = np.isfinite(cleaned[:, col])
        indices = np.maximum.accumulate(np.where(valid, np.arange(len(cleaned)), -1))
        filled = np.where(indices >= 0, cleaned[np.maximum(indices, 0), col], defaults[col])
        cleaned[:, col] = np.clip(filled, *bounds[col])
    if len(cleaned) < window:
        return np.empty((0, len(FEATURE_NAMES)))
    windows = np.lib.stride_tricks.sliding_window_view(cleaned, window, axis=0)
    centered = np.arange(window) - (window - 1) / 2
    slope = (windows * centered).sum(axis=2) / (centered ** 2).sum()
    output = np.stack([windows[:, :, -1], windows.mean(axis=2), windows.std(axis=2), windows.max(axis=2), slope], axis=2)
    return output.reshape(len(output), -1).astype(np.float32)


def latest(history):
    output = features(history)
    return output[-1:] if len(output) else None
