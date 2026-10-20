"""Analyze 0,1,2,3,4,5,24 h without modifying the previous 02–04 outputs.
Requires numpy, Pillow, OpenCV and matplotlib. All comparisons reference 0 h.
"""
from pathlib import Path
import csv,json,hashlib,shutil
import numpy as np
from PIL import Image,ImageDraw
import cv2
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from background_correction import bbox,boxes,region,GROUPS
from aligned_color_analysis import register,mask_for,feature,corr
ROOT=Path(__file__).resolve().parents[2];DAY=ROOT/'data/processed/20261015';OUT=DAY/'05_image_time_series_0to24h'
TIMES=[0,1,2,3,4,5,24];TAGS=['BrRb_1','BrRb_2','Sn25_1','Sn25_2'];COLORS=['#1768ac','#63a6d4','#bd4a16','#e89b34']

def csvsave(name,rows):
 with (OUT/name).open('w',newline='',encoding='utf-8-sig') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def save(fig,path):
 fig.savefig(path.with_suffix('.png'),dpi=150,bbox_inches='tight');fig.savefig(path.with_suffix('.pdf'),bbox_inches='tight');plt.close(fig)

def apply_warp(ref,mov,rec):
 h,w=ref.shape[:2];k=rec['coarse_rotation_ccw_degrees']//90
 inp=cv2.resize(np.rot90(mov,k).copy(),(w,h),interpolation=cv2.INTER_LINEAR)
 warp=np.array(rec['warp_reference_to_resized_input'],np.float32)
 aligned=cv2.warpAffine(inp.astype(np.float32),warp,(w,h),flags=cv2.INTER_LINEAR|cv2.WARP_INVERSE_MAP)
 v=cv2.warpAffine(np.ones((h,w),np.uint8),warp,(w,h),flags=cv2.INTER_NEAREST|cv2.WARP_INVERSE_MAP)>0
 return aligned,cv2.erode(v.astype(np.uint8),np.ones((5,5),np.uint8))>0

def main():
 OUT.mkdir(parents=True,exist_ok=True)
 oldhash={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for d in ['02_background_correction','03_xrd_comparison','04_image_time_series'] for p in (DAY/d).rglob('*') if p.is_file()}
 # Validate all inputs before generating any results.
 for group,(owner,material) in GROUPS.items():
  for s in [1,2]:
   for t in TIMES:
    for p in [ROOT/'data/raw'/owner/material/'10_15'/f'{s}枚目{t}h.jpg',DAY/'01_crops'/owner/material/f'{s}枚目{t}h.jpg']:assert p.is_file(),p
 oldreg=json.loads((DAY/'04_image_time_series/registration.json').read_text())
 summaries=[];background=[];patchrows=[];regs=[];sens=[];bgsens=[];meta=[];qcs=[];inputhash=[]
 for group,(owner,material) in GROUPS.items():
  for s in [1,2]:
   tag=f'{group}_{s}';dest=OUT/tag;dest.mkdir(exist_ok=True)
   arrays=[];valids=[];gains=[];patchgains=[];ref=None;reference=None;corrected=[]
   for t in TIMES:
    rp=ROOT/'data/raw'/owner/material/'10_15'/f'{s}枚目{t}h.jpg';cp=DAY/'01_crops'/owner/material/f'{s}枚目{t}h.jpg'
    for p in [rp,cp]:inputhash.append({'path':str(p.relative_to(ROOT)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
    im=Image.open(rp).convert('RGB');a=np.asarray(im,dtype=float);b=bbox(a);bs=boxes(b)
    for x0,y0,x1,y1 in bs:
     assert 0<=x0<x1<=im.width and 0<=y0<y1<=im.height
     assert x1<=b[0] or x0>=b[2] or y1<=b[1] or y0>=b[3]
    patches=np.array([np.median(region(a,z),axis=(0,1)) for z in bs])
    if t==0:reference=patches.copy()
    pg=reference/patches;gain=np.median(pg[:4],axis=0);gains.append(gain);patchgains.append(pg[:4])
    before=float(np.mean(np.abs((patches[4:]/reference[4:]-1)*100)))
    after=float(np.mean(np.abs((patches[4:]*gain/reference[4:]-1)*100)))
    spread=float(np.max(np.abs(pg[:4]/gain-1))*100)
    br={'sample':tag,'hour':t,'heldout_before_mae_percent':before,'heldout_after_mae_percent':after,'gain_spread_percent':spread}
    for j,ch in enumerate('RGB'):br['gain_'+ch]=float(gain[j])
    background.append(br)
    for pi,z in enumerate(bs):
     pr={'sample':tag,'hour':t,'patch':pi,'role':'fit' if pi<4 else 'held_out','box':str(z)}
     for j,ch in enumerate('RGB'):pr['median_'+ch]=float(patches[pi,j]);pr['gain_'+ch]=float(pg[pi,j])
     patchrows.append(pr)
    mov=np.asarray(Image.open(cp).convert('RGB'))
    if t==0:
     ref=mov;aligned=mov.astype(float);valid=np.ones(mov.shape[:2],bool)
     rec=next(dict(r) for r in oldreg if r['sample']==tag and r['hour']==0);rec['status']='reference'
    elif t<=3:
     rec=next(dict(r) for r in oldreg if r['sample']==tag and r['hour']==t);aligned,valid=apply_warp(ref,mov,rec);rec['status']='reused_previous_transform'
    else:
     try:
      aligned,valid,rec=register(ref,mov);rec={'sample':tag,'hour':t,**rec,'status':'registered'}
     except (RuntimeError,cv2.error) as err:
      # Do not silently turn failure into a confident alignment.
      h,w=ref.shape[:2];aligned=cv2.resize(mov,(w,h)).astype(float);valid=np.ones((h,w),bool)
      rec={'sample':tag,'hour':t,'status':'FAILED_resize_only','low_alignment_confidence':True,'feature_correlation_after':None,'coarse_rotation_ccw_degrees':0,'warp_reference_to_resized_input':np.eye(2,3).tolist(),'error':str(err)}
    if t>=4 and rec.get('feature_correlation_after') is not None and rec['feature_correlation_after']<.25:
     # Appearance changed too strongly: ECC can select a spurious 180-degree rotation.
     # Keep the photographed orientation and use the crop geometry only, explicitly provisional.
     attempted=dict(rec);h,w=ref.shape[:2];aligned=cv2.resize(mov,(w,h)).astype(float);valid=np.ones((h,w),bool)
     rec={'sample':tag,'hour':t,'status':'REVIEW_REQUIRED_resize_only','low_alignment_confidence':True,
       'feature_correlation_after':corr(feature(ref),feature(aligned),valid),'coarse_rotation_ccw_degrees':0,
       'warp_reference_to_resized_input':np.eye(2,3).tolist(),'rejected_unreliable_ecc_candidate':attempted,
       'reason':'Texture correlation below 0.25; orientation-sensitive local comparison not reliable. Resize-only provisional result.'}
    regs.append(rec);arrays.append(aligned);valids.append(valid)
    cal=aligned*gain;corrected.append(cal)
    Image.fromarray(np.clip(np.rint(cal),0,255).astype(np.uint8)).save(dest/f'{t}h_aligned_corrected.png')
    Image.fromarray(np.clip(np.rint(mov*gain),0,255).astype(np.uint8)).save(dest/f'{t}h_corrected.png')
    q=im.copy();q.thumbnail((800,450));scale=q.width/im.width;draw=ImageDraw.Draw(q)
    for pi,z in enumerate(bs):
     z=tuple(v*scale for v in z);draw.rectangle(z,outline='red' if pi<4 else 'blue',width=2)
    draw.rectangle(tuple(v*scale for v in b),outline='yellow',width=2);draw.text((10,10),f'{tag} {t}h',fill='black');qcs.append(q)
    meta.append({'sample':tag,'hour':t,'raw':str(rp.relative_to(ROOT)),'crop':str(cp.relative_to(ROOT)),'raw_size':im.size,'sample_bbox':b,'background_boxes':bs})
    print(tag,t,rec['status'],rec.get('feature_correlation_after'),flush=True)
   raw=np.array(arrays);cal=np.array(corrected);common=np.logical_and.reduce(valids);h,w=ref.shape[:2]
   mainmask=mask_for(h,w,.18,common,tag,False);excluded=mask_for(h,w,.18,common,tag,True)
   assert mainmask.sum()>1000
   Image.fromarray((mainmask*255).astype(np.uint8)).save(dest/'analysis_mask_with_ellipse.png')
   Image.fromarray((excluded*255).astype(np.uint8)).save(dest/'analysis_mask_excluded.png')
   for i,t in enumerate(TIMES):
    diff=cal[i]-cal[0];dist=np.linalg.norm(diff,axis=2)
    np.savez_compressed(dest/f'{t}h_color_difference.npz',delta_rgb=diff.astype(np.float32),rgb_distance=dist.astype(np.float32),analysis_mask=mainmask,excluded_mask=excluded)
    rec=next(r for r in regs if r['sample']==tag and r['hour']==t)
    for exclude,m in [(False,mainmask),(True,excluded)]:
     sr={'sample':tag,'hour':t,'reflection_excluded':exclude,'roi_pixels':int(m.sum()),'low_alignment_confidence':rec['low_alignment_confidence'],'mean_pixel_rgb_distance':float(dist[m].mean()),'median_pixel_rgb_distance':float(np.median(dist[m])),'map_above50_pixel_percent':float((dist[m]>50).mean()*100),'clipped_pixel_percent':float(np.any((cal[i]<0)|(cal[i]>255),axis=2)[m].mean()*100)}
     for j,ch in enumerate('RGB'):
      sr['raw_mean_'+ch]=float(raw[i][m,j].mean());sr['corrected_mean_'+ch]=float(cal[i][m,j].mean());sr['raw_delta_'+ch]=float((raw[i]-raw[0])[m,j].mean());sr['corrected_delta_'+ch]=float(diff[m,j].mean())
     sr['rgb_distance_of_means']=float(np.linalg.norm([sr['corrected_delta_'+ch] for ch in 'RGB']));summaries.append(sr)
    for margin in [.12,.18,.24]:
     for exclude in [False,True]:
      m=mask_for(h,w,margin,common,tag,exclude);delta=diff[m].mean(axis=0)
      sr={'sample':tag,'hour':t,'margin_fraction':margin,'reflection_excluded':exclude,'pixels':int(m.sum())}
      for j,ch in enumerate('RGB'):sr['delta_'+ch]=float(delta[j])
      sr['rgb_distance_of_means']=float(np.linalg.norm(delta));sens.append(sr)
    for pi,g in enumerate(patchgains[i]):
     delta=(raw[i]*g-raw[0])[mainmask].mean(axis=0);sr={'sample':tag,'hour':t,'background_patch':pi}
     for j,ch in enumerate('RGB'):sr['delta_'+ch]=float(delta[j])
     bgsens.append(sr)
   plots_for_sample(tag,cal,raw,mainmask,excluded,regs,sens)
   for ext in ["png","pdf"]:
    shutil.copy2(dest/f"color_change_maps_with_ellipse_all_times.{ext}",dest/f"color_change_maps_with_ellipse.{ext}")
    shutil.copy2(dest/f"color_change_maps_excluded_all_times.{ext}",dest/f"color_change_maps.{ext}")
 csvsave('aligned_rgb.csv',summaries);csvsave('background_validation.csv',background);csvsave('background_patches.csv',patchrows);csvsave('roi_sensitivity.csv',sens);csvsave('background_sensitivity.csv',bgsens)
 (OUT/'registration.json').write_text(json.dumps(regs,indent=2));(OUT/'metadata.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2));(OUT/'input_manifest.json').write_text(json.dumps(inputhash,ensure_ascii=False,indent=2))
 (OUT/'analysis_config.json').write_text(json.dumps({'times_h':TIMES,'reference_h':0,'main_roi_margin':.18,'main_ellipse_excluded':False,'map_limits':[0,50],'extended_map_limits':[0,200],'signed_component_limits':[-100,100],'nominal_times_from_filenames':True},indent=2))
 sheet=Image.new('RGB',(7*400,4*225),'white')
 for i,q in enumerate(qcs):sheet.paste(q.resize((400,225)),((i%7)*400,(i//7)*225))
 sheet.save(OUT/'background_regions.png')
 overview(summaries,sens,bgsens)
 report(summaries,background,regs)
 for p,sha in oldhash.items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==sha,p
 print('Completed; previous 02–04 result files unchanged.',flush=True)

def plots_for_sample(tag,cal,raw,mainmask,excluded,regs,sens):
 dest=OUT/tag
 for exclude,m,suffix in [(False,mainmask,'with_ellipse'),(True,excluded,'excluded')]:
  for ts,label,vmax in [(TIMES,'all_times',50),([0,4,5,24],'late_times',50),([0,4,5,24],'late_times_extended_scale',200)]:
   fig,axs=plt.subplots(3,len(ts),figsize=(3*len(ts),8.8),layout='constrained')
   for c,t in enumerate(ts):
    i=TIMES.index(t);diff=cal[i]-cal[0];d=np.linalg.norm(diff,axis=2);rec=next(r for r in regs if r['sample']==tag and r['hour']==t)
    axs[0,c].imshow(np.clip(cal[i]/255,0,1));axs[0,c].contour(m,levels=[.5],colors=['lime'],linewidths=.8);axs[0,c].set_title(f'{tag}: {t} h')
    im=axs[1,c].imshow(np.ma.array(d,mask=~m),cmap='magma',vmin=0,vmax=vmax);axs[1,c].set_title('RGB distance from 0 h'+(' [LOW ALIGNMENT]' if rec['low_alignment_confidence'] else ''),fontsize=9)
    imr=axs[2,c].imshow(np.ma.array(diff[:,:,0],mask=~m),cmap='coolwarm',vmin=-30,vmax=30);axs[2,c].set_title('Signed R change from 0 h',fontsize=10)
    for ax in axs[:,c]:ax.axis('off')
   fig.colorbar(im,ax=list(axs[1]),shrink=.6,label=f'JPEG RGB distance 0–{vmax}');fig.colorbar(imr,ax=list(axs[2]),shrink=.6,label='R change -30 to 30 (display clips)')
   fig.suptitle(f'Ellipse {"excluded" if exclude else "included"}; outer 18% removed; all differences reference 0 h; color change is not a degradation verdict',fontsize=11)
   save(fig,dest/f'color_change_maps_{suffix}_{label}')
 # Show all component maps with a common signed scale, no arbitrary preference for R.
 ts=[0,4,5,24];fig,axs=plt.subplots(3,4,figsize=(12,8.5),layout='constrained')
 for j,ch in enumerate('RGB'):
  for c,t in enumerate(ts):
   v=(cal[TIMES.index(t)]-cal[0])[:,:,j];im=axs[j,c].imshow(np.ma.array(v,mask=~mainmask),cmap='coolwarm',vmin=-100,vmax=100);axs[j,c].set_title(f'{t} h: delta {ch}');axs[j,c].axis('off')
 fig.colorbar(im,ax=list(axs.flat),shrink=.55,label='Signed JPEG RGB change from 0 h (-100 to 100)');fig.suptitle(f'{tag}: ellipse included, signed R/G/B maps (0,4,5,24 h)');save(fig,dest/'rgb_component_maps')
 fig,axs=plt.subplots(2,7,figsize=(21,6.5),layout='constrained')
 for c,t in enumerate(TIMES):
  axs[0,c].imshow(np.clip((raw[0]+raw[c])/510,0,1));axs[0,c].set_title(f'0h + {t}h overlay')
  axs[1,c].imshow(np.clip(cal[c]/255,0,1));axs[1,c].contour(mainmask,levels=[.5],colors=['lime']);rec=next(r for r in regs if r['sample']==tag and r['hour']==t);score=rec.get('feature_correlation_after');axs[1,c].set_title((f'corr={score:.3f}' if score is not None else 'ALIGNMENT FAILED')+(' [REVIEW]' if rec['low_alignment_confidence'] else ''))
  for ax in axs[:,c]:ax.axis('off')
 fig.suptitle(f'{tag}: geometric alignment diagnostic; large appearance changes can reduce confidence');save(fig,dest/'registration_check')
 # Three margins, inclusion vs exclusion, explicit curves.
 fig,axs=plt.subplots(3,3,figsize=(12,10),layout='constrained')
 for j,ch in enumerate('RGB'):
  vals=[r['delta_'+ch] for r in sens if r['sample']==tag];lo=min(vals);hi=max(vals);pad=max((hi-lo)*.1,.3)
  for i,margin in enumerate([.12,.18,.24]):
   for excluded,col,ls in [(False,'#e17717','--'),(True,'#1767b1','-')]:
    rr=[r for r in sens if r['sample']==tag and r['margin_fraction']==margin and r['reflection_excluded']==excluded]
    axs[i,j].plot([r['hour'] for r in rr],[r['delta_'+ch] for r in rr],ls+'o',color=col,label='ellipse excluded' if excluded else 'ellipse included')
   axs[i,j].set(title=f'Outer {margin:.0%} removed: {ch}',xlabel='Time (h)',ylabel=f'Delta {ch}',ylim=(lo-pad,hi+pad),xticks=[0,5,24]);axs[i,j].grid(alpha=.2)
 axs[0,0].legend(fontsize=9);fig.suptitle(f'{tag}: ROI sensitivity (real elapsed-time axis)');save(fig,dest/'roi_inclusion_comparison')

def overview(rows,sens,bgs):
 main=[r for r in rows if not r['reflection_excluded']]
 for ts,name in [(TIMES,'rgb_time_series_0to24h'),(TIMES[:-1],'rgb_time_series_0to5h')]:
  fig,axs=plt.subplots(2,3,figsize=(13,8),layout='constrained')
  for j,ch in enumerate('RGB'):
   for tag,col in zip(TAGS,COLORS):
    rr=[r for r in main if r['sample']==tag and r['hour'] in ts];x=[r['hour'] for r in rr]
    axs[0,j].plot(x,[r['corrected_delta_'+ch] for r in rr],'-o',color=col,label=tag);axs[0,j].plot(x,[r['raw_delta_'+ch] for r in rr],'--',color=col,alpha=.6)
    lo=[];hi=[]
    for t in x:
     v=[r['delta_'+ch] for r in sens if r['sample']==tag and r['hour']==t];lo.append(min(v));hi.append(max(v))
    axs[1,j].plot(x,[r['corrected_delta_'+ch] for r in rr],'-o',color=col);axs[1,j].fill_between(x,lo,hi,color=col,alpha=.14)
   for ax in axs[:,j]:ax.set(xlabel='Elapsed time (h)',ylabel=f'Mean {ch} change from 0 h');ax.grid(alpha=.2);ax.axhline(0,color='gray',lw=.5)
   axs[0,j].set_title(f'{ch}: solid corrected; dashed uncorrected');axs[1,j].set_title(f'{ch}: ROI sensitivity range')
  axs[0,0].legend(fontsize=9);fig.suptitle('Main ROI: outer 18% removed, ellipse included; actual time spacing');save(fig,OUT/name)
 fig,axs=plt.subplots(1,3,figsize=(13,4.5),layout='constrained')
 for j,ch in enumerate('RGB'):
  for tag,col in zip(TAGS,COLORS):
   rr=[r for r in main if r['sample']==tag];lo=[];hi=[]
   for t in TIMES:
    v=[r['delta_'+ch] for r in bgs if r['sample']==tag and r['hour']==t];lo.append(min(v));hi.append(max(v))
   axs[j].plot(TIMES,[r['corrected_delta_'+ch] for r in rr],'-o',color=col,label=tag);axs[j].fill_between(TIMES,lo,hi,color=col,alpha=.14)
  axs[j].set(xlabel='Elapsed time (h)',ylabel=f'Mean {ch} change from 0 h');axs[j].grid(alpha=.2)
 axs[0].legend(fontsize=9);fig.suptitle('Background patch-choice sensitivity: ellipse included; band is not measurement uncertainty');save(fig,OUT/'background_sensitivity')

def report(rows,bg,regs):
 main=[r for r in rows if not r['reflection_excluded']]
 lines=['# 0–24 hの膜画像経時変化解析','',
 '4膜 × 0・1・2・3・4・5・24 h＝28枚。過去の02〜04結果は上書きしていません。時刻はファイル名による公称値で、実際の撮影間隔の精度・保存環境の同一性は未確認です。','',
 '## 主な図','',
 '- [RGB時間変化：0–24 h](rgb_time_series_0to24h.png)（横軸は実時間間隔）','- [RGB時間変化：0–5 h拡大](rgb_time_series_0to5h.png)','- [背景選択感度](background_sensitivity.png)','- [背景領域の確認](background_regions.png)','',
 '主解析は外周18%を除いた中央領域、楕円内も含む条件。膜の端までを測った全体解析ではありません。各膜で全時点共通の有効画素を使用。0–3 hの変換行列は以前の結果を再利用、4・5・24 hは同じ回転候補＋ECCアフィン法で位置合わせしました。',
 '', '背景補正はrawの上下左右4領域の中央値から、各膜の0 hに対するRGB別係数の中央値を算出。未使用の斜め4領域で検証。線形反射率の校正ではありません。係数・領域・元ファイル・ハッシュはCSV/JSONに保存。',
 '', '## 24 hの色変化（0 h基準、主解析領域）','', '|膜|ΔR|ΔG|ΔB|平均RGBの距離|位置合わせ相関|','|---|---:|---:|---:|---:|---:|']
 for tag in TAGS:
  r=next(r for r in main if r['sample']==tag and r['hour']==24);rec=next(v for v in regs if v['sample']==tag and v['hour']==24);score=rec.get('feature_correlation_after');sc='失敗' if score is None else f'{score:.3f}'
  lines.append(f"|{tag}|{r['corrected_delta_R']:.2f}|{r['corrected_delta_G']:.2f}|{r['corrected_delta_B']:.2f}|{r['rgb_distance_of_means']:.2f}|{sc}|")
 lines+=['','## 各膜のマップ','', '|膜|0–24 h一覧|0・4・5・24 h|大きな変化を見る広い尺度|G/Bも含む成分別マップ|','|---|---|---|---|---|']
 for tag in TAGS:lines.append(f'|{tag}|[全時点]({tag}/color_change_maps_with_ellipse_all_times.png)|[後半]({tag}/color_change_maps_with_ellipse_late_times.png)|[0–200]({tag}/color_change_maps_with_ellipse_late_times_extended_scale.png)|[R/G/B]({tag}/rgb_component_maps.png)|')
 lines+=['','各膜フォルダには楕円除外条件（excluded）の同じマップも保存。Sn系は元々楕円を設定していないため一致します。マップは全て0 hとの差です。直前の時点との差ではありません。',
 '', '## 背景検証','', '|膜|時点|未使用背景の偏差：補正前→後(%)|補正係数の場所依存(%)|','|---|---:|---:|---:|']
 for r in bg:
  if r['hour'] in [4,5,24]:lines.append(f"|{r['sample']}|{r['hour']}|{r['heldout_before_mae_percent']:.2f} → {r['heldout_after_mae_percent']:.2f}|{r['gain_spread_percent']:.2f}|")
 lines+=['','## 位置合わせの注意','', '|膜|時点|相関|判定|粗回転(反時計回り)|','|---|---:|---:|---|---:|']
 for r in regs:
  sc=r.get('feature_correlation_after');score='失敗' if sc is None else f'{sc:.3f}'
  lines.append(f"|{r['sample']}|{r['hour']}|{score}|{'LOW ALIGNMENT' if r['low_alignment_confidence'] else '参考基準以上'}|{r['coarse_rotation_ccw_degrees']}|")
 lines+=['','位置合わせ後の高域画像相関0.4未満を暫定的にLOW ALIGNMENTと表示。これは実測した位置誤差の基準ではありません。24 hの見た目が大きく変わる場合、相関低下は実変化と位置ずれの両方を含み、局所比較は参考です。相関0.25未満の候補は回転誤判定の恐れがあるため採用せず、撮影時の向きを維持したリサイズのみの暫定結果（REVIEW_REQUIRED）としました。FAILEDもリサイズのみ。24 hの辻2膜が該当し、細かな画素位置の一致は保証しません。','',
 '## 解釈と表示上の限界','',
 '- RGB変化は材料の劣化の証明ではありません。相変化・PbI2量・性能低下は判定しません。傷の自動判定も行っていません。',
 '- 比較用のマップは前回と同じRGB距離0–50、符号付きRは−30〜30。24 hで色尺度が飽和し得るので、RGB距離0–200の図も保存しました。成分別マップはR/G/B共通−100〜100です。表示上の飽和率はCSVに記録、NPZは未クリップの数値。',
 '- 補正画像PNGは0–255に丸めて保存。集計と差分NPZは丸め前の値を使用。背景補正で反射や撮影角度の差は除去できません。',
 '- グラフは5→24 hの間を線で結びますが、この間の変化開始時刻・経路は観察していません。',
 '- 12/18/24%の外周除外と楕円あり/なし、背景4領域の単独選択による感度を保存。帯は信頼区間ではありません。',
 '- 切り抜き画像寸法は約240 px角。倍率・解像度の制約があり、細かな局所模様の判定に限界があります。',
 '', '## 保存ファイル','',
 '- aligned_rgb.csv：楕円含む／除外両条件の補正前後RGB・0 h差分（56行）','- roi_sensitivity.csv：解析領域を変えた結果（168行）','- background_validation.csv / background_patches.csv：背景補正の測定・検証','- background_sensitivity.csv：背景単独選択によるRGB変化','- registration.json / metadata.json / input_manifest.json：変換・入力・領域・ハッシュ','- 各膜/*h_corrected.png：背景補正のみ（28枚）','- 各膜/*h_aligned_corrected.png：位置合わせ後（28枚）','- 各膜/*h_color_difference.npz：RGB差分・距離・両解析マスク（28個）','- 各図はPNG/PDF両形式。再実行：python3 notebooks/film_time_series/analyze_extended_time_series.py（numpy、Pillow、OpenCV、matplotlibが必要）。']
 (OUT/'README.md').write_text('\n'.join(lines),encoding='utf-8')
 (OUT/'report.md').write_text('\n'.join(lines),encoding='utf-8')
if __name__=='__main__':main()
