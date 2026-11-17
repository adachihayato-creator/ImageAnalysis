from pathlib import Path
import sys,json
import numpy as np,cv2
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
sys.path.insert(0,'notebooks/capture_repeatability')
from analyze_repeatability import corners_and_bbox
out=Path('results/20261112/04_orientation_check');out.mkdir(exist_ok=True)
paths=[Path('data/raw/Touma/FACsSnPbI3(Sn10mol%)_SnF2_0.1mol%/20261112/5min/1h/photo_20261112_163701_835677.jpg'),Path('data/raw/試行錯誤写真/photo_20261112_185622_645764.jpg')]
crops=[]
for p in paths:
 a=np.array(Image.open(p));corners,_=corners_and_bbox(a);crops.append(cv2.warpPerspective(a,cv2.getPerspectiveTransform(corners,np.float32([[0,0],[255,0],[255,255],[0,255]])),(256,256)))
def feature(a):
 g=cv2.cvtColor(a,cv2.COLOR_RGB2GRAY).astype(float);return cv2.GaussianBlur(g,(0,0),2)-cv2.GaussianBlur(g,(0,0),10)
x=feature(crops[0])[35:-35,35:-35].ravel();scores=[]
for flip in [False,True]:
 for k in range(4):
  candidate=np.rot90(np.fliplr(crops[1]) if flip else crops[1],k);y=feature(candidate)[35:-35,35:-35].ravel();scores.append({'mirror':flip,'ccw_rotation_deg':k*90,'correlation':float(np.corrcoef(x,y)[0,1])})
print(json.dumps(sorted(scores,key=lambda r:-r['correlation']),indent=2))
fig,axes=plt.subplots(1,2,figsize=(9,4.5))
for ax,a,label in zip(axes,crops,['Previous: 16:37','Current: 18:56']):ax.imshow(a);ax.set_title(label);ax.axis('off')
fig.tight_layout();fig.savefig(out/'comparison.png',dpi=160)
(out/'orientation_scores.json').write_text(json.dumps(scores,indent=2))
