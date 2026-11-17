from pathlib import Path
import sys,json
import numpy as np,cv2
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
sys.path.insert(0,'notebooks/capture_repeatability')
from analyze_repeatability import corners_and_bbox
B=Path('data/raw/Touma/FACsSnPbI3(Sn10mol%)_SnF2_0.1mol%/20261112');O=Path('results/20261112/08_capture_orientation_1941');O.mkdir(exist_ok=True)
old=[next((B/f'{m}min/1h').glob('*.jpg')) for m in [5,10,15]]
new=[next(Path('data/raw').rglob(n+'.jpg')) for n in ['photo_20261112_194141_190983','photo_20261112_194238_111697','photo_20261112_194343_578299']]
def crop(p):
 a=np.array(Image.open(p));c,_=corners_and_bbox(a);return cv2.warpPerspective(a,cv2.getPerspectiveTransform(c,np.float32([[0,0],[255,0],[255,255],[0,255]])),(256,256))
def f(a):
 g=cv2.cvtColor(a,cv2.COLOR_RGB2GRAY).astype(float);return (cv2.GaussianBlur(g,(0,0),2)-cv2.GaussianBlur(g,(0,0),10))[35:-35,35:-35].ravel()
a=[crop(p) for p in old];b=[crop(p) for p in new];scores=[]
for i,n in enumerate(b):
 for j,r in enumerate(a):
  matches=[]
  for flip in [False,True]:
   for k in range(4):matches.append((float(np.corrcoef(f(r),f(np.rot90(np.fliplr(n) if flip else n,k)))[0,1]),flip,k*90))
  best=max(matches);scores.append({'new':new[i].name,'reference_anneal_min':[5,10,15][j],'correlation':best[0],'mirror':best[1],'ccw_rotation_deg':best[2]})
fig,axes=plt.subplots(3,2,figsize=(8,12))
for i in range(3):
 for j,img in enumerate([a[i],b[i]]):axes[i,j].imshow(img);axes[i,j].set_title(f'{[5,10,15][i]}min '+('Reference 1h' if j==0 else new[i].stem[15:21]));axes[i,j].axis('off')
fig.tight_layout();fig.savefig(O/'01_膜の対応確認.png',dpi=140)
(O/'identity_scores.json').write_text(json.dumps(scores,indent=2));print(json.dumps(scores,indent=2))
for p in new:
 d=json.loads(p.with_suffix('.json').read_text());print(p.name,d['fixed_settings_verified'])
