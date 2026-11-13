"""Nine Sn10% images: descriptive time changes, background and ROI sensitivity."""
from pathlib import Path
from datetime import datetime
import sys,json,csv,hashlib
import numpy as np
import cv2
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import fontManager
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'notebooks/capture_repeatability'))
from analyze_repeatability import corners_and_bbox,roi
B=ROOT/'data/raw/Touma/FACsSnPbI3(Sn10mol%)_SnF2_0.1mol%/20261112';O=ROOT/'data/processed/20261112/03_image_time_series';O.mkdir(exist_ok=True);(O/'crops').mkdir(exist_ok=True)
fontManager.addfont('/mnt/c/Windows/Fonts/YuGothR.ttc');plt.rcParams['font.family']='Yu Gothic'
C=['#cf493f','#278d4f','#426dc9'];PATCHES=[(785,555),(1585,555),(1185,250),(1185,855)]
def save(fig,name):
 fig.savefig(O/(name+'.png'),dpi=150,bbox_inches='tight');fig.savefig(O/(name+'.pdf'),bbox_inches='tight');plt.close(fig)
def csvwrite(name,rs):
 with (O/name).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rs[0]));w.writeheader();w.writerows(rs)
rows=[];sensitivity=[];manifest=[];crops={};allmeta=[]
for minute in [5,10,15]:
 files=sorted((B/f'{minute}min').glob('*/*.jpg'));assert len(files)==3
 for index,p in enumerate(files):
  d=json.loads(p.with_suffix('.json').read_text());allmeta.append(d);a=np.array(Image.open(p).convert('RGB'));corners,bbox=corners_and_bbox(a)
  t=cv2.getPerspectiveTransform(corners,np.float32([[0,0],[255,0],[255,255],[0,255]]));crop=cv2.warpPerspective(a,t,(256,256));crops[minute,index]=crop
  mask=np.zeros(a.shape[:2],np.uint8);cv2.fillConvexPoly(mask,corners.astype(np.int32),1);bg=[]
  for x,y in PATCHES:
   assert not mask[y-20:y+20,x-20:x+20].any();bg.append(a[y-20:y+20,x-20:x+20].mean((0,1)))
  bg=np.mean(bg,0);fine=cv2.GaussianBlur(crop.astype(float),(0,0),.7)-cv2.GaussianBlur(crop.astype(float),(0,0),3)
  r={'anneal_min':minute,'label':p.parent.name,'filename':p.name,'captured_at':d['captured_at'],'verified':d['fixed_settings_verified']}
  if index==0:base_time=datetime.fromisoformat(d['captured_at'])
  r['hours_since_first_photo']=(datetime.fromisoformat(d['captured_at'])-base_time).total_seconds()/3600
  for margin in [.12,.18,.24]:
   pixels=roi(crop,margin).reshape(-1,3);fp=roi(fine,margin).reshape(-1,3);entry={'anneal_min':minute,'label':r['label'],'margin':margin}
   for j,c in enumerate('RGB'):
    entry['mean_'+c]=float(pixels[:,j].mean());entry['spatial_sd_'+c]=float(pixels[:,j].std());entry['fine_sd_'+c]=float(fp[:,j].std())
    if margin==.18:
     for prefix in ['mean_','spatial_sd_','fine_sd_']:r[prefix+c]=entry[prefix+c]
     r['paper_'+c]=float(bg[j])
   sensitivity.append(entry)
  if index==0:baseline=r.copy()
  for c in 'RGB':
   r['delta_'+c]=r['mean_'+c]-baseline['mean_'+c];r['bg_normalized_'+c]=r['mean_'+c]*baseline['paper_'+c]/r['paper_'+c];r['bg_normalized_delta_'+c]=r['bg_normalized_'+c]-baseline['mean_'+c]
  rows.append(r);Image.fromarray(crop).save(O/'crops'/f'{minute}min_{r["label"]}.png')
  manifest.append({'image':str(p.relative_to(ROOT)),'image_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'json_sha256':hashlib.sha256(p.with_suffix('.json').read_bytes()).hexdigest(),'corners':corners.tolist()})
assert all(d['fixed_settings_verified'] for d in allmeta)
assert len({d['fixed_settings']['profile_sha256'] for d in allmeta})==1
for k in ['ExposureTime','AnalogueGain','ColourGains','LensPosition']:assert all(d['settings'][k]==allmeta[0]['settings'][k] for d in allmeta)
csvwrite('metrics.csv',rows);csvwrite('roi_sensitivity.csv',sensitivity)
(O/'input_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
(O/'analysis_config.json').write_text(json.dumps({'primary_margin':.18,'sensitivity_margins':[.12,.18,.24],'ellipse_exclusion':False,'canonical_size':256,'registration':'substrate corners; not pixel precise','background_patch_centers':PATCHES,'patch_size':40,'fine_pattern_gaussian_sigmas':[.7,3],'time_axis':'actual hours since first image of each film; first age differs','code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},ensure_ascii=False,indent=2))
fig,axes=plt.subplots(3,3,figsize=(10,10))
for i,m in enumerate([5,10,15]):
 for j in range(3):
  r=rows[i*3+j];ax=axes[i,j];ax.imshow(crops[m,j]);ax.add_patch(plt.Rectangle((46,46),164,164,fill=False,color='lime',lw=1));ax.set_title(f'{m}分・公称{r["label"]}\n{r["captured_at"][11:19]}');ax.axis('off')
fig.suptitle('3膜の時系列：緑枠内を解析／楕円除外なし・色補正なし');fig.tight_layout();save(fig,'01_膜の時系列')
fig,axes=plt.subplots(3,3,figsize=(14,11))
for i,m in enumerate([5,10,15]):
 subset=rows[i*3:i*3+3];x=[r['hours_since_first_photo'] for r in subset]
 for j,(prefix,title) in enumerate([('delta_','最初の写真からの平均RGB変化'),('spatial_sd_','色むら：画素の標準偏差'),('fine_sd_','細かな模様：参考指標')]):
  ax=axes[i,j]
  for k,c in enumerate('RGB'):ax.plot(x,[r[prefix+c] for r in subset],'o-',color=C[k],label=c)
  ax.set_title(f'{m}分：{title}');ax.set_xlabel('各膜の最初の写真からの実時間 (h)');ax.set_ylabel('JPEG RGB単位');ax.grid(alpha=.25);ax.legend()
fig.suptitle('各条件1膜・各時点1枚／誤差棒なし／5・10分は1h開始、15分は0h開始');fig.tight_layout(rect=[0,0,1,.96]);save(fig,'02_色と模様の経時変化')
fig,axes=plt.subplots(3,2,figsize=(12,10))
for i,m in enumerate([5,10,15]):
 subset=rows[i*3:i*3+3];x=[r['hours_since_first_photo'] for r in subset]
 for k,c in enumerate('RGB'):
  axes[i,0].plot(x,[r['paper_'+c] for r in subset],'o-',color=C[k],label=c)
  axes[i,1].plot(x,[r['delta_'+c] for r in subset],'o-',color=C[k],label=c+' 補正前')
  axes[i,1].plot(x,[r['bg_normalized_delta_'+c] for r in subset],'s--',color=C[k],label=c+' 背景で簡易補正')
 for j,ax in enumerate(axes[i]):ax.set_title(f'{m}分：'+['背景の平均RGB','平均色変化への背景の影響'][j]);ax.set_xlabel('最初の写真からの実時間 (h)');ax.set_ylabel('RGB単位');ax.grid(alpha=.25);ax.legend(fontsize=8,ncol=2)
fig.suptitle('背景補正は参考：JPEGの成分別比率補正であり、真の色の校正ではない');fig.tight_layout(rect=[0,0,1,.96]);save(fig,'03_背景の変動と影響')
for m in [5,10,15]:
 first,last=[r for r in rows if r['anneal_min']==m][::2]
 print(m,'actual span',last['hours_since_first_photo'],'delta',[round(last['delta_'+c],2) for c in 'RGB'],'bgdelta',[round(last['bg_normalized_delta_'+c],2) for c in 'RGB'],'sd first/last',[[round(r['spatial_sd_'+c],2) for c in 'RGB'] for r in [first,last]])
