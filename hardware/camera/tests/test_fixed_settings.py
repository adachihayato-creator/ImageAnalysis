import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('fixed_settings',Path(__file__).resolve().parents[1]/'fixed_settings.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)

CONTEXT={'model':'imx708','camera_id':'camera-test','capture_size':[2304,1296],'format':'RGB888'}
VALUES={'ExposureTime':13066,'AnalogueGain':1.122807,'ColourGains':[2.19,2.0],'LensPosition':9.5}


def profile():
    return {'schema_version':1,'context':copy.deepcopy(CONTEXT),'values':copy.deepcopy(VALUES),
            'tolerances':dict(mod.TOLERANCES)}


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.session=mod.LockSession(copy.deepcopy(CONTEXT))

    def frames(self,start=1):
        for i in range(start,start+5):
            self.session.observe_fixed(dict(VALUES,SensorTimestamp=i),i*.1)

    def test_restart_loads_saved_values_without_calibration(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'settings.json'
            mod.save_profile(path,profile())
            saved=mod.load_profile(path,CONTEXT)
            self.session.begin_apply(saved,0,persisted=True)
            self.assertFalse(self.session.can_capture)
            self.frames()
            self.assertTrue(self.session.can_capture)
            self.assertEqual(self.session.profile['values'],VALUES)

    def test_unsaved_candidate_does_not_allow_capture(self):
        self.session.begin_apply(profile(),0,persisted=False)
        self.frames()
        self.assertEqual(self.session.state,'confirm_preview')
        self.assertFalse(self.session.can_capture)
        self.session.mark_saved()
        self.assertTrue(self.session.can_capture)

    def test_delayed_controls_reset_consecutive_counter(self):
        self.session.begin_apply(profile(),0,True)
        self.session.observe_fixed(dict(VALUES,SensorTimestamp=1),.1)
        self.session.observe_fixed(dict(VALUES,ExposureTime=15000,SensorTimestamp=2),.2)
        self.assertEqual(self.session.match_count,0)
        self.frames(start=3)
        self.assertTrue(self.session.can_capture)

    def test_duplicate_frames_do_not_pass(self):
        self.session.begin_apply(profile(),0,True)
        for i in range(10):self.session.observe_fixed(dict(VALUES,SensorTimestamp=1),i*.1)
        self.assertFalse(self.session.can_capture)
        self.session.observe_fixed(dict(VALUES,SensorTimestamp=1),16)
        self.assertEqual(self.session.state,'error')

    def test_failed_ae_disable_detected_from_values_or_flags(self):
        for updates in ({'ExposureTime':14000},{'AeEnable':True},{'AwbEnable':True},{'AfMode':2}):
            result=mod.check_frame(dict(VALUES,**updates),VALUES,mod.TOLERANCES)
            self.assertFalse(result['passed'])

    def test_drift_on_capture_invalidates_lock_and_records_requested_values(self):
        self.session.begin_apply(profile(),0,True);self.frames()
        record=self.session.capture_record(dict(VALUES,LensPosition=10.0),2)
        self.assertFalse(record['fixed_settings_verified'])
        self.assertFalse(self.session.can_capture)
        self.assertEqual(record['profile']['values'],VALUES)
        self.assertEqual(record['requested_auto_controls']['AeEnable'],False)

    def test_missing_and_nonfinite_values_rejected(self):
        for bad in ({},dict(VALUES,ColourGains=[1]),dict(VALUES,LensPosition=float('nan'))):
            self.assertFalse(mod.check_frame(bad,VALUES,mod.TOLERANCES)['passed'])

    def test_invalid_context_corrupt_file_and_expanded_tolerance_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'settings.json'
            path.write_text('broken')
            with self.assertRaises(ValueError):mod.load_profile(path,CONTEXT)
            for change in ('context','tolerances'):
                p=profile()
                if change=='context':p['context']['model']='different'
                else:p['tolerances']['ExposureTime']=10000
                path.write_text(json.dumps(p))
                with self.assertRaises(ValueError):mod.load_profile(path,CONTEXT)

    def test_camera_capability_and_ranges_checked(self):
        supported={key:(0,100,0) for key in ('AeEnable','AwbEnable','AfMode',*mod.KEYS)}
        supported['ExposureTime']=(100,100000,0)
        mod.validate_profile(profile(),CONTEXT,supported)
        del supported['LensPosition']
        with self.assertRaises(ValueError):mod.validate_profile(profile(),CONTEXT,supported)
        supported['LensPosition']=(0,2,0)
        with self.assertRaises(ValueError):mod.validate_profile(profile(),CONTEXT,supported)

    def test_backup_and_failed_atomic_save_preserve_previous_values(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'settings.json';p=profile();mod.save_profile(path,p)
            p['values']['ExposureTime']=12000
            mod.save_profile(path,p)
            backups=list(Path(directory).glob('settings.json.backup_*'))
            self.assertEqual(len(backups),1)
            self.assertEqual(json.loads(backups[0].read_text())['values']['ExposureTime'],13066)
            with patch.object(mod.os,'replace',side_effect=OSError('disk error')):
                with self.assertRaises(OSError):mod.save_profile(path,profile())
            self.assertEqual(json.loads(path.read_text())['values']['ExposureTime'],12000)

    def test_calibration_requires_focused_stable_distinct_frames_and_no_default_values(self):
        self.assertIsNone(self.session.profile)
        self.session.begin_calibration(0)
        for i in range(15):
            self.assertFalse(self.session.observe_calibration(dict(VALUES,SensorTimestamp=i),i*.3,False))
        for i in range(15,23):
            ready=self.session.observe_calibration(dict(VALUES,SensorTimestamp=i),i*.3,True)
        self.assertTrue(ready)
        self.assertEqual(self.session.make_candidate(VALUES)['values'],VALUES)

    def test_calibration_timeout_cannot_save(self):
        self.session.begin_calibration(0)
        self.session.observe_calibration(VALUES,31,False)
        self.assertEqual(self.session.state,'error')
        with self.assertRaises(ValueError):self.session.mark_saved()

    def test_measured_constant_exposure_offset_corrects_command_not_tolerance(self):
        self.session.begin_apply(profile(),0,False)
        for i in range(5):
            self.session.observe_fixed(dict(VALUES,ExposureTime=VALUES['ExposureTime']-27,
                                            SensorTimestamp=i+1),.1*(i+1))
        fixed=self.session.corrected_exposure_profile()
        self.assertEqual(fixed['command_values']['ExposureTime'],VALUES['ExposureTime']+27)
        self.assertEqual(fixed['values'],VALUES)
        self.assertEqual(fixed['tolerances']['ExposureTime'],1)
        self.session.begin_apply(fixed,1,False)
        self.frames(start=10)
        self.assertEqual(self.session.state,'confirm_preview')
        self.session.mark_saved()
        # Restart sends the adjusted command, checks the original desired actual.
        self.assertEqual(mod.validate_profile(fixed,CONTEXT)['ExposureTime'],VALUES['ExposureTime']+27)
        self.session.begin_apply(fixed,3,True)
        self.frames(start=40)
        self.assertTrue(self.session.can_capture)

    def test_varying_large_or_saved_exposure_error_never_autocorrects(self):
        for persisted,offsets in ((False,[27,26,27,26,27,26]),(False,[100]*6),(True,[27]*6)):
            self.session.begin_apply(profile(),0,persisted)
            for i,offset in enumerate(offsets):
                self.session.observe_fixed(dict(VALUES,ExposureTime=VALUES['ExposureTime']-offset,
                                                SensorTimestamp=i+1),.1*(i+1))
            self.assertIsNone(self.session.pending_exposure_correction)

    def test_failed_correction_is_not_repeated_or_saved(self):
        p=profile();p['exposure_rounding_adjustment']={'attempted':True}
        p['command_values']=dict(VALUES,ExposureTime=VALUES['ExposureTime']+27)
        self.session.begin_apply(p,0,False)
        for i in range(6):
            self.session.observe_fixed(dict(VALUES,ExposureTime=VALUES['ExposureTime']-27,
                                            SensorTimestamp=i+1),.1*(i+1))
        self.assertIsNone(self.session.pending_exposure_correction)
        self.session.observe_fixed(dict(VALUES,ExposureTime=10000,SensorTimestamp=7),16)
        self.assertEqual(self.session.state,'error')


if __name__=='__main__':unittest.main()
