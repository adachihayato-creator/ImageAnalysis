"""Nine XRD scans and latest three images; descriptive, no phase fractions."""
from pathlib import Path
from datetime import datetime
import sys,csv,json,hashlib
import numpy as np,cv2
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import fontManager
from analyze_sn10_xrd import features,scan_metadata,WINDOWS
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'notebooks/capture_repeatability'))
from analyze_repeatability import corners_and_bbox,roi
B=ROOT/'data/raw/Touma/FACsSnPbI3(Sn10mol%)_SnF2_0.1mol%/20261112';O=ROOT/'results/20261112/13_xrd_0h_1h_5h';O.mkdir(exist_ok=True)
fontManager.addfont('/mnt/c/Windows/Fonts/YuGothR.ttc');plt.rcParams['font.family']='Yu Gothic'
colors=['#dd8c26','#2775b2','#27955f'];scans={};rows=[];timings=[];manifest=[]
def record(p,kind):manifest.append({'path':str(p.relative_to(ROOT)),'kind':kind,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
def write(name,rs):
 with (O/name).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rs[0]));w.writeheader();w.writerows(rs)
def save(fig,name):
 fig.savefig(O/(name+'.png'),dpi=150,bbox_inches='tight');fig.savefig(O/(name+'.pdf'),bbox_inches='tight');plt.close(fig)
for m in [5,10,15]:
 for age in ['0h','1h','5h']:
  folder=B/'XRD'/f'{m}min'/age;txt=next(folder.glob('*.txt'));rasx=next(folder.glob('*.rasx'));x,y=np.loadtxt(txt,skiprows=2,encoding='utf-8-sig').T;meta,native=scan_metadata(rasx);dwell=float(meta['Step'])/(float(meta['Speed'])/60)
  assert len(x)==5701 and np.allclose(x,native[:,0]) and np.allclose(y,native[:,1]/dwell,rtol=1e-6,atol=.001)
  r={'anneal_min':m,'elapsed_label':age}
  for key,w in WINDOWS.items():r.update({key+'_'+k:v for k,v in features(x,y,w).items()})
  r['low_over_main_net_area']=r['low_net_area_cps_deg']/r['main_net_area_cps_deg'] if r['low_resolved_by_window_rule'] and r['main_resolved_by_window_rule'] else None
  scans[m,age]=(x,y,r,meta);rows.append(r);timings.append({'anneal_min':m,'label':age,**meta});record(txt,'xrd_txt');record(rasx,'xrd_rasx')
write('xrd_features.csv',rows);write('scan_metadata.csv',timings)
changes=[]
for m in [5,10,15]:
 a=scans[m,'0h'][2];b=scans[m,'5h'][2];c={'anneal_min':m}
 for key in WINDOWS:
  c[key+'_shift_0to5_deg']=b[key+'_angle_deg']-a[key+'_angle_deg'] if a[key+'_angle_deg'] is not None and b[key+'_angle_deg'] is not None else None
 c['main_height_change_0to5_percent']=(b['main_height_net_cps']/a['main_height_net_cps']-1)*100;changes.append(c)
write('changes_0to5.csv',changes)
# Photo matching uses actual timestamps; 15min latest age is intentionally not assumed to be5h.
photo_rows=[];crops=[]
metrics=list(csv.DictReader((ROOT/'results/20261112/09_image_time_series_4points/metrics.csv').open(encoding='utf-8-sig')))
for m,stem in [(5,'205257_705981'),(10,'205350_731887'),(15,'205430_272313')]:
 p=next((ROOT/'data/raw').rglob('photo_20261112_'+stem+'.jpg'));d=json.loads(p.with_suffix('.json').read_text());a=np.array(Image.open(p).convert('RGB'));corners,_=corners_and_bbox(a);crop=cv2.warpPerspective(a,cv2.getPerspectiveTransform(corners,np.float32([[0,0],[255,0],[255,255],[0,255]])),(256,256));crops.append(crop)
 base=next(r for r in metrics if int(r['anneal_min'])==m);paper=np.mean([a[y-20:y+20,x-20:x+20].mean((0,1)) for x,y in [(785,555),(1585,555),(1185,250),(1185,855)]],axis=0);pix=roi(crop,.18);gain=np.array([float(base['paper_'+c]) for c in 'RGB'])/paper
 corrected=np.rint(np.clip(crop.astype(float)*gain,0,255)).astype(np.uint8);Image.fromarray(corrected).save(O/f'{m}min_latest_corrected.png')
 meta=scans[m,'5h'][3];pt=datetime.fromisoformat(d['captured_at']);start=datetime.fromisoformat(meta['StartTimeJST']);end=datetime.fromisoformat(meta['EndTimeJST'])
 r={'anneal_min':m,'photo_filename':p.name,'photo_timestamp':d['captured_at'],'xrd_label':'5h','xrd_start_jst':meta['StartTimeJST'],'xrd_end_jst':meta['EndTimeJST'],'photo_minus_xrd_start_minutes':(pt-start).total_seconds()/60,'photo_minus_xrd_end_minutes':(pt-end).total_seconds()/60,'photo_age_label':'5h provisional' if m!=15 else '4h provisional; not5h','photo_fixed_verified':d['fixed_settings_verified'],'xrd_main_fwhm_deg':scans[m,'5h'][2]['main_apparent_fwhm_deg'],'xrd_low_over_main_net_area':scans[m,'5h'][2]['low_over_main_net_area']}
 for j,c in enumerate('RGB'):
  mean=float(pix[:,:,j].mean());r['raw_delta_from_first_'+c]=mean-float(base['mean_'+c]);r['background_normalized_delta_from_first_'+c]=mean*gain[j]-float(base['mean_'+c])
 photo_rows.append(r);record(p,'latest_photo');record(p.with_suffix('.json'),'latest_photo_metadata')
write('latest_photo_xrd_pairs.csv',photo_rows)
(O/'input_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
(O/'analysis_config.json').write_text(json.dumps({'windows':WINDOWS,'smoothing_points':5,'phase_fractions':False,'instrument_broadening_correction':False,'angular_shift_correction':False,'ROI_margin':.18,'background_correction':'perchannel baseline paper/current paper ratio, JPEG units','clock_assumption':'RASX Z as UTC, device clocks not independently verified','photo_pairing':'latest matching-film photograph, actual time gaps reported; not necessarily same nominal age'},ensure_ascii=False,indent=2))
print('FEATURES',json.dumps(rows,ensure_ascii=False));print('PAIRS',json.dumps(photo_rows,ensure_ascii=False))
fig,axes=plt.subplots(3,3,figsize=(15,10))
for i,m in enumerate([5,10,15]):
 for age,color in zip(['0h','1h','5h'],colors):
  x,y,r,meta=scans[m,age];smooth=np.convolve(y,np.ones(5)/5,'same');norm=smooth[(x>=13.4)&(x<=14.7)].max();axes[i,0].plot(x,y,color=color,label=age,lw=.6)
  for j in [1,2]:axes[i,j].plot(x,smooth/norm,color=color,label=age,lw=1)
 for j,ax in enumerate(axes[i]):
  ax.set_xlim(*[(3,60),(11,15.3),(25.5,29.5)][j]);ax.set_title(f'{m}分：'+['全体・測定強度','低角側・規格化','主ピーク付近・規格化'][j]);ax.set_xlabel('2θ (°)');ax.set_ylabel('cps' if j==0 else '約14°の最大値で規格化（背景込み）');ax.legend();ax.grid(alpha=.2)
fig.suptitle('Sn10%：0h・1h・5hのXRD／角度補正なし／規格化は相割合ではない');fig.tight_layout(rect=[0,0,1,.96]);save(fig,'01_XRD_0h_1h_5h')
fig,axes=plt.subplots(1,3,figsize=(14,4.8))
for j,(key,title) in enumerate([('main_angle_deg','約14°ピーク位置 (°)'),('main_apparent_fwhm_deg','約14°見かけ半値幅 (°)'),('low_over_main_net_area','約12.7°/14°の面積比（暫定）')]):
 for m,color in zip([5,10,15],colors):axes[j].plot([0,1,5],[scans[m,age][2][key] if scans[m,age][2][key] is not None else np.nan for age in ['0h','1h','5h']],'o-',color=color,label=f'{m}分')
 axes[j].set_title(title);axes[j].set_xlabel('公称成膜後時間 (h)');axes[j].grid(alpha=.2);axes[j].legend()
fig.suptitle('各条件1膜／誤差棒なし／ピークのずれ・配向・背景の影響を含む');fig.tight_layout(rect=[0,0,1,.93]);save(fig,'02_XRD特徴の変化')
fig,axes=plt.subplots(3,2,figsize=(12,12),gridspec_kw={'width_ratios':[1,2]})
for i,m in enumerate([5,10,15]):
 r=photo_rows[i];axes[i,0].imshow(np.array(Image.open(O/f'{m}min_latest_corrected.png')));axes[i,0].set_title(f'{m}分：最新画像・背景補正\n'+r['photo_timestamp'][11:19]);axes[i,0].axis('off')
 for age,color in zip(['0h','1h','5h'],colors):x,y,_,_=scans[m,age];axes[i,1].plot(x,y,color=color,label=age,lw=.8)
 axes[i,1].set_xlim(10.8,15.3);axes[i,1].set_xlabel('2θ (°)');axes[i,1].set_ylabel('cps');axes[i,1].set_title(f'{m}分：XRD／同時撮影ではない');axes[i,1].legend();axes[i,1].grid(alpha=.2)
fig.suptitle('最新の膜画像とXRD：15分膜の写真は公称4h、XRDは公称5h');fig.tight_layout(rect=[0,0,1,.96]);save(fig,'03_最新画像とXRD')
