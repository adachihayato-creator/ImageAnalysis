"""Report all prespecified conditions without selecting the best result."""
from pathlib import Path
import csv,json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import fontManager
ROOT=Path(__file__).resolve().parents[2];O=ROOT/'results/20261117/06_xrd_ratio_prediction'
fontManager.addfont('/mnt/c/Windows/Fonts/YuGothR.ttc');plt.rcParams.update({'font.family':'Yu Gothic','font.size':11})
def read(n):return list(csv.DictReader((O/n).open(encoding='utf-8-sig')))
scores=read('validation_scores.csv');pred=read('out_of_film_predictions.csv');summary=json.loads((O/'summary.json').read_text());names=['training_mean','conditions','image','conditions_plus_image'];labels=['平均値だけ','組成・作製条件等','画像だけ','条件等＋画像'];colors=['#999999','#287bab','#dc8a26','#27955f']
fig,axes=plt.subplots(1,3,figsize=(14,5))
for ax,analysis,split,title in zip(axes,['today_gap_le30','all_batches_exploratory','all_batches_exploratory'],['leave_one_film_out','leave_one_film_out','older_to_today'],['今日・時差30分以内\n12組・9膜、膜単位で評価','過去＋今日\n25組・13膜、膜単位で評価','過去で学習→今日を予測\n過去4膜で学習・今日9膜で評価']):
 rs=[r for r in scores if r['analysis']==analysis and r['split']==split and r['corrected']=='True' and float(r['margin'])==0]
 vals=[float(next(r for r in rs if r['model']==m)['film_weighted_MAE']) for m in names];ax.bar(range(4),vals,color=colors)
 for i,v in enumerate(vals):ax.text(i,v+.012,f'{v:.3f}',ha='center')
 ax.set_xticks(range(4),labels,rotation=25,ha='right');ax.set_ylim(0,.85);ax.set_ylabel('平均絶対誤差（膜ごとの平均を等重み）');ax.set_title(title);ax.grid(axis='y',alpha=.2)
fig.suptitle('XRD候補ピーク面積比の試作予測／小さい誤差ほど良い／相含有率や正解率ではない');fig.tight_layout();fig.savefig(O/'02_モデルの予測誤差.png',dpi=150,bbox_inches='tight');plt.close(fig)
fig,axes=plt.subplots(1,2,figsize=(11,5))
for ax,m,label in zip(axes,['conditions','conditions_plus_image'],['条件等だけ','条件等＋画像']):
 rs=[r for r in pred if r['analysis']=='all_batches_exploratory' and r['split']=='leave_one_film_out' and r['corrected']=='True' and float(r['margin'])==0 and r['model']==m]
 for batch,col in [('20261015','#999999'),('20261112','#dc8a26'),('20261117','#287bab')]:
  ss=[r for r in rs if r['batch']==batch];ax.scatter([float(r['observed']) for r in ss],[float(r['predicted']) for r in ss],label=batch,color=col)
 ax.plot([-.25,2.5],[-.25,2.5],'k--',lw=1);ax.set_xlim(-.25,2.5);ax.set_ylim(-.25,2.5);ax.set_title(label);ax.set_xlabel('XRDから計算した面積比');ax.set_ylabel('未使用膜に対する予測値');ax.grid(alpha=.2);ax.legend()
fig.suptitle('斜めの線に近いほど良い／同じ膜の全時点を一緒に除外して予測');fig.tight_layout();fig.savefig(O/'03_実測と予測.png',dpi=150,bbox_inches='tight');plt.close(fig)
fig,axes=plt.subplots(1,2,figsize=(12,4.8))
for ax,a,title in zip(axes,['today_gap_le30','all_batches_exploratory'],['今日・時差30分以内','過去＋今日']):
 for m,col,lab in [('conditions','#287bab','条件等'),('conditions_plus_image','#27955f','条件等＋画像')]:
  vals=[]
  for corr,margin in [('False',0.),('True',0.),('False',.18),('True',.18)]:vals.append(float(next(r for r in scores if r['analysis']==a and r['split']=='leave_one_film_out' and r['corrected']==corr and float(r['margin'])==margin and r['model']==m)['film_weighted_MAE']))
  ax.plot(range(4),vals,'o-',label=lab,color=col)
 ax.set_xticks(range(4),['未補正・全体','補正・全体','未補正・中央','補正・中央'],rotation=15);ax.set_title(title);ax.set_ylabel('膜単位の平均絶対誤差');ax.legend();ax.grid(alpha=.2)
fig.suptitle('画像の効果が補正や領域を変えて残るか／中央は外周18%除外');fig.tight_layout();fig.savefig(O/'04_補正と領域による影響.png',dpi=150,bbox_inches='tight');plt.close(fig)
text='''# 画像からXRD面積比を推定する予備試験

## 結論

試作は実行できたが、画像を使う追加価値はまだ確認できない。今日の時差30分以内・全体補正画像では条件等のみMAE0.521→条件等＋画像0.493と小幅低下。しかし外周18%除外・補正後では0.521→0.523と改善せず。過去を加えた25組・13膜では0.406→0.414へ悪化。過去4膜で学習して今日9膜を評価すると0.650→0.645で、平均値予測0.613より悪い。写真だけのモデルも条件等だけのモデルを上回らなかった。画像でXRDを代替できる、精度が実用的、PbI2を定量したという結論にはしない。

## 対象

今日10膜28測定＋11/12の3膜の1h/1day計6測定＋10/15の4膜の0h計4測定＝38候補・17膜を確認。13測定は候補ピークを安定に抽出できず除外し、ゼロに置き換えない。残る25測定・13膜を探索的に使用。候補ピークが抽出しやすい膜に偏っているため、全膜に対する性能ではない。

今日のみは19組・9膜。撮影と測定の時間差30分以内に仮に制限すると12組・9膜。30分は材料の安定性を保証する根拠のある境界ではなく、時間差の影響を見る暫定的な運用条件。過去データは公称時点の対応のみで正確な時差を確認できないため主評価と分けた。XRDのない11/10のSn5%膜は教師付き予測に使用しない。

## 予測対象と抽出

12.25–13.0°の候補ピーク正味面積を13.4–14.7°主ピーク正味面積で割る。5点移動平均・両側中央値の直線背景。背景3種類のうち2種類以上で既存のピーク抽出規則を満たした場合のみ、成立した比の中央値を目的変数に使用。成立しなかったものは欠測。副相の含有率ではない。組成をまたいで同じ化学相と確認したモデルではなく、指定角度窓の相対XRD信号を予測した探索。ピーク帰属の確認が今後必要。比が1を超えても物理的な含有率100%超という意味ではない。

## 入力と評価

条件等：Sn比、Rb添加系か、FA比、アニール温度・時間、滴下量、公称XRD経過時間。画像：全体または中央の平均RGB、明るさCV、明るい斑点候補面積率、細かな模様の相対標準偏差。組成や工程の未確認値は欠測のまま、学習側の中央値と欠測指示変数で処理。過去と今日ではRb添加量も異なるが、旧量の定義が揃わないためRb添加系かという粗い指標のみ。条件モデルも情報不足の基準モデルである。

モデルはRidge回帰、alpha10固定。テスト結果を見て最適モデルを選んだり調整したりしない。欠測補完・標準化は各学習データ内で実施。同じ膜の全時点をまとめて除外するleave-one-film-out。膜ごとの学習重みと評価重みをそろえる。画像だけでなく単なる学習平均、条件等だけと比較。補正有無×全体/中央の4条件を全提示。MAEは予測誤差の大きさで、精度何%という値ではない。

## 重要な制限

XRDと画像は同時ではなく、全期間で撮影装置条件も異なる。今日のデータのみの評価は同日・同条件の他の膜を学習できる評価で、未知の作製日や未知組成に使えるという意味ではない。過去→今日は4膜しか学習に残らず条件範囲も異なるため、不成功を画像に情報がない証明とはしない。反射、傷、ピントも画像特徴に入る。独立膜数が少なく、誤差差の統計的有意性・予測区間は評価していない。化学的劣化、良膜/不良膜、効率、将来寿命の予測ではない。

## 図とファイル

- 02_モデルの予測誤差.png：最初に見る図。左が今日、中央が全データ、右が過去→今日。
- 03_実測と予測.png：斜めの線に近いほど一致。同じ膜のデータは学習から除外。
- 04_補正と領域による影響.png：解析条件を変えると画像追加の小さな改善が消えることを確認。
- all_candidates.csv：採用/除外を含む全38候補、時間差、ピーク成立条件。
- out_of_film_predictions.csv：各未使用膜の実測・予測・誤差。
- validation_scores.csv：全条件の評価。
- input_manifest.json / analysis_config.json：入力のSHA256と方法。

## 次の一歩

まず独立した作製日と膜を増やし、測定終了後できるだけ短時間で画像を撮る。条件をそろえた同組成内で、参照パターンに基づいたピーク帰属と抽出の再現性を確かめる。その後、作製日を丸ごと外した評価で画像追加の効果が残るか調べる。現時点で深層学習に替えるだけで解決する根拠はない。

再実行：PYTHONPATH=/tmp/film-analysis-deps MPLCONFIGDIR=/tmp/film-mpl OPENBLAS_NUM_THREADS=1 python3 notebooks/prediction/predict_xrd_ratio.py
図・説明：同じ環境で notebooks/prediction/report_xrd_ratio.py
'''
(O/'README.md').write_text(text)
print('Saved3reportfigures andREADME')
