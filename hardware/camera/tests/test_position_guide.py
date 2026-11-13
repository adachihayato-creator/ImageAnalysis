import importlib.util
from pathlib import Path
import tempfile
import json
import unittest

spec=importlib.util.spec_from_file_location('position_guide',Path(__file__).resolve().parents[1]/'position_guide.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
CONTEXT={'model':'imx708','camera_id':'test','capture_size':[2304,1296],'format':'RGB888'}
POINTS=[[.4,.3],[.6,.3],[.6,.5],[.4,.5]]


class GeometryTests(unittest.TestCase):
    def test_translation_keeps_every_edge_and_clamps_whole_frame(self):
        points=[[.01,.1],[.2,.12],[.22,.4],[.02,.38]]
        moved,delta=mod.translate_corners(points,-100,50,(2304,1296))
        self.assertAlmostEqual(min(p[0] for p in moved),0)
        self.assertAlmostEqual(delta[0],-.01*2303)
        self.assertAlmostEqual(delta[1],50)
        for i in range(4):
            for j in range(2):
                self.assertAlmostEqual(moved[(i+1)%4][j]-moved[i][j],points[(i+1)%4][j]-points[i][j])
        again,actual=mod.translate_corners(moved,-20,0,(2304,1296))
        self.assertAlmostEqual(actual[0],0)
        self.assertEqual(again,moved)

    def test_repeated_fine_moves_match_coarse_move(self):
        fine=POINTS
        for _ in range(20):fine,_=mod.translate_corners(fine,1,0,(2304,1296))
        coarse,_=mod.translate_corners(POINTS,20,0,(2304,1296))
        for a,b in zip(fine,coarse):
            for x,y in zip(a,b):self.assertAlmostEqual(x,y,places=12)

    def test_mapping_round_trip_full_and_zoom_at_different_screen_sizes(self):
        for size in ((800,480),(480,320),(1200,500)):
            for zoom in (False,True):
                view=mod.viewport((2304,1296),POINTS,zoom)
                mapping=mod.display_mapping((2304,1296),size,view)
                for point in POINTS:
                    x,y=mod.normalized_to_display(point,mapping);ox,oy=mapping['offset']
                    normalized=mod.widget_to_normalized((x+ox,y+oy),mapping)
                    for actual,expected in zip(normalized,point):self.assertAlmostEqual(actual,expected,places=10)

    def test_letterbox_taps_ignored(self):
        mapping=mod.display_mapping((2304,1296),(800,800),(0,0,2304,1296))
        self.assertIsNone(mod.widget_to_normalized((400,0),mapping))

    def test_invalid_order_degenerate_outside_and_context_rejected(self):
        for points in (POINTS[::-1],[[0,0]]*4,[[2,0],[1,0],[1,1],[0,1]]):
            with self.assertRaises(ValueError):mod.make_guide(points,CONTEXT,{})
        profile=mod.make_guide(POINTS,CONTEXT,{})
        with self.assertRaises(ValueError):mod.validate_guide(profile,dict(CONTEXT,model='different'))

    def test_saved_profile_roundtrip_and_no_automatic_alignment_claim(self):
        profile=mod.make_guide(POINTS,CONTEXT,{})
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'guide.json';path.write_text(json.dumps(profile))
            loaded=mod.load_guide(path,CONTEXT)
        self.assertEqual(loaded,profile)
        record=mod.guide_record(loaded,True)
        self.assertFalse(record['alignment_verified'])
        self.assertEqual(record['state'],'registered')

    def test_overlay_uses_a_copy(self):
        # Pillow is needed on the Pi; keep geometry/UI tests runnable without it.
        try:
            from PIL import Image
        except ImportError:
            self.skipTest('Pillow unavailable in this interpreter')
        image=Image.new('RGB',(800,450),'black')
        before=image.tobytes();mapping=mod.display_mapping((2304,1296),(800,450),(0,0,2304,1296))
        output=mod.overlay_preview(image,mod.make_guide(POINTS,CONTEXT,{}),mapping)
        self.assertEqual(image.tobytes(),before)
        self.assertNotEqual(output.tobytes(),before)


if __name__=='__main__':unittest.main()
