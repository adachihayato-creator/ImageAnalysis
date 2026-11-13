"""Persistence and a frame-verified camera lock, independent of Pi/Tk modules."""
from collections import deque
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import shutil
import tempfile
import os

KEYS = ('ExposureTime', 'AnalogueGain', 'ColourGains', 'LensPosition')
# Provisional engineering comparison thresholds, NOT calibrated camera accuracy.
# No exposure, gain or focus operating values are supplied by this program.
TOLERANCES = {'ExposureTime': 1.0, 'AnalogueGain': 0.0001,
              'ColourGains': 0.0001, 'LensPosition': 0.005}
VERIFY_FRAMES = 5
VERIFY_TIMEOUT = 15.0
# Observed on this IMX708 setup: request 12986 us -> reported 12959 us.
# Correct the command once after measuring a constant offset; never relax the
# actual-value verification tolerance or adapt an already saved profile.
MAX_EXPOSURE_COMMAND_CORRECTION_US = 27


def operating_values(metadata):
    result = {}
    for key in KEYS:
        value = metadata.get(key)
        values = list(value) if key == 'ColourGains' and isinstance(value, (list, tuple)) else [value]
        if len(values) != (2 if key == 'ColourGains' else 1):
            raise ValueError(f'{key}: 値が不足しています')
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
               for v in values):
            raise ValueError(f'{key}: 有効な数値がありません')
        if key == 'LensPosition':
            if values[0] < 0: raise ValueError('LensPosition < 0')
        elif any(v <= 0 for v in values):
            raise ValueError(f'{key} <= 0')
        if key == 'ExposureTime':
            if values[0] != int(values[0]): raise ValueError('ExposureTime must be an integer')
            result[key] = int(values[0])
        else:
            result[key] = [float(v) for v in values] if key == 'ColourGains' else float(values[0])
    return result


def check_frame(metadata, requested, tolerances):
    differences = {}
    try:
        actual = operating_values(metadata)
    except (ValueError, TypeError) as error:
        return {'passed': False, 'problems': [str(error)], 'differences': {}}
    for key in KEYS:
        a = actual[key] if key == 'ColourGains' else [actual[key]]
        b = requested[key] if key == 'ColourGains' else [requested[key]]
        differences[key] = [abs(x-y) for x,y in zip(a,b)]
    problems = [key for key in KEYS if any(v > tolerances[key] + 1e-12 for v in differences[key])]
    for key in ('AeEnable','AwbEnable'):
        if key in metadata and metadata[key] != False:
            problems.append(key + ': auto enabled')
    if 'AfMode' in metadata and metadata['AfMode'] != 0:
        problems.append('AfMode: not manual')
    return {'passed': not problems, 'problems': problems, 'differences': differences}


def profile_digest(profile):
    return hashlib.sha256(json.dumps(profile, sort_keys=True, ensure_ascii=False,
                                     allow_nan=False).encode()).hexdigest()


def validate_profile(profile, context, supported=None):
    if profile.get('schema_version') != 1 or profile.get('context') != context:
        raise ValueError('保存設定の機器・解像度が一致しません。基準で調整し直してください。')
    values = operating_values(profile.get('values', {}))
    commands = operating_values(profile.get('command_values', values))
    if any(commands[key] != values[key] for key in KEYS if key != 'ExposureTime'):
        raise ValueError('露光以外の補正指示は許可されていません')
    if abs(commands['ExposureTime']-values['ExposureTime']) > MAX_EXPOSURE_COMMAND_CORRECTION_US:
        raise ValueError('露光補正指示が実測した範囲を超えています')
    tolerances = profile.get('tolerances', {})
    if set(tolerances) != set(TOLERANCES) or any(
        isinstance(tolerances[k], bool) or not isinstance(tolerances[k], (int,float))
        or not math.isfinite(tolerances[k]) or tolerances[k] < 0
        or tolerances[k] > TOLERANCES[k] for k in TOLERANCES
    ):
        raise ValueError('保存設定の比較許容差が不正です')
    if supported is not None:
        for key in ('AeEnable', 'AwbEnable', 'AfMode', *KEYS):
            if key not in supported: raise ValueError(f'カメラが {key} を提供していません')
        for key in KEYS:
            low, high = supported[key][:2]
            numbers = commands[key] if key == 'ColourGains' else [commands[key]]
            if any(v < low or v > high for v in numbers):
                raise ValueError(f'{key} がカメラの範囲外です')
    return commands


def load_profile(path, context, supported=None):
    profile = json.loads(Path(path).read_text())
    validate_profile(profile, context, supported)
    return profile


def save_profile(path, profile):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(profile, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    temporary = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent, delete=False) as out:
            temporary = Path(out.name)
            out.write(payload); out.flush(); os.fsync(out.fileno())
        if path.exists():
            stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            shutil.copy2(path, path.with_name(path.name + '.backup_' + stamp))
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists(): temporary.unlink()


class LockSession:
    """Never permit research capture until saved values pass frame checks."""
    def __init__(self, context):
        self.context = context
        self.state = 'unconfigured'
        self.profile = None
        self.persisted = False
        self.error = ''
        self.samples = deque(maxlen=8)
        self.started = 0.0
        self.last_sample_at = -1.0
        self.last_sensor_timestamp = None
        self.match_count = 0
        self.last_check = {'passed': False, 'problems': ['未設定']}
        self.rounding_samples = deque(maxlen=VERIFY_FRAMES)
        self.pending_exposure_correction = None
        self.rounding_attempted = False

    @property
    def can_capture(self):
        return self.state == 'locked' and self.persisted and self.last_check['passed']

    def begin_calibration(self, now):
        self.state = 'calibrating'
        self.persisted = False
        self.profile = None
        self.error = ''

        self.rounding_samples.clear()
        self.pending_exposure_correction = None
        self.rounding_attempted = False
        self.samples.clear()
        self.started = now
        self.last_sample_at = -1.0
        self.last_sensor_timestamp = None

    def observe_calibration(self, metadata, now, focused):
        if now - self.started > 30:
            self.fail('30秒以内に調整が安定しませんでした。基準の模様・照明を確認してください。')
            return False
        if not focused:
            self.samples.clear()
            return False
        if now - self.last_sample_at < .25: return False
        self.last_sample_at = now
        stamp = metadata.get('SensorTimestamp')
        if stamp is None or stamp == self.last_sensor_timestamp: return False
        self.last_sensor_timestamp = stamp
        try:
            values = operating_values(metadata)
        except (ValueError, TypeError):
            self.samples.clear(); return False
        self.samples.append(values)
        if now-self.started < 3 or len(self.samples) < self.samples.maxlen: return False
        # Stability is only a gate for candidate selection, not proof of quality.
        for key in KEYS:
            columns = zip(*(v[key] for v in self.samples)) if key == 'ColourGains' else ([v[key] for v in self.samples],)
            for column in columns:
                span = max(column) - min(column)
                limit = .02 if key == 'LensPosition' else abs(sum(column)/len(column)) * .01
                if span > limit: return False
        self.state = 'candidate'
        return True

    def make_candidate(self, metadata):
        if self.state != 'candidate': raise ValueError('基準の調整完了を待ってください')
        return {'schema_version': 1, 'context': self.context,
                'created_at': datetime.now().astimezone().isoformat(),
                'values': operating_values(metadata), 'tolerances': dict(TOLERANCES),
                'tolerances_note': 'Provisional numeric comparison only; not calibrated accuracy',
                'operator_reference_check_required': True,
                'reference_note': 'Operator confirms neutral reference/texture at sample plane and fixed lighting',
                'calibration_method': 'auto reference -> manual preview -> operator save'}

    def begin_apply(self, profile, now, persisted):
        validate_profile(profile, self.context)
        self.profile = profile
        self.persisted = persisted
        self.state = 'applying'
        self.started = now
        self.match_count = 0
        self.last_sensor_timestamp = None
        self.last_check = {'passed': False, 'problems': ['反映確認中']}
        self.error = ''
        self.rounding_samples.clear()
        self.pending_exposure_correction = None
        self.rounding_attempted = bool(profile.get('exposure_rounding_adjustment'))

    def observe_fixed(self, metadata, now):
        result = check_frame(metadata, self.profile['values'], self.profile['tolerances'])
        self.last_check = result
        if self.state == 'applying':
            stamp = metadata.get('SensorTimestamp')
            fresh = stamp is not None and stamp != self.last_sensor_timestamp
            if fresh:
                self.last_sensor_timestamp = stamp
                self.match_count = self.match_count+1 if result['passed'] else 0
                if not self.persisted and not self.rounding_attempted and result['problems']==['ExposureTime']:
                    self.rounding_samples.append(metadata['ExposureTime'])
                    if len(self.rounding_samples)==VERIFY_FRAMES and len(set(self.rounding_samples))==1:
                        offset=self.profile['values']['ExposureTime']-self.rounding_samples[-1]
                        if 0 < abs(offset) <= MAX_EXPOSURE_COMMAND_CORRECTION_US:
                            self.pending_exposure_correction=offset
                            self.rounding_attempted=True
                else:
                    self.rounding_samples.clear()
            if self.match_count >= VERIFY_FRAMES:
                self.state = 'locked' if self.persisted else 'confirm_preview'
            elif now-self.started > VERIFY_TIMEOUT:
                self.fail('設定が反映されません：' + ', '.join(result['problems']))
        elif self.state in ('locked', 'confirm_preview') and not result['passed']:
            self.fail('設定値の逸脱：' + ', '.join(result['problems']))
        return result

    def corrected_exposure_profile(self):
        if self.state!='applying' or self.persisted or self.pending_exposure_correction is None:
            raise ValueError('露光指示の補正条件が成立していません')
        profile=dict(self.profile)
        commands=dict(profile.get('command_values',profile['values']))
        original_command=commands['ExposureTime']
        commands['ExposureTime']+=self.pending_exposure_correction
        profile['command_values']=commands
        profile['exposure_rounding_adjustment']={
            'original_command_us':original_command,
            'observed_actual_us':self.rounding_samples[-1],
            'corrected_command_us':commands['ExposureTime'],
            'stable_distinct_frames':VERIFY_FRAMES,
            'note':'One attempt based on observed constant offset; original actual-value tolerance unchanged'}
        return profile

    def mark_saved(self):
        if self.state != 'confirm_preview' or not self.last_check['passed']:
            raise ValueError('固定プレビューの確認が必要です')
        self.persisted = True
        self.state = 'locked'

    def fail(self, message):
        self.state = 'error'
        self.error = message

    def capture_record(self, metadata, now):
        was_ready = self.can_capture
        result = self.observe_fixed(metadata, now)
        return {'mode': 'fixed_settings', 'profile': self.profile,
                'profile_sha256': profile_digest(self.profile),
                'requested_controls': self.profile.get('command_values',self.profile['values']),
                'expected_actual_values': self.profile['values'],
                'requested_auto_controls': {'AeEnable': False, 'AwbEnable': False, 'AfMode': 'Manual'},
                'frame_verification': result,
                'fixed_settings_verified': bool(was_ready and result['passed']),
                'verification_note': 'Values match within stored provisional tolerances; not proof of optical stability'}
