from pathlib import Path
import csv,json
P=Path('data/processed/20261113/05_threshold_5to50');read=lambda n:list(csv.DictReader((P/n).open(encoding='utf-8-sig')))
primary=read('primary_threshold_metrics.csv');allrows=read('all_threshold_metrics.csv');regional=[]
for t in range(5,51,5):
 rows=[r for r in primary if int(r['threshold_percent'])==t];order=sorted(rows,key=lambda r:-float(r['inside_edge5_area_percent']));count=0
 for corrected in ['False','True']:
  for sigma in ['6.0','8.0','12.0']:
   group=[r for r in allrows if int(r['threshold_percent'])==t and r['corrected']==corrected and r['sigma_px']==sigma]
   winner=max(group,key=lambda r:float(r['inside_edge5_area_percent']));count+=winner['anneal_min']=='15'
 regional.append({'threshold_percent':t,'inside_edge5_primary_order':' > '.join(r['anneal_min'] for r in order),'15min_largest_settings':count,'settings':6})
with (P/'rank_inside_edge5.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(regional[0]));w.writeheader();w.writerows(regional)
lines=['# 明るい斑点候補のしきい値：5〜50%で比較','',
'## 結論','',
'**全体解析では、5〜50%の全しきい値で15分膜の斑点候補面積が最大でした。** ただし高いしきい値では最外周帯の寄与が増えます。最外周約5%帯を除く参考比較では20%以上で10分膜が最大になるため、「しきい値を上げても副相候補と同じ対応が維持された」と無条件には結論しません。','',
'## 見る図','',
'- [しきい値と面積の曲線](01_しきい値と面積の曲線.png)：左は基板全体、右は最外周約5%帯の内側。線σ8px、帯σ6〜12px（統計的な信頼区間ではない）。',
'- [10/20/30/50%で残った場所](02_10_20_30_50パーセントの抽出.png)：黄色が抽出された候補。高いしきい値で何が残るかを目視確認できます。','',
'## 基板全体の面積割合','',
'同じ公称1hの3膜、共通の色補正、局所平均Gaussianσ8px、連結3画素以上、外周・楕円除外なし。','',
'| 周囲との明暗差しきい値 | 5分膜 | 10分膜 | 15分膜 |','|---|---:|---:|---:|']
for t in [5,10,15,20,25,30,35,40,45,50]:
 rr=[r for r in primary if int(r['threshold_percent'])==t];lines.append('| '+str(t)+'% | '+' | '.join(f"{float(r['full_area_percent']):.2f}%" for r in rr)+' |')
lines+=['','しきい値を上げると面積は減少します。全体では、10%だけでなく20・30・50%でも15分膜が最大です。ただし30%では10分と15分の差が約0.24ポイントと小さく、有意な差と検証していません。5分と10分の順位は10→15%で逆転しており、どのしきい値でも3膜の並びが全て同じというわけではありません。','',
'## 高いしきい値では、何が残るか','',
'50%のとき、検出した候補画素のうち最外周約5%幅の帯にある割合は、5分膜93.8%、10分膜42.5%、15分膜64.8%でした。しきい値を高くすると、強い斑点だけでなく基板の縁・反射等も相対的に残りやすい結果です。最外周帯の全てを反射と同定したわけではありません。','',
'### 最外周約5%帯の内側だけを集計すると','',
'全体で抽出した同じ候補画素を使い、縁の帯以外の面積を分母として集計しました。5%という帯幅は感度確認の暫定値で、物理的な膜境界の同定ではありません。','',
'| しきい値 | 5分膜 | 10分膜 | 15分膜 |','|---|---:|---:|---:|']
for t in [10,20,30,50]:
 rr=[r for r in primary if int(r['threshold_percent'])==t];lines.append('| '+str(t)+'% | '+' | '.join(f"{float(r['inside_edge5_area_percent']):.2f}%" for r in rr)+' |')
lines+=['','この参考範囲では、10%で15分膜が最大ですが、20・30・50%では10分膜が最大。補正有無とぼかし幅を変えた6設定でも、これら各しきい値で同じ最大膜となりました。高しきい値における全体の順位は、縁付近を含めるかに依存します。10分膜には曲線状の線等もあり、内部の明るい画素も全て化学的斑点とみなせません。','',
'## 10%という定義について何が言えるか','',
'10%だけを使ったために全体の15分膜が最大になったわけではありません。一方、この検証から10%が科学的に最適な値と決まったわけでもありません。10%は比較的淡い明部の広がり、30〜50%は強い明部を評価し、別の特徴を見ています。','',
'**15分が最大になる値を選ぶのではなく、しきい値を上げたときの面積の減り方や、検出場所が縁/内部のどちらかも併せて評価する**ことが重要です。今回の画像特徴は副相候補との関連を検討する探索段階で、PbI₂の位置・含有率や膜の良否を求めた解析ではありません。','',
'## 方法と保存データ','',
'しきい値5,10,…,50%。(I−Gaussian(I))/max(Gaussian(I),1)を使用。50%は周囲より1.5倍を超える明るさで、相含有率50%という意味ではありません。グレースケールはJPEG RGBの重み付き和。Gaussianσ6/8/12px、補正あり/なし、全体65536画素。連結3画素以上の条件を維持。補正の基準・原写真・位置合わせは従来と同じです。','',
'全体で抽出した同じマスクを中央・最外周・その内側へ分配し、抽出条件を地域ごとに変更していません。原本は変更していません。XRDは既存の公称1hとの対応のみで、PC時計は使っていません。独立膜数は3、強い副相候補ピークの独立膜は1です。処理設定数を独立試料や分類精度と解釈しません。','',
'all_threshold_metrics.csv＝3膜×補正2×ぼかし3×しきい値10＝180行、primary_threshold_metrics.csv＝主条件30行、rank_by_threshold.csv＝全体の順位、rank_inside_edge5.csv＝内側の順位、input_manifest.json＝原本SHA-256、analysis_config.json＝条件。','',
'再実行：python3 notebooks/film_time_series/spot_threshold_sweep.py → python3 notebooks/film_time_series/report_spot_threshold_sweep.py（リポジトリ直下）。']
(P/'README.md').write_text('\n'.join(lines)+'\n');f=P.parent/'README.md';s=f.read_text();link='\n[斑点しきい値5〜50%の比較](05_threshold_5to50/README.md)\n';f.write_text(s+link if link not in s else s)
print('しきい値比較の説明を保存')
