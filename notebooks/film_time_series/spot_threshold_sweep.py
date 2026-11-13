"""Threshold 5..50% sweep for nominal1h three films, same full-frame local contrast definition."""
from pathlib import Path
import csv,json,sys,hashlib
import numpy as np,cv2
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import fontManager
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'notebooks/capture_repeatability'))
from analyze_repeatability import corners_and_bbox
B=ROOT/'data/raw/Touma/FACsSnPbI3(Sn10mol%)_SnF2_0.1mol%/20261112';O=ROOT/'data/processed/20261113/05_threshold_5to50';O.mkdir(parents=True,exist_ok=True)
FIT=[(785,555),(1585,555),(1185,250),(1185,855)];thresholds=list(range(5,51,5));rows=[];manifest=[];crops={};masks={};yy,xx=np.mgrid[:256,:256];edge=(xx<13)|(xx>=243)|(yy<13)|(yy>=243);central=(xx>=46)&(xx<210)&(yy>=46)&(yy<210)
def get(p):
 a=np.array(Image.open(p).convert('RGB'));corners,_=corners_and_bbox(a);raw=cv2.warpPerspective(a,cv2.getPerspectiveTransform(corners,np.float32([[0,0],[255,0],[255,255],[0,255]])),(256,256)).astype(float);bg=np.mean([a[y-20:y+20,x-20:x+20].mean((0,1)) for x,y in FIT],0);return raw,bg,corners
ref=next((B/'5min/1h').glob('*.jpg'));_,bgref,_=get(ref)
for m in [5,10,15]:
 p=next((B/f'{m}min/1h').glob('*.jpg'));raw,bg,corners=get(p)
 for f,kind in [(p,'photo'),(p.with_suffix('.json'),'metadata')]:manifest.append({'path':str(f.relative_to(ROOT)),'kind':kind,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()})
 for corrected in [False,True]:
  rgb=raw*bgref/bg if corrected else raw;gray=rgb[:,:,0]*.2126+rgb[:,:,1]*.7152+rgb[:,:,2]*.0722
  for sigma in [6.,8.,12.]:
   smooth=cv2.GaussianBlur(gray,(0,0),sigma);contrast=(gray-smooth)/np.maximum(smooth,1);previous=None
   for percent in thresholds:
    binary=(contrast>percent/100).astype(np.uint8);_,labels,stats,_=cv2.connectedComponentsWithStats(binary,8);valid=np.flatnonzero(stats[1:,cv2.CC_STAT_AREA]>=3)+1;spots=np.isin(labels,valid);count=int(spots.sum())
    if previous is not None:assert not np.any(spots&~previous)
    previous=spots
    r={'anneal_min':m,'elapsed_label':'1h','corrected':corrected,'sigma_px':sigma,'threshold_percent':percent,'bright_pixels':count,'full_area_percent':float(spots.mean()*100),'central18_area_percent':float(spots[central].mean()*100),'edge5_area_percent':float(spots[edge].mean()*100),'inside_edge5_area_percent':float(spots[~edge].mean()*100),'edge_share_of_detected_pixels_percent':float(spots[edge].sum()/count*100) if count else None,'component_count':len(valid)};rows.append(r)
    if corrected and sigma==8:
     masks[m,percent]=spots;crops[m]=np.rint(np.clip(rgb,0,255)).astype(np.uint8)
primary=[r for r in rows if r['corrected'] and r['sigma_px']==8]
ranks=[]
for percent in thresholds:
 rr=[r for r in primary if r['threshold_percent']==percent];rank=sorted(rr,key=lambda r:-r['full_area_percent']);groups=[]
 for corrected in [False,True]:
  for sigma in [6.,8.,12.]:
   vv=[r for r in rows if r['threshold_percent']==percent and r['corrected']==corrected and r['sigma_px']==sigma];maxv=max(r['full_area_percent'] for r in vv);winners=[r['anneal_min'] for r in vv if r['full_area_percent']==maxv];groups.append(winners)
 ranks.append({'threshold_percent':percent,'primary_order':' > '.join(str(r['anneal_min']) for r in rank),'15min_largest_settings':sum(v==[15] for v in groups),'settings':len(groups)})
def write(name,rs):
 with (O/name).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rs[0]));w.writeheader();w.writerows(rs)
write('all_threshold_metrics.csv',rows);write('primary_threshold_metrics.csv',primary);write('rank_by_threshold.csv',ranks)
(O/'input_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2));(O/'analysis_config.json').write_text(json.dumps({'independent_films':3,'nominal_age':'1h','perimeter_exclusion':False,'ellipse_exclusion':False,'thresholds_percent':thresholds,'primary_sigma_px':8,'sigma_sensitivity':[6,8,12],'correction_sensitivity':[False,True],'minimum_component_pixels':3,'common_bg_reference':str(ref.relative_to(ROOT)),'fit_centers':FIT,'intensity':'0.2126R+0.7152G+0.0722B in JPEG RGB units','contrast':'(I-Gaussian(I))/max(Gaussian(I),1)','area':'whole65536 pixels; secondary region densities use same full-frame mask','edge5':'13pixel wide outer band, sensitivity region not physically identified glass/reflection mask','uncertainty':'sensitivity bands are processing choices, not statistical confidence intervals','code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},ensure_ascii=False,indent=2))
print('PRIMARY',primary);print('RANK',ranks)
fontManager.addfont('/mnt/c/Windows/Fonts/YuGothR.ttc');plt.rcParams.update({'font.family':'Yu Gothic','font.size':13});COL=['#777777','#287bab','#dc8a26']
def save(fig,name):fig.savefig(O/(name+'.png'),dpi=150,bbox_inches='tight');fig.savefig(O/(name+'.pdf'),bbox_inches='tight');plt.close(fig)
fig,axes=plt.subplots(1,2,figsize=(13,5))
for ax,key,title in [(axes[0],'full_area_percent','基板全体'),(axes[1],'inside_edge5_area_percent','最外周約5%帯の内側（参考）')]:
 for m,col in zip([5,10,15],COL):
  rr=[r for r in primary if r['anneal_min']==m];ax.plot(thresholds,[r[key] for r in rr],'o-',color=col,label=f'{m}分膜')
  samples=np.array([[r[key] for r in rows if r['anneal_min']==m and r['corrected'] and r['sigma_px']==sigma] for sigma in [6.,8.,12.] ]);ax.fill_between(thresholds,samples.min(0),samples.max(0),color=col,alpha=.12)
 ax.set_title(title);ax.set_xticks(thresholds);ax.set_xlabel('周囲より明るいとするしきい値 (%)');ax.set_ylabel('斑点候補の面積 (%)');ax.grid(alpha=.2);ax.legend()
fig.suptitle('しきい値5〜50%：実線はぼかしσ8px／帯はσ6〜12pxの範囲');fig.tight_layout(rect=[0,0,1,.92]);save(fig,'01_しきい値と面積の曲線')
fig,axes=plt.subplots(3,4,figsize=(12,10))
for i,m in enumerate([5,10,15]):
 for j,t in enumerate([10,20,30,50]):
  overlay=crops[m].copy();overlay[masks[m,t]]=[255,220,0];ax=axes[i,j];ax.imshow(overlay);rr=next(r for r in primary if r['anneal_min']==m and r['threshold_percent']==t);ax.set_title(f'{m}分膜・閾値{t}%\n候補面積{rr["full_area_percent"]:.2f}%');ax.axis('off')
fig.suptitle('黄色＝抽出領域／高いしきい値では特に明るい部分だけが残る');fig.tight_layout(rect=[0,0,1,.95]);save(fig,'02_10_20_30_50パーセントの抽出')
