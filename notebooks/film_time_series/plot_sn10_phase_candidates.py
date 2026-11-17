from pathlib import Path
import csv,hashlib,json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'data/raw/Touma/FACsSnPbI3(Sn10mol%)_SnF2_0.1mol%/20261112/XRD'
OUT=ROOT/'results/20261112/02_xrd_phase_candidates';OUT.mkdir(exist_ok=True)
font=FontProperties(fname='/mnt/c/Windows/Fonts/YuGothR.ttc');plt.rcParams['font.family']=font.get_name();matplotlib.font_manager.fontManager.addfont(font.get_file())
fig,axes=plt.subplots(3,3,figsize=(16,12));rows=[];manifest=[]
windows=[('FA系δ相候補',11.8,.35),('ヨウ化物候補',12.7,.4),('Cs系副相候補',13.2,.25),('ペロブスカイト',14.1,.55),('Cs系副相候補',26.5,.35),('ペロブスカイト',28.3,.5),('PbI2補助候補',53.5,.4)]
for row,minute in enumerate((5,10,15)):
 for age,color in [('0h','tab:orange'),('1h','tab:blue')]:
  p=next((BASE/f'{minute}min'/age).glob('*.txt'));x,y=np.loadtxt(p,skiprows=2,encoding='utf-8-sig').T;s=np.convolve(y,np.ones(5)/5,'same');norm=s[(x>13.3)&(x<14.8)].max()
  manifest.append({'path':str(p.relative_to(ROOT)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
  for j,(a,b) in enumerate([(10.8,15.3),(24.5,29.5),(51.5,55.5)]):
   mask=(x>=a)&(x<=b);axes[row,j].plot(x[mask],s[mask]/norm,color=color,label=age,lw=1.2)
  for label,center,half in windows:
   ids=np.flatnonzero((x>=center-half)&(x<=center+half));i=ids[np.argmax(s[ids])]
   rows.append({'anneal_min':minute,'age':age,'candidate_region':label,'reference_deg':center,'window_halfwidth_deg':half,'window_max_deg':float(x[i]),'window_max_smoothed_cps':float(s[i]),'maximum_on_boundary':bool(i in (ids[0],ids[-1])),'interpretation':'窓内最大値のみ。ピーク検出・相同定・検出限界判定ではない'})
 for j,ax in enumerate(axes[row]):
  ax.set_title(f'{minute}分：'+['低角側','26〜28°付近','53.5°付近'][j]);ax.set_xlabel('2θ (°)');ax.set_ylabel('約14°領域の最大値で規格化');ax.grid(alpha=.2);ax.legend()
 for ax,refs in zip(axes[row],[[ (11.8,'FA系δ?'),(12.7,'PbI2等?'),(13.2,'Cs系副相?'),(14.1,'PVK?')],[(26.5,'Cs系副相?'),(28.3,'PVK?')],[(53.5,'PbI2?')]]):
  for k,(v,label) in enumerate(refs):
   ax.axvline(v,color='grey',ls=':',alpha=.7);ax.text(v,.98-(k%2)*.09,label,transform=ax.get_xaxis_transform(),ha='center',va='top',fontsize=8)
fig.suptitle('文献の代表位置と実測の照合（点線は参考位置・相の確定ではありません）\n組成差・測定ずれあり／背景込み・5点平滑化／自動角度補正なし',fontsize=16)
fig.tight_layout(rect=[0,0,1,.94]);fig.savefig(OUT/'01_相候補の照合.png',dpi=150);fig.savefig(OUT/'01_相候補の照合.pdf');plt.close(fig)
with (OUT/'reference_window_checks.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
(OUT/'input_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
print('6測定・7参考領域の図と確認表を作成')
