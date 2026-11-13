"""Exploratory comparison of 3 films at nominal1h. No inference from pixels as replicates."""
from pathlib import Path
import sys,json,csv,hashlib
import numpy as np,cv2
from PIL import Image
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'notebooks/capture_repeatability'))
from analyze_repeatability import corners_and_bbox
B=ROOT/'data/raw/Touma/FACsSnPbI3(Sn10mol%)_SnF2_0.1mol%/20261112';O=ROOT/'data/processed/20261113/02_xrd_image_features_fullframe';O.mkdir(parents=True,exist_ok=True);(O/'crops').mkdir(exist_ok=True)
FIT=[(785,555),(1585,555),(1185,250),(1185,855)];rows=[];manifest=[];maps={};crops={};target=np.float32([[0,0],[255,0],[255,255],[0,255]])
def read(p):return list(csv.DictReader(p.open(encoding='utf-8-sig')))
def write(name,rs):
 with (O/name).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rs[0]));w.writeheader();w.writerows(rs)
def crop(p):
 a=np.array(Image.open(p).convert('RGB'));corners,_=corners_and_bbox(a);return a,cv2.warpPerspective(a,cv2.getPerspectiveTransform(corners,target),(256,256)).astype(float),corners
ref=next((B/'5min/1h').glob('*.jpg'));a,_,_=crop(ref);refbg=np.mean([a[y-20:y+20,x-20:x+20].mean((0,1)) for x,y in FIT],axis=0)
yy,xx=np.mgrid[:256,:256];ellipse=((xx-127.5)/(256*.13))**2+((yy-127.5)/(256*.17))**2<=1
for minute in [5,10,15]:
 p=next((B/f'{minute}min/1h').glob('*.jpg'));a,raw,corners=crop(p);bg=np.mean([a[y-20:y+20,x-20:x+20].mean((0,1)) for x,y in FIT],axis=0);gain=refbg/bg
 maskfull=np.zeros(a.shape[:2],np.uint8);cv2.fillConvexPoly(maskfull,corners.astype(np.int32),1)
 for x,y in FIT:assert not maskfull[y-20:y+20,x-20:x+20].any()
 for f,kind in [(p,'photo_1h'),(p.with_suffix('.json'),'photo_metadata')]:manifest.append({'path':str(f.relative_to(ROOT)),'kind':kind,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()})
 for corrected in [False,True]:
  rgb=raw*gain if corrected else raw.copy();gray=rgb[:,:,0]*.2126+rgb[:,:,1]*.7152+rgb[:,:,2]*.0722
  lab=cv2.cvtColor((np.clip(rgb,0,255)/255).astype(np.float32),cv2.COLOR_RGB2LAB)
  hp=cv2.GaussianBlur(gray,(0,0),.7)-cv2.GaussianBlur(gray,(0,0),3)
  for margin in [0.,.12,.18,.24]:
   n=round(256*margin);mask=(xx>=n)&(xx<256-n)&(yy>=n)&(yy<256-n)
   for exclude in [False,True]:
    analysis=mask&(~ellipse if exclude else True);pix=rgb[analysis];g=gray[analysis];mean=float(g.mean());normalized_fine=float(hp[analysis].std()/mean);cv=float(g.std()/mean)
    rad=np.maximum(abs(xx-127.5),abs(yy-127.5))/(128-n);central=analysis&(rad<=.5);peripheral=analysis&(rad>=.75)
    centralratio=float(gray[central].mean()/gray[peripheral].mean()) if central.any() else None
    for sigma in [6.,8.,12.]:
     smooth=cv2.GaussianBlur(gray,(0,0),sigma);contrast=(gray-smooth)/np.maximum(smooth,1.)
     for threshold in [.05,.1,.15]:
      binary=((contrast>threshold)&analysis).astype(np.uint8);count,labels,stats,centers=cv2.connectedComponentsWithStats(binary,8);valid=np.flatnonzero(stats[1:,cv2.CC_STAT_AREA]>=3)+1;kept=np.isin(labels,valid)&analysis;areas=stats[valid,cv2.CC_STAT_AREA];border=(cv2.dilate((~analysis).astype(np.uint8),np.ones((3,3),np.uint8))>0)
      # All components that cross the ROI edge are counted as observed fragments; no physical grain size claim.
      row={'anneal_min':minute,'elapsed_label':'1h','background_normalized':corrected,'roi_margin':margin,'exclude_central_ellipse':exclude,'local_sigma_px':sigma,'contrast_threshold':threshold,'roi_pixels':int(analysis.sum()),'mean_R':float(pix[:,0].mean()),'mean_G':float(pix[:,1].mean()),'mean_B':float(pix[:,2].mean()),'mean_Lstar':float(lab[:,:,0][analysis].mean()),'mean_astar':float(lab[:,:,1][analysis].mean()),'mean_bstar':float(lab[:,:,2][analysis].mean()),'gray_spatial_cv':cv,'relative_fine_pattern_sd':normalized_fine,'bright_area_percent':float(kept.sum()/analysis.sum()*100),'bright_components_per_10000px':float(len(valid)/analysis.sum()*10000),'bright_component_median_area_px':float(np.median(areas)) if len(areas) else 0.,'center_over_periphery_brightness':centralratio,'relative_contrast_p95':float(np.percentile(contrast[analysis],95))}
      rows.append(row)
      if corrected and margin==0. and not exclude and sigma==8 and threshold==.1:
       maps[minute]={'mask':analysis,'spots':kept,'contrast':contrast};crops[minute]=np.rint(np.clip(rgb,0,255)).astype(np.uint8);Image.fromarray(crops[minute]).save(O/'crops'/f'{minute}min_1h_corrected.png')
write('all_feature_sensitivity.csv',rows)
primary=[r for r in rows if r['background_normalized'] and r['roi_margin']==0. and not r['exclude_central_ellipse'] and r['local_sigma_px']==8 and r['contrast_threshold']==.1];write('primary_features.csv',primary)
xrdsrc=ROOT/'data/processed/20261112/14_integrated_reanalysis/xrd_low_peak_sensitivity.csv';xrs=read(xrdsrc);paired=[]
for r in primary:
 vals=[float(x['low_over_main_area']) for x in xrs if x['anneal_min']==str(r['anneal_min']) and x['label']=='1h' and x['resolved']=='True'];paired.append({**r,'xrd_1h_low_main_area_min':min(vals) if vals else None,'xrd_1h_low_main_area_max':max(vals) if vals else None,'xrd_note':'副相候補/主相候補の面積比・相含有率ではない' if vals else '抽出不成立、ゼロではない'})
write('paired_image_xrd.csv',paired)
keys=['gray_spatial_cv','relative_fine_pattern_sd','bright_area_percent','bright_components_per_10000px','bright_component_median_area_px','center_over_periphery_brightness','relative_contrast_p95','mean_Lstar','mean_astar','mean_bstar'];rank=[]
for key in keys:
 scenarios={}
 for r in rows:
  signature=tuple(r[k] for k in ['background_normalized','roi_margin','exclude_central_ellipse','local_sigma_px','contrast_threshold']);scenarios.setdefault(signature,[]).append(r)
 groups=list(scenarios.values());higher=sum(all(r[key] is not None for r in group) and next(r[key] for r in group if r['anneal_min']==15)>max(r[key] for r in group if r['anneal_min']!=15) for group in groups)
 lower=sum(all(r[key] is not None for r in group) and next(r[key] for r in group if r['anneal_min']==15)<min(r[key] for r in group if r['anneal_min']!=15) for group in groups)
 rank.append({'feature':key,'settings_compared':len(groups),'15min_largest_count':higher,'15min_smallest_count':lower,'note':'条件数は独立膜数や確率ではない。複数特徴を探索した結果。'})
write('rank_sensitivity_summary.csv',rank)
manifest.append({'path':str(xrdsrc.relative_to(ROOT)),'kind':'xrd_feature_input','sha256':hashlib.sha256(xrdsrc.read_bytes()).hexdigest()})
for m in [5,10,15]:
 for f in (B/'XRD'/f'{m}min/1h').iterdir():
  if f.suffix in ['.txt','.rasx']:manifest.append({'path':str(f.relative_to(ROOT)),'kind':'xrd1h_original','sha256':hashlib.sha256(f.read_bytes()).hexdigest()})
(O/'input_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2));(O/'analysis_config.json').write_text(json.dumps({'independent_films':3,'time_label':'nominal1h all3; XRD clock unreliable; no precise simultaneity assumption','common_background_reference':str(ref.relative_to(ROOT)),'correction':'same background RGB reference for cross-film comparison, raw retained','fit_centers':FIT,'patch_size':40,'primary':{'margin':0.,'ellipse_excluded':False,'sigma':8,'threshold':.1,'minimum_component_area_px':3},'sensitivities':{'margins':[0.,.12,.18,.24],'ellipse':[False,True],'background_normalized':[False,True],'sigma':[6,8,12],'threshold':[.05,.1,.15]},'spot_definition':'local grayscale contrast (I-Gaussian(I))/Gaussian(I) above threshold; connected pixels >=3','ellipse':'center127.5,127.5 radii33.28,43.52 px in256px image; generic sensitivity mask, not detected reflection','inference':'exploratory; no correlations, pvalues, phase segmentation or machine learning','code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},ensure_ascii=False,indent=2))
print('PRIMARY',json.dumps(primary,ensure_ascii=False));print('RANK',json.dumps(rank,ensure_ascii=False))
# Figures show primary maps and matched XRD, with no conversion to phase percentage.
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import fontManager
fontManager.addfont('/mnt/c/Windows/Fonts/YuGothR.ttc');plt.rcParams.update({'font.family':'Yu Gothic','font.size':12})
def save(fig,name):fig.savefig(O/(name+'.png'),dpi=150,bbox_inches='tight');fig.savefig(O/(name+'.pdf'),bbox_inches='tight');plt.close(fig)
fig,axes=plt.subplots(3,3,figsize=(11,10))
for j,m in enumerate([5,10,15]):
 rgb=crops[m];axes[0,j].imshow(rgb);axes[0,j].set_title(f'{m}分膜・公称1h\n共通基準で色補正');overlay=rgb.copy();overlay[maps[m]['spots']]=[255,220,0];axes[1,j].imshow(overlay);axes[1,j].set_title('黄＝局所的に明るい斑点の候補');masked=np.ma.array(maps[m]['contrast'],mask=~maps[m]['mask']);im=axes[2,j].imshow(masked,cmap='coolwarm',vmin=-.3,vmax=.3);axes[2,j].set_title('周囲に対する明暗差');
 for i in range(3):axes[i,j].axis('off')
fig.suptitle('基板全体（外周・中央を含む）／明るい斑点はPbI₂同定領域ではない',fontsize=15);fig.tight_layout(rect=[0,0,1,.94]);fig.colorbar(im,ax=list(axes[2]),shrink=.65,label='(I − local mean) / local mean');save(fig,'01_画像特徴の抽出')
fig,axes=plt.subplots(1,3,figsize=(12,4.5))
for ax,(key,title) in zip(axes,[('bright_area_percent','明るい斑点の面積 (%)'),('relative_fine_pattern_sd','平均明るさで割った細かな模様'),('gray_spatial_cv','明るさのばらつき／平均')]):
 ax.bar(range(3),[r[key] for r in primary],color=['#777777','#287bab','#dc8a26']);ax.set_xticks(range(3),['5分','10分','15分']);ax.set_title(title);ax.grid(axis='y',alpha=.2)
fig.suptitle('主条件：外周除外なし・楕円除外なし・共通の背景基準で補正');fig.tight_layout(rect=[0,0,1,.92]);save(fig,'02_3膜の特徴比較')
fig,axes=plt.subplots(1,2,figsize=(12,4.8))
for m,col in zip([5,10,15],['#777777','#287bab','#dc8a26']):
 p=next((B/'XRD'/f'{m}min/1h').glob('*.txt'));x,y=np.loadtxt(p,skiprows=2,encoding='utf-8-sig').T;smooth=np.convolve(y,np.ones(5)/5,'same');norm=smooth[(x>=13.4)&(x<=14.7)].max();axes[0].plot(x,smooth/norm,label=f'{m}分',color=col)
axes[0].set_xlim(11.5,14.9);axes[0].set_xlabel('2θ (°)');axes[0].set_ylabel('約14°最大値で規格化（背景込み）');axes[0].set_title('各膜の公称1h XRD');axes[0].legend();axes[0].grid(alpha=.2)
for i,r in enumerate(paired):
 if r['xrd_1h_low_main_area_min'] is None:axes[1].text(i,.025,'抽出不成立\n≠ゼロ',ha='center',fontsize=11)
 else:
  low=r['xrd_1h_low_main_area_min'];high=r['xrd_1h_low_main_area_max'];axes[1].plot([i,i],[low,high],color=['#777777','#287bab','#dc8a26'][i],lw=8);axes[1].scatter([i],[(low+high)/2],color='black',s=20)
axes[1].set_xlim(-.5,2.5);axes[1].set_ylim(0,.7);axes[1].set_xticks(range(3),['5分','10分','15分']);axes[1].set_ylabel('副相候補／主相候補の面積比');axes[1].set_title('3通りの背景処理による範囲');axes[1].grid(axis='y',alpha=.2)
fig.suptitle('15分膜の副相候補信号は大きい／相の含有率ではない');fig.tight_layout(rect=[0,0,1,.92]);save(fig,'03_対応するXRD')
