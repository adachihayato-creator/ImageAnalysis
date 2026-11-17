"""Register cropped film images, apply existing background gains, analyze fixed ROIs.
Dependencies: numpy, Pillow, matplotlib, opencv-python-headless.
Run from any directory. No input files are modified.
"""
from pathlib import Path
import csv,json
import numpy as np
from PIL import Image
import cv2
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[2];DAY=ROOT/'results/20261015';OUT=DAY/'04_image_time_series'
TAGS=['BrRb_1','BrRb_2','Sn25_1','Sn25_2'];COLORS=['#1768ac','#63a6d4','#bd4a16','#e89b34']
# Conservative, manually selected potential reflection regions in 0 h normalized coordinates.
# These are hypotheses about optical artifacts, not automatic defect identification.
EXCLUDE={'BrRb_1':[(.52,.50,.13,.17)],'BrRb_2':[(.52,.49,.13,.14),(.18,.78,.18,.14)],'Sn25_1':[],'Sn25_2':[]}

def save(fig,path):
 fig.savefig(path.with_suffix('.png'),dpi=160,bbox_inches='tight');fig.savefig(path.with_suffix('.pdf'),bbox_inches='tight');plt.close(fig)

def feature(a):
 gray=cv2.cvtColor(a.astype(np.uint8),cv2.COLOR_RGB2GRAY).astype(np.float32)
 # High-pass removes broad illumination gradients; spatial texture and edges remain.
 return (cv2.GaussianBlur(gray,(0,0),.8)-cv2.GaussianBlur(gray,(0,0),5)).astype(np.float32)

def corr(a,b,mask):
 x=a[mask].ravel();y=b[mask].ravel()
 return float(np.corrcoef(x,y)[0,1])

def register_single(ref,mov):
 h,w=ref.shape[:2];res=cv2.resize(mov,(w,h),interpolation=cv2.INTER_LINEAR)
 rf,mf=feature(ref),feature(res);warp=np.eye(2,3,dtype=np.float32)
 score,warp=cv2.findTransformECC(rf,mf,warp,cv2.MOTION_AFFINE,(cv2.TERM_CRITERIA_COUNT|cv2.TERM_CRITERIA_EPS,500,1e-6),None,3)
 sv=np.linalg.svd(warp[:,:2],compute_uv=False);angle=float(np.degrees(np.arctan2(warp[1,0],warp[0,0])))
 if not (.88<sv.min()<=sv.max()<1.12 and abs(angle)<10 and np.max(np.abs(warp[:,2]))<35):raise RuntimeError(f'Implausible transform {warp}')
 aligned=cv2.warpAffine(res.astype(np.float32),warp,(w,h),flags=cv2.INTER_LINEAR|cv2.WARP_INVERSE_MAP,borderMode=cv2.BORDER_CONSTANT)
 valid=cv2.warpAffine(np.ones((h,w),np.uint8),warp,(w,h),flags=cv2.INTER_NEAREST|cv2.WARP_INVERSE_MAP)>0
 # Remove interpolation boundary pixels.
 valid=cv2.erode(valid.astype(np.uint8),np.ones((5,5),np.uint8))>0
 return aligned,valid,{'ecc_score':float(score),'warp_reference_to_resized_input':warp.tolist(),'resize_from':list(mov.shape[:2]),'resize_to':[h,w],'rotation_deg':angle,'linear_singular_values':sv.tolist(),'feature_correlation_before':corr(rf,mf,np.ones((h,w),bool)),'feature_correlation_after':corr(rf,feature(aligned),valid)}

def register(ref,mov):
 candidates=[]
 for k in range(4):
  try:
   aligned,valid,rec=register_single(ref,np.rot90(mov,k).copy())
   rec['coarse_rotation_ccw_degrees']=k*90
   candidates.append((rec['feature_correlation_after'],aligned,valid,rec))
  except (RuntimeError,cv2.error):
   continue
 if not candidates:raise RuntimeError('No valid rotation/affine candidate')
 _,aligned,valid,rec=max(candidates,key=lambda c:c[0])
 h,w=ref.shape[:2]
 rec['feature_correlation_before']=corr(feature(ref),feature(cv2.resize(mov,(w,h))),np.ones((h,w),bool))
 rec['low_alignment_confidence']=rec['feature_correlation_after']<.4
 return aligned,valid,rec

def mask_for(h,w,margin,valid,tag,exclude=True):
 yy,xx=np.mgrid[:h,:w];xn=xx/(w-1);yn=yy/(h-1)
 m=(xn>=margin)&(xn<=1-margin)&(yn>=margin)&(yn<=1-margin)&valid
 if exclude:
  for cx,cy,rx,ry in EXCLUDE[tag]:m&=((xn-cx)/rx)**2+((yn-cy)/ry)**2>1
 return m

def writecsv(path,rows):
 with path.open('w',encoding='utf-8-sig',newline='') as fp:
  wr=csv.DictWriter(fp,fieldnames=list(rows[0]));wr.writeheader();wr.writerows(rows)

def main():
 OUT.mkdir(parents=True,exist_ok=True)
 meta=json.loads((DAY/'02_background_correction/metadata.json').read_text())
 old=list(csv.DictReader((DAY/'02_background_correction/rgb_summary.csv').open(encoding='utf-8-sig')))
 patches=list(csv.DictReader((DAY/'02_background_correction/background_patches.csv').open(encoding='utf-8-sig')))
 measurements=[];sensitivity=[];registration=[];previews=[]
 for tag in TAGS:
  dest=OUT/tag;dest.mkdir(exist_ok=True)
  arrays=[];valids=[];gains=[];ref=None;processed=[]
  for t in range(4):
   info=next(m for m in meta if m['sample']==tag and m['hour']==t)
   a=np.asarray(Image.open(ROOT/info['processed']).convert('RGB'))
   if t==0:
    ref=a;aligned=a.astype(float);valid=np.ones(a.shape[:2],bool)
    rec={'ecc_score':1.,'warp_reference_to_resized_input':np.eye(2,3).tolist(),'resize_from':list(a.shape[:2]),'resize_to':list(a.shape[:2]),'rotation_deg':0.,'coarse_rotation_ccw_degrees':0,'low_alignment_confidence':False,'linear_singular_values':[1.,1.],'feature_correlation_before':1.,'feature_correlation_after':1.}
   else:aligned,valid,rec=register(ref,a)
   registration.append({'sample':tag,'hour':t,**rec})
   row=next(r for r in old if r['sample']==tag and int(r['hour'])==t)
   gain=np.array([float(row['gain_'+ch]) for ch in 'RGB'])
   arrays.append(aligned);valids.append(valid);gains.append(gain);processed.append(a)
  raw=np.array(arrays);cal=raw*np.array(gains)[:,None,None,:];common=np.logical_and.reduce(valids);h,w=ref.shape[:2]
  mainmask=mask_for(h,w,.18,common,tag);np.save(dest/'analysis_mask.npy',mainmask)
  Image.fromarray((mainmask*255).astype(np.uint8)).save(dest/'analysis_mask.png')
  for t in range(4):
   Image.fromarray(np.clip(np.rint(cal[t]),0,255).astype(np.uint8)).save(dest/f'{t}h_aligned_corrected.png')
   diff=cal[t]-cal[0];distance=np.linalg.norm(diff,axis=2)
   np.savez_compressed(dest/f'{t}h_color_difference.npz',delta_rgb=diff.astype(np.float32),rgb_distance=distance.astype(np.float32),analysis_mask=mainmask)
   row={'sample':tag,'hour':t,'roi_pixels':int(mainmask.sum()),'roi_fraction':float(mainmask.mean()),'mean_pixel_rgb_distance':float(distance[mainmask].mean()),'median_pixel_rgb_distance':float(np.median(distance[mainmask]))}
   for j,ch in enumerate('RGB'):
    row['raw_mean_'+ch]=float(raw[t][mainmask,j].mean());row['corrected_mean_'+ch]=float(cal[t][mainmask,j].mean())
    row['raw_delta_'+ch]=float((raw[t]-raw[0])[mainmask,j].mean());row['corrected_delta_'+ch]=float(diff[mainmask,j].mean())
   row['rgb_distance_of_means']=float(np.linalg.norm([row['corrected_delta_'+ch] for ch in 'RGB']))
   measurements.append(row)
   for margin in [.12,.18,.24]:
    for exclude in [False,True]:
     # Duplicate no-exclusion cases are intentional for a consistent sensitivity table.
     m=mask_for(h,w,margin,common,tag,exclude)
     rr={'sample':tag,'hour':t,'margin_fraction':margin,'reflection_excluded':exclude,'pixels':int(m.sum())}
     delta=(cal[t]-cal[0])[m].mean(axis=0)
     for j,ch in enumerate('RGB'):rr['delta_'+ch]=float(delta[j])
     rr['rgb_distance_of_means']=float(np.linalg.norm(delta));sensitivity.append(rr)
  # Show actual masks and fixed-scale maps, not per-panel contrast stretching.
  fig,axs=plt.subplots(3,4,figsize=(12,8.8),layout='constrained')
  for t in range(4):
   axs[0,t].imshow(np.clip(cal[t]/255,0,1));axs[0,t].contour(mainmask,levels=[.5],colors=['lime'],linewidths=.8);axs[0,t].set_title(f'{tag}: {t} h, corrected')
   d=np.linalg.norm(cal[t]-cal[0],axis=2);d=np.ma.array(d,mask=~mainmask)
   im=axs[1,t].imshow(d,cmap='magma',vmin=0,vmax=50);axs[1,t].set_title('RGB distance from 0 h' + (' [LOW ALIGNMENT]' if next(r for r in registration if r['sample']==tag and r['hour']==t)['low_alignment_confidence'] else ''),fontsize=9)
   dr=np.ma.array((cal[t]-cal[0])[:,:,0],mask=~mainmask)
   imr=axs[2,t].imshow(dr,cmap='coolwarm',vmin=-30,vmax=30);axs[2,t].set_title('Signed red change from 0 h')
   for ax in axs[:,t]:ax.axis('off')
  fig.colorbar(im,ax=list(axs[1]),shrink=.6,label='JPEG RGB distance (fixed 0–50)');fig.colorbar(imr,ax=list(axs[2]),shrink=.6,label='JPEG R units (fixed -30 to 30)')
  fig.suptitle('Color change only; green outline = analysis region; masked areas not evaluated',fontsize=11)
  save(fig,dest/'color_change_maps')
  fig,axs=plt.subplots(2,4,figsize=(12,6.5),layout='constrained')
  for t in range(4):
   a=cv2.resize(processed[t],(w,h));before=(ref.astype(float)+a)/2;after=(ref.astype(float)+raw[t])/2
   # Edge contours on reference aid visual check without assuming unchanged color.
   axs[0,t].imshow(before.astype(np.uint8));axs[0,t].set_title(f'{t} h: before alignment')
   axs[1,t].imshow(after.astype(np.uint8));axs[1,t].set_title(f'{t} h: after alignment')
   for ax in axs[:,t]:ax.axis('off')
  fig.suptitle('50/50 overlays with 0 h: double edges indicate mismatch');save(fig,dest/'registration_check')
  # Color changes under each of four independently selected background patches.
  for t in range(4):
   for p in range(4):
    pr=next(r for r in patches if r['sample']==tag and int(r['hour'])==t and int(r['patch'])==p)
    g=np.array([float(pr['gain_'+ch]) for ch in 'RGB']);delta=(raw[t]*g-raw[0])[mainmask].mean(axis=0)
    rr={'sample':tag,'hour':t,'background_patch':p}
    for j,ch in enumerate('RGB'):rr['delta_'+ch]=float(delta[j])
    rr['rgb_distance_of_means']=float(np.linalg.norm(delta));previews.append(rr)
 writecsv(OUT/'aligned_rgb.csv',measurements);writecsv(OUT/'roi_sensitivity.csv',sensitivity);writecsv(OUT/'background_sensitivity.csv',previews)
 (OUT/'registration.json').write_text(json.dumps(registration,indent=2))
 (OUT/'analysis_config.json').write_text(json.dumps({'main_margin':.18,'sensitivity_margins':[.12,.18,.24],'potential_reflection_ellipses_normalized':EXCLUDE,'map_rgb_distance_max':50,'map_delta_R_range':[-30,30]},indent=2))
 overview(measurements,sensitivity,previews)
 report(measurements,registration,sensitivity,previews)
 print(json.dumps(registration,indent=2))

def overview(rows,sens,bgs):
 fig,axs=plt.subplots(2,3,figsize=(13,8),layout='constrained')
 for j,ch in enumerate('RGB'):
  for k,tag in enumerate(TAGS):
   rr=[r for r in rows if r['sample']==tag];ts=[r['hour'] for r in rr]
   axs[0,j].plot(ts,[r['corrected_delta_'+ch] for r in rr],'-o',color=COLORS[k],label=tag)
   axs[0,j].plot(ts,[r['raw_delta_'+ch] for r in rr],'--',color=COLORS[k],alpha=.6)
   # min/max of alternate ROI choices: sensitivity, not uncertainty interval.
   lo=[];hi=[]
   for t in ts:
    vals=[r['delta_'+ch] for r in sens if r['sample']==tag and r['hour']==t];lo.append(min(vals));hi.append(max(vals))
   axs[1,j].plot(ts,[r['corrected_delta_'+ch] for r in rr],'-o',color=COLORS[k]);axs[1,j].fill_between(ts,lo,hi,color=COLORS[k],alpha=.14)
  for ax in axs[:,j]:ax.axhline(0,color='gray',lw=.6);ax.set(xlabel='Time (h)',ylabel=f'Delta {ch} (JPEG units)',xticks=[0,1,2,3]);ax.grid(alpha=.2)
  axs[0,j].set_title(f'{ch}: solid corrected / dashed uncorrected');axs[1,j].set_title(f'{ch}: shaded = alternate ROI range')
 axs[0,0].legend(fontsize=9);fig.suptitle('Registered images: raw/corrected trends and ROI sensitivity (not confidence intervals)');save(fig,OUT/'rgb_time_series')
 fig,axs=plt.subplots(1,3,figsize=(13,4.5),layout='constrained')
 for j,ch in enumerate('RGB'):
  for k,tag in enumerate(TAGS):
   rr=[r for r in rows if r['sample']==tag];ts=[r['hour'] for r in rr]
   lo=[];hi=[]
   for t in ts:
    v=[r['delta_'+ch] for r in bgs if r['sample']==tag and r['hour']==t];lo.append(min(v));hi.append(max(v))
   axs[j].plot(ts,[r['corrected_delta_'+ch] for r in rr],'-o',color=COLORS[k],label=tag);axs[j].fill_between(ts,lo,hi,color=COLORS[k],alpha=.14)
  axs[j].set(xlabel='Time (h)',ylabel=f'Delta {ch} (JPEG units)',xticks=[0,1,2,3]);axs[j].grid(alpha=.2)
 axs[0].legend(fontsize=9);fig.suptitle('Sensitivity to background choice: shaded = four separate patch corrections, not error bars');save(fig,OUT/'background_sensitivity')

def report(rows,reg,sens,bgs):
 lines=['# 4膜の位置合わせと色変化解析','',
 '対象：2026-10-15、4膜×0–3 h。既存の背景補正係数を使用。XRDはこの解析に使用していません。','',
 '## 方法','',
 '各膜の0 hの切り抜き画像を基準に、他時点の画像を0/90/180/270°の各候補で比較したうえで同じ寸法にリサイズし、照明の広い勾配を抑えた高域通過グレースケール画像でECCアフィン位置合わせを実施。係数・相関・変換行列はregistration.jsonに記録。変換は幾何学的補正のみで、膜のRGB値を0 hに合わせる処理ではありません。',
 '', 'その後、背景から既に求めたチャネル別係数を適用。全時点で有効な共通画素のうち外周18%を除いた領域を主解析に使用。BrRb系は0 hで見られる潜在的な反射の領域を保守的に楕円除外（analysis_config.json）。この判別は暫定であり、全反射を除去した保証はありません。Sn系の斑点は0 hから存在する試料模様として一律除外していません。',
 '', '各膜のマップの緑線は解析領域。黒/空白部分は解析対象外。RGB距離はsqrt(ΔR²+ΔG²+ΔB²)で、色知覚のΔEでも劣化率でもありません。マップの尺度は全膜・全時点で共通。50を超えるRGB距離は表示のみ飽和し、保存NPZとCSVには実値を保持しています。',
 '', '## 0→3 hの主領域の結果','', '|膜|ΔR|ΔG|ΔB|平均RGBの距離|','|---|---:|---:|---:|---:|']
 for tag in TAGS:
  r=next(r for r in rows if r['sample']==tag and r['hour']==3)
  lines.append(f"|{tag}|{r['corrected_delta_R']:.2f}|{r['corrected_delta_G']:.2f}|{r['corrected_delta_B']:.2f}|{r['rgb_distance_of_means']:.2f}|")
 lines+=['','## 位置合わせの検証','', '|膜|時点|高域画像の相関：前→後|粗回転＋微調整(°)|','|---|---:|---:|---:|']
 for r in reg:
  if r['hour']:lines.append(f"|{r['sample']}|{r['hour']}|{r['feature_correlation_before']:.3f} → {r['feature_correlation_after']:.3f}|{r['coarse_rotation_ccw_degrees']} + {r['rotation_deg']:.2f}|")
 lines+=['','高域画像の位置合わせ後相関が0.4未満の画像はLOW ALIGNMENTと表示（運用上の注意基準であり、校正された誤差基準ではありません）。細かな場所の比較は参考扱いです。各膜のregistration_check.pngで50%重ね合わせを確認してください。相関向上は見た目の位置合わせの指標で、物理的な位置精度や材料不変の証明ではありません。','',
 '## 感度確認','',
 '外周除外を12/18/24%に変更し、潜在反射の楕円除外あり/なしで再集計（roi_sensitivity.csv）。上下左右それぞれ単独の背景から補正した場合も再集計（background_sensitivity.csv）。図の帯は選択条件による範囲で、反復撮影から求めた誤差・信頼区間ではありません。','',
 '## 解釈の限界','',
 '- 自動位置合わせは表面模様・輪郭を使います。実変化・反射の移動が変換推定へ影響する可能性があり、サブピクセル精度を保証しません。アフィン変換は傾きによる色変化を補正しません。',
 '- 画像再標本化による補間を含み、元画像の解像度は約240 px角です。細かい傷や亀裂の幅・発生を断定しません。既存の線や反射も色変化として写り得ます。',
 '- 色変化の統計的有意性・化学的劣化・相変化は判定しません。各時点の反復撮影がなく、同組成2膜では一般化できません。',
 '- 背景補正後にも位置・照明むら・反射の影響が残ります。小さい変化や領域選択で方向が変わる変化は保留してください。',
 '', '## ファイル','', '- rgb_time_series.png/pdf：補正前後の時間変化とROI選択感度','- background_sensitivity.png/pdf：背景選択感度','- aligned_rgb.csv：主領域の数値','- 各膜/color_change_maps.png/pdf：補正済み画像と色変化マップ','- 各膜/registration_check.png/pdf：位置合わせの確認','- 各膜/*h_aligned_corrected.png：位置合わせ済み補正画像16枚','- 各膜/*h_color_difference.npz：数値マップと解析マスク','',
 '再実行：python3 notebooks/film_time_series/aligned_color_analysis.py（numpy、Pillow、matplotlib、opencv-python-headlessが必要）。']
 (OUT/'report.md').write_text('\n'.join(lines),encoding='utf-8')
if __name__=='__main__':main()
