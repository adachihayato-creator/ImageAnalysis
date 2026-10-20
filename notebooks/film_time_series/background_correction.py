"""Relative JPEG-RGB background normalization; no physical reflectance calibration.
Run: python background_correction.py (requires numpy and Pillow).
Original files are never overwritten. See generated report.md for limitations.
"""
from pathlib import Path
import csv, json
import numpy as np
from PIL import Image, ImageDraw
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'data/processed/20261015/02_background_correction'
GROUPS={'BrRb':('Tuji','FACsPbI3_BrRb_5mol_per_gram'),'Sn25':('Touma','FACsSnPbI3(Sn25mol%)')}

def save_csv(name, rows):
 with (OUT/name).open('w',newline='',encoding='utf-8-sig') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def bbox(a):
 h,w=a.shape[:2];x0,x1=int(w*.35),int(w*.65);y0,y1=int(h*.25),int(h*.65)
 dark=a[y0:y1,x0:x1].mean(axis=2)<95
 ys=np.flatnonzero(dark.sum(axis=1)>30);xs=np.flatnonzero(dark.sum(axis=0)>30)
 if len(xs)<80 or len(ys)<80:raise ValueError('Sample detection failed')
 b=(x0+int(xs[0]),y0+int(ys[0]),x0+int(xs[-1])+1,y0+int(ys[-1])+1)
 if not (100<b[2]-b[0]<450 and 100<b[3]-b[1]<450):raise ValueError(b)
 return b

def boxes(b):
 x0,y0,x1,y1=b;cx=(x0+x1)//2;cy=(y0+y1)//2
 centers=[(cx,y0-90),(cx,y1+90),(x0-90,cy),(x1+90,cy),
          (x0-90,y0-90),(x1+90,y0-90),(x0-90,y1+90),(x1+90,y1+90)]
 return [(x-35,y-35,x+35,y+35) for x,y in centers]

def region(a,b):
 x0,y0,x1,y1=b;return a[y0:y1,x0:x1]

def main():
 OUT.mkdir(parents=True,exist_ok=True)
 rows=[];patchrows=[];metarows=[];qc=[]
 for group,(owner,material) in GROUPS.items():
  for sample in (1,2):
   tag=f'{group}_{sample}';dest=OUT/tag;dest.mkdir(exist_ok=True)
   references=None;base_mean=None;base_corrected=None;panels=[]
   for t in range(4):
    name=f'{sample}枚目{t}h.jpg';raw=ROOT/'data/raw'/owner/material/'10_15'/name
    processed=ROOT/'data/processed/20261015/01_crops'/owner/material/name
    im=Image.open(raw).convert('RGB');a=np.asarray(im,dtype=float)
    b=bbox(a);bs=boxes(b);patch=np.array([np.median(region(a,z),axis=(0,1)) for z in bs])
    if t==0:references=patch.copy()
    pg=references/patch
    # Fit only cardinal patches. Diagonals are held out for a spatial consistency check.
    gain=np.median(pg[:4],axis=0)
    residual_before=(patch[4:]/references[4:]-1)*100
    residual_after=(patch[4:]*gain/references[4:]-1)*100
    spread=np.max(np.abs(pg[:4]/gain-1))*100
    c=np.asarray(Image.open(processed).convert('RGB'),dtype=float)
    h,w=c.shape[:2];roi=(int(.18*w),int(.18*h),int(.82*w),int(.82*h))
    core=region(c,roi);cm=core.mean(axis=(0,1));corrected=cm*gain
    if t==0:base_mean=cm.copy();base_corrected=corrected.copy()
    corrected_im=Image.fromarray(np.clip(np.rint(c*gain),0,255).astype('uint8'))
    corrected_im.save(dest/f'{t}h_corrected.png')
    # A spatial-sensitivity envelope, not a confidence interval.
    alternate=cm[None,:]*pg[:4]
    row={'sample':tag,'hour':t,'core_pixels':core.shape[0]*core.shape[1],
         'gain_spread_percent':round(float(spread),4),
         'heldout_before_mae_percent':round(float(np.abs(residual_before).mean()),4),
         'heldout_after_mae_percent':round(float(np.abs(residual_after).mean()),4),
         'clipped_pixel_percent':round(float(np.any(c*gain>255,axis=2).mean()*100),4)}
    for j,ch in enumerate('RGB'):
     row.update({f'gain_{ch}':round(float(gain[j]),6),f'raw_{ch}':round(float(cm[j]),4),
      f'corrected_{ch}':round(float(corrected[j]),4),f'delta_raw_{ch}':round(float(cm[j]-base_mean[j]),4),
      f'delta_corrected_{ch}':round(float(corrected[j]-base_corrected[j]),4),
      f'patch_choice_min_{ch}':round(float(alternate[:,j].min()),4),
      f'patch_choice_max_{ch}':round(float(alternate[:,j].max()),4)})
    rows.append(row)
    for i,(z,med,g) in enumerate(zip(bs,patch,pg)):
     patchrows.append({'sample':tag,'hour':t,'patch':i,'role':'fit' if i<4 else 'held_out','box':str(z),
      **{f'median_{ch}':round(float(med[j]),4) for j,ch in enumerate('RGB')},
      **{f'gain_{ch}':round(float(g[j]),6) for j,ch in enumerate('RGB')}})
    exif=im.getexif(); metarows.append({'sample':tag,'hour':t,'raw':str(raw.relative_to(ROOT)),
       'processed':str(processed.relative_to(ROOT)),'raw_size':im.size,'sample_bbox':b,'background_boxes':bs,
       'processed_core_box':roi,'exif':{str(k):str(v) for k,v in exif.items()}})
    for label,img in [('raw',Image.fromarray(c.astype('uint8'))),('corrected',corrected_im)]:
     tile=Image.new('RGB',(280,300),'white');img.thumbnail((260,260));tile.paste(img,((280-img.width)//2,28))
     ImageDraw.Draw(tile).text((8,8),f'{tag} {t}h {label}',fill='black');panels.append(tile)
    q=im.copy();q.thumbnail((1024,576));draw=ImageDraw.Draw(q);scale=q.width/im.width
    for i,z in enumerate(bs):
     zz=tuple(v*scale for v in z);draw.rectangle(zz,outline='red' if i<4 else 'blue',width=2);draw.text((zz[0],zz[1]),str(i),fill='black')
    draw.rectangle(tuple(v*scale for v in b),outline='yellow',width=2);draw.text((10,10),f'{tag} {t}h: red=fit blue=heldout',fill='black');qc.append(q)
   sheet=Image.new('RGB',(1120,600),'white')
   for t in range(4):
    sheet.paste(panels[t*2],(t*280,0));sheet.paste(panels[t*2+1],(t*280,300))
   sheet.save(dest/'comparison.png')
 save_csv('rgb_summary.csv',rows);save_csv('background_patches.csv',patchrows)
 (OUT/'metadata.json').write_text(json.dumps(metarows,ensure_ascii=False,indent=2),encoding='utf-8')
 # 4 columns (times), 4 rows (samples), smaller previews.
 sheet=Image.new('RGB',(2048,1152),'white')
 for i,q in enumerate(qc):sheet.paste(q.resize((512,288)),((i%4)*512,(i//4)*288))
 sheet.save(OUT/'background_regions.png')
 make_svg(rows)
 write_report(rows)
 print(json.dumps(rows,indent=2))

def make_svg(rows):
 colors={'R':'#d33','G':'#198c38','B':'#36c'};s=['<svg xmlns="http://www.w3.org/2000/svg" width="1040" height="740" viewBox="0 0 1040 740"><rect width="1040" height="740" fill="white"/>']
 for k,tag in enumerate(dict.fromkeys(r['sample'] for r in rows)):
  x=65+(k%2)*520;y=65+(k//2)*360; rr=[r for r in rows if r['sample']==tag]
  vals=[abs(r[f'delta_{v}_{c}']) for r in rr for v in ('raw','corrected') for c in 'RGB'];lim=max(3,np.ceil(max(vals)/2)*2)
  s.append(f'<text x="{x}" y="{y-25}" font-family="sans-serif" font-size="17">{tag}: RGB change from 0h</text>')
  for tick in [-lim,-lim/2,0,lim/2,lim]:
   yy=y+120-tick/lim*110;s.append(f'<path d="M{x},{yy}h390" stroke="#ddd"/><text x="{x-40}" y="{yy+4}" font-size="12">{tick:g}</text>')
  for t in range(4):s.append(f'<text x="{x+t*130}" y="{y+255}" font-size="13">{t}h</text>')
  for c in 'RGB':
   for v,dash in [('raw','6,4'),('corrected','none')]:
    points=' '.join(f"{x+r['hour']*130},{y+120-r[f'delta_{v}_{c}']/lim*110}" for r in rr)
    s.append(f'<polyline points="{points}" fill="none" stroke="{colors[c]}" stroke-width="2" stroke-dasharray="{dash}"/>')
  s.append(f'<text x="{x}" y="{y+280}" font-family="sans-serif" font-size="13">solid: corrected; dashed: raw; JPEG RGB units</text>')
 s.append('</svg>');(OUT/'rgb_changes.svg').write_text('\n'.join(s))

def write_report(rows):
 lines=['# 2026-10-15 膜画像の背景基準による相対色補正','',
 '対象：BrRb系2膜、Sn25%系2膜、各0–3 hの計16画像。元画像・既存切り抜き画像は変更していません。','',
 '## 方法','',
 '各元画像の中央付近から暗い試料の外接矩形を検出。周囲の上下左右4領域（各70×70 px）のRGB中央値を測定し、同じ膜の0 hに対するチャネル別比率の中央値を補正係数としました。係数の決定に膜の画素は使っていません。斜め4領域は係数計算には使わず、背景補正の検証に使用しました。領域は background_regions.png に表示しています。',
 '', '既存切り抜き画像に係数を適用し、PNGで保存。定量値は各切り抜きの幅・高さの18–82%の中央領域の平均RGBです。画像の幾何学的位置合わせはしていないため、完全に同じ物理領域の比較ではありません。縁の除外はできますが、膜内部の反射を除去した解析ではありません。',
 '', '## 背景検証','', '|膜|時刻|補正係数の場所依存 最大偏差(%)|未使用背景の誤差 補正前→後(%)|','|---|---:|---:|---:|']
 for r in rows:
  if r['hour']:lines.append(f"|{r['sample']}|{r['hour']}h|{r['gain_spread_percent']:.2f}|{r['heldout_before_mae_percent']:.2f} → {r['heldout_after_mae_percent']:.2f}|")
 lines+=['','誤差は未使用の斜め4領域における0 hからのRGB相対偏差の絶対値平均です。場所依存性は上下左右で得た係数のばらつきであり、統計的な信頼区間ではありません。','',
 '## 解釈上の限界','',
 '- JPEGの保存RGB値に対する乗算補正です。線形光量・反射率の校正ではありません。照明スペクトルやカメラ内部処理の違いを完全には戻せません。',
 '- 0 hは各膜固有の基準です。異なる膜の絶対色を同一基準に校正した結果ではありません。背景材が一定であるとの仮定を置いています。',
 '- 照明むら・撮影位置・角度の違い・LED/レンズの映り込みは残ります。白飛び/黒つぶれの情報は復元できません。',
 '- 同時点の反復撮影がないため、撮影誤差の大きさや有意差は評価できません。色変化から化学的劣化を断定しないでください。',
 '- 補正前後の傾向と、背景領域の選び方による範囲（CSVのpatch_choice_min/max）を併せて判断してください。',
 '', '## 出力','', '- rgb_summary.csv：補正係数、補正前後RGB、0 h差分、背景領域による感度範囲','- background_patches.csv：全背景領域の測定値','- metadata.json：元ファイル、矩形座標、EXIF','- background_regions.png：背景領域の確認用一覧','- rgb_changes.svg：0 hからのRGB変化','- 各膜フォルダ：補正済み4枚とcomparison.png（上段：補正前、下段：補正後）','',
 '再実行：`python notebooks/film_time_series/background_correction.py`（numpy、Pillowが必要）。']
 (OUT/'report.md').write_text('\n'.join(lines),encoding='utf-8')
if __name__=='__main__':main()
