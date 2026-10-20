"""Visualize existing ROI sensitivity results without recomputing measurements."""
from pathlib import Path
import csv
import numpy as np
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from aligned_color_analysis import DAY,OUT,TAGS,mask_for
font=Path('/mnt/c/Windows/Fonts/meiryo.ttc')
if font.exists():
 font_manager.fontManager.addfont(str(font));plt.rcParams['font.family']=font_manager.FontProperties(fname=str(font)).get_name()
plt.rcParams['axes.unicode_minus']=False
rows=list(csv.DictReader((OUT/'roi_sensitivity.csv').open(encoding='utf-8-sig')))
def save(fig,p):
 fig.savefig(p.with_suffix('.png'),dpi=160,bbox_inches='tight');fig.savefig(p.with_suffix('.pdf'),bbox_inches='tight');plt.close(fig)
for tag in TAGS:
 fig,axs=plt.subplots(3,3,figsize=(12,10),layout='constrained')
 for j,ch in enumerate('RGB'):
  vals=[float(r['delta_'+ch]) for r in rows if r['sample']==tag];lo=min(vals);hi=max(vals);pad=max((hi-lo)*.12,.15)
  for i,margin in enumerate([.12,.18,.24]):
   ax=axs[i,j]
   for excluded,color,style,marker,label in [(False,'#e17717','--','s','楕円を含める'),(True,'#1767b1','-','o','楕円を除外する')]:
    rr=sorted([r for r in rows if r['sample']==tag and float(r['margin_fraction'])==margin and r['reflection_excluded']==str(excluded)],key=lambda r:int(r['hour']))
    assert len(rr)==4
    ax.plot([int(r['hour']) for r in rr],[float(r['delta_'+ch]) for r in rr],color=color,ls=style,marker=marker,ms=6 if excluded else 8,label=label)
   ax.axhline(0,color='gray',lw=.6);ax.set(title=f'外周{margin:.0%}除外 ／ {ch}',xlabel='成膜後の時間（h）',ylabel=f'0 hからの平均{ch}変化（RGB値）',xticks=[0,1,2,3],ylim=(lo-pad,hi+pad));ax.grid(alpha=.25)
 axs[0,0].legend(fontsize=9)
 note='Sn系には楕円を設定していないため、2本の線は重なります。' if tag.startswith('Sn') else '同じ外周割合のグラフ内で、青実線と橙破線を比較してください。'
 fig.suptitle(f'{tag}：解析範囲と楕円除外による違い\n{note}',fontsize=13)
 save(fig,OUT/tag/'roi_inclusion_comparison')
 image=np.asarray(Image.open(OUT/tag/'0h_aligned_corrected.png'));h,w=image.shape[:2]
 fig,axs=plt.subplots(3,2,figsize=(7,10),layout='constrained')
 for i,margin in enumerate([.12,.18,.24]):
  for j,excluded in enumerate([False,True]):
   m=mask_for(h,w,margin,np.ones((h,w),bool),tag,excluded)
   row=next(r for r in rows if r['sample']==tag and r['hour']=='0' and float(r['margin_fraction'])==margin and r['reflection_excluded']==str(excluded))
   assert m.sum()==int(row['pixels']),('Mask differs from measurements',tag,margin,excluded)
   overlay=image.astype(float)*.25;overlay[m]=image[m]
   axs[i,j].imshow(overlay.astype(np.uint8));axs[i,j].contour(m,levels=[.5],colors=['lime'],linewidths=.8)
   axs[i,j].set_title(f'外周{margin:.0%}除外・楕円'+('除外' if excluded else '含む'));axs[i,j].axis('off')
 fig.suptitle(f'{tag}：実際の解析領域\n明るい部分＝解析対象、暗い部分＝対象外',fontsize=13)
 save(fig,OUT/tag/'roi_regions')
print('Created 4 comparison plots and 4 ROI diagrams (PNG/PDF); verified masks match CSV pixel counts.')
