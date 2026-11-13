from pathlib import Path
import csv,json
P=Path('data/processed/20261112/09_image_time_series_4points');rows=list(csv.DictReader((P/'metrics.csv').open(encoding='utf-8-sig')))
lines=['# Sn10%：4時点・12枚の画像解析','',
'[12枚の写真](01_膜の時系列.png)／[RGB・模様の経時変化](02_色と模様の経時変化.png)／[背景の影響](03_背景の変動と影響.png)','',
'[補正後の写真と未使用背景での検証](../10_background_corrected_images_4points/README.md)／[問題時点を含める・除く4通りの比較](../11_background_sensitivity_4points/README.md)','',
'## 今回の結論','',
'- 最新19:41〜19:43の3枚を追加しました。古い順にアニール5・10・15分。公称時点は前回の続きとして4h・4h・3hと暫定整理。実際には前回から約42分であり、時刻に基づいて解析しています。',
'- 背景補正後の平均色は前回19時頃から大きくは変わっていません。特に10分膜のB低下は前回から進行せず、15分膜のBもほぼ同じです。したがって一方向に劣化が進んでいるとは結論しません。',
'- 最新画像も背景色の差は残るため、背景補正なしの色変化をそのまま膜の変化とみなしません。',
'- アニール条件間の違いは各条件1膜の観測であり、条件の因果効果や最良条件の判定ではありません。','',
'## 最初の写真から最新まで','',
'| アニール | 公称比較 | 実撮影間隔 | 補正前ΔR/ΔG/ΔB | 背景補正後ΔR/ΔG/ΔB |','|---|---|---:|---|---|']
for m in [5,10,15]:
 rs=[r for r in rows if int(r['anneal_min'])==m];r=rs[-1];fmt=lambda prefix:' / '.join(f'{float(r[prefix+c]):+.2f}' for c in 'RGB')
 lines.append(f'| {m}分 | {rs[0]["label"]}→{r["label"]} | {float(r["hours_since_first_photo"]):.2f}h | {fmt("delta_")} | {fmt("bg_normalized_delta_")} |')
lines+=['','数値はJPEGのRGB単位（0〜255）、割合や劣化率ではありません。5/10分は最初が公称1h、15分は0hのため、同じ成膜後時刻の比較ではありません。','',
'## 前回19時頃から今回まで：背景補正後の差','',
'| アニール | ΔR | ΔG | ΔB |','|---|---:|---:|---:|']
for m in [5,10,15]:
 rs=[r for r in rows if int(r['anneal_min'])==m];lines.append('| '+str(m)+'分 | '+' | '.join(f'{float(rs[-1]["bg_normalized_"+c])-float(rs[-2]["bg_normalized_"+c]):+.2f}' for c in 'RGB')+' |')
lines+=['','この小さな差について撮り直し誤差を超えるとは検証していません。B低下の有無だけで膜の良否や劣化を判定しません。','',
'## 模様とXRDについて','',
'- 模様の場所は維持されています。画素の標準偏差（広い色むら）とGaussian差分の標準偏差（細かな模様）を別々に計算しました。これらは照明・反射・ぼけにも左右され、結晶粒径や欠陥量ではありません。',
'- 最新3枚は以前の各膜との模様照合で対応を確認済み。10分膜は四隅整形後の単純画素相関が不安定なため、厳密な画素差マップは使っていません。',
'- XRDは依然各膜0h/1hのみ。最新時点の結晶変化は確認できません。画像0h/1hもそろう15分膜では1h写真が背景問題の対象のため、これを除いた解析でXRD0→1hとの直接対応を検証できません。画像とXRDの変化の対応は保留します。','',
'## 方法・再現性','',
'全12枚のJPEG/JSONを使用。保存済みの露光・ゲイン・色ゲイン・ピントの実測値が一致し、固定設定照合も成功。これは照明・合焦の完全一致を保証しません。基板四隅から256×256へ整形し、各辺18%を除く中央領域を解析。楕円除外なし。12/18/24%の結果はroi_sensitivity.csv。背景は固定4領域40×40pxから係数を計算し、別の4領域で検証。補正はJPEG RGB比率補正で、物理的な色校正ではありません。','',
'元画像は変更せずPNGを派生出力。metrics.csv、input_manifest.json、analysis_config.jsonに数値・入力ハッシュ・条件を記録。旧9枚の解析結果は残しています。','',
'再実行（リポジトリ直下）：analyze_sn10_images_4points.py → sn10_corrected_images_4points.py / sn10_sensitivity_4points.py → report_sn10_4points.py（notebooks/film_time_series内）。']
(P/'README.md').write_text('\n'.join(lines)+'\n')
f=Path('data/processed/20261112/README.md');s=f.read_text();link='\n## 最新：19:41〜19:43追加・12枚\n\n[4時点の画像解析・背景補正・感度比較](09_image_time_series_4points/README.md)\n';f.write_text(s+link if link not in s else s)
