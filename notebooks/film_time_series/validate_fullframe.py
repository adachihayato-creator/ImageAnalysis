"""Validate full-frame vs central ROI descriptively, using three films and five technical repeats."""
from pathlib import Path
import sys,csv,json,hashlib
import numpy as np,cv2
from PIL import Image
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'notebooks/capture_repeatability'))
from analyze_repeatability import corners_and_bbox
B=ROOT/'data/raw/Touma/FACsSnPbI3(Sn10mol%)_SnF2_0.1mol%/20261112';O=ROOT/'results/20261113/03_fullframe_validation';O.mkdir(parents=True,exist_ok=True)
FIT=[(785,555),(1585,555),(1185,250),(1185,855)];yy,xx=np.mgrid[:256,:256];central=(xx>=46)&(xx<210)&(yy>=46)&(yy<210);inner5=(xx>=13)&(xx<243)&(yy>=13)&(yy<243)
MASKS={'full':np.ones((256,256),bool),'central18':central,'outer18':~central,'edge5':~inner5,'outer18_without_edge5':(~central)&inner5,'inside_edge5':inner5};manifest=[];primary=[];sensitivity=[];repeat=[];imagecache={}
def rec(p,kind):manifest.append({'path':str(p.relative_to(ROOT)),'kind':kind,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
def get(p):
 a=np.array(Image.open(p).convert('RGB'));c,_=corners_and_bbox(a);crop=cv2.warpPerspective(a,cv2.getPerspectiveTransform(c,np.float32([[0,0],[255,0],[255,255],[0,255]])),(256,256)).astype(float);bg=np.mean([a[y-20:y+20,x-20:x+20].mean((0,1)) for x,y in FIT],0);return crop,bg
ref=next((B/'5min/1h').glob('*.jpg'));_,REFBG=get(ref)
def measure(raw,bg,corrected,sigma,threshold,independent_masks=False):
 rgb=raw*REFBG/bg if corrected else raw;gray=rgb[:,:,0]*.2126+rgb[:,:,1]*.7152+rgb[:,:,2]*.0722;sm=cv2.GaussianBlur(gray,(0,0),sigma);contrast=(gray-sm)/np.maximum(sm,1);fine=cv2.GaussianBlur(gray,(0,0),.7)-cv2.GaussianBlur(gray,(0,0),3);binary=(contrast>threshold).astype(np.uint8)
 def components(b):
  _,lab,stats,_=cv2.connectedComponentsWithStats(b.astype(np.uint8),8);valid=np.flatnonzero(stats[1:,cv2.CC_STAT_AREA]>=3)+1;return np.isin(lab,valid)
 spots=components(binary);rs=[]
 for name,mask in MASKS.items():
  kept=components(binary&mask) if independent_masks else spots;count=int((kept&mask).sum());vals=gray[mask];rs.append({'region':name,'area_pixels':int(mask.sum()),'bright_pixels':count,'bright_area_percent':count/mask.sum()*100,'gray_mean':float(vals.mean()),'gray_spatial_cv':float(vals.std()/vals.mean()),'relative_fine_sd':float(fine[mask].std()/vals.mean())})
 return rs,spots
for m in [5,10,15]:
 p=next((B/f'{m}min/1h').glob('*.jpg'));raw,bg=get(p);rec(p,'film1h');rec(p.with_suffix('.json'),'film_metadata');imagecache[m]=(raw,bg)
 # Main masks segmented separately to match previous published comparisons.
 rs,spots=measure(raw,bg,True,8,.1,True);primary.extend({'anneal_min':m,**r} for r in rs);np.save(O/f'{m}min_spots.npy',spots)
 # Partition full-frame detections; a single definition ensures additive pixel accounting.
 part,_=measure(raw,bg,True,8,.1,False)
 for r in part:r['anneal_min']=m
 # persist partition separately below
 if m==5:partition=[]
 partition.extend(part)
 for corrected in [False,True]:
  for sigma in [6.,8.,12.]:
   for threshold in [.05,.1,.15]:
    rs,_=measure(raw,bg,corrected,sigma,threshold,True);sensitivity.extend({'anneal_min':m,'corrected':corrected,'sigma':sigma,'threshold':threshold,**r} for r in rs)
repeats=json.loads((ROOT/'results/20261112/16_reanalysis_with_repeats/input_manifest.json').read_text());files=[ROOT/e['path'] for e in repeats if e['kind']=='repeat_photo'];assert len(files)==5
for i,p in enumerate(files):
 raw,bg=get(p);rec(p,'repeat10min');rec(p.with_suffix('.json'),'repeat_metadata');rs,_=measure(raw,bg,True,8,.1,True);repeat.extend({'capture_index':i+1,'filename':p.name,**r} for r in rs)
summary=[]
for name in MASKS:
 rr=[r for r in repeat if r['region']==name];r={'region':name,'n_repeat_images':len(rr)}
 for key in ['bright_area_percent','gray_mean','gray_spatial_cv','relative_fine_sd']:
  a=np.array([v[key] for v in rr]);r[key+'_mean']=float(a.mean());r[key+'_sd']=float(a.std(ddof=1));r[key+'_range']=float(np.ptp(a))
 full=[r for r in primary if r['region']==name];v15=next(r['bright_area_percent'] for r in full if r['anneal_min']==15);others=[r['bright_area_percent'] for r in full if r['anneal_min']!=15];r['15min_minus_larger_other_percentage_points']=v15-max(others);r['contrast_over_10min_repeat_sd_descriptive']=r['15min_minus_larger_other_percentage_points']/r['bright_area_percent_sd'] if r['bright_area_percent_sd']>0 else None;summary.append(r)
rank=[]
for name in MASKS:
 rs=[r for r in sensitivity if r['region']==name];groups={}
 for r in rs:groups.setdefault((r['corrected'],r['sigma'],r['threshold']),[]).append(r)
 wins=sum(next(r['bright_area_percent'] for r in g if r['anneal_min']==15)>max(r['bright_area_percent'] for r in g if r['anneal_min']!=15) for g in groups.values());rank.append({'region':name,'settings':len(groups),'15min_largest_count':wins})
def write(name,rs):
 with (O/name).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rs[0]));w.writeheader();w.writerows(rs)
for name,rs in [('primary_regions.csv',primary),('partition_of_full_detections.csv',partition),('region_sensitivity.csv',sensitivity),('repeat_region_metrics.csv',repeat),('repeatability_summary.csv',summary),('ranking_by_region.csv',rank)]:write(name,rs)
(O/'input_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2));(O/'analysis_config.json').write_text(json.dumps({'common_reference':str(ref.relative_to(ROOT)),'primary_sigma':8,'primary_threshold':.1,'minimum_component_area':3,'canonical_size':256,'masks_pixels':{k:int(v.sum()) for k,v in MASKS.items()},'central_each_edge_fraction':46/256,'edge5_each_edge_fraction':13/256,'segmentation':'primary: connected components separately within each mask; partition: full spots partitioned without resegmentation','inference':'3 independent films, high peak1 film;5 technical repeats of10min only; no causal or equivalence claim','code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},ensure_ascii=False,indent=2))
print('SUMMARY',json.dumps(summary,ensure_ascii=False));print('RANK',rank);print('PARTITION',partition)
# Readable figures.
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import fontManager
fontManager.addfont('/mnt/c/Windows/Fonts/YuGothR.ttc');plt.rcParams.update({'font.family':'Yu Gothic','font.size':13})
def save(fig,name):fig.savefig(O/(name+'.png'),dpi=150,bbox_inches='tight');fig.savefig(O/(name+'.pdf'),bbox_inches='tight');plt.close(fig)
fig,axes=plt.subplots(1,3,figsize=(12,4.2))
for ax,m in zip(axes,[5,10,15]):
 raw,bg=imagecache[m];ax.imshow(np.rint(np.clip(raw*REFBG/bg,0,255)).astype(np.uint8));ax.add_patch(plt.Rectangle((46,46),164,164,fill=False,color='lime',lw=1.2));ax.add_patch(plt.Rectangle((13,13),230,230,fill=False,color='cyan',lw=1.2));ax.set_title(f'{m}分膜');ax.axis('off')
fig.suptitle('全画面を解析し、中央・外側・最外周を別集計\n緑＝外周18%の内側／水色＝最外周約5%帯の内側',fontsize=14);fig.tight_layout(rect=[0,0,1,.88]);save(fig,'01_領域の区分')
fig,ax=plt.subplots(figsize=(10,4.5));names=['central18','outer18_without_edge5','edge5','full'];labels=['中央','外側（最外周帯を除く）','最外周約5%帯','全体'];x=np.arange(4)
for j,m in enumerate([5,10,15]):
 vals=[next(r['bright_area_percent'] for r in primary if r['anneal_min']==m and r['region']==n) for n in names];ax.bar(x+(j-1)*.24,vals,.24,color=['#777777','#287bab','#dc8a26'][j],label=f'{m}分膜')
ax.set_xticks(x,labels);ax.set_ylabel('斑点候補の面積 (%)');ax.legend();ax.grid(axis='y',alpha=.2);fig.tight_layout();save(fig,'02_外側にある特徴')
fig,axes=plt.subplots(1,2,figsize=(11,4.5));regions=['central18','full'];cols=['#777777','#dc8a26']
for ax,key,title in zip(axes,['bright_area_percent','relative_fine_sd'],['斑点候補面積の5回撮影','細かな模様指標の5回撮影']):
 for region,col,label in zip(regions,cols,['中央','全体']):
  rr=[r for r in repeat if r['region']==region];v=np.array([r[key] for r in rr]);ax.plot(range(1,6),v-v.mean(),'o-',label=label,color=col)
 ax.set_title(title);ax.set_xlabel('撮影番号');ax.set_ylabel('5回の平均からの差');ax.legend();ax.grid(alpha=.2)
fig.suptitle('同じ10分膜で比較：全体と中央の短時間のばらつき');fig.tight_layout(rect=[0,0,1,.92]);save(fig,'03_中央と全体の再現性')
