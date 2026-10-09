import json
import os
from pathlib import Path
from functools import lru_cache


@lru_cache
def secrets():
    path = Path(os.getenv('SECRETS_FILE', '/secrets/config.json'))
    if not path.exists():
        raise RuntimeError('Segredos ausentes. Inicie com docker compose up --build.')
    return json.loads(path.read_text())


def credential(service=None):
    return secrets()['services'][service or os.getenv('SERVICE_NAME', 'api')]


DATA_DIR = Path(os.getenv('DATA_DIR', '/data'))
MODEL = os.getenv('OLLAMA_MODEL', 'llama3.2:3b')
EXCHANGE = 'court.events'
QUEUES = {
    'writer': ['telemetry.#', 'highlight.#'],
    'inference': ['telemetry.#', 'model.#'],
    'api': ['telemetry.#', 'highlight.#', 'prediction.#', 'alert.#', 'job.#', 'ack.#'],
    'gateway': ['command.#'],
    'rules': ['telemetry.#', 'prediction.#'],
    'generator': ['task.generate'],
    'trainer': ['task.train'],
}
