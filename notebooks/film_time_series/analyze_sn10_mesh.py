"""Spatial 8x8 /4x4 description of full cropped substrates, nominal1h three films."""
from pathlib import Path
import csv,json,hashlib,sys
import numpy as np,cv2
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import fontManager
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'notebooks/capture_repeatability'))
from analyze_repeatability import corners_and_bbox
B=ROOT/'data/raw/Touma/FACsSnPbI3(Sn10mol%)_SnF2_0.1mol%/20261112';O=ROOT/'results/20261113/04_mesh_8x8';O.mkdir(parents=True,exist_ok=True);(O/'images').mkdir(exist_ok=True)
FIT=[(785,555),(1585,555),(1185,250),(1185,855)];cells=[];whole=[];manifest=[];cornerslog=[];maps={};cropimages={}
fontManager.addfont('/mnt/c/Windows/Fonts/YuGothR.ttc');plt.rcParams.update({'font.family':'Yu Gothic','font.size':12})
def write(name,rs):
 with (O/name).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rs[0]));w.writeheader();w.writerows(rs)
def save(fig,name):fig.savefig(O/(name+'.png'),dpi=150,bbox_inches='tight');fig.savefig(O/(name+'.pdf'),bbox_inches='tight');plt.close(fig)
def load(p):
 a=np.array(Image.open(p).convert('RGB'));corners,_=corners_and_bbox(a);t=cv2.getPerspectiveTransform(corners,np.float32([[0,0],[255,0],[255,255],[0,255]]));return a,cv2.warpPerspective(a,t,(256,256)).astype(float),corners
getbg=lambda a:np.mean([a[y-20:y+20,x-20:x+20].mean((0,1)) for x,y in FIT],axis=0)
ref=next((B/'5min/1h').glob('*.jpg'));a,_,_=load(ref);refbg=getbg(a)
for m in [5,10,15]:
 p=next((B/f'{m}min/1h').glob('*.jpg'));a,raw,corners=load(p);bg=getbg(a);gain=refbg/bg;meta=json.loads(p.with_suffix('.json').read_text());assert meta['fixed_settings_verified'];cornerslog.append({'anneal_min':m,'corners':corners.tolist(),'input_size':list(a.shape[:2][::-1]),'gain_RGB':gain.tolist()})
 for f,kind in [(p,'photo'),(p.with_suffix('.json'),'metadata')]:manifest.append({'path':str(f.relative_to(ROOT)),'kind':kind,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()})
 for mode in ['raw','common_corrected']:
  rgb=raw if mode=='raw' else raw*gain;g=rgb[:,:,0]*.2126+rgb[:,:,1]*.7152+rgb[:,:,2]*.0722;smooth=cv2.GaussianBlur(g,(0,0),8);contrast=(g-smooth)/np.maximum(smooth,1);binary=(contrast>.1).astype(np.uint8);_,labels,stats,_=cv2.connectedComponentsWithStats(binary,8);valid=np.flatnonzero(stats[1:,cv2.CC_STAT_AREA]>=3)+1;spots=np.isin(labels,valid);fine=cv2.GaussianBlur(g,(0,0),.7)-cv2.GaussianBlur(g,(0,0),3)
  whole.append({'anneal_min':m,'color_mode':mode,'mean_R':float(rgb[:,:,0].mean()),'mean_G':float(rgb[:,:,1].mean()),'mean_B':float(rgb[:,:,2].mean()),'bright_area_percent':float(spots.mean()*100)})
  for n in [8,4]:
   step=256//n
   for row in range(n):
    for col in range(n):
     ys=slice(row*step,(row+1)*step);xs=slice(col*step,(col+1)*step);block=rgb[ys,xs];gray=g[ys,xs];sp=spots[ys,xs];r={'anneal_min':m,'elapsed_label':'1h','color_mode':mode,'grid':n,'row':row+1,'column':col+1,'pixels':step*step,'x0':col*step,'y0':row*step,'mean_R':float(block[:,:,0].mean()),'mean_G':float(block[:,:,1].mean()),'mean_B':float(block[:,:,2].mean()),'sd_R':float(block[:,:,0].std()),'sd_G':float(block[:,:,1].std()),'sd_B':float(block[:,:,2].std()),'gray_mean':float(gray.mean()),'gray_sd':float(gray.std()),'gray_cv':float(gray.std()/max(gray.mean(),1)),'bright_pixels':int(sp.sum()),'bright_area_percent':float(sp.mean()*100),'relative_fine_sd':float(fine[ys,xs].std()/max(gray.mean(),1))};cells.append(r)
  if mode=='common_corrected':cropimages[m]=np.rint(np.clip(rgb,0,255)).astype(np.uint8);maps[m]={'spots':spots};Image.fromarray(cropimages[m]).save(O/'images'/f'{m}min_1h_corrected.png')
write('mesh_cells.csv',cells);write('whole_image.csv',whole)
# Exact consistency of equal-area partitions (RGB means and binary occupancy).
for m in [5,10,15]:
 for mode in ['raw','common_corrected']:
  w=next(r for r in whole if r['anneal_min']==m and r['color_mode']==mode)
  for n in [4,8]:
   rr=[r for r in cells if r['anneal_min']==m and r['color_mode']==mode and r['grid']==n];assert sum(r['pixels'] for r in rr)==65536
   for key in ['mean_R','mean_G','mean_B','bright_area_percent']:assert abs(np.mean([r[key] for r in rr])-w[key])<1e-10
  for row in range(4):
   for col in range(4):
    big=next(r for r in cells if r['anneal_min']==m and r['color_mode']==mode and r['grid']==4 and r['row']==row+1 and r['column']==col+1);small=[r for r in cells if r['anneal_min']==m and r['color_mode']==mode and r['grid']==8 and r['row'] in [2*row+1,2*row+2] and r['column'] in [2*col+1,2*col+2]]
    for key in ['mean_R','mean_G','mean_B','bright_area_percent']:assert abs(np.mean([r[key] for r in small])-big[key])<1e-10
summary=[]
for m in [5,10,15]:
 for n in [4,8]:
  rr=[r for r in cells if r['anneal_min']==m and r['color_mode']=='common_corrected' and r['grid']==n];areas=np.array([r['bright_area_percent'] for r in rr]);maximum=max(rr,key=lambda r:r['bright_area_percent']);central=[r for r in rr if n//4<r['row']<=3*n//4 and n//4<r['column']<=3*n//4];outer=[r for r in rr if r['row'] in [1,n] or r['column'] in [1,n]]
  summary.append({'anneal_min':m,'grid':n,'whole_bright_area_percent':float(areas.mean()),'cell_bright_area_median_percent':float(np.median(areas)),'cell_bright_area_min_percent':float(areas.min()),'cell_bright_area_max_percent':float(areas.max()),'max_cell_row':maximum['row'],'max_cell_column':maximum['column'],'central128px_mean_bright_area_percent':float(np.mean([r['bright_area_percent'] for r in central])),'outermost_cell_band_mean_bright_area_percent':float(np.mean([r['bright_area_percent'] for r in outer])),'outer_band_width_px':256//n})
write('mesh_summary.csv',summary)
(O/'input_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2));(O/'analysis_config.json').write_text(json.dumps({'independent_films':3,'time_label':'nominal1h, not precise simultaneous XRD','grids':[8,4],'canonical_size':256,'cell_pixels':{'8x8':'32x32','4x4':'64x64'},'perimeter_exclusion':False,'ellipse_exclusion':False,'common_reference':str(ref.relative_to(ROOT)),'fit_centers':FIT,'spot_extraction':'computed once over full256 image, sigma8 local contrast>.1,connected pixels>=3, then partitioned; no cell-specific threshold','fine_pattern':'Gaussian sigma0.7 minus3, computed over full image then partitioned','cells_not_independent_samples':True,'coordinates':'row1=top,column1=left in detected substrate orientation; separate films have no shared physical feature coordinates','registration':cornerslog,'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},ensure_ascii=False,indent=2))
print('SUMMARY',json.dumps(summary,ensure_ascii=False))
fig,axes=plt.subplots(1,3,figsize=(12,4.6))
for ax,m in zip(axes,[5,10,15]):
 ax.imshow(cropimages[m],extent=(0,8,8,0));ax.set_xticks(np.arange(8)+.5,[str(i) for i in range(1,9)]);ax.set_yticks(np.arange(8)+.5,[str(i) for i in range(1,9)]);ax.set_xticks(np.arange(9),minor=True);ax.set_yticks(np.arange(9),minor=True);ax.grid(which='minor',color='white',alpha=.8,lw=.6);ax.tick_params(which='minor',length=0);ax.set_title(f'{m}分膜・公称1h');ax.set_xlabel('列');ax.set_ylabel('行')
fig.suptitle('膜画像を8×8＝64区画へ分割／1区画32×32画素／外周も解析');fig.tight_layout(rect=[0,0,1,.92]);save(fig,'01_8x8の区画')
def array(m,n,key):
 rr=[r for r in cells if r['anneal_min']==m and r['color_mode']=='common_corrected' and r['grid']==n];return np.array([r[key] for r in rr]).reshape(n,n)
fig,axes=plt.subplots(2,3,figsize=(12,9));vmax=max(array(m,n,'bright_area_percent').max() for m in [5,10,15] for n in [8,4])
for i,n in enumerate([8,4]):
 for j,m in enumerate([5,10,15]):
  ax=axes[i,j];arr=array(m,n,'bright_area_percent');im=ax.imshow(arr,cmap='magma',vmin=0,vmax=vmax);ax.set_xticks(range(n),range(1,n+1));ax.set_yticks(range(n),range(1,n+1));ax.set_title(f'{m}分膜：{n}×{n}');ax.set_xlabel('列');ax.set_ylabel('行')
  for row in range(n):
   for col in range(n):ax.text(col,row,f'{arr[row,col]:.0f}',ha='center',va='center',fontsize=7 if n==8 else 11,color='black' if arr[row,col]>.6*vmax else 'white')
fig.suptitle('明るい斑点候補の面積割合 (%)／上8×8・下4×4／全図で色の尺度は共通');fig.tight_layout(rect=[0,0,.9,.94]);fig.colorbar(im,ax=list(axes.flat),fraction=.025,pad=.03,label='候補面積 (%)');save(fig,'02_斑点面積の分布')
fig,axes=plt.subplots(3,3,figsize=(12,11))
for j,c in enumerate('RGB'):
 vals=[array(m,8,'mean_'+c) for m in [5,10,15]];vmin=min(a.min() for a in vals);vmax=max(a.max() for a in vals)
 for i,m in enumerate([5,10,15]):
  ax=axes[i,j];im=ax.imshow(vals[i],cmap=['Reds','Greens','Blues'][j],vmin=vmin,vmax=vmax);ax.set_title(f'{m}分膜：平均{c}');ax.set_xticks(range(8),range(1,9));ax.set_yticks(range(8),range(1,9))
 fig.colorbar(im,ax=list(axes[:,j]),shrink=.65,label='JPEG '+c)
fig.suptitle('8×8区画の平均RGB／同じ成分は3膜で共通尺度／色校正値ではない');fig.subplots_adjust(top=.91,hspace=.4,wspace=.4);save(fig,'03_区画ごとの平均RGB')
fig,axes=plt.subplots(1,3,figsize=(12,4.5));vmax=max(array(m,8,'gray_cv').max() for m in [5,10,15])
for ax,m in zip(axes,[5,10,15]):
 im=ax.imshow(array(m,8,'gray_cv'),cmap='viridis',vmin=0,vmax=vmax);ax.set_title(f'{m}分膜');ax.set_xticks(range(8),range(1,9));ax.set_yticks(range(8),range(1,9));ax.set_xlabel('列');ax.set_ylabel('行')
fig.suptitle('区画内の明るさのばらつき／平均 (CV)／明るいほど値が大きい');fig.subplots_adjust(top=.84,right=.88,wspace=.3);fig.colorbar(im,ax=list(axes),fraction=.03,pad=.03,label='明るさCV');save(fig,'04_区画内の色むら')
