import json
import os
from pathlib import Path
import joblib
import numpy as np
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.compose import TransformedTargetRegressor
from .config import DATA_DIR
from .contracts import LabConfig
from .features import features, FEATURE_NAMES, WINDOW
from .equipment import PHYSICS_VERSION, STEP_HOURS, NATURAL_RATE, AMBIENT_NOISE, TEMPERATURE_PROFILE, compressor_signals, load_at, ambient_at

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
        # Bloco por equipamento: estados de carga, paradas e relógio de operação.
        phase = rng.uniform(0, 2 * np.pi)
        on_hours = rng.uniform(2.5, 5.)
        off_hours = rng.uniform(1., 3.)
        cooling = np.mod(hours + rng.uniform(0, on_hours + off_hours), on_hours + off_hours) < on_hours
        operating = np.cumsum(cooling) * config.interval_minutes / 60
        # A falha tem uma fase observável de 4–14 horas de OPERAÇÃO.
        # O tempo de início continua oculto: não inferir prazo na fase saudável.
        duration = rng.uniform(4., 14.)
        onset = rng.uniform(.15, .8) * max(0, operating[-1] - duration)
        if equipment not in failing:
            onset = operating[-1] + rng.uniform(100, 1000)
        natural = np.minimum(operating, onset) * NATURAL_RATE
        rate = (1 - onset * NATURAL_RATE) / duration
        degrade = np.clip(natural + np.maximum(0, operating - onset) * rate, 0, 1)
        load = load_at(hours, phase)
        ambient = ambient_at(hours, phase) + rng.normal(0, AMBIENT_NOISE, steps)
        mode = rng.choice(config.failure_modes)
        offsets = rng.normal(0, [.6, .04, .05])
        signals = compressor_signals(ambient, load, degrade, cooling, mode, offsets, rng, config.noise, sample_hours=config.interval_minutes / 60)
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
        feature_values = features(np.column_stack([means, ambient]), sample_hours=config.interval_minutes / 60)
        prefix = steps - len(feature_values)
        x[offset:end] = np.nan
        x[offset + prefix:end] = feature_values
        # Não misturar partida/parada nem usar linhas posteriores à falha.
        window_steps = max(1, int(np.ceil((WINDOW - 1) * STEP_HOURS / (config.interval_minutes / 60))))
        off_count = np.concatenate([[0], np.cumsum(~cooling)])
        indices = np.arange(steps)
        uninterrupted = off_count[indices + 1] - off_count[np.maximum(0, indices - window_steps)] == 0
        x[offset:end][~uninterrupted | (degrade >= 1)] = np.nan
        y[offset:end, 0] = np.clip(100 * (1 - degrade ** 1.2), 0, 100)
        y[offset:end, 1] = np.maximum(onset + duration - operating, 0)
        groups[offset:end] = equipment
        progress(round((equipment + 1) * 100 / config.equipment_count), f'Equipamento {equipment + 1}/{config.equipment_count}')
    for array in [x, y, groups, readings]:
        array.flush()
    result = {'id': identifier, 'rows': rows, 'readings': rows * 3 * config.sensors_per_type, 'equipment_count': config.equipment_count, 'config': config.model_dump(), 'physics_version': PHYSICS_VERSION, 'features': FEATURE_NAMES, 'window': WINDOW, 'step_hours': STEP_HOURS, 'rul_unit': 'simulated_operating_hours', 'label_columns': ['health', 'rul_hours']}
    result['temperature_profile'] = TEMPERATURE_PROFILE
    temporary = directory / 'metadata.tmp'
    temporary.write_text(json.dumps(result))
    temporary.replace(metadata_file)
    return result


def score(real, predicted):
    return {'mae': float(mean_absolute_error(real, predicted)), 'rmse': float(np.sqrt(mean_squared_error(real, predicted))), 'r2': float(r2_score(real, predicted))}


def train(identifier, dataset_id, progress=lambda *_: None):
    directory = safe_path(dataset_id, 'datasets')
    metadata = json.loads((directory / 'metadata.json').read_text())
    if metadata.get('physics_version') != PHYSICS_VERSION:
        raise ValueError('Dataset de dinâmica antiga. Gere um novo dataset; os anteriores serão preservados.')
    x = np.load(directory / 'features.npy', mmap_mode='r')
    y = np.load(directory / 'targets.npy', mmap_mode='r')
    groups = np.load(directory / 'groups.npy', mmap_mode='r')
    rng = np.random.default_rng(metadata['config']['seed'] + 7)
    equipment = rng.permutation(np.unique(groups))
    train_end = max(1, int(len(equipment) * .6))
    val_end = max(train_end + 1, int(len(equipment) * .8))
    partitions = [equipment[:train_end], equipment[train_end:val_end], equipment[val_end:]]
    valid = np.isfinite(x).all(axis=1)
    models = {}
    metrics = {}
    for target, name in enumerate(['health', 'rul_hours']):
        # RUL só aprende onde há degradação observável; não rotular sinais
        # saudáveis idênticos com prazos arbitrários para a regressão pontual.
        eligible = valid & ((y[:, 0] < 90) if target == 1 else True)
        selected = []
        for members in partitions:
            indices = np.flatnonzero(np.isin(groups, members) & eligible)
            if len(indices) < 100:
                raise ValueError('Amostras degradadas insuficientes por equipamento; aumente equipamentos/dias/falhas.')
            # Saúde: incluir a fase degradada rara, sem excluir normais.
            if target == 0 and len(indices) > 50_000:
                healthy = indices[y[indices, 0] >= 90]
                degraded = indices[y[indices, 0] < 90]
                part = rng.choice(degraded, min(len(degraded), 25_000), replace=False)
                indices = np.concatenate([part, rng.choice(healthy, min(len(healthy), 50_000 - len(part)), replace=False)])
            selected.append(rng.choice(indices, min(len(indices), 50_000), replace=False))
        train_idx, val_idx, test_idx = selected
        progress(15 + target * 40, f'Treinando {name}')
        model = make_pipeline(SimpleImputer(strategy='median'), ExtraTreesRegressor(n_estimators=128 if target == 1 else 64, max_depth=18 if target == 1 else 16, min_samples_leaf=3 if target == 1 else 8, n_jobs=2, random_state=metadata['config']['seed']))
        if target == 1:
            # Dar atenção também aos horizontes curtos, sem negativos e sem
            # permitir que prazos longos dominem o critério de ajuste.
            model = TransformedTargetRegressor(regressor=model, func=np.log1p, inverse_func=np.expm1)
        model.fit(x[train_idx], np.asarray(y[train_idx, target], dtype=np.float64))
        real = y[test_idx, target]
        pred = model.predict(x[test_idx])
        baseline = np.full(len(real), np.mean(y[train_idx, target]))
        validation = score(y[val_idx, target], model.predict(x[val_idx]))
        test_score = score(real, pred)
        baseline_score = score(real, baseline)
        beats_baseline = test_score['mae'] < baseline_score['mae'] and test_score['rmse'] < baseline_score['rmse'] and validation['mae'] < mean_absolute_error(y[val_idx, target], np.full(len(val_idx), baseline[0]))
        importance = (model.regressor_[-1] if target == 1 else model[-1]).feature_importances_
        metrics[name] = {
            'test': test_score, 'validation': validation, 'baseline': baseline_score, 'beats_baseline': bool(beats_baseline),
            'samples': {'train': len(train_idx), 'validation': len(val_idx), 'test': len(test_idx)},
            'scope': 'degradation_observed' if target == 1 else 'all_operating_conditions',
            'scatter': [{'real': float(a), 'predicted': float(b)} for a, b in zip(real[:150], pred[:150])],
            'importance': [{'feature': feature, 'value': float(value)} for feature, value in sorted(zip(FEATURE_NAMES, importance), key=lambda pair: -pair[1])],
        }
        models[name] = model
    calibration = calibrate_rul(models, x, y, val_idx, test_idx)
    accepted = all(value['beats_baseline'] for value in metrics.values())
    result = {'version': identifier, 'dataset_id': dataset_id, 'metrics': metrics, 'accepted': accepted, 'physics_version': PHYSICS_VERSION, 'rul_unit': 'simulated_operating_hours', 'step_hours': STEP_HOURS, 'rul_calibration': calibration, 'split': {'train': partitions[0].tolist(), 'validation': partitions[1].tolist(), 'test': partitions[2].tolist()}, 'features': FEATURE_NAMES, 'window': WINDOW}
    result['temperature_profile'] = metadata.get('temperature_profile', 'instant-v1')
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


def calibrate_rul(models, x, y, validation, test):
    """Faixas empíricas por horizonte, ajustadas só na validação, avaliadas no teste.

    Equipamentos saudáveis têm vidas distintas com sinais semelhantes. Uma média
    de horas nessa região não constitui um prazo identificável de falha.
    """
    validation_rul = models['rul_hours'].predict(x[validation])
    residual = np.abs(y[validation, 1] - validation_rul)
    test_rul = models['rul_hours'].predict(x[test])
    bins = []
    for low, high in [(0, 1), (1, 2), (2, 4), (4, 8), (8, None)]:
        mask = (validation_rul >= low) & ((validation_rul < high) if high is not None else True)
        # O erro absoluto depende do horizonte previsto. Faixas de saúde
        # misturavam prazos curtos e longos com incertezas muito diferentes.
        center = (low + high) / 2 if high is not None else low * 1.5
        errors = residual[mask] if mask.sum() >= 40 else residual[np.argsort(np.abs(validation_rul - center))[:min(40, len(residual))]]
        quantile = min(1., np.ceil((len(errors) + 1) * .9) / len(errors))
        radius = float(np.quantile(errors, quantile, method='higher'))
        check = (test_rul >= low) & ((test_rul < high) if high is not None else True)
        covered = np.abs(y[test, 1] - test_rul) <= radius
        bins.append({'rul_min': low, 'rul_max': high, 'radius_hours': radius,
                     'validation_samples': int(mask.sum()), 'test_samples': int(check.sum()),
                     'test_coverage': float(covered[check].mean()) if check.any() else None})
    return {'nominal_coverage': .9, 'source': 'synthetic_validation', 'unit': 'simulated_operating_hours', 'binning': 'predicted_rul', 'bins': bins}


def qualify_rul(estimate, health, calibration):
    result = {'rul_hours': None, 'rul_estimate_hours': estimate, 'rul_status': 'uncalibrated'}
    if not calibration:
        result['rul_reason'] = 'Treine uma nova versão para avaliar a incerteza da RUL.'
        return result
    if health >= 90:
        # O regressor condicional não foi treinado para prazos saudáveis.
        # Nem ponto nem faixa dessa extrapolação podem alimentar alertas.
        result['rul_status'] = 'not_identifiable'
        result['rul_reason'] = 'Leituras sem desgaste suficiente para identificar um prazo de falha.'
        return result
    if calibration.get('binning') == 'predicted_rul':
        band = next(item for item in calibration['bins'] if item['rul_min'] <= estimate and (item['rul_max'] is None or estimate < item['rul_max']))
    else:
        band = next(item for item in calibration['bins'] if item['health_min'] <= health < item['health_max'])
    radius = band['radius_hours']
    result['rul_interval'] = [max(0., estimate - radius), estimate + radius]
    # Erro amplo qualifica a estimativa como baixa confiança, sem ocultá-la.
    # A faixa continua sendo usada pelas regras de alerta, não apenas o ponto.
    allowance = .5 if calibration.get('unit') == 'simulated_operating_hours' else 48.
    uncertain = radius > max(allowance, .25 * estimate)
    result['rul_status'] = 'low_confidence' if uncertain else 'estimated'
    result['rul_reason'] = ('Estimativa de baixa confiança: erro de validação amplo; interprete o valor junto com a faixa experimental.' if uncertain else
                            'Estimativa experimental com faixa de erro medida em dados sintéticos.')
    result['rul_hours'] = estimate
    return result


class Predictor:
    def __init__(self):
        self.version = None
        self.models = None
        self.calibration = None

    def reload(self):
        active = DATA_DIR / 'models' / 'active.json'
        if not active.exists():
            return
        version = json.loads(active.read_text())['version']
        if version != self.version:
            artifact = joblib.load(safe_path(version, 'models') / 'model.joblib')
            if artifact['metadata']['features'] != FEATURE_NAMES or artifact['metadata']['window'] != WINDOW:
                self.models = None
                self.version = version
                return
            self.models = artifact['models']
            self.calibration = artifact['metadata'].get('rul_calibration')
            self.version = version

    def predict(self, history):
        self.reload()
        if not self.models:
            return {'status': 'incompatible_model' if self.version else 'no_model', 'version': self.version}
        vector = features(history)
        if not len(vector):
            return {'status': 'warming_up', 'version': self.version, 'required_samples': WINDOW}
        health = float(np.clip(self.models['health'].predict(vector[-1:])[0], 0, 100))
        estimate = float(max(0, self.models['rul_hours'].predict(vector[-1:])[0]))
        return {'status': 'ready', 'version': self.version, 'health': health,
                'rul_unit': 'simulated_operating_hours', 'step_hours': STEP_HOURS,
                **qualify_rul(estimate, health, self.calibration)}
