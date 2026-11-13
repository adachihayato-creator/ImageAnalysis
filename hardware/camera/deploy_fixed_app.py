"""Back up and update only the camera app files over the verified SSH link."""
import hashlib
import json
from pathlib import Path
import shlex
import subprocess

from import_captures import SSHTransport


REMOTE = r'''
import ast,hashlib,json,os,pathlib,shutil,sys,tempfile,datetime
from libcamera import controls
# Check names used by this version without opening/starting the camera.
required_enums=[controls.AfModeEnum.Manual,controls.AfModeEnum.Auto,
                controls.AfTriggerEnum.Start,controls.AfStateEnum.Focused]
payload=json.load(sys.stdin)
root=pathlib.Path('/home/morimoto.takumi.pi/camera_pero')
if not root.is_dir() or root.is_symlink(): raise RuntimeError('Unexpected app directory')
allowed={'camera_app.py','capture_metadata.py','fixed_settings.py','FIXED_SETTINGS_GUIDE.md',
         'position_guide.py','position_guide_candidate.json','POSITION_GUIDE.md'}
if set(payload['files'])!=allowed: raise RuntimeError('Unexpected files')
for name,text in payload['files'].items():
    target=root/name
    if target.is_symlink(): raise RuntimeError('Symlink at '+name)
    if name.endswith('.py'):ast.parse(text)
    if target.exists():
        old=hashlib.sha256(target.read_bytes()).hexdigest()
        new=hashlib.sha256(text.encode()).hexdigest()
        expected=payload['expected_previous'].get(name)
        if name.endswith('.py') and old not in (expected,new):
            raise RuntimeError('File changed on Pi; kept untouched: '+name)
backup=root/'backups'/('before_fixed_deploy_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
backup.mkdir(parents=True)
existing=[]
for name in allowed:
    if (root/name).exists():
        shutil.copy2(root/name,backup/name);existing.append(name)
with tempfile.TemporaryDirectory(prefix='.fixed-update-',dir=root) as directory:
    stage=pathlib.Path(directory)
    for name,text in payload['files'].items():
        (stage/name).write_text(text,encoding='utf-8')
    # Before touching live files, import and validate the pure helper modules.
    import importlib.util
    for name in ('fixed_settings.py','capture_metadata.py','position_guide.py'):
        spec=importlib.util.spec_from_file_location(name[:-3],stage/name)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    try:
        for name in sorted(allowed):os.replace(stage/name,root/name)
    except Exception:
        for name in allowed:
            if name in existing:shutil.copy2(backup/name,root/name)
            elif (root/name).exists():(root/name).unlink()
        raise
print(json.dumps({'backup':str(backup),'files':{name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in sorted(allowed)},
                 'camera_started':False,'calibration_performed':False}))
'''


def main():
    directory=Path(__file__).resolve().parent
    config=json.loads((directory/'import_config.json').read_text())
    for name in ('identity_file','known_hosts'):
        config[name]=str((directory/config[name]).resolve())
    transport=SSHTransport(config)
    files={name:(directory/name).read_text() for name in
           ('camera_app.py','capture_metadata.py','fixed_settings.py','FIXED_SETTINGS_GUIDE.md',
            'position_guide.py','position_guide_candidate.json','POSITION_GUIDE.md')}
    previous={name:hashlib.sha256((directory/'backups/before_fixed_settings_20261110'/name).read_bytes()).hexdigest()
              for name in ('camera_app.py','capture_metadata.py')}
    receipt_path=directory/'.connection/fixed_deploy_receipt.json'
    if receipt_path.exists():
        previous.update(json.loads(receipt_path.read_text())['files'])
    result=subprocess.run(transport.base+[shlex.join(['python3','-c',REMOTE])],
                          input=json.dumps({'files':files,'expected_previous':previous}).encode(),
                          stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=40)
    if result.returncode:
        raise SystemExit(result.stderr.decode(errors='replace'))
    receipt=json.loads(result.stdout)
    for name,text in files.items():
        if receipt['files'][name]!=hashlib.sha256(text.encode()).hexdigest():
            raise RuntimeError('Deployed hash mismatch: '+name)
    (directory/'.connection/fixed_deploy_receipt.json').write_text(json.dumps(receipt,indent=2))
    print('Updated app files and verified hashes. Backup:',receipt['backup'])
    print('Camera was not started; reference calibration and restart test are pending.')


if __name__=='__main__':main()
