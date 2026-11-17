from pathlib import Path
import csv,json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import fontManager
ROOT=Path(__file__).resolve().parents[2];O=ROOT/'results/20261117/07_image_time_prediction'
fontManager.addfont('/mnt/c/Windows/Fonts/YuGothR.ttc');plt.rcParams.update({'font.family':'Yu Gothic','font.size':11})
def read(n):return list(csv.DictReader((O/n).open(encoding='utf-8-sig')))
scores=read('validation_scores.csv');pred=read('heldout_predictions.csv');ab=read('image_feature_ablation.csv');summary=json.loads((O/'summary.json').read_text())
models=['persistence','linear_trend','training_mean_change','ridge','random_forest'];labels=['変化しない','直前の傾向を延長','学習膜の平均変化','Ridge回帰','ランダムフォレスト'];colors=['#999999','#b88e59','#7799bb','#287bab','#27955f']
fig,axes=plt.subplots(1,3,figsize=(15,5))
for ax,split,title in zip(axes,['leave_one_film_out','leave_one_batch_out','older_to_today'],['膜単位で分割\n19膜・64組','撮影日グループを丸ごと除外\n4グループ・19膜','過去9膜で学習→今日10膜\n今日36組で評価']):
 rs=[r for r in scores if r['mode']=='exclude_known_bad' and r['corrected']=='True' and float(r['margin'])==0 and r['split']==split];vals=[float(next(r for r in rs if r['model']==m)['film_weighted_MAE_RGB']) for m in models];ax.bar(range(5),vals,color=colors)
 for i,v in enumerate(vals):ax.text(i,v+.025,f'{v:.2f}',ha='center')
 ax.set_xticks(range(5),labels,rotation=30,ha='right');ax.set_ylim(0,1.65);ax.set_title(title);ax.set_ylabel('平均RGBの予測誤差（JPEG RGB単位）');ax.grid(axis='y',alpha=.2)
fig.suptitle('30〜120分後の平均RGB予測／組成やXRDは入力しない／小さい誤差ほど良い');fig.tight_layout();fig.savefig(O/'01_まず見る_予測誤差.png',dpi=150,bbox_inches='tight');plt.close(fig)
fig,axes=plt.subplots(1,2,figsize=(11,5))
for ax,split,title in zip(axes,['leave_one_film_out','older_to_today'],['19膜の膜単位評価','過去で学習→今日を予測']):
 vals=[float(next(r for r in ab if r['split']==split and r['model']==m)['film_weighted_MAE_RGB']) for m in ['history_only','meanRGB_plus_history','all_image_plus_history']];ax.bar(range(3),vals,color=['#999999','#dc8a26','#287bab']);ax.set_xticks(range(3),['過去のRGB変化と時間だけ','＋現在の平均RGB','＋色むら・斑点・模様も'],rotation=20,ha='right');ax.set_ylim(0,1.2);ax.set_title(title);ax.set_ylabel('平均絶対誤差')
 for i,v in enumerate(vals):ax.text(i,v+.02,f'{v:.3f}',ha='center')
 ax.grid(axis='y',alpha=.2)
fig.suptitle('画像の詳細特徴を加える効果は、今日への予測では確認できない');fig.tight_layout();fig.savefig(O/'02_画像特徴を加える効果.png',dpi=150,bbox_inches='tight');plt.close(fig)
fig,axes=plt.subplots(1,2,figsize=(12,5))
for ax,corr,title in zip(axes,['True','False'],['背景補正後の予測','未補正の予測']):
 for mode,col in [('exclude_known_bad','#287bab'),('include_known_bad','#dc8a26')]:
  vals=[]
  for model in models:vals.append(float(next(r for r in scores if r['mode']==mode and r['corrected']==corr and float(r['margin'])==0 and r['split']=='leave_one_film_out' and r['model']==model)['film_weighted_MAE_RGB']))
  ax.plot(range(5),vals,'o-',color=col,label='既知の問題画像を除く' if mode.startswith('exclude') else '既知の問題画像を含む')
 ax.set_xticks(range(5),labels,rotation=25,ha='right');ax.set_title(title);ax.set_ylabel('平均RGBの予測誤差');ax.legend();ax.grid(alpha=.2)
fig.suptitle('撮影環境の影響を含む／補正前後は予測する値の定義も異なる');fig.tight_layout();fig.savefig(O/'03_背景条件による違い.png',dpi=150,bbox_inches='tight');plt.close(fig)
text='''# 画像を中心にした時間変化の予測

## 今回選んだ課題

「現在の膜画像と、それまでの変化から、次の撮影（30〜120分後）の平均RGBを予測する」。0h/1h/2hに限定しないため、0hがない先週のSn5%膜も利用できる。10/15・11/10〜11・11/12〜13・11/17の19膜、98枚を確認し、主解析では正解画像のある64組を作った。組成・作製者・XRD・日付・膜IDはモデルに入力しない。撮影間隔を入力する。

- 10/15：4膜・20組
- 11/10〜11：Sn5%の2膜・2組
- 11/12〜13：Sn10%の3膜・6組
- 11/17：10膜・36組

元画像の枚数98は、その後の追加撮影を含む時点の数。24h/1day画像は一覧に保持するが、30〜120分先の課題では長すぎるため正解組から除いた。11/12の既知の背景不良3枚は主解析から除き、含める場合も別に評価。時点を飛ばしても時間差が範囲内なら使う。19膜を増幅して64独立膜と数えるものではない。

## 結果

補正後・外周と中央楕円を含めた全体平均RGBの予測。誤差は各膜内で平均し、その後19膜を等重みで平均したMAE。RGBの0〜255に対応する値のずれで、正解率ではない。

| 方法 | 膜単位で分割（19膜） | 過去9膜で学習→今日10膜 |
|---|---:|---:|
| 変化しない | 1.171 | 1.319 |
| 直前の変化が続く | 1.223 | 1.337 |
| 学習膜の平均変化を使う | 0.854 | 0.914 |
| Ridge回帰 | 0.781 | 0.865 |
| ランダムフォレスト | 0.816 | 0.851 |

Ridge回帰を事前に主モデル、ランダムフォレストを比較モデルとした。結果を見て最良のモデルだけを選んでいない。単なる「変化しない」より短時間先の平均色を近く予測できた。一方、平均的な変化を使うだけでもかなり改善し、それに対する機械学習の追加改善は小さい。

画像の詳細特徴を加える価値の切り分け：過去のRGB変化と時間だけのRidgeは0.805、現在の平均RGB・色むら・斑点・模様も加えると0.781（膜単位）。しかし過去→今日では0.836→0.865と悪化。現在の画像の詳細な模様が予測に不可欠だ、という根拠は得られなかった。過去傾向からの平均色予測の試作は成立したが、詳細模様から将来を読む研究成果としてはまだ弱い。

日付グループを丸ごと外す評価ではRidge0.873、平均変化0.917。未知日の傾向を完全に保証しない。主解析に既知の背景不良画像を加えると、補正後でもRidge1.072、平均変化1.064で、改善は安定しない。未補正の主解析はRidge1.490、変化しない1.752、平均変化1.632。補正は将来の紙の色を入力に漏らすためではなく、答え合わせするRGBを同じ基準で定義するために行う。

## 本当に次の時点も予測した

next_1h_forecasts_UNVERIFIED.csvに、今日の10膜の最新画像から1時間後のRGB予測を保存。学習は過去9膜だけを使用。今日の正解画像や将来の画像は学習しない。主モデルのRidgeの予測と「変化しない」予測を併記。まだ答え合わせしていない予測なので、採用値や実測値と混ぜない。予測対象は、同じ膜の初回写真を背景基準に補正したRGB。将来の照明そのものを予測するものではなく、実画像が届いたら同じ背景正規化で比較する。

## 方法と限界

入力は現在の平均RGB、明るさCV、斑点候補面積率、細かい模様、直前のRGB変化速度（履歴がある場合）、履歴の有無、過去の間隔、予測先までの時間。最初の画像しかないときは過去傾向をゼロとし、履歴なしフラグを付ける。ターゲットは次の平均RGB。内部では時間当たりのRGB変化を回帰して予測間隔を掛け、現在値に足す。次の画像は正解作成だけに使う。

Ridgeはalpha10固定、RandomForestは200木・深さ3・葉の最小4に固定。テスト結果によるパラメータ調整や特徴選択は行わない。標準化は学習側だけで実施。同じ膜の全時点をまとめて学習か評価に置く。学習・評価とも膜ごとの重みを均等にする。膜IDは分割専用でモデルには入らない。

各膜の最初の画像の背景RGBを基準に、その膜の各画像をチャンネル比で補正。初回は予測時点で既に見られる過去画像なので使用可能。将来画像の紙は実測正解を正規化するためだけに使用。補正は物理的な反射率校正ではなく、材料の本当の色を保証しない。未補正と外周18%除外も全提示。10/15は公称時間で、カメラ時刻を記録した11月とは時間精度が異なる。

撮影・保管・経過時間の影響を分離した材料劣化モデルではない。平均RGBを予測しているので、斑点の位置や将来画像そのものは予測していない。独立19膜、日付グループ4で小規模。統計的有意性、実用的な許容誤差、予測区間は確立していない。「RGBが1未満の誤差なら良い膜評価に十分」とは言わない。

## 見る順番

1. 01_まず見る_予測誤差.png：単純な予測と機械学習の比較。
2. 02_画像特徴を加える効果.png：詳細画像特徴の追加価値を確認。
3. next_1h_forecasts_UNVERIFIED.csv：今日の10膜についての未検証の1時間先予測。
4. 03_背景条件による違い.png：背景不良や補正の影響。

数値：validation_scores.csv、heldout_predictions.csv（実測と予測）、forecast_pairs.csv（学習組と除外理由）、image_observations.csv（全時点の画像特徴）。入力ハッシュはinput_manifest.json、条件はanalysis_config.json。

再実行：PYTHONPATH=/tmp/film-analysis-deps MPLCONFIGDIR=/tmp/film-mpl OPENBLAS_NUM_THREADS=1 python3 notebooks/prediction/predict_image_change.py
次に check_image_forecast_ablation.py と report_image_change.py を同じ環境で実行。
'''
(O/'README.md').write_text(text);print('Saved forecast report and3figures')
