"""Sensitivity to middle captures and simple background normalization."""
from pathlib import Path
import csv,json,hashlib
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import fontManager
ROOT=Path(__file__).resolve().parents[2];P=ROOT/'results/20261112/03_image_time_series';O=ROOT/'results/20261112/06_background_sensitivity';O.mkdir(exist_ok=True)
fontManager.addfont('/mnt/c/Windows/Fonts/YuGothR.ttc');plt.rcParams['font.family']='Yu Gothic'
rows=list(csv.DictReader((P/'metrics.csv').open(encoding='utf-8-sig')));COL=['#cf493f','#278d4f','#426dc9'];results=[]
fig,axes=plt.subplots(3,4,figsize=(17,11))
for i,m in enumerate([5,10,15]):
 rs=[r for r in rows if int(r['anneal_min'])==m];assert len(rs)==3
 for j,(exclude,correct) in enumerate([(False,False),(False,True),(True,False),(True,True)]):
  selected=[rs[0],rs[-1]] if exclude else rs;x=np.array([float(r['hours_since_first_photo']) for r in selected]);ax=axes[i,j]
  for k,c in enumerate('RGB'):
   key=('bg_normalized_delta_' if correct else 'delta_')+c;y=np.array([float(r[key]) for r in selected]);slope=float(np.polyfit(x,y,1)[0]);delta=float(y[-1]-y[0])
   results.append({'anneal_min':m,'channel':c,'exclude_middle':exclude,'background_normalized':correct,'n':len(x),'slope_rgb_per_hour':slope,'endpoint_delta_rgb':delta,'monotonic_at_observed_times':bool(np.all(np.diff(y)>=0) or np.all(np.diff(y)<=0))})
   ax.plot(x,y,'o-',color=COL[k],label=c,lw=1.5)
  ax.axhline(0,color='gray',lw=.6);ax.grid(alpha=.2);ax.legend();ax.set_title(f'{m}分：'+('途中を除く' if exclude else '全3枚')+'／'+('背景補正' if correct else '補正なし'));ax.set_xlabel('最初の写真からの実時間 (h)');ax.set_ylabel('最初の写真からのRGB変化量')
fig.suptitle('背景の異なる途中3枚への感度：4通りを比較\n各条件1膜／2点の直線は途中経過の証明ではない／色補正はJPEGの比率補正',fontsize=15);fig.tight_layout(rect=[0,0,1,.94]);fig.savefig(O/'01_4通りの比較.png',dpi=150);fig.savefig(O/'01_4通りの比較.pdf');plt.close(fig)
summary=[]
for m in [5,10,15]:
 for c in 'RGB':
  rs=[r for r in results if r['anneal_min']==m and r['channel']==c];signs=[np.sign(r['slope_rgb_per_hour']) for r in rs];summary.append({'anneal_min':m,'channel':c,'same_slope_direction_all_four':len(set(signs))==1,'slopes':';'.join(f"{r['slope_rgb_per_hour']:.5f}" for r in rs),'raw_endpoint_delta':rs[0]['endpoint_delta_rgb'],'corrected_endpoint_delta':rs[1]['endpoint_delta_rgb'],'note':'descriptive only, no uncertainty or significance threshold'})
for name,data in [('four_way_metrics.csv',results),('direction_summary.csv',summary)]:
 with (O/name).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
fig,axes=plt.subplots(1,3,figsize=(13,4.5))
for ax,m in zip(axes,[5,10,15]):
 rs=[r for r in summary if r['anneal_min']==m];x=np.arange(3)
 ax.bar(x-.18,[r['raw_endpoint_delta'] for r in rs],.36,label='補正なし',color='#777777');ax.bar(x+.18,[r['corrected_endpoint_delta'] for r in rs],.36,label='背景で簡易補正',color='#e5a34e');ax.set_xticks(x,list('RGB'));ax.axhline(0,color='black',lw=.8);ax.set_title(f'{m}分：最初→最新');ax.set_ylabel('RGB変化量');ax.legend();ax.grid(axis='y',alpha=.2)
fig.suptitle('端点の変化：途中を除いても同じ値なので独立した裏付けではない');fig.tight_layout();fig.savefig(O/'02_最初と最新の比較.png',dpi=160);fig.savefig(O/'02_最初と最新の比較.pdf');plt.close(fig)
lines=['# 途中3枚を含める／外す・背景補正あり／なしの比較','',
'[4通りの時系列](01_4通りの比較.png) と [最初・最新の差](02_最初と最新の比較.png)。','',
'問題の途中写真：5分2h 17:53:49、10分2h 17:54:29、15分1h 17:55:16。最新は差し替え後の18:59〜19:01を採用。元写真は削除していません。','',
'## 比較の読み方','',
'4通りそれぞれでRGBを実撮影時刻に対して並べ、直線の傾きの符号を記述的に比較しました。途中を除いた場合は2点を結ぶだけで、変化の形状や統計的な有意性を示しません。端点の差は途中写真の有無で変わらないため、それだけで「頑健」とは判断しません。','',
'背景補正は固定した紙4領域の平均RGB比を各成分に掛ける簡易補正。補正後も膜の真の色とはみなしません。数値の増減は劣化方向を意味しません。','',
'## 結果','',
'| アニール | 成分 | 最初→最新・補正前 | 背景補正後 | 4通りの傾きの方向 |',
'|---|---|---:|---:|---|']
for r in summary:lines.append(f"| {r['anneal_min']}分 | {r['channel']} | {r['raw_endpoint_delta']:+.2f} | {r['corrected_endpoint_delta']:+.2f} | {'一致' if r['same_slope_direction_all_four'] else '不一致・保留'} |")
lines+=['','**傾きの方向が一致しても、小さな差を材料変化と認定することはできません。** 同条件・同膜の撮り直し誤差が今回の各時点にないため、検出限界や有意差は設定していません。','',
'## 模様・色むらの扱い','',
'色むらと細かな模様の補正前結果は[既存グラフ](../03_image_time_series/02_色と模様の経時変化.png)を参照。背景の成分別定数を掛けるだけの補正では、各成分の標準偏差も同じ係数で機械的に変わります。その補正結果を模様の物理的な改善の裏付けにはしません。途中を除くと模様の一時的変化は評価できません。','',
'## XRDとの対応','',
'XRD0h/1hと写真0h/1hを両方持つのは15分膜のみですが、その1h写真が今回の背景問題の対象です。補正あり／なしでの参考比較は残せる一方、問題画像を除くと、この膜の0→1h画像変化とXRD変化の直接比較はできなくなります。したがって「画像変化とXRD変化が対応する」は現段階では保留します。5分・10分は0h写真がなく、最新時点のXRDも未取得です。','',
'各条件1膜の探索解析で、アニール時間の効果・良否・寿命は結論しません。','',
'## 再生成・記録','',
'コード：notebooks/film_time_series/sn10_sensitivity.py。入力：03_image_time_series/metrics.csv。元データとROI・背景領域は同フォルダのinput_manifest.json/analysis_config.json。CSVは傾き・端点差の全4通りと符号判定を保存。']
(O/'README.md').write_text('\n'.join(lines)+'\n');(O/'analysis_config.json').write_text(json.dumps({'input':str((P/'metrics.csv').relative_to(ROOT)),'sha256':hashlib.sha256((P/'metrics.csv').read_bytes()).hexdigest(),'slope_method':'unweighted least squares, descriptive only','four_cases':['all_raw','all_bg_normalized','endpoints_raw','endpoints_bg_normalized'],'middle_exclusion_reason':'background color shift','robustness':'same slope sign across four cases; no significance claim'},ensure_ascii=False,indent=2))
for r in summary:print(r)
