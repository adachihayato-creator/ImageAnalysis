"""Plot initial XRD and pair descriptive features with existing RGB changes.
Requires numpy, matplotlib. Sample numbers are confirmed by the user.
No phase quantification, crystallite size estimation, or causal inference.
"""
from pathlib import Path
import csv,json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'results/20261015/03_xrd_comparison'
FILES={
'BrRb_1':'Tuji/FACsPbI3_BrRb_5mol_per_gram/10_15/BrRb5% 1.txt',
'BrRb_2':'Tuji/FACsPbI3_BrRb_5mol_per_gram/10_15/BrRb5% 2.txt',
'Sn25_1':'Touma/FACsSnPbI3(Sn25mol%)/10_15/Sn 25%1.txt',
'Sn25_2':'Touma/FACsSnPbI3(Sn25mol%)/10_15/Sn 25% 2.txt'}
COLORS=dict(zip(FILES,['#1968b3','#56a5d8','#c04a14','#e69e41']))

def save(fig,name):
 fig.savefig(OUT/(name+'.png'),dpi=180,bbox_inches='tight');fig.savefig(OUT/(name+'.pdf'),bbox_inches='tight');plt.close(fig)

def peak(x,y,window):
 # Five-point (0.05 degree) moving average, not a peak-profile fit.
 sm=np.convolve(y,np.ones(5)/5,mode='same');mask=(x>=window[0])&(x<=window[1]);idx=np.flatnonzero(mask)
 i=idx[np.argmax(sm[idx])];return float(x[i]),float(sm[i])

def feature14(x,y):
 # Local straight-line background from flanking medians.
 left=(x>=13.0)&(x<=13.3);right=(x>=14.6)&(x<=14.9)
 bg=np.interp(x,[np.median(x[left]),np.median(x[right])],[np.median(y[left]),np.median(y[right])])
 sm=np.convolve(y,np.ones(5)/5,mode='same');z=sm-bg
 ids=np.flatnonzero((x>=13.4)&(x<=14.4));i=ids[np.argmax(z[ids])];half=z[i]/2
 lo=i
 while lo>0 and z[lo]>half:lo-=1
 hi=i
 while hi<len(x)-1 and z[hi]>half:hi+=1
 xl=x[lo]+(half-z[lo])/(z[lo+1]-z[lo])*(x[lo+1]-x[lo])
 xr=x[hi-1]+(half-z[hi-1])/(z[hi]-z[hi-1])*(x[hi]-x[hi-1])
 if not (13.0<xl<x[i]<xr<14.9):raise ValueError('FWHM crossing outside window')
 return float(x[i]),float(xr-xl),float(z[i]),bg

def main():
 OUT.mkdir(parents=True,exist_ok=True)
 rgb=list(csv.DictReader((ROOT/'results/20261015/02_background_correction/rgb_summary.csv').open(encoding='utf-8-sig')))
 data={};features=[]
 for tag,path in FILES.items():
  a=np.loadtxt(ROOT/'data/raw'/path,skiprows=2,encoding='utf-8-sig');x,y=a.T
  assert a.shape==(5701,2) and np.all(np.diff(x)>0)
  data[tag]=(x,y);p14,w,h,bg=feature14(x,y);p24,h24=peak(x,y,(23.7,24.8));p28,h28=peak(x,y,(27.8,28.6))
  r=next(r for r in rgb if r['sample']==tag and r['hour']=='3')
  f={'sample':tag,'xrd_file':path,'mapping':'user-confirmed','angle14_deg':p14,'fwhm14_apparent_deg':w,
     'height14_local_background_cps':h,'angle24_deg':p24,'angle28_deg':p28,
     'height24_over_height14_raw_smoothed':h24/peak(x,y,(13.4,14.4))[1]}
  for ch in 'RGB':f['delta3h_'+ch]=float(r['delta_corrected_'+ch])
  f['rgb_distance3h']=float(np.sqrt(sum(f['delta3h_'+ch]**2 for ch in 'RGB')))
  features.append(f)
 with (OUT/'paired_features.csv').open('w',encoding='utf-8-sig',newline='') as fp:
  wr=csv.DictWriter(fp,fieldnames=list(features[0]));wr.writeheader();wr.writerows(features)
 fig,axes=plt.subplots(2,2,figsize=(12,8),layout='constrained')
 for ax,tag in zip(axes.flat,FILES):
  x,y=data[tag];ax.plot(x,y,color=COLORS[tag],lw=.65);ax.set(title=tag,xlabel='Scan angle (degrees; instrument label: theta/2theta)',ylabel='Intensity (cps)',xlim=(3,60));ax.grid(alpha=.2)
 fig.suptitle('Initial XRD: measured intensities, no normalization');save(fig,'01_xrd_raw')
 fig,axes=plt.subplots(1,3,figsize=(15,4.8),layout='constrained')
 for ax,limits in zip(axes,[(10,16),(23,29),(30,33)]):
  for tag,(x,y) in data.items():
   sm=np.convolve(y,np.ones(5)/5,mode='same');normalizer=sm[(x>=13.4)&(x<=14.4)].max()
   ax.plot(x,sm/normalizer,label=tag,color=COLORS[tag],lw=1)
  ax.set(xlim=limits,xlabel='Scan angle (degrees)',ylabel='Intensity / peak near 14 degrees',title=f'{limits[0]}–{limits[1]} degrees');ax.grid(alpha=.2)
 axes[0].legend();fig.suptitle('Shape comparison: 5-point smoothing; normalization includes background');save(fig,'02_xrd_zoom')
 fig,axes=plt.subplots(1,2,figsize=(11,4.8),layout='constrained')
 for ax,tags in zip(axes,[['BrRb_1','BrRb_2'],['Sn25_1','Sn25_2']]):
  for tag in tags:
   x,y=data[tag];p,w,h,bg=feature14(x,y);sm=np.convolve(y,np.ones(5)/5,mode='same')
   ax.plot(x,(sm-bg)/h,color=COLORS[tag],label=f'{tag}: {p:.2f} deg, FWHM {w:.3f} deg')
  ax.axhline(.5,color='gray',ls=':');ax.set(xlim=(13.3,14.6),ylim=(-.15,1.2),xlabel='Scan angle (degrees)',ylabel='Local-background-subtracted / peak height');ax.legend(fontsize=8);ax.grid(alpha=.2)
 fig.suptitle('Apparent width near 14 degrees: exploratory, no instrumental correction');save(fig,'03_peak14_width')
 fig,axes=plt.subplots(1,3,figsize=(14,4.5),layout='constrained')
 for ax,ch in zip(axes,'RGB'):
  for tag in FILES:
   rr=[r for r in rgb if r['sample']==tag]
   ax.plot([int(r['hour']) for r in rr],[float(r['delta_corrected_'+ch]) for r in rr],marker='o',color=COLORS[tag],label=tag)
  ax.axhline(0,color='gray',lw=.7);ax.set(xlabel='Elapsed time (h)',ylabel=f'Corrected {ch} change from 0 h (JPEG RGB units)',xticks=[0,1,2,3]);ax.grid(alpha=.2)
 axes[0].legend();fig.suptitle('Image color change: background-normalized, central crop region');save(fig,'04_color_time_series')
 fig,axes=plt.subplots(1,3,figsize=(15,4.8),layout='constrained')
 for ax,key,label in zip(axes,['angle14_deg','fwhm14_apparent_deg','height24_over_height14_raw_smoothed'],['Peak position near 14 deg (degrees)','Apparent FWHM near 14 deg (degrees)','Raw smoothed peak height ratio 24 / 14']):
  for f in features:
   tag=f['sample'];ax.scatter(f[key],f['rgb_distance3h'],color=COLORS[tag],marker='o' if tag.startswith('BrRb') else '^',s=65)
   ax.annotate(tag,(f[key],f['rgb_distance3h']),xytext=(5,6),textcoords='offset points',fontsize=9)
  ax.margins(.25);ax.set(xlabel=label,ylabel='0–3 h RGB distance (JPEG RGB units)');ax.grid(alpha=.2)
 fig.suptitle('Exploratory pairing only (n=4): no correlation fit or causal conclusion');save(fig,'05_xrd_vs_color')
 lines=['# 初期XRDと画像経時変化の比較','',
 '4膜のXRD番号と写真番号の対応はユーザー確認済みです。XRDは成膜直後の測定のみです。ファイルの角度列見出しは「θ/2θ, °」。一般的なθ–2θ測定の2θ軸であるか、X線源、基板・下地、測定条件は未確認です。数値はファイルに記載された角度です。','',
 '## 測定結果（記述的特徴）','',
 '|膜|約14°ピーク位置|見かけの半値幅|約24°ピーク位置|約28°ピーク位置|0→3h ΔR|ΔG|ΔB|',
 '|---|---:|---:|---:|---:|---:|---:|---:|']
 for f in features:lines.append(f"|{f['sample']}|{f['angle14_deg']:.2f}|{f['fwhm14_apparent_deg']:.3f}|{f['angle24_deg']:.2f}|{f['angle28_deg']:.2f}|{f['delta3h_R']:.2f}|{f['delta3h_G']:.2f}|{f['delta3h_B']:.2f}|")
 lines+=['','## 比較の仕方','',
 'まず同組成の2膜を比較します。初期ピーク位置・幅・相対強度が異なる膜で、その後の色変化の方向・大きさも異なるかを並べて見る構成です。異なる組成間では組成そのものがXRDと光学応答の両方に影響するので、初期結晶性と劣化の因果関係を論じられません。',
 '', '画像指標は既存の背景補正で算出した中央領域RGBの0 hからの差です。散布図のRGB距離は sqrt(ΔR²+ΔG²+ΔB²)。人の知覚に均等な色差ΔEでも、劣化率・相含有率でもありません。背景・位置・反射の残差があり、微小な差は確証になりません。',
 '', '## 数値抽出方法・限界','',
 '- 元データは各5701点、角度3–60°、0.01°刻み。生の強度図も保存しました。',
 '- ピーク位置は5点（0.05°幅）の移動平均後の局所最大。約14°は13.4–14.4°、約24°は23.7–24.8°、約28°は27.8–28.6°で探索。位相同定の結果ではありません。',
 '- 14°付近の背景は13.0–13.3°と14.6–14.9°の中央値を直線で結んで推定。半値幅は背景差引き後の左右交点を線形補間。プロファイルフィット・装置幅補正は未実施。単純な見かけの幅であり、結晶子径や結晶性の順位に直接変換しません。',
 '- 24/14強度比は背景込みの平滑化ピーク高さ比。相含有率ではありません。絶対強度・相対強度は膜厚・配向・基板・測定位置でも変わり得ます。',
 '- 約14°/28°は関連ペロブスカイトで報告される領域ですが、基板・X線源確認前に各ピークへ相名を断定しません。24°近傍も同様です。',
 '- n=4、各組成2膜。相関係数や回帰による一般化は行いません。成膜後の相変化・PbI2生成はこの初期XRDのみでは確認できません。',
 '', '## 図','',
 '1. 01_xrd_raw：4本の生データ（cps）','2. 02_xrd_zoom：主な領域の重ね描き（14°ピークで規格化）','3. 03_peak14_width：約14°の位置・見かけ幅','4. 04_color_time_series：補正済みRGBの時間変化','5. 05_xrd_vs_color：初期XRD特徴と0→3 hの色変化の対応（探索的）','',
 'PNGとPDFを保存。数値はpaired_features.csv。再実行：python notebooks/film_time_series/xrd_image_comparison.py（numpy、matplotlibが必要）。']
 (OUT/'report.md').write_text('\n'.join(lines),encoding='utf-8');print(json.dumps(features,indent=2))
if __name__=='__main__':main()
