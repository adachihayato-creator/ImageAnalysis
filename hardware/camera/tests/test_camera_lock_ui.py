"""Exercise the actual UI class with fake widgets/camera; no Pi dependencies."""
import ast
import importlib.util
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
import time
from datetime import datetime

spec=importlib.util.spec_from_file_location('fixed_settings',Path(__file__).resolve().parents[1]/'fixed_settings.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
spec2=importlib.util.spec_from_file_location('position_guide',Path(__file__).resolve().parents[1]/'position_guide.py')
guide_mod=importlib.util.module_from_spec(spec2);spec2.loader.exec_module(guide_mod)


class Widget:
    def __init__(self,*args,**kwargs):self.enabled=True
    def pack(self,*args,**kwargs):pass
    def pack_forget(self):pass
    def configure(self,*args,**kwargs):pass
    def set_enabled(self,value):self.enabled=value
    def set_text(self,value):pass
    def bind(self,*args):pass
    def winfo_width(self):return 800
    def winfo_height(self):return 600


class FakeFrame:
    shape=(1296,2304,3)
    def copy(self):return self


class FakeImage:
    def crop(self,view):return self
    def resize(self,size):return self


class FakeCamera:
    camera_properties={'Model':'imx708'}
    camera_controls={k:(0,100,0) for k in ('AeEnable','AwbEnable','AfMode','AfTrigger',*mod.KEYS)}
    camera_controls['ExposureTime']=(100,1000000,0)
    def __init__(self):
        self.events=[];self.stamp=0
        self.metadata={'ExposureTime':13066,'AnalogueGain':1.122807,
                       'ColourGains':[2.19,2.0],'LensPosition':9.5}
    @staticmethod
    def global_camera_info():return [{'Id':'camera-test'}]
    def create_preview_configuration(self,**kwargs):return kwargs
    def configure(self,config):self.events.append(('configure',config))
    def set_controls(self,values):self.events.append(('controls',values))
    def start(self):self.events.append(('start',None))
    def capture_request(self):
        self.stamp+=1
        request=Mock()
        request.make_array.return_value=FakeFrame()
        request.get_metadata.return_value=dict(self.metadata,SensorTimestamp=self.stamp)
        return request


class CameraUITests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup)
        self.path=Path(self.directory.name)/'settings.json'
        self.context={'model':'imx708','camera_id':'camera-test','capture_size':[2304,1296],'format':'RGB888'}
        self.profile={'schema_version':1,'context':self.context,'values':FakeCamera().metadata,
                      'tolerances':dict(mod.TOLERANCES)}
        tree=ast.parse((Path(__file__).resolve().parents[1]/'camera_app.py').read_text())
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='CameraApp')
        self.namespace=dict(tk=SimpleNamespace(Frame=Widget,Label=Widget),RoundedButton=Widget,
                            BG='white',TEXT='black',RED='red',MAIN='blue',RED_ACTIVE='red',FONT='sans',SUBTEXT='gray',
                            CAPTURE_SIZE=(2304,1296),SETTINGS_FILE=self.path,Picamera2=FakeCamera,
                            GUIDE_FILE=Path(self.directory.name)/'position_guide.json',
                            GUIDE_CANDIDATE=Path(self.directory.name)/'candidate.json',
                            load_guide=guide_mod.load_guide,make_guide=guide_mod.make_guide,
                            guide_record=guide_mod.guide_record,viewport=guide_mod.viewport,
                            display_mapping=guide_mod.display_mapping,
                            widget_to_normalized=guide_mod.widget_to_normalized,
                            overlay_preview=lambda img,*args:img,
                            translate_corners=guide_mod.translate_corners,
                            LockSession=mod.LockSession,load_profile=mod.load_profile,validate_profile=mod.validate_profile,
                            save_profile=mod.save_profile,json_value=lambda value:value,datetime=datetime,
                            messagebox=SimpleNamespace(askyesno=lambda *a,**k:True),
                            software_versions=lambda:{},time=time,
                            controls=SimpleNamespace(AfModeEnum=SimpleNamespace(Manual=0,Auto=1),
                                                     AfTriggerEnum=SimpleNamespace(Start=0),
                                                     AfStateEnum=SimpleNamespace(Focused=2)),
                            cv2=SimpleNamespace(resize=lambda a,b:a,cvtColor=lambda a,b:a,COLOR_BGR2RGB=1),
                            Image=SimpleNamespace(fromarray=lambda a:FakeImage()),ImageTk=SimpleNamespace(PhotoImage=lambda a:a))
        exec(compile(ast.Module(body=[cls],type_ignores=[]),'camera_app.py','exec'),self.namespace)

    def start(self):return self.namespace['CameraApp'](Mock())

    def test_startup_applies_saved_manual_values_before_start_and_waits_for_frames(self):
        mod.save_profile(self.path,self.profile)
        app=self.start()
        controls_event=next((i,v) for i,(name,v) in enumerate(app.picam2.events) if name=='controls')
        start=next(i for i,(name,v) in enumerate(app.picam2.events) if name=='start')
        self.assertLess(controls_event[0],start)
        self.assertFalse(controls_event[1]['AeEnable'])
        self.assertFalse(controls_event[1]['AwbEnable'])
        self.assertEqual(controls_event[1]['AfMode'],0)
        self.assertFalse(app.capture_button.enabled)
        for _ in range(4):app.update_frame()
        self.assertTrue(app.capture_button.enabled)
        app.picam2.metadata['ExposureTime']=15000
        app.update_frame()
        self.assertFalse(app.capture_button.enabled)
        self.assertEqual(app.lock.state,'error')

    def test_missing_profile_never_creates_default_values_or_enables_capture(self):
        app=self.start()
        self.assertEqual(app.lock.state,'unconfigured')
        self.assertFalse(app.capture_button.enabled)
        self.assertFalse(self.path.exists())

    def test_corrupt_profile_is_visible_error_and_never_falls_back_to_auto_capture(self):
        self.path.write_text('broken')
        app=self.start()
        self.assertEqual(app.lock.state,'error')
        self.assertFalse(app.capture_button.enabled)

    def test_touch_workflow_calibrate_freeze_confirm_save_then_restart(self):
        clock=[0.0]
        self.namespace['time']=SimpleNamespace(monotonic=lambda:clock[0])
        app=self.start()
        app.picam2.metadata['AfState']=2
        app.calibrate()
        for _ in range(16):
            clock[0]+=.4
            app.update_frame()
        self.assertEqual(app.lock.state,'confirm_preview')
        self.assertFalse(app.capture_button.enabled)
        app.save_settings()
        self.assertTrue(self.path.exists())
        self.assertTrue(app.capture_button.enabled)
        app2=self.start()
        for _ in range(4):
            clock[0]+=.4
            app2.update_frame()
        self.assertTrue(app2.capture_button.enabled)
        self.assertEqual(app2.lock.profile['values'],app.lock.profile['values'])

    def test_guide_registration_persists_without_changing_camera_settings(self):
        mod.save_profile(self.path,self.profile)
        app=self.start()
        original_settings=self.path.read_bytes()
        controls_before=list(app.picam2.events)
        candidate=guide_mod.make_guide([[.4,.3],[.6,.3],[.6,.5],[.4,.5]],self.context,{'method':'test'})
        app.persist_guide(candidate)
        self.assertTrue(app.guide_registered)
        self.assertEqual(self.path.read_bytes(),original_settings)
        self.assertEqual(app.picam2.events,controls_before)
        app2=self.start()
        self.assertEqual(app2.guide['corners_normalized'],candidate['corners_normalized'])
        self.assertTrue(app2.guide_registered)

    def test_editing_guide_blocks_capture_and_cancel_restores_it(self):
        mod.save_profile(self.path,self.profile)
        app=self.start()
        for _ in range(4):app.update_frame()
        self.assertTrue(app.capture_button.enabled)
        app.begin_guide_edit()
        self.assertFalse(app.capture_button.enabled)
        app.update_frame()
        self.assertFalse(app.capture_button.enabled)
        app.cancel_guide_edit()
        self.assertTrue(app.capture_button.enabled)

    def test_arrow_draft_cancel_preserves_guide_and_camera_settings(self):
        mod.save_profile(self.path,self.profile)
        app=self.start()
        profile=guide_mod.make_guide([[.4,.3],[.6,.3],[.6,.5],[.4,.5]],self.context,{})
        app.persist_guide(profile)
        for _ in range(4):app.update_frame()
        guide_path=self.namespace['GUIDE_FILE'];guide_before=guide_path.read_bytes()
        camera_before=self.path.read_bytes();events_before=list(app.picam2.events)
        app.guide_zoom=True
        app.begin_guide_move()
        self.assertFalse(app.capture_button.enabled)
        app.nudge_guide(1,0)
        app.toggle_move_step()
        app.nudge_guide(0,-1)
        self.assertEqual(app.move_offset,[20.0,-1.0])
        self.assertEqual(guide_path.read_bytes(),guide_before)
        self.assertEqual(app.guide,profile)
        # View stays full-frame while translating so the arrow movement is visible.
        self.assertEqual(app.move_view,(0,0,2304,1296))
        app.cancel_guide_edit()
        self.assertTrue(app.guide_zoom)
        self.assertTrue(app.capture_button.enabled)
        self.assertEqual(guide_path.read_bytes(),guide_before)
        self.assertEqual(self.path.read_bytes(),camera_before)
        self.assertEqual(app.picam2.events,events_before)

    def test_arrow_save_restart_preserves_shape_and_only_updates_position_file(self):
        mod.save_profile(self.path,self.profile)
        app=self.start()
        points=[[.4,.3],[.6,.3],[.6,.5],[.4,.5]]
        app.persist_guide(guide_mod.make_guide(points,self.context,{}))
        camera_before=self.path.read_bytes();controls_before=list(app.picam2.events)
        app.begin_guide_move();app.nudge_guide(1,0);app.nudge_guide(0,1)
        app.save_moved_guide()
        self.assertFalse(app.editing_guide)
        self.assertEqual(self.path.read_bytes(),camera_before)
        self.assertEqual(app.picam2.events,controls_before)
        self.assertEqual(app.guide['source']['translation_pixels'],[20.0,20.0])
        moved=app.guide['corners_normalized']
        for before,after in zip(points,moved):
            self.assertAlmostEqual((after[0]-before[0])*2303,20)
            self.assertAlmostEqual((after[1]-before[1])*1295,20)
        app2=self.start()
        self.assertEqual(app2.guide['corners_normalized'],moved)


if __name__=='__main__':unittest.main()
