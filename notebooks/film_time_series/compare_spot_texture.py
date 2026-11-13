"""Compare thresholded bright-area and threshold-free band-pass contrast; stress tests only."""
from pathlib import Path
import sys,csv,json,hashlib,itertools
import numpy as np,cv2
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import fontManager
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'notebooks/capture_repeatability'))
from analyze_repeatability import corners_and_bbox
B=ROOT/'data/raw/Touma/FACsSnPbI3(Sn10mol%)_SnF2_0.1mol%/20261112';O=ROOT/'data/processed/20261113/06_spot_texture_comparison';O.mkdir(exist_ok=True)
FIT=[(785,555),(1585,555),(1185,250),(1185,855)];SCALES=[(.7,3.),(1.5,6.),(3.,12.)];BLURS=[0.,.5,1.,2.];MARGINS=[0.,.05,.18,.24];rows=[];manifest=[];repeat=[];maps={};yy,xx=np.mgrid[:256,:256];ellipse=((xx-127.5)/(256*.13))**2+((yy-127.5)/(256*.17))**2<=1
ref=next((B/'5min/1h').glob('*.jpg'))
def get(p):
 a=np.array(Image.open(p).convert('RGB'));corners,_=corners_and_bbox(a);crop=cv2.warpPerspective(a,cv2.getPerspectiveTransform(corners,np.float32([[0,0],[255,0],[255,255],[0,255]])),(256,256)).astype(float);bg=np.mean([a[y-20:y+20,x-20:x+20].mean((0,1)) for x,y in FIT],0);return crop,bg
_,REF=get(ref)
def record(p,kind):manifest.append({'path':str(p.relative_to(ROOT)),'kind':kind,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
def calculate(raw,bg,m,source,corrected,blurs,excludes):
 out=[]
 for blur in blurs:
  rgb=raw*REF/bg if corrected else raw.copy();rgb=cv2.GaussianBlur(rgb,(0,0),blur) if blur else rgb;gray=rgb[:,:,0]*.2126+rgb[:,:,1]*.7152+rgb[:,:,2]*.0722;smooth=cv2.GaussianBlur(gray,(0,0),8);contrast=(gray-smooth)/np.maximum(smooth,1);_,labels,stats,_=cv2.connectedComponentsWithStats((contrast>.1).astype(np.uint8),8);spots=np.isin(labels,np.flatnonzero(stats[1:,cv2.CC_STAT_AREA]>=3)+1)
  for small,large in SCALES:
   hp=cv2.GaussianBlur(gray,(0,0),small)-cv2.GaussianBlur(gray,(0,0),large)
   for margin in MARGINS:
    n=round(256*margin);base=(xx>=n)&(xx<256-n)&(yy>=n)&(yy<256-n)
    for exclude in excludes:
     mask=base&(~ellipse if exclude else True);g=gray[mask];row={'anneal_min':m,'source':source,'corrected':corrected,'added_blur_sigma_px':blur,'small_sigma_px':small,'large_sigma_px':large,'margin':margin,'exclude_ellipse':exclude,'fine_relative_sd':float(hp[mask].std()/g.mean()),'bright_area_percent':float(spots[mask].mean()*100),'gray_cv':float(g.std()/g.mean())};out.append(row)
     if corrected and blur==0 and margin==0 and not exclude and small==.7 and m not in maps:maps[m]={'rgb':np.rint(np.clip(rgb,0,255)).astype(np.uint8),'fine':np.abs(hp)/gray.mean(),'spots':spots}
 return out
for m in [5,10,15]:
 p=next((B/f'{m}min/1h').glob('*.jpg'));raw,bg=get(p)
 for f,kind in [(p,'film1h'),(p.with_suffix('.json'),'film_metadata')]:record(f,kind)
 for corrected in [False,True]:rows.extend(calculate(raw,bg,m,p.name,corrected,BLURS,[False,True]))
repeat_manifest=json.loads((ROOT/'data/processed/20261112/16_reanalysis_with_repeats/input_manifest.json').read_text())
for e in repeat_manifest:
 if e['kind']!='repeat_photo':continue
 p=ROOT/e['path'];raw,bg=get(p);record(p,'repeat10min');record(p.with_suffix('.json'),'repeat_metadata');repeat.extend(calculate(raw,bg,10,p.name,True,[0.],[False]))
def write(name,rs):
 with (O/name).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rs[0]));w.writeheader();w.writerows(rs)
write('all_image_metrics.csv',rows);write('repeat_metrics.csv',repeat)
# Treat matched processing configurations as sensitivity settings, never independent films.
groups={}
for r in rows:
 signature=tuple(r[k] for k in ['corrected','added_blur_sigma_px','small_sigma_px','large_sigma_px','margin','exclude_ellipse']);groups.setdefault(signature,[]).append(r)
ranks=[]
for signature,rs in groups.items():
 r={'corrected':signature[0],'added_blur_sigma_px':signature[1],'small_sigma_px':signature[2],'large_sigma_px':signature[3],'margin':signature[4],'exclude_ellipse':signature[5]}
 for key in ['fine_relative_sd','bright_area_percent','gray_cv']:r[key+'_largest_film']=max(rs,key=lambda a:a[key])['anneal_min']
 ranks.append(r)
write('matched_setting_ranks.csv',ranks)
primary=[r for r in rows if r['corrected'] and r['added_blur_sigma_px']==0 and r['small_sigma_px']==.7 and r['margin']==0 and not r['exclude_ellipse']];write('primary_comparison.csv',primary)
rsum=[]
for small,large in SCALES:
 for margin in MARGINS:
  rr=[r for r in repeat if r['small_sigma_px']==small and r['margin']==margin];r={'small_sigma_px':small,'large_sigma_px':large,'margin':margin,'n':len(rr)}
  for key in ['fine_relative_sd','bright_area_percent']:a=np.array([s[key] for s in rr]);r[key+'_mean']=float(a.mean());r[key+'_sd']=float(a.std(ddof=1));r[key+'_range']=float(np.ptp(a));r[key+'_relative_sd_percent']=float(a.std(ddof=1)/a.mean()*100)
  rsum.append(r)
write('repeatability_summary.csv',rsum)
# Unequal blur simulates differing sharpness, not actual camera defocus or measured uncertainties.
mixed=[]
for margin in [0.,.05,.18]:
 for small,large in SCALES:
  for combo in itertools.product([0.,.5,1.],repeat=3):
   picked=[next(r for r in rows if r['anneal_min']==m and r['corrected'] and r['added_blur_sigma_px']==blur and r['small_sigma_px']==small and r['margin']==margin and not r['exclude_ellipse']) for m,blur in zip([5,10,15],combo)];mixed.append({'margin':margin,'small_sigma_px':small,'large_sigma_px':large,'5min_blur_sigma':combo[0],'10min_blur_sigma':combo[1],'15min_blur_sigma':combo[2],'texture_largest_film':max(picked,key=lambda r:r['fine_relative_sd'])['anneal_min'],'spot_largest_film':max(picked,key=lambda r:r['bright_area_percent'])['anneal_min']})
write('unequal_blur_sensitivity.csv',mixed)
# Existing XRD descriptors are paired at film-level only.
xrd=ROOT/'data/processed/20261113/02_xrd_image_features_fullframe/paired_image_xrd.csv';prior=list(csv.DictReader(xrd.open(encoding='utf-8-sig')));paired=[]
for r in primary:
 x=next(a for a in prior if a['anneal_min']==str(r['anneal_min']));paired.append({**r,'xrd_low_main_min':x['xrd_1h_low_main_area_min'],'xrd_low_main_max':x['xrd_1h_low_main_area_max'],'xrd_note':x['xrd_note']})
write('paired_texture_spot_xrd.csv',paired);record(xrd,'xrd_descriptor_input')
(O/'input_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2));(O/'analysis_config.json').write_text(json.dumps({'primary_age':'nominal1h','independent_films':3,'technical_repeats':'10min only, n5, later session','texture':'SD(Gaussian sigma_small(I)-Gaussian sigma_large(I))/mean(I), no intensity threshold','image_texture_not_XRD_preferred_orientation':True,'spot':'same local contrast10%,Gaussian sigma8,connected pixels>=3,partitioned full-frame mask','correction':'shared5min1h paper reference','margins':MARGINS,'scales':SCALES,'blur_sigmas':BLURS,'unequal_blur':[0,.5,1],'stress_test':'synthetic Gaussian blur after256px warp, not measured focal error or correction','no_machine_learning_or_significance_tests':True,'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},ensure_ascii=False,indent=2))
print('PRIMARY',primary);print('REPEAT',rsum)
fontManager.addfont('/mnt/c/Windows/Fonts/YuGothR.ttc');plt.rcParams.update({'font.family':'Yu Gothic','font.size':12});COL=['#777777','#287bab','#dc8a26']
def save(fig,name):fig.savefig(O/(name+'.png'),dpi=150,bbox_inches='tight');fig.savefig(O/(name+'.pdf'),bbox_inches='tight');plt.close(fig)
fig,axes=plt.subplots(1,2,figsize=(11,4.5))
for ax,key,title in [(axes[0],'fine_relative_sd','しきい値なし：細かな明暗の強さ'),(axes[1],'bright_area_percent','しきい値10%：斑点候補面積')]:
 vals=[r[key] for r in primary];ax.bar(range(3),vals,color=COL);ax.set_xticks(range(3),['5分膜','10分膜','15分膜']);ax.set_title(title);ax.grid(axis='y',alpha=.2)
 for i,v in enumerate(vals):ax.text(i,v+max(vals)*.03,f'{v:.3f}' if key=='fine_relative_sd' else f'{v:.1f}%',ha='center')
 ax.set_ylim(0,max(vals)*1.22)
fig.suptitle('公称1h・基板全体：副相候補ピークが強い15分膜で両指標が大きい');fig.tight_layout(rect=[0,0,1,.93]);save(fig,'01_斑点と模様の比較')
fig,axes=plt.subplots(1,3,figsize=(13,4.5))
for ax,margin,title in zip(axes,[0.,.05,.18],['基板全体','最外周約5%帯の内側','中央（各辺18%除外）']):
 for m,col in zip([5,10,15],COL):
  rr=[r for r in rows if r['anneal_min']==m and r['corrected'] and r['small_sigma_px']==.7 and r['margin']==margin and not r['exclude_ellipse']];ax.plot([r['added_blur_sigma_px'] for r in rr],[r['fine_relative_sd'] for r in rr],'o-',label=f'{m}分膜',color=col)
 ax.set_title(title);ax.set_xlabel('人工的に追加したぼかし σ (px)');ax.set_ylabel('細かな明暗の強さ（単位なし）');ax.legend();ax.grid(alpha=.2)
fig.suptitle('鮮明さへの感度：同じぼかしを3膜に加えた試験／実際のピント誤差ではない');fig.tight_layout(rect=[0,0,1,.92]);save(fig,'02_ぼかしと解析範囲への感度')
fig,axes=plt.subplots(3,3,figsize=(11,10));vmax=max(np.percentile(v['fine'],99) for v in maps.values())
for j,m in enumerate([5,10,15]):
 axes[0,j].imshow(maps[m]['rgb']);axes[0,j].set_title(f'{m}分膜・公称1h');im=axes[1,j].imshow(maps[m]['fine'],cmap='magma',vmin=0,vmax=vmax);axes[1,j].set_title('細かな明暗の絶対値');rgb=maps[m]['rgb'].copy();rgb[maps[m]['spots']]=[255,220,0];axes[2,j].imshow(rgb);axes[2,j].set_title('黄＝斑点候補（10%）')
 for i in range(3):axes[i,j].axis('off')
fig.suptitle('模様を数値化した場所：縁・傷・反射も指標に含まれる');fig.tight_layout(rect=[0,0,.9,.94]);fig.colorbar(im,ax=list(axes[1]),fraction=.025,pad=.02,label='|細かな明暗| / 全体の平均明るさ');save(fig,'03_画像と模様の分布')
