"""Backup verificável do código e dos volumes deste Compose antes da limpeza."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PROJECT = 'smart-court'
HELPER = 'smart-court-app:local'


def run(*arguments):
    result = subprocess.run(arguments, cwd=ROOT, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout)
    return result.stdout.strip()


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


def backup(destination):
    destination = Path(destination).resolve()
    if destination == ROOT or ROOT in destination.parents:
        raise ValueError('Backup deve ficar fora do projeto.')
    destination.mkdir(parents=True, exist_ok=True)
    if (destination / 'manifest.json').exists():
        raise ValueError('Use uma pasta nova para não sobrescrever um backup verificado.')
    volumes_dir = destination / 'volumes'
    volumes_dir.mkdir(exist_ok=True)
    names = run('docker', 'volume', 'ls', '--filter', f'label=com.docker.compose.project={PROJECT}', '--format', '{{.Name}}').splitlines()
    if len(names) != 7:
        raise ValueError(f'Esperados sete volumes do projeto; encontrados {len(names)}.')
    for name in names:
        metadata = json.loads(run('docker', 'volume', 'inspect', name))[0]
        if metadata.get('Labels', {}).get('com.docker.compose.project') != PROJECT:
            raise ValueError('Volume não pertence ao projeto.')
    image_names = sorted(set(run('docker', 'compose', 'config', '--images').splitlines()))
    images = json.loads(run('docker', 'image', 'inspect', *image_names))
    # Todos os bancos param antes da cópia física, preservando consistência.
    print('Parando os serviços para copiar os volumes...', flush=True)
    run('docker', 'compose', 'stop', '--timeout', '30')
    files = []
    for name in names:
        archive = volumes_dir / (name + '.tar')
        run('docker', 'run', '--rm', '--user', '0', '--entrypoint', 'tar', '--mount', f'type=volume,source={name},target=/source,readonly', '--mount', f'type=bind,source={volumes_dir},target=/backup', HELPER, '-cf', '/backup/' + archive.name, '-C', '/source', '.')
        with tarfile.open(archive) as check:
            members = check.getmembers()
            if not members:
                raise ValueError('Arquivo de volume vazio: ' + name)
        files.append({'path': archive.relative_to(destination).as_posix(), 'volume': name, 'bytes': archive.stat().st_size, 'sha256': digest(archive), 'members': len(members)})
        print('Volume verificado:', name, archive.stat().st_size, 'bytes', flush=True)
    code = destination / 'projeto.zip'
    excluded = {'node_modules', '.venv', '__pycache__', 'dist', 'artifacts', 'data', 'secrets'}
    with zipfile.ZipFile(code, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for path in ROOT.rglob('*'):
            relative = path.relative_to(ROOT)
            if path.is_file() and not any(part in excluded for part in relative.parts) and path.name != '.env':
                archive.write(path, 'IOT/' + relative.as_posix())
    with zipfile.ZipFile(code) as archive:
        if archive.testzip() is not None:
            raise ValueError('ZIP do projeto está corrompido.')
        if 'IOT/CONTEXTO_PARA_RETOMAR.md' not in archive.namelist():
            raise ValueError('Markdown de contexto ausente no backup.')
    files.append({'path': code.name, 'bytes': code.stat().st_size, 'sha256': digest(code)})
    manifest = {'project': PROJECT, 'commit': run('git', 'rev-parse', 'HEAD'), 'files': files, 'images': [{'tags': row.get('RepoTags'), 'digests': row.get('RepoDigests')} for row in images]}
    (destination / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    (destination / 'RESTAURAR.md').write_text('''# Restaurar o projeto após a formatação

O backup contém projeto.zip (incluindo Git e Markdown de contexto), sete volumes Docker e manifest.json com hashes SHA-256. Os serviços estavam parados durante a cópia dos bancos. O volume de segredos inclui senhas locais; mantenha este backup privado, fora do GitHub.

1. Preserve esta pasta em D: ao formatar; formate somente a unidade pretendida.
2. Instale Git e Docker Desktop/WSL2.
3. Extraia projeto.zip em uma pasta de trabalho, por exemplo D:\\Projetos.
4. Na raiz IOT, execute `docker compose build api` para criar a imagem usada pela restauração.
5. Com um ambiente Docker vazio para este projeto, execute `python scripts/backup_project.py restore --destination "CAMINHO_DESTA_PASTA"`. Requer Python. A restauração recusa volumes já existentes.
6. Execute `docker compose up --build -d` e abra http://localhost:8080.
7. Leia CONTEXTO_PARA_RETOMAR.md e docs/implementacao-2bim.md.

Se quiser um ambiente novo e dispensar o histórico e modelos antigos, basta recuperar o código e subir o Compose; senhas novas serão geradas e você poderá gerar/treinar novamente pela interface.

As imagens públicas podem ser baixadas novamente. O manifesto registra seus digests; se uma versão futura mudar o formato de dados, use o digest registrado para recuperar os volumes originais. Nenhuma imagem pesada está incluída no ZIP.
''', encoding='utf-8')
    print('BACKUP VERIFICADO:', destination, flush=True)


def restore(destination):
    destination = Path(destination).resolve()
    manifest = json.loads((destination / 'manifest.json').read_text(encoding='utf-8'))
    if manifest['project'] != PROJECT:
        raise ValueError('Manifesto de outro projeto.')
    # Verificar tudo antes de criar qualquer volume.
    for row in manifest['files']:
        path = (destination / row['path']).resolve()
        if destination not in path.parents or digest(path) != row['sha256']:
            raise ValueError('Hash ou caminho inválido: ' + row['path'])
    existing = set(run('docker', 'volume', 'ls', '--format', '{{.Name}}').splitlines())
    volumes = [row for row in manifest['files'] if 'volume' in row]
    if any(row['volume'] in existing for row in volumes):
        raise ValueError('Já existem volumes deste projeto; restauração não sobrescreve dados.')
    for row in volumes:
        name = row['volume']
        if not name.startswith(PROJECT + '_') or not all(c.isalnum() or c in '_-' for c in name):
            raise ValueError('Nome de volume inválido.')
        run('docker', 'volume', 'create', '--label', f'com.docker.compose.project={PROJECT}', '--label', 'com.docker.compose.volume=' + name.removeprefix(PROJECT + '_'), name)
        run('docker', 'run', '--rm', '--user', '0', '--entrypoint', 'tar', '--mount', f'type=volume,source={name},target=/target', '--mount', f'type=bind,source={destination / "volumes"},target=/backup,readonly', HELPER, '-xf', '/backup/' + Path(row['path']).name, '-C', '/target')
        print('Restaurado:', name, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['backup', 'restore'])
    parser.add_argument('--destination', required=True)
    args = parser.parse_args()
    (backup if args.action == 'backup' else restore)(args.destination)
