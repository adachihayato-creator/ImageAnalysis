from pathlib import Path
import sys,csv,json
import numpy as np,cv2
from PIL import Image
sys.path.insert(0,'notebooks/capture_repeatability')
from analyze_repeatability import corners_and_bbox
P=Path('results/20261112/14_integrated_reanalysis');O=Path('results/20261113/01_xrd_image_features');manifest=json.loads((P/'input_manifest.json').read_text());metrics=list(csv.DictReader((P/'image_metrics.csv').open(encoding='utf-8-sig')));sources={Path(e['path']).name:Path(e['path']) for e in manifest if e['kind']=='photo'}
ref=sources['photo_20261112_163701_835677.jpg'];a=np.array(Image.open(ref));FIT=[(785,555),(1585,555),(1185,250),(1185,855)];patch=lambda a:np.mean([a[y-20:y+20,x-20:x+20].mean((0,1)) for x,y in FIT],0);bgref=patch(a);rows=[];yy,xx=np.mgrid[:256,:256];mask=(xx>=46)&(xx<210)&(yy>=46)&(yy<210)
for age in ['1h','3h','4h']:
 for m in [5,10,15]:
  r=next(r for r in metrics if r['anneal_min']==str(m) and r['label'].replace('暫定','')==age);p=sources[r['filename']];a=np.array(Image.open(p));corners,_=corners_and_bbox(a);c=cv2.warpPerspective(a,cv2.getPerspectiveTransform(corners,np.float32([[0,0],[255,0],[255,255],[0,255]])),(256,256)).astype(float)*bgref/patch(a);g=c[:,:,0]*.2126+c[:,:,1]*.7152+c[:,:,2]*.0722;s=cv2.GaussianBlur(g,(0,0),8);contrast=(g-s)/np.maximum(s,1);n,l,st,ct=cv2.connectedComponentsWithStats(((contrast>.1)&mask).astype(np.uint8),8);valid=np.flatnonzero(st[1:,cv2.CC_STAT_AREA]>=3)+1;kept=np.isin(l,valid)&mask
  rows.append({'anneal_min':m,'nominal_image_age':age,'filename':p.name,'bright_area_percent':float(kept.sum()/mask.sum()*100),'note':'1hのみ同時点XRDあり。3h/4hは同じ膜の画像で特徴持続を確認、独立膜ではない'})
with (O/'same_film_followup.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
print(rows)
