"""Render channel-ratio correction and held-out background checks."""
from pathlib import Path
import json,csv,hashlib,sys
import numpy as np,cv2
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import fontManager
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'notebooks/capture_repeatability'))
from analyze_repeatability import corners_and_bbox
P=ROOT/'results/20261112/09_image_time_series_4points';O=ROOT/'results/20261112/10_background_corrected_images_4points';O.mkdir(exist_ok=True)
for folder in ['corrected_full','corrected_crops']:(O/folder).mkdir(exist_ok=True)
fontManager.addfont('/mnt/c/Windows/Fonts/YuGothR.ttc');plt.rcParams['font.family']='Yu Gothic'
FIT=[(785,555),(1585,555),(1185,250),(1185,855)];CHECK=[(785,250),(1585,250),(785,855),(1585,855)];size=40
manifest=json.loads((P/'input_manifest.json').read_text());rs=list(csv.DictReader((P/'metrics.csv').open(encoding='utf-8-sig')));byname={r['filename']:r for r in rs};records=[];validation=[];images={};checkimages=[]
def patches(a,centers):return np.array([a[y-20:y+20,x-20:x+20].mean((0,1)) for x,y in centers])
for m in [5,10,15]:
 entries=[e for e in manifest if byname[Path(e['image']).name]['anneal_min']==str(m)]
 base=np.array(Image.open(ROOT/entries[0]['image']).convert('RGB'),dtype=float);basefit=patches(base,FIT).mean(0);basecheck=patches(base,CHECK)
 for index,e in enumerate(entries):
  p=ROOT/e['image'];r=byname[p.name];a=np.array(Image.open(p).convert('RGB'));assert hashlib.sha256(p.read_bytes()).hexdigest()==e['image_sha256'];corners=np.array(e['corners'],dtype=np.float32)
  mask=np.zeros(a.shape[:2],np.uint8);cv2.fillConvexPoly(mask,corners.astype(np.int32),1)
  for x,y in FIT+CHECK:assert not mask[y-20:y+20,x-20:x+20].any()
  gain=basefit/patches(a,FIT).mean(0);floating=a.astype(float)*gain;clipped=np.any((floating<0)|(floating>255),axis=2);corrected=np.rint(np.clip(floating,0,255)).astype(np.uint8)
  # Held-out metrics use floating values, avoiding output PNG rounding.
  before=patches(a,CHECK);after=patches(floating,CHECK)
  for k in range(4):
   rb=float(np.linalg.norm((before[k]-basecheck[k])/basecheck[k])*100/np.sqrt(3));ra=float(np.linalg.norm((after[k]-basecheck[k])/basecheck[k])*100/np.sqrt(3))
   validation.append({'anneal_min':m,'label':r['label'],'filename':p.name,'patch':k+1,'before_relative_rgb_rms_percent':rb,'after_relative_rgb_rms_percent':ra,'improved':ra<rb})
  target=np.float32([[0,0],[255,0],[255,255],[0,255]]);t=cv2.getPerspectiveTransform(corners,target);rawcrop=cv2.warpPerspective(a,t,(256,256));crop=cv2.warpPerspective(corrected,t,(256,256));images[m,index]=(rawcrop,crop,r)
  Image.fromarray(corrected).save(O/'corrected_full'/p.with_suffix('.png').name);Image.fromarray(crop).save(O/'corrected_crops'/f'{m}min_{r["label"]}.png')
  records.append({'filename':p.name,'anneal_min':m,'label':r['label'],'gains_RGB':gain.tolist(),'full_image_clipped_fraction':float(clipped.mean()),'input':e['image'],'input_sha256':e['image_sha256']})
  if index==1:checkimages.append((a,corrected,m,r))
 fig,axes=plt.subplots(2,4,figsize=(13,7))
 for j in range(4):
  raw,corr,r=images[m,j]
  for i,img in enumerate([raw,corr]):
   ax=axes[i,j];ax.imshow(img);ax.set_title(f'{m}分・{r["label"]} '+('元画像' if i==0 else '背景補正後'));ax.axis('off')
 fig.suptitle('各膜の最初の写真の背景へ合わせる／膜の真の色への校正ではない');fig.tight_layout();fig.savefig(O/f'0{[5,10,15].index(m)+1}_{m}min_補正前後.png',dpi=150);fig.savefig(O/f'0{[5,10,15].index(m)+1}_{m}min_補正前後.pdf');plt.close(fig)
fig,axes=plt.subplots(3,2,figsize=(13,10))
for i,(a,corr,m,r) in enumerate(checkimages):
 for j,img in enumerate([a,corr]):
  ax=axes[i,j];ax.imshow(img)
  for centers,color,label in [(FIT,'lime','補正用'),(CHECK,'magenta','検証用')]:
   for k,(x,y) in enumerate(centers):ax.add_patch(plt.Rectangle((x-20,y-20),40,40,fill=False,color=color,lw=1));ax.text(x+25,y,label+str(k+1),color=color,fontsize=7)
  ax.set_title(f'{m}分・{r["label"]} '+('元画像' if j==0 else '背景補正後'));ax.axis('off')
fig.suptitle('問題の途中3枚：緑＝補正に使用／紫＝補正に未使用の検証領域');fig.tight_layout();fig.savefig(O/'04_背景領域と補正結果.png',dpi=160);plt.close(fig)
with (O/'held_out_background_validation.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(validation[0]));w.writeheader();w.writerows(validation)
(O/'correction_manifest.json').write_text(json.dumps(records,ensure_ascii=False,indent=2))
fig,axes=plt.subplots(1,3,figsize=(13,4.5));summary=[]
for ax,m in zip(axes,[5,10,15]):
 vals=[]
 for j in range(4):
  r=images[m,j][2];vs=[v for v in validation if v['filename']==r['filename']];b=np.mean([v['before_relative_rgb_rms_percent'] for v in vs]);a=np.mean([v['after_relative_rgb_rms_percent'] for v in vs]);vals.append((r['label'],b,a));summary.append({'anneal_min':m,'label':r['label'],'before':b,'after':a})
 x=np.arange(4);ax.bar(x-.18,[v[1] for v in vals],.36,label='補正前',color='gray');ax.bar(x+.18,[v[2] for v in vals],.36,label='補正後',color='#e5a34e');ax.set_xticks(x,[v[0] for v in vals]);ax.set_title(f'{m}分：検証背景4領域の平均');ax.set_ylabel('最初の写真に対する相対RGBずれ (%)');ax.legend();ax.grid(axis='y',alpha=.2)
fig.suptitle('未使用の背景で検証／膜の色の正確さを示す指標ではない');fig.tight_layout();fig.savefig(O/'05_未使用背景での検証.png',dpi=160);fig.savefig(O/'05_未使用背景での検証.pdf');plt.close(fig)
lines=['# 背景補正後の画像と独立領域での確認','',
'## 見る順番','',
'- [5分膜の補正前後](01_5min_補正前後.png)','- [10分膜の補正前後](02_10min_補正前後.png)','- [15分膜の補正前後](03_15min_補正前後.png)',
'- [背景領域と補正結果](04_背景領域と補正結果.png)','- [補正に未使用の背景での検証](05_未使用背景での検証.png)','',
'上段が元画像、下段が背景補正後。列は撮影順です。各膜の最初の写真を基準にしており、最初の写真自体が正しい白であるとは仮定していません。','',
'## 未使用背景での結果','',
'| アニール | 時点 | 補正前のずれ | 補正後のずれ |','|---|---|---:|---:|']
for s in summary:lines.append(f"| {s['anneal_min']}分 | {s['label']} | {s['before']:.2f}% | {s['after']:.2f}% |")
lines+=['','値は、各検証領域の最初の写真に対するRGB成分別相対差のRMSを求め、4領域で平均したもの。色差ΔE、膜の誤差、劣化率ではありません。最初の写真は自己比較なので0です。検証領域は補正係数の計算に使っていませんが、同じ紙・画像内の領域であり独立した撮影試験ではありません。','',
'## 方法と使い方','',
'元のフル画像の上下左右4箇所・40×40pxの平均RGBを基準写真に合わせる成分別係数を求め、その係数をフル画像全体へ適用。その後、従来と同じ基板四隅で切り抜きました。斜め方向4箇所・40×40pxを未使用の検証領域としています。領域と基板が重ならないことを確認。係数は膜色から計算していません。','',
'補正はJPEG相当の非線形RGB上の比率補正です。照明スペクトル・反射角度・映り込み・ぼけを復元できず、白い紙と鏡面性のある膜が同じ比率で変わる保証はありません。背景の整合性改善と、膜の色の正しさは区別します。補正前後は両方残し、主要結論は[4通りの感度比較](../11_background_sensitivity_4points/README.md)と併せて判断してください。','',
'出力PNGは8bit、範囲外をクリップし丸めています。数値解析は既存の浮動小数点補正を使用し、このPNGの再読み込みには置き換えません。クリップ率と係数・入力ハッシュはcorrection_manifest.json。元写真とJSONは変更していません。','',
'corrected_full/＝背景を含む補正画像、corrected_crops/＝補正後の膜切り抜き。再実行：python3 notebooks/film_time_series/sn10_corrected_images.py。']
(O/'README.md').write_text('\n'.join(lines)+'\n');(O/'analysis_config.json').write_text(json.dumps({'fit_centers':FIT,'held_out_centers':CHECK,'patch_size':size,'baseline':'first image per film','formula':'corrected_RGB = original_RGB * baseline_fit_mean / current_fit_mean','metric':'mean over 4 held-out patches of 100*sqrt(mean(((current-reference)/reference)**2))','source_manifest':str((P/'input_manifest.json').relative_to(ROOT))},indent=2))
print(json.dumps(summary,ensure_ascii=False,indent=2))
