import json
import os
from pathlib import Path
import joblib
import numpy as np
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from .config import DATA_DIR
from .contracts import LabConfig
from .features import features, FEATURE_NAMES, WINDOW

MAX_ROWS = 2_000_000


def safe_path(identifier, folder):
    import re
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', identifier):
        raise ValueError('Identificador inválido.')
    return DATA_DIR / folder / identifier


def generate(identifier, config: LabConfig, progress=lambda *_: None):
    if not 1_000_000 <= config.readings <= 20_000_000 or config.rows > MAX_ROWS:
        raise ValueError('Configure de 1 a 20 milhões de leituras, com no máximo 2 milhões de amostras de equipamento.')
    directory = safe_path(identifier, 'datasets')
    directory.mkdir(parents=True, exist_ok=True)
    metadata_file = directory / 'metadata.json'
    if metadata_file.exists():
        return json.loads(metadata_file.read_text())
    rng = np.random.default_rng(config.seed)
    steps = config.days * 1440 // config.interval_minutes
    rows = config.equipment_count * steps
    x = np.lib.format.open_memmap(directory / 'features.npy', mode='w+', dtype='float32', shape=(rows, len(FEATURE_NAMES)))
    y = np.lib.format.open_memmap(directory / 'targets.npy', mode='w+', dtype='float32', shape=(rows, 2))
    groups = np.lib.format.open_memmap(directory / 'groups.npy', mode='w+', dtype='int32', shape=(rows,))
    readings = np.lib.format.open_memmap(directory / 'readings.npy', mode='w+', dtype='float32', shape=(rows, 3 * config.sensors_per_type))
    hours = np.arange(steps) * config.interval_minutes / 60
    failed_count = max(1, round(config.equipment_count * config.failure_percent / 100))
    failing = set(rng.choice(config.equipment_count, failed_count, replace=False).tolist())
    for equipment in range(config.equipment_count):
        # Um bloco vetorizado por equipamento; sem loop por leitura sintética.
        failure_time = rng.uniform(config.days * 0.65, config.days * 0.98) * 24 if equipment in failing else config.days * 24 * rng.uniform(1.8, 2.6)
        onset = failure_time * rng.uniform(0.12, 0.30)
        degrade = np.clip((hours - onset) / (failure_time - onset), 0, 1)
        phase = rng.uniform(0, 2 * np.pi)
        day = np.sin(hours * 2 * np.pi / 24 + phase)
        load = 0.7 + 0.22 * day + 0.1 * np.sin(hours / (24 * 7))
        ambient = 27 + 6 * day + 2 * np.sin(hours * 2 * np.pi / (24 * 365))
        mode = rng.choice(config.failure_modes)
        multipliers = {'bearing': (1., 1., 1.3), 'overheating': (1.4, 1.1, 0.8), 'imbalance': (0.85, 1., 1.4)}[mode]
        signals = np.column_stack([
            ambient + 12 * load + 38 * degrade * multipliers[0] + rng.normal(0, 1.3 * config.noise, steps),
            1.9 + 1.1 * load + 3.8 * degrade * multipliers[1] + rng.normal(0, 0.2 * config.noise, steps),
            0.65 + 0.4 * load + 6 * degrade * multipliers[2] + rng.normal(0, 0.3 * config.noise, steps),
        ])
        signals += rng.normal(0, [2., .15, .2], (1, 3))
        replicas = np.tile(signals, (1, config.sensors_per_type)) + rng.normal(0, .08 * config.noise, (steps, 3 * config.sensors_per_type))
        missing = rng.random(replicas.shape) < config.missing_percent / 100
        outliers = rng.random(replicas.shape) < config.outlier_percent / 100
        replicas[outliers] += rng.normal(0, 25, outliers.sum())
        replicas[missing] = np.nan
        reshaped = replicas.reshape(steps, config.sensors_per_type, 3)
        counts = np.isfinite(reshaped).sum(axis=1)
        means = np.divide(np.nansum(reshaped, axis=1), counts, out=np.full((steps, 3), np.nan), where=counts > 0)
        offset = equipment * steps
        end = offset + steps
        readings[offset:end] = replicas
        x[offset:offset + WINDOW - 1] = np.nan
        x[offset + WINDOW - 1:end] = features(means)
        y[offset:end, 0] = np.clip(100 * (1 - degrade ** 1.2), 0, 100)
        y[offset:end, 1] = np.maximum(failure_time - hours, 0)
        groups[offset:end] = equipment
        progress(round((equipment + 1) * 100 / config.equipment_count), f'Equipamento {equipment + 1}/{config.equipment_count}')
    for array in [x, y, groups, readings]:
        array.flush()
    result = {'id': identifier, 'rows': rows, 'readings': rows * 3 * config.sensors_per_type, 'equipment_count': config.equipment_count, 'config': config.model_dump(), 'features': FEATURE_NAMES, 'window': WINDOW, 'label_columns': ['health', 'rul_hours']}
    temporary = directory / 'metadata.tmp'
    temporary.write_text(json.dumps(result))
    temporary.replace(metadata_file)
    return result


def score(real, predicted):
    return {'mae': float(mean_absolute_error(real, predicted)), 'rmse': float(np.sqrt(mean_squared_error(real, predicted))), 'r2': float(r2_score(real, predicted))}


def train(identifier, dataset_id, progress=lambda *_: None):
    directory = safe_path(dataset_id, 'datasets')
    metadata = json.loads((directory / 'metadata.json').read_text())
    x = np.load(directory / 'features.npy', mmap_mode='r')
    y = np.load(directory / 'targets.npy', mmap_mode='r')
    groups = np.load(directory / 'groups.npy', mmap_mode='r')
    rng = np.random.default_rng(metadata['config']['seed'] + 7)
    equipment = rng.permutation(np.unique(groups))
    train_end = max(1, int(len(equipment) * .6))
    val_end = max(train_end + 1, int(len(equipment) * .8))
    partitions = [equipment[:train_end], equipment[train_end:val_end], equipment[val_end:]]
    selected = []
    for members in partitions:
        indices = np.flatnonzero(np.isin(groups, members) & np.isfinite(x).all(axis=1))
        if len(indices) < 100:
            raise ValueError('Amostras insuficientes para dividir por equipamento.')
        selected.append(rng.choice(indices, min(len(indices), 50_000), replace=False))
    train_idx, val_idx, test_idx = selected
    models = {}
    metrics = {}
    for target, name in enumerate(['health', 'rul_hours']):
        progress(15 + target * 40, f'Treinando {name}')
        model = make_pipeline(SimpleImputer(strategy='median'), ExtraTreesRegressor(n_estimators=64, max_depth=16, min_samples_leaf=8, n_jobs=2, random_state=metadata['config']['seed']))
        model.fit(x[train_idx], y[train_idx, target])
        real = y[test_idx, target]
        pred = model.predict(x[test_idx])
        baseline = np.full(len(real), np.mean(y[train_idx, target]))
        validation = score(y[val_idx, target], model.predict(x[val_idx]))
        test_score = score(real, pred)
        baseline_score = score(real, baseline)
        beats_baseline = test_score['mae'] < baseline_score['mae'] and test_score['rmse'] < baseline_score['rmse'] and validation['mae'] < mean_absolute_error(y[val_idx, target], np.full(len(val_idx), baseline[0]))
        importance = model[-1].feature_importances_
        metrics[name] = {
            'test': test_score, 'validation': validation, 'baseline': baseline_score, 'beats_baseline': bool(beats_baseline),
            'scatter': [{'real': float(a), 'predicted': float(b)} for a, b in zip(real[:150], pred[:150])],
            'importance': [{'feature': feature, 'value': float(value)} for feature, value in sorted(zip(FEATURE_NAMES, importance), key=lambda pair: -pair[1])],
        }
        models[name] = model
    accepted = all(value['beats_baseline'] for value in metrics.values())
    result = {'version': identifier, 'dataset_id': dataset_id, 'metrics': metrics, 'accepted': accepted, 'split': {'train': partitions[0].tolist(), 'validation': partitions[1].tolist(), 'test': partitions[2].tolist()}, 'features': FEATURE_NAMES, 'window': WINDOW}
    model_dir = safe_path(identifier, 'models')
    model_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump({'models': models, 'metadata': result}, model_dir / 'model.joblib')
    (model_dir / 'metadata.json').write_text(json.dumps(result))
    progress(100, 'Treinamento concluído' if accepted else 'Modelo não superou a base simples; versão não ativada')
    return result


def activate(identifier):
    artifact = safe_path(identifier, 'models') / 'model.joblib'
    if not artifact.exists():
        raise ValueError('Artefato do modelo não encontrado.')
    active = DATA_DIR / 'models' / 'active.json'
    temporary = active.with_suffix('.tmp')
    temporary.write_text(json.dumps({'version': identifier}))
    os.replace(temporary, active)


class Predictor:
    def __init__(self):
        self.version = None
        self.models = None

    def reload(self):
        active = DATA_DIR / 'models' / 'active.json'
        if not active.exists():
            return
        version = json.loads(active.read_text())['version']
        if version != self.version:
            artifact = joblib.load(safe_path(version, 'models') / 'model.joblib')
            if artifact['metadata']['features'] != FEATURE_NAMES or artifact['metadata']['window'] != WINDOW:
                raise ValueError('Contrato de features incompatível.')
            self.models = artifact['models']
            self.version = version

    def predict(self, history):
        self.reload()
        if not self.models:
            return {'status': 'no_model', 'version': None}
        vector = features(history)
        if not len(vector):
            return {'status': 'warming_up', 'version': self.version, 'required_samples': WINDOW}
        return {'status': 'ready', 'version': self.version, 'health': float(np.clip(self.models['health'].predict(vector[-1:])[0], 0, 100)), 'rul_hours': float(max(0, self.models['rul_hours'].predict(vector[-1:])[0]))}
