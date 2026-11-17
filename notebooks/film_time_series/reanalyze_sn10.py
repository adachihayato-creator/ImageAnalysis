"""Integrated Sn10% reanalysis: latest15 images, held-out validation, ROI/XRD sensitivity.
Run from repo root with numpy,opencv,pillow,matplotlib available.
"""
from pathlib import Path
import sys,csv,json,hashlib
from datetime import datetime
import numpy as np,cv2
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import fontManager
from analyze_sn10_xrd import features,scan_metadata,WINDOWS
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'notebooks/capture_repeatability'))
from analyze_repeatability import corners_and_bbox,roi
B=ROOT/'data/raw/Touma/FACsSnPbI3(Sn10mol%)_SnF2_0.1mol%/20261112';O=ROOT/'results/20261112/14_integrated_reanalysis';O.mkdir(exist_ok=True);(O/'corrected_crops').mkdir(exist_ok=True)
fontManager.addfont('/mnt/c/Windows/Fonts/YuGothR.ttc');plt.rcParams['font.family']='Yu Gothic'
COL=['#cf493f','#278d4f','#426dc9'];FIT=[(785,555),(1585,555),(1185,250),(1185,855)];CHECK=[(785,250),(1585,250),(785,855),(1585,855)]
rows=[];sens=[];validation=[];manifest=[];crops={};metas=[]
def rec(p,kind):manifest.append({'path':str(p.relative_to(ROOT)),'kind':kind,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
def patches(a,centers):return np.array([a[y-20:y+20,x-20:x+20].mean((0,1)) for x,y in centers])
def write(name,rs):
 with (O/name).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rs[0]));w.writeheader();w.writerows(rs)
def save(fig,name):
 fig.savefig(O/(name+'.png'),dpi=150,bbox_inches='tight');fig.savefig(O/(name+'.pdf'),bbox_inches='tight');plt.close(fig)
latest={5:'205257_705981',10:'205350_731887',15:'205430_272313'}
for m in [5,10,15]:
 paths=sorted((B/f'{m}min').glob('*/*.jpg'));assert len(paths)==4
 paths.append(next((ROOT/'data/raw').rglob('photo_20261112_'+latest[m]+'.jpg')))
 for i,p in enumerate(paths):
  a=np.array(Image.open(p).convert('RGB'));d=json.loads(p.with_suffix('.json').read_text());metas.append(d);corners,_=corners_and_bbox(a);mask=np.zeros(a.shape[:2],np.uint8);cv2.fillConvexPoly(mask,corners.astype(np.int32),1)
  for x,y in FIT+CHECK:assert not mask[y-20:y+20,x-20:x+20].any()
  bg=patches(a,FIT).mean(0);held=patches(a,CHECK)
  if i==0:basebg=bg;baseheld=held;t0=datetime.fromisoformat(d['captured_at'])
  gain=basebg/bg;corr=a.astype(float)*gain
  error=lambda v:float(np.sqrt(np.mean(((v-baseheld)/baseheld)**2,axis=1)).mean()*100)
  validation.append({'anneal_min':m,'photo_index':i+1,'raw_error_percent':error(held),'corrected_error_percent':error(held*gain)})
  t=cv2.getPerspectiveTransform(corners,np.float32([[0,0],[255,0],[255,255],[0,255]]));crop=cv2.warpPerspective(a,t,(256,256)).astype(float);corrected=crop*gain;fine=cv2.GaussianBlur(crop,(0,0),.7)-cv2.GaussianBlur(crop,(0,0),3)
  label=p.parent.name if i<4 else ('5h暫定' if m!=15 else '4h暫定');r={'anneal_min':m,'photo_index':i+1,'label':label,'filename':p.name,'captured_at':d['captured_at'],'hours_since_first_photo':(datetime.fromisoformat(d['captured_at'])-t0).total_seconds()/3600,'excluded_from_primary':i==1,'fixed_verified':d['fixed_settings_verified']}
  for margin in [.12,.18,.24]:
   pixels=roi(crop,margin).reshape(-1,3);fp=roi(fine,margin).reshape(-1,3);s={'anneal_min':m,'photo_index':i+1,'margin':margin}
   for j,c in enumerate('RGB'):
    s['raw_mean_'+c]=float(pixels[:,j].mean());s['corrected_mean_'+c]=float(pixels[:,j].mean()*gain[j]);s['raw_sd_'+c]=float(pixels[:,j].std());s['corrected_sd_'+c]=float(pixels[:,j].std()*gain[j]);s['raw_fine_'+c]=float(fp[:,j].std());s['corrected_fine_'+c]=float(fp[:,j].std()*gain[j])
    if margin==.18:
     for prefix in ['raw_mean_','corrected_mean_','raw_sd_','corrected_sd_','raw_fine_','corrected_fine_']:r[prefix+c]=s[prefix+c]
     r['paper_'+c]=float(bg[j]);r['gain_'+c]=float(gain[j])
   sens.append(s)
  rows.append(r);crops[m,i+1]=np.rint(np.clip(corrected,0,255)).astype(np.uint8);Image.fromarray(crops[m,i+1]).save(O/'corrected_crops'/f'{m}min_{i+1}.png');rec(p,'photo');rec(p.with_suffix('.json'),'photo_metadata')
assert all(d['fixed_settings_verified'] for d in metas)
for k in ['ExposureTime','AnalogueGain','ColourGains','LensPosition']:assert all(d['settings'][k]==metas[0]['settings'][k] for d in metas)
write('image_metrics.csv',rows);write('image_roi_sensitivity.csv',sens);write('held_out_background.csv',validation)
# Recompute all XRD features; alternate low-angle backgrounds expose extraction instability.
scan={};xr=[];xs=[]
low_variants=[{'search':(12.25,13.0),'background':((11.5,11.8),(13.1,13.3))},{'search':(12.25,13.0),'background':((12.,12.2),(13.05,13.2))},{'search':(12.25,13.0),'background':((12.1,12.25),(13.,13.15))}]
for m in [5,10,15]:
 for age in ['0h','1h','5h']:
  folder=B/'XRD'/f'{m}min'/age;p=next(folder.glob('*.txt'));z=next(folder.glob('*.rasx'));x,y=np.loadtxt(p,skiprows=2,encoding='utf-8-sig').T;meta,native=scan_metadata(z);dt=float(meta['Step'])/(float(meta['Speed'])/60);assert np.allclose(x,native[:,0]) and np.allclose(y,native[:,1]/dt,rtol=1e-6,atol=.001)
  r={'anneal_min':m,'label':age}
  for key,w in WINDOWS.items():r.update({key+'_'+k:v for k,v in features(x,y,w).items()})
  xr.append(r);scan[m,age]=(x,y,r);rec(p,'xrd_txt');rec(z,'xrd_rasx')
  for j,w in enumerate(low_variants):
   lo=features(x,y,w);ratio=lo['net_area_cps_deg']/r['main_net_area_cps_deg'] if lo['resolved_by_window_rule'] else None
   xs.append({'anneal_min':m,'label':age,'background_variant':j+1,'low_angle_deg':lo['angle_deg'],'low_net_area':lo['net_area_cps_deg'],'resolved':lo['resolved_by_window_rule'],'low_over_main_area':ratio})
write('xrd_features.csv',xr);write('xrd_low_peak_sensitivity.csv',xs)
# Primary endpoint and previous-to-latest effects, with ROI variation range.
summary=[]
for m in [5,10,15]:
 rr=[r for r in rows if r['anneal_min']==m]
 for c in 'RGB':
  values=[]
  for margin in [.12,.18,.24]:
   aa=[s for s in sens if s['anneal_min']==m and s['margin']==margin];values.append(aa[-1]['corrected_mean_'+c]-aa[0]['corrected_mean_'+c])
  summary.append({'anneal_min':m,'channel':c,'raw_first_to_last':rr[-1]['raw_mean_'+c]-rr[0]['raw_mean_'+c],'corrected_first_to_last':rr[-1]['corrected_mean_'+c]-rr[0]['corrected_mean_'+c],'corrected_previous_to_last':rr[-1]['corrected_mean_'+c]-rr[-2]['corrected_mean_'+c],'roi_delta_min':min(values),'roi_delta_max':max(values)})
write('image_change_summary.csv',summary)
(O/'input_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2));(O/'analysis_config.json').write_text(json.dumps({'primary_image_indices':[1,3,4,5],'reference_image_index':1,'sensitivity':'all five images, raw/corrected, ROI12/18/24%','image_time':'actual camera time since first; nominal labels provisional for newest photographs','xrd_time':'user nominal0h/1h/5h; XRD PC clock unreliable, no cross-device timestamp inference','low_variants':low_variants,'main_high_windows':WINDOWS,'fit_patches':FIT,'heldout_patches':CHECK,'patch_size':40,'phase_fraction_estimation':False,'replicates_per_condition':1,'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},ensure_ascii=False,indent=2))
print('SUMMARY',summary);print('LOW_SENSITIVITY',xs)
fig,axes=plt.subplots(3,4,figsize=(13,10))
for i,m in enumerate([5,10,15]):
 for j,k in enumerate([1,3,4,5]):
  r=next(r for r in rows if r['anneal_min']==m and r['photo_index']==k);ax=axes[i,j];ax.imshow(crops[m,k]);ax.axis('off');ax.set_title(f'{m}分・写真{k}・{r["label"]}\n{r["captured_at"][11:19]}',fontsize=11)
fig.suptitle('主解析：背景補正後／問題の写真2を除外／列は撮影順');fig.tight_layout(rect=[0,0,1,.96]);save(fig,'01_主解析の写真')
fig,axes=plt.subplots(3,2,figsize=(13,10))
for i,m in enumerate([5,10,15]):
 rr=[r for r in rows if r['anneal_min']==m];primary=[r for r in rr if not r['excluded_from_primary']];base=rr[0]
 for j,c in enumerate('RGB'):
  xp=[r['hours_since_first_photo'] for r in primary];yp=[r['corrected_mean_'+c]-base['corrected_mean_'+c] for r in primary];axes[i,0].plot(xp,yp,'o-',color=COL[j],label=c)
  axes[i,0].plot([r['hours_since_first_photo'] for r in rr],[r['corrected_mean_'+c]-base['corrected_mean_'+c] for r in rr],':',color=COL[j],alpha=.4)
  lo=[];hi=[]
  for r in primary:
   ds=[]
   for margin in [.12,.18,.24]:
    aa=next(s for s in sens if s['anneal_min']==m and s['photo_index']==1 and s['margin']==margin);bb=next(s for s in sens if s['anneal_min']==m and s['photo_index']==r['photo_index'] and s['margin']==margin);ds.append(bb['corrected_mean_'+c]-aa['corrected_mean_'+c])
   lo.append(min(ds));hi.append(max(ds))
  axes[i,0].fill_between(xp,lo,hi,color=COL[j],alpha=.12)
  axes[i,1].plot(xp,[r['corrected_sd_'+c] for r in primary],'o-',color=COL[j],label=c)
 for j,ax in enumerate(axes[i]):ax.set_title(f'{m}分：'+['平均色の変化（帯＝ROI範囲の違い）','色むら（画素標準偏差）'][j]);ax.set_xlabel('最初の写真からの実時間 (h)');ax.set_ylabel('JPEG RGB単位');ax.legend();ax.grid(alpha=.2)
fig.suptitle('実線＝主解析（写真2除外）／左の薄い点線＝写真2を含む参考／誤差帯ではない');fig.tight_layout(rect=[0,0,1,.95]);save(fig,'02_主解析の色と色むら')
fig,axes=plt.subplots(3,2,figsize=(12,10))
for i,m in enumerate([5,10,15]):
 for age,col in zip(['0h','1h','5h'],['#dd8c26','#2775b2','#27955f']):
  x,y,r=scan[m,age];smooth=np.convolve(y,np.ones(5)/5,'same');axes[i,0].plot(x,y,col,label=age,lw=.6);norm=smooth[(x>=13.4)&(x<=14.7)].max();axes[i,1].plot(x,smooth/norm,col,label=age,lw=1)
 for j,ax in enumerate(axes[i]):ax.set_xlim(*[(3,60),(11,15.3)][j]);ax.set_title(f'{m}分：'+['全体','低角側・規格化'][j]);ax.set_xlabel('2θ (°)');ax.set_ylabel('cps' if j==0 else '約14°最大値で規格化（背景込み）');ax.legend();ax.grid(alpha=.2)
fig.suptitle('XRD：申告された0h・1h・5h／PC時計は使用しない／角度補正なし');fig.tight_layout(rect=[0,0,1,.96]);save(fig,'03_XRDの再比較')
