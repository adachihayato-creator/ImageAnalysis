#!/usr/bin/env python3
"""Run on the Raspberry Pi as its usual user to authorize photo import."""
from pathlib import Path
import datetime
import getpass
import shutil

PUBLIC_KEY = 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOFpyDVS26MeGwRETz99sjtcsIGfjQSlLxeeFMePqNkv film-photo-import'

def main():
    if getpass.getuser() != 'morimoto.takumi.pi':
        raise SystemExit('Run as morimoto.takumi.pi, without sudo.')
    directory = Path.home() / '.ssh'
    if directory.is_symlink():
        raise SystemExit('SSH directory is a symlink; review manually.')
    directory.mkdir(mode=0o700, exist_ok=True)
    target = directory / 'authorized_keys'
    if target.is_symlink():
        raise SystemExit('authorized_keys is a symlink; review manually.')
    previous = target.read_text() if target.exists() else ''
    key_blob = PUBLIC_KEY.split()[1]
    if not any(key_blob in line.split() for line in previous.splitlines()):
        if target.exists():
            stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            shutil.copy2(target, directory / ('authorized_keys.backup_' + stamp))
        # Disable forwarding and PTYs for this key; remote Python still works.
        with target.open('a') as output:
            if previous and not previous.endswith('\n'):
                output.write('\n')
            output.write('restrict ' + PUBLIC_KEY + '\n')
    directory.chmod(0o700)
    target.chmod(0o600)
    print('OK: photo-import public key installed. Existing keys were preserved.')

if __name__ == '__main__':
    main()
