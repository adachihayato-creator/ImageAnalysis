"""Compare five technical repeats to Sn10% longitudinal image changes."""
from pathlib import Path
import json,csv,sys,hashlib
from datetime import datetime
import numpy as np,cv2
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import fontManager
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'notebooks/capture_repeatability'))
from analyze_repeatability import corners_and_bbox,roi
P=ROOT/'data/processed/20261112/14_integrated_reanalysis';O=ROOT/'data/processed/20261112/16_reanalysis_with_repeats';O.mkdir(exist_ok=True)
fontManager.addfont('/mnt/c/Windows/Fonts/YuGothR.ttc');plt.rcParams['font.family']='Yu Gothic'
series=list(csv.DictReader((P/'image_metrics.csv').open(encoding='utf-8-sig')));base=next(r for r in series if r['anneal_min']=='10' and r['photo_index']=='1');bgref=np.array([float(base['paper_'+c]) for c in 'RGB'])
refpath=next((ROOT/'data/raw').rglob('photo_20261112_205350_731887.jpg'))
paths=[next((ROOT/'data/raw').rglob('photo_20261112_'+s+'.jpg')) for s in ['214248_811391','214503_875751','214527_791849','214548_050694','214621_290887']]
COL=['#cf493f','#278d4f','#426dc9'];FIT=[(785,555),(1585,555),(1185,250),(1185,855)];CHECK=[(785,250),(1585,250),(785,855),(1585,855)]
rows=[];sensitivity=[];crops=[];manifest=[];metas=[];matches=[]
def readcrop(p):
 a=np.array(Image.open(p).convert('RGB'));corners,_=corners_and_bbox(a);t=cv2.getPerspectiveTransform(corners,np.float32([[0,0],[255,0],[255,255],[0,255]]));return a,cv2.warpPerspective(a,t,(256,256)),corners
_,refcrop,_=readcrop(refpath);sift=cv2.SIFT_create(contrastThreshold=.01);k0,d0=sift.detectAndCompute(cv2.cvtColor(refcrop,cv2.COLOR_RGB2GRAY),None)
for i,p in enumerate(paths):
 a,crop,corners=readcrop(p);d=json.loads(p.with_suffix('.json').read_text());metas.append(d)
 # Match local features, handling small errors in corner normalization.
 key,desc=sift.detectAndCompute(cv2.cvtColor(crop,cv2.COLOR_RGB2GRAY),None);pairs=cv2.BFMatcher().knnMatch(d0,desc,k=2);good=[u for u,v in pairs if u.distance<.7*v.distance];inliers=0
 if len(good)>=4:
  H,mask=cv2.findHomography(np.float32([key[g.trainIdx].pt for g in good]),np.float32([k0[g.queryIdx].pt for g in good]),cv2.RANSAC,3);inliers=int(mask.sum()) if mask is not None else 0
 matches.append({'filename':p.name,'reference':refpath.name,'good_sift_matches':len(good),'ransac_inliers':inliers})
 bg=np.mean([a[y-20:y+20,x-20:x+20].mean((0,1)) for x,y in FIT],axis=0);gain=bgref/bg;crops.append(np.rint(np.clip(crop.astype(float)*gain,0,255)).astype(np.uint8))
 row={'capture_index':i+1,'filename':p.name,'captured_at':d['captured_at'],'fixed_verified':d['fixed_settings_verified']}
 for margin in [.12,.18,.24]:
  pixels=roi(crop,margin).reshape(-1,3);r={'capture_index':i+1,'margin':margin}
  for j,c in enumerate('RGB'):
   r['raw_'+c]=float(pixels[:,j].mean());r['corrected_'+c]=float(pixels[:,j].mean()*gain[j])
   if margin==.18:row['raw_'+c]=r['raw_'+c];row['corrected_'+c]=r['corrected_'+c];row['paper_'+c]=float(bg[j]);row['gain_'+c]=float(gain[j])
  sensitivity.append(r)
 rows.append(row)
 for f,kind in [(p,'repeat_photo'),(p.with_suffix('.json'),'repeat_metadata')]:manifest.append({'path':str(f.relative_to(ROOT)),'kind':kind,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()})
assert all(d['fixed_settings_verified'] for d in metas)
for k in ['ExposureTime','AnalogueGain','ColourGains','LensPosition']:assert all(d['settings'][k]==metas[0]['settings'][k] for d in metas)
# Apply SAME baseline used in the time series, not the first repeat's paper reference.
summary=[]
for c in 'RGB':
 raw=np.array([r['raw_'+c] for r in rows]);y=np.array([r['corrected_'+c] for r in rows]);rr=[r for r in series if r['anneal_min']=='10'];delta=float(rr[-1]['corrected_mean_'+c])-float(rr[0]['corrected_mean_'+c]);mean=float(y.mean());offset=mean-float(rr[-1]['corrected_mean_'+c])
 summary.append({'channel':c,'raw_repeat_sd_ddof1':float(raw.std(ddof=1)),'corrected_repeat_sd_ddof1':float(y.std(ddof=1)),'corrected_repeat_range':float(np.ptp(y)),'corrected_repeat_mean':mean,'longitudinal_first_to_last_delta':delta,'delta_magnitude_over_repeat_sd_descriptive':abs(delta)/float(y.std(ddof=1)),'repeat_mean_minus_latest_series':offset})
def write(name,data):
 with (O/name).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
def save(fig,name):
 fig.savefig(O/(name+'.png'),dpi=150,bbox_inches='tight');fig.savefig(O/(name+'.pdf'),bbox_inches='tight');plt.close(fig)
write('repeat_metrics_common_reference.csv',rows);write('repeat_roi_sensitivity.csv',sensitivity);write('repeat_vs_time_change.csv',summary);write('film_identity_matches.csv',matches)
# Validate on paper regions not used to estimate channel gains.
basepath=next((ROOT/'data/raw').rglob(base['filename']))
baseimage=np.array(Image.open(basepath).convert('RGB'),dtype=float)
getcheck=lambda a:np.array([a[y-20:y+20,x-20:x+20].mean((0,1)) for x,y in CHECK])
basecheck=getcheck(baseimage);heldout=[]
for r,p in zip(rows,paths):
 image=np.array(Image.open(p).convert('RGB'),dtype=float);before=getcheck(image);gain=np.array([r['gain_'+c] for c in 'RGB']);after=before*gain
 error=lambda a:float(np.sqrt(np.mean(((a-basecheck)/basecheck)**2,axis=1)).mean()*100)
 heldout.append({'filename':p.name,'before_percent':error(before),'after_percent':error(after)})
write('held_out_background.csv',heldout)
for p,kind in [(basepath,'baseline_photo'),(refpath,'identity_reference_photo')]:manifest.append({'path':str(p.relative_to(ROOT)),'kind':kind,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
(O/'input_manifest.json').write_text(json.dumps(manifest+[{'path':str((P/'image_metrics.csv').relative_to(ROOT)),'kind':'series_metrics','sha256':hashlib.sha256((P/'image_metrics.csv').read_bytes()).hexdigest()}],ensure_ascii=False,indent=2))
(O/'analysis_config.json').write_text(json.dumps({'repeat_sample':'10min film inferred from user following requested protocol; same-film features verified','repeat_count':5,'repeat_protocol':'user following remove/replace protocol; each individual action not independently observed','common_background_reference_filename':base['filename'],'common_paper_RGB':bgref.tolist(),'primary_ROI_margin':.18,'sensitivity_margins':[.12,.18,.24],'sd_ddof':1,'units':'JPEG RGB values, not percent or calibrated color difference','scope':'five technical replicates, one film, one session; not independent films or between-day uncertainty','XRD_clock':'unreliable per user; nominal times only'},ensure_ascii=False,indent=2))
fig,axes=plt.subplots(1,5,figsize=(14,3.5))
for i,ax in enumerate(axes):ax.imshow(crops[i]);ax.axis('off');ax.set_title(f'撮影{i+1}\n{rows[i]["captured_at"][11:19]}')
fig.suptitle('10分膜の5回撮影：経時解析と同じ基準へ背景補正');fig.tight_layout(rect=[0,0,1,.92]);save(fig,'01_5回撮影の写真')
fig,axes=plt.subplots(1,2,figsize=(12,5))
for j,c in enumerate('RGB'):
 for ax,prefix in zip(axes,['raw_','corrected_']):
  y=np.array([r[prefix+c] for r in rows]);ax.plot(range(1,6),y-y.mean(),'o-',color=COL[j],label=c)
for ax,title in zip(axes,['補正前','背景補正後（経時解析と同じ基準）']):ax.set_title(title);ax.set_xlabel('撮影番号');ax.set_ylabel('5枚の平均からの差 (RGB単位)');ax.legend();ax.grid(alpha=.2);ax.axhline(0,color='gray',lw=.7)
fig.suptitle('置き直し試験のばらつき：膜の経時変化とは別に評価');fig.tight_layout(rect=[0,0,1,.93]);save(fig,'02_撮影間のばらつき')
fig,axes=plt.subplots(1,3,figsize=(14,4.8))
for ax,c,sm in zip(axes,'RGB',summary):
 rr=[r for r in series if r['anneal_min']=='10' and r['photo_index']!='2'];x=[float(r['hours_since_first_photo']) for r in rr];y=[float(r['corrected_mean_'+c])-float(base['corrected_mean_'+c]) for r in rr];ax.plot(x,y,'o-',color=COL['RGB'.index(c)],label='経時撮影（写真2除外）')
 first=datetime.fromisoformat(base['captured_at']);tx=[(datetime.fromisoformat(r['captured_at'])-first).total_seconds()/3600 for r in rows];ty=[r['corrected_'+c]-float(base['corrected_mean_'+c]) for r in rows];ax.scatter(tx,ty,marker='x',color='black',label='今回の5回撮影');ax.axhspan(-sm['corrected_repeat_sd_ddof1'],sm['corrected_repeat_sd_ddof1'],color='gray',alpha=.14,label='参考：±今回の撮影SD');ax.axhline(0,color='gray',lw=.8);ax.set_title(c+'成分');ax.set_xlabel('最初の写真からの実時間 (h)');ax.set_ylabel('最初の写真からの差 (RGB単位)');ax.grid(alpha=.2);ax.legend(fontsize=8)
fig.suptitle('10分膜：経時変化と5回撮影を同じ補正・尺度で比較／帯は有意差の基準ではない');fig.tight_layout(rect=[0,0,1,.93]);save(fig,'03_経時変化と撮影ばらつきの比較')
print('SUMMARY',json.dumps(summary,ensure_ascii=False));print('IDENTITY',matches)
