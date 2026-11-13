#!/usr/bin/env python3
"""Pull completed JPEG/JSON pairs from a Pi, leaving originals untouched."""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import tempfile
import time


# Executed on the Pi using only Python's standard library; nothing is installed there.
REMOTE_LIST = r'''
import hashlib,json,pathlib,sys,time
root=pathlib.Path(sys.argv[1]); result=[]
for sidecar in sorted(root.glob('*.json')):
    image=sidecar.with_suffix('.jpg')
    if not image.is_file(): continue
    try:
        paths=(image,sidecar); before=[p.stat() for p in paths]
        if any(time.time()-s.st_mtime < 3 for s in before): continue
        data=json.loads(sidecar.read_text())
        if data.get('image_filename') != image.name: continue
        hashes=[hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]
        after=[p.stat() for p in paths]
        if any((a.st_size,a.st_mtime_ns)!=(b.st_size,b.st_mtime_ns) for a,b in zip(before,after)): continue
        result.append({'image':image.name,'json':sidecar.name,'sha256':hashes,
                       'sizes':[s.st_size for s in after]})
    except (OSError,ValueError): continue
print(json.dumps(result))
'''
REMOTE_GET = r'''
import pathlib,sys
root=pathlib.Path(sys.argv[1]); name=sys.argv[2]
if pathlib.Path(name).name != name or name in ('.','..'): raise ValueError('Invalid filename')
with (root/name).open('rb') as source:
    while True:
        block=source.read(1024*1024)
        if not block: break
        sys.stdout.buffer.write(block)
'''


def digest(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


class SSHTransport:
    def __init__(self, config):
        self.config = config
        host, user = config['host'], config['user']
        if host.startswith('-') or user.startswith('-') or not host or not user:
            raise ValueError('Invalid SSH host/user')
        self.base = ['ssh', '-F', '/dev/null', '-o', 'BatchMode=yes',
                     '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=5',
                     '-o', 'ServerAliveInterval=10', '-o', 'ServerAliveCountMax=2',
                     '-p', str(int(config.get('port', 22))), f'{user}@{host}']
        # Optional dedicated files, resolved by main relative to the config.
        for key, option in (('known_hosts', 'UserKnownHostsFile'),):
            if config.get(key):
                self.base[3:3] = ['-o', f'{option}={config[key]}']
        if config.get('identity_file'):
            self.base[3:3] = ['-i', config['identity_file'], '-o', 'IdentitiesOnly=yes']

    def run(self, script, *args, stdout=subprocess.PIPE):
        command = shlex.join(['python3', '-c', script, self.config['remote_dir'], *args])
        result = subprocess.run(self.base + [command], stdout=stdout,
                                stderr=subprocess.PIPE, timeout=120)
        if result.returncode:
            raise RuntimeError(result.stderr.decode(errors='replace').strip())
        return result

    def inventory(self):
        return json.loads(self.run(REMOTE_LIST).stdout)

    def download(self, name, destination):
        with destination.open('wb') as out:
            self.run(REMOTE_GET, name, stdout=out)


def validate_entry(entry):
    image, sidecar = entry['image'], entry['json']
    for name in (image, sidecar):
        if not isinstance(name, str) or Path(name).name != name or '/' in name or '\\' in name:
            raise ValueError('Unsafe remote filename')
    if not image.endswith('.jpg') or sidecar != image[:-4] + '.json':
        raise ValueError('Invalid pair')
    if len(entry['sha256']) != 2 or len(entry['sizes']) != 2:
        raise ValueError('Invalid inventory')


def import_pair(transport, entry, destination):
    """Publish JSON last as the completion marker; never replace existing data."""
    validate_entry(entry)
    names = [entry['image'], entry['json']]
    targets = [destination / name for name in names]
    for target, expected in zip(targets, entry['sha256']):
        if target.is_symlink():
            raise FileExistsError(f'Symlink conflict: {target.name}')
        if target.exists() and digest(target) != expected:
            raise FileExistsError(f'Content conflict; kept existing file: {target.name}')
    if all(p.exists() for p in targets):
        return False
    with tempfile.TemporaryDirectory(prefix='.import-', dir=destination) as folder:
        stage = Path(folder)
        for name, expected, size in zip(names, entry['sha256'], entry['sizes']):
            file = stage / name
            transport.download(name, file)
            if file.stat().st_size != size or digest(file) != expected:
                raise ValueError(f'Transfer verification failed: {name}')
        record = json.loads((stage / names[1]).read_text())
        if record.get('image_filename') != names[0]:
            raise ValueError('JSON does not refer to this JPEG')
        if not (stage / names[0]).read_bytes().startswith(b'\xff\xd8'):
            raise ValueError('Not a JPEG')
        # Hard links publish each completed file without overwriting even if
        # another importer races us. A stopped pair is repaired on the next run.
        for name, target, expected in zip(names, targets, entry['sha256']):
            try:
                target.hardlink_to(stage / name)
            except FileExistsError:
                if target.is_symlink() or digest(target) != expected:
                    raise FileExistsError(f'Content conflict: {name}')
    return True


def sync_once(transport, destination, routes=None):
    destination.mkdir(parents=True, exist_ok=True)
    imported = skipped = failed = 0
    for entry in transport.inventory():
        try:
            pair_destination = Path((routes or {}).get(entry['image'], destination))
            pair_destination.mkdir(parents=True, exist_ok=True)
            if import_pair(transport, entry, pair_destination):
                imported += 1
                print('取り込み:', entry['image'], flush=True)
            else:
                skipped += 1
        except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
            failed += 1
            print('保留:', error, flush=True)
    print(f'新規 {imported}組 / 取り込み済み {skipped}組 / 保留 {failed}組', flush=True)
    return failed


def load_routes(config_path, config):
    if not config.get('routes_file'):
        return {}
    directory=Path(config_path).resolve().parent
    route_file=directory/config['routes_file']
    return {name:(directory/folder).resolve()
            for name,folder in json.loads(route_file.read_text()).items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=Path(__file__).with_name('import_config.json'))
    parser.add_argument('--watch', action='store_true', help='Repeat while this process runs')
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    for key in ('known_hosts', 'identity_file'):
        if config.get(key):
            config[key] = str((args.config.resolve().parent / config[key]).resolve())
    destination = (args.config.resolve().parent / config['destination']).resolve()
    transport = SSHTransport(config)
    print('保存先:', destination, flush=True)
    try:
        while True:
            try:
                routes = load_routes(args.config, config)
                failures = sync_once(transport, destination, routes)
                if not args.watch:
                    return 1 if failures else 0
            except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
                print('接続・取得待ち:', error, flush=True)
                if not args.watch:
                    return 1
            time.sleep(max(5, float(config.get('interval_seconds', 15))))
    except KeyboardInterrupt:
        print('\n停止しました。再実行で続きから取り込みます。')
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
