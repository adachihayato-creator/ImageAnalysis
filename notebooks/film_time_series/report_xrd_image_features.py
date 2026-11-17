from pathlib import Path
import csv,json,hashlib
P=Path('results/20261113/01_xrd_image_features');read=lambda n:list(csv.DictReader((P/n).open(encoding='utf-8-sig')))
rs=read('paired_image_xrd.csv');ranks=read('rank_sensitivity_summary.csv');follow=read('same_film_followup.csv')
lines=['# 約12.7°の副相候補ピークと画像特徴の探索','',
'## 結論','',
'**今回、副相候補のピークが強い15分アニール膜では、局所的に明るい斑点の候補領域が、5分・10分膜より広いという対応が見つかりました。** これは今回の1枚の強ピーク膜についての探索的な対応であり、明るい斑点をPbI₂と同定した結果ではありません。','',
'## 見る図','',
'- [画像と斑点の抽出](01_画像特徴の抽出.png)：上段＝公称1hの膜、中段＝黄色が抽出した候補領域、下段＝周囲に対する明暗差。',
'- [3膜の特徴比較](02_3膜の特徴比較.png)：斑点の面積・細かな模様・広い色むらを別々に評価。',
'- [対応する公称1h XRD](03_対応するXRD.png)：右の範囲はXRD背景3条件の違いで、統計誤差ではありません。','',
'## 同じ公称1hでの主結果','',
'| アニール | 副相候補/主相候補の面積比 | 明るい斑点の面積 | 明るさで規格化した細かな模様 | 広い色むら/平均明るさ |','|---|---|---:|---:|---:|']
for r in rs:
 ratio=f"{float(r['xrd_1h_low_main_area_min']):.3f}〜{float(r['xrd_1h_low_main_area_max']):.3f}" if r['xrd_1h_low_main_area_min'] else '抽出不成立（ゼロではない）'
 lines.append(f"| {r['anneal_min']}分 | {ratio} | {float(r['bright_area_percent']):.1f}% | {float(r['relative_fine_pattern_sd']):.3f} | {float(r['gray_spatial_cv']):.3f} |")
lines+=['','**15分膜の斑点候補の面積は、5分より約3.2ポイント、10分より約4.0ポイント大きい**値でした。斑点面積17%は画像の抽出領域の割合であり、PbI₂の含有率・体積比ではありません。','',
'細かな模様も主条件では15分膜が大きい一方、広い色むらは10分膜が最大でした。単に「最も色むらが大きい膜＝副相候補ピークが最も強い膜」とはなっていません。斑点の個数・大きさ・中央/周辺比は、抽出条件で順位が変わるため主要な特徴候補にはしていません。','',
'## 条件を変えても残るか','',
'補正あり/なし、外周12/18/24%除外、中央楕円の包含/除外、局所平均のGaussian幅6/8/12px、明暗差しきい値5/10/15%を組み合わせた108条件を確認しました。**明るい斑点の面積で15分膜が最大だったのは103/108条件**でした。残り5条件では別の膜が最大であり、全条件で一致したわけではありません。','',
'108は処理設定の組合せ数で、独立した試料数・正解率・確率ではありません。指標を複数探索したため、新しい膜での検証が必要です。元画像と補正画像で比較し、画像全体の単なる明るさ差への依存を減らすため局所的な相対明暗差を使用しました。ただし照明・反射・ピント・JPEG処理の影響をなくしたわけではありません。','',
'色の特徴では15分膜の平均b*が全設定で最も高い結果でしたが、RGBから計算したLabは色校正されておらず、公称1hの撮影状態の差もあるため、相同定や黄色化の確証には使いません。主な候補は局所斑点面積としました。','',
'## 他の時点にも特徴が見えるか','',
'同じ膜の公称3h/4hにも同じ斑点抽出を適用しました。これらは撮影状態に問題のある3枚を含まない補助確認です。','',
'| 写真の公称時点 | 5分膜 | 10分膜 | 15分膜 |','|---|---:|---:|---:|']
for age in ['1h','3h','4h']:
 rr=[r for r in follow if r['nominal_image_age']==age];lines.append('| '+age+' | '+' | '.join(f"{float(r['bright_area_percent']):.1f}%" for r in rr)+' |')
lines+=['','15分膜の斑点候補面積が大きい傾向は、同じ膜の別時点でも見られました。ただし同じ膜を繰り返し見ているため、独立した強ピーク膜が増えたわけではありません。また3h/4hには対応するXRDがないため、XRDとの同時点の対応の検証には数えません。','',
'## 研究として言えること','',
'発表では、次の表現が適切です。','',
'> 公称1hの3膜を比較したところ、約12.7°の副相候補ピークが強い15分アニール膜では、局所的に明るい斑点の面積が大きかった。この傾向は処理条件を変えた多くの設定および同じ膜の別時点でも残り、画像から副相候補の出現を評価するための特徴候補となった。','',
'「斑点がPbI₂である」「斑点面積から副相の含有率を求めた」「この特徴で新しい膜を分類できる」「15分アニールが原因」「15分膜の性能が最も悪い」とは言えません。強ピーク群が1膜で、条件と個体差が交絡しています。XRDは試料全体の信号であり、画像中の特定の斑点と空間的に対応した測定でもありません。','',
'## 方法・データ上の注意','',
'- FA:Cs=9:1、Sn:Pb=1:9、SnF₂ 0.1mol%、130℃、ガラス基板・下地なし。アニール時間5/10/15分、独立膜は計3枚。',
'- 主比較は公称1hで画像とXRDがそろう3膜。XRD用PC時計は不正確なので絶対時刻・同時撮影の推定には使っていません。',
'- 15分膜の1h写真は以前、背景色の問題があった撮影回です。今回はこの時点でのXRDとの対応を探索するため、補正あり/なしと別時点の画像で感度を確認し、確定的な結論を避けています。',
'- **膜間比較のため背景補正の基準を3膜で共通にしました。** 5分膜1hの紙4領域の平均RGBを使用。以前の各膜の初回を別々の基準にした経時解析とは、補正後RGBの絶対値が異なります。',
'- 元画像から基板四隅で256×256へ整形。主条件は各辺18%除外、中央楕円を含む。Labは参考指標で色校正なし。',
'- グレースケールはJPEG RGBの重み付き和(0.2126R+0.7152G+0.0722B)。局所相対明暗差=(I−Gaussianσ8(I))/Gaussianσ8(I)、10%超かつ連結3画素以上の領域を明るい斑点候補と定義。線・傷・反射も含み得ます。物理的な結晶粒や析出物のセグメンテーションではありません。',
'- 斑点面積の分母は解析対象画素数。解析端をまたぐ成分は観察された断片として残すため、個数・サイズはROI境界にも依存します。',
'- 細かな模様はGaussianσ0.7とσ3の差の標準偏差を平均明るさで割った値。広い色むらは明るさ標準偏差/平均。単位なしで、結晶性・膜厚むらの直接測定ではありません。',
'- XRD面積比は従来の局所背景3条件、低角側積分12.25〜13.0°、主ピークは既存処理。5分1hは全背景で抽出不成立なので0とはせず、相関係数・検定・機械学習は行っていません。','',
'原本は変更していません。paired_image_xrd.csv、primary_features.csv、all_feature_sensitivity.csv、rank_sensitivity_summary.csv、same_film_followup.csvに数値。input_manifest.json/analysis_config.jsonに入力と条件。','',
'再実行（リポジトリ直下）：explore_xrd_image_features.py → explore_xrd_image_followup.py → report_xrd_image_features.py（notebooks/film_time_series内）。NumPy/OpenCV/Pillow/Matplotlibと日本語フォント使用。']
(P/'README.md').write_text('\n'.join(lines)+'\n')
# Track supplementary photographs and feature extraction inputs too.
f=P/'input_manifest.json';manifest=json.loads(f.read_text());seen={m['path'] for m in manifest}
for r in follow:
 p=next(Path('data/raw').rglob(r['filename']))
 for source,kind in [(p,'followup_photo'),(p.with_suffix('.json'),'followup_metadata')]:
  if str(source) not in seen:manifest.append({'path':str(source),'kind':kind,'sha256':hashlib.sha256(source.read_bytes()).hexdigest()});seen.add(str(source))
f.write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
f=P.parent/'README.md';f.write_text('# 2026年11月13日\n\n[約12.7°の副相候補と画像特徴の探索](01_xrd_image_features/README.md)\n')
print('探索解析の結果をまとめました')
