"""Gera segredos locais e configurações dos brokers sem credenciais no Git."""
import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess

ROOT = Path(os.getenv('BOOTSTRAP_DIR', '/secrets'))
SERVICES = ['api', 'gateway', 'writer', 'inference', 'rules', 'generator', 'trainer', 'simulator', 'monitor']
BINDINGS = {
    'writer': ['telemetry.#', 'highlight.#'],
    'inference': ['telemetry.#', 'model.#'],
    'api': ['#'],
    'gateway': ['command.#'],
    'rules': ['telemetry.#', 'prediction.#'],
    'generator': ['task.generate'],
    'trainer': ['task.train'],
}


def password_hash(password):
    salt = secrets.token_bytes(4)
    return base64.b64encode(salt + hashlib.sha256(salt + password.encode()).digest()).decode()


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    file = ROOT / 'config.json'
    if file.exists():
        config = json.loads(file.read_text())
    else:
        config = {
            'postgres_password': secrets.token_urlsafe(32),
            'influx_password': secrets.token_urlsafe(32),
            'influx_token': secrets.token_urlsafe(48),
            'jwt_secret': secrets.token_urlsafe(48),
            'services': {name: {'user': name, 'password': secrets.token_urlsafe(24)} for name in SERVICES},
            'demo_users': {role: {'username': name, 'password': secrets.token_urlsafe(15)} for role, name in [('viewer', 'visualizador'), ('operator', 'operador'), ('admin', 'administrador')]},
        }
        file.write_text(json.dumps(config, indent=2))
    for name in ['postgres_password', 'influx_password', 'influx_token']:
        (ROOT / name).write_text(config[name])
    (ROOT / 'demo-users.txt').write_text('\n'.join(f"{v['username']} ({role}): {v['password']}" for role, v in config['demo_users'].items()) + '\n')
    users = []
    permissions = []
    for name, cred in config['services'].items():
        if name == 'simulator':
            continue
        users.append({'name': name, 'password_hash': password_hash(cred['password']), 'hashing_algorithm': 'rabbit_password_hashing_sha256', 'tags': ['monitoring'] if name == 'monitor' else []})
        permissions.append({'user': name, 'vhost': 'court', 'configure': '^$', 'write': '^court\\.events$' if name not in ['monitor', 'writer'] else '^$', 'read': '^court\\.dlq$' if name == 'monitor' else f'^court\\.{name}$'})
    exchanges = [{'name': name, 'vhost': 'court', 'type': 'topic', 'durable': True, 'auto_delete': False, 'internal': False, 'arguments': {}} for name in ['court.events', 'court.dead']]
    queues = [{'name': f'court.{name}', 'vhost': 'court', 'durable': True, 'auto_delete': False, 'arguments': {'x-dead-letter-exchange': 'court.dead'}} for name in BINDINGS]
    queues.append({'name': 'court.dlq', 'vhost': 'court', 'durable': True, 'auto_delete': False, 'arguments': {}})
    bindings = [{'source': 'court.events', 'vhost': 'court', 'destination': f'court.{name}', 'destination_type': 'queue', 'routing_key': key, 'arguments': {}} for name, keys in BINDINGS.items() for key in keys]
    bindings.append({'source': 'court.dead', 'vhost': 'court', 'destination': 'court.dlq', 'destination_type': 'queue', 'routing_key': '#', 'arguments': {}})
    publish_keys = {'api': '^(command\\..*|task\\.(generate|train))$', 'gateway': '^(telemetry|highlight|ack)\\..*$', 'inference': '^prediction\\..*$', 'rules': '^(command|alert)\\..*$', 'generator': '^job\\.generate\\..*$', 'trainer': '^(job\\.train\\..*|model\\..*)$'}
    topic_permissions = [{'user': name, 'vhost': 'court', 'exchange': 'court.events', 'write': pattern, 'read': '.*'} for name, pattern in publish_keys.items()]
    (ROOT / 'rabbit-definitions.json').write_text(json.dumps({'vhosts': [{'name': 'court'}], 'users': users, 'permissions': permissions, 'topic_permissions': topic_permissions, 'exchanges': exchanges, 'queues': queues, 'bindings': bindings}))
    (ROOT / 'rabbitmq.conf').write_text('management.load_definitions = /secrets/rabbit-definitions.json\nvm_memory_high_watermark.absolute = 768MiB\ndefault_user = disabled\ndefault_pass = ' + secrets.token_urlsafe(32) + '\n')
    passwd = ROOT / 'mosquitto.passwd'
    if passwd.exists():
        passwd.unlink()
    for index, name in enumerate(['gateway', 'simulator']):
        cred = config['services'][name]
        args = ['mosquitto_passwd', '-b'] + (['-c'] if index == 0 else []) + [str(passwd), name, cred['password']]
        subprocess.run(args, check=True, capture_output=True)
    (ROOT / 'mosquitto.acl').write_text('user simulator\ntopic write court/+/telemetry/#\ntopic write court/+/highlight/#\ntopic write court/+/ack/#\ntopic read court/+/command/#\n\nuser gateway\ntopic read court/+/telemetry/#\ntopic read court/+/highlight/#\ntopic read court/+/ack/#\ntopic write court/+/command/#\n')
    for path in ROOT.iterdir():
        if path.is_file():
            # Brokers têm UIDs diferentes; o volume fica acessível somente aos containers.
            path.chmod(0o644)
    print('Segredos e configurações prontos. Credenciais de demonstração em /secrets/demo-users.txt.')


if __name__ == '__main__':
    main()
