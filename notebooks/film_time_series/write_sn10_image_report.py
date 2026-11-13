from pathlib import Path
import csv,json
P=Path('data/processed/20261112/03_image_time_series')
rows=list(csv.DictReader((P/'metrics.csv').open(encoding='utf-8-sig')))
lines=['# Sn10%：3膜の画像経時変化とXRDの対応','',
'## 最初に見る図','',
'- [9枚の時系列](01_膜の時系列.png)：行がアニール5/10/15分、列が撮影順。緑枠が解析領域。',
'- [色・模様の経時変化](02_色と模様の経時変化.png)：平均色の差、領域内の色むら、細かな模様を区別。',
'- [背景の変動と影響](03_背景の変動と影響.png)：撮影環境の影響を確認。','',
'## 今回分かったこと','',
'1. 画像ごとの平均RGBは変化しています。ただし背景の紙も、とくにG/Bが大きく低下しているため、膜だけの変化とは判定できません。',
'2. 最新時点はユーザー指定により18:59〜19:01の撮り直しに差し替えました。3膜の特徴的な模様と向きを目視・変換比較で確認しました。差し替え前の18:36〜18:37画像で見られたぼけを、採用画像の結論として引き継ぎません。色むらや細かな模様の指標は照明・合焦の影響も受けるため、均一性改善と即断しません。',
'3. アニール条件間で色や模様は異なりますが、各条件1膜、撮影開始の膜齢が異なるため、アニール時間による因果的な差や最良条件は決められません。','',
'## 各膜の最初→最後の変化','',
'数値はJPEGのRGB単位。色差規格のΔE・割合・劣化率ではありません。簡易補正は固定した背景4領域のRGB比を用い、真の反射色への校正ではありません。','',
'| アニール | 公称時点 | 実際の撮影間隔 | 補正前 ΔR / ΔG / ΔB | 背景で簡易補正後 ΔR / ΔG / ΔB |',
'|---|---|---:|---|---|']
for m in [5,10,15]:
 rs=[r for r in rows if int(r['anneal_min'])==m];r=rs[-1]
 vals=lambda pre:' / '.join(f'{float(r[pre+c]):+.2f}' for c in 'RGB')
 lines.append(f'| {m}分 | {rs[0]["label"]}→{r["label"]} | {float(r["hours_since_first_photo"]):.2f} h | {vals("delta_")} | {vals("bg_normalized_delta_")} |')
lines+=['','補正後にも差は残りますが、背景反射と膜の鏡面反射は同じではなく、ぼけの影響もあるので材料変化の確定値ではありません。','',
'## XRDの変化と対応しているか','',
'- XRDは各膜の公称0h/1h。5分・10分は0h写真がないため、画像の0→1h変化とXRDの0→1h変化の直接比較はできません。',
'- 15分だけは0h/1hで両方がそろいます。画像は0h 16:41:17、1h 17:55:16、XRDは各16:14:22〜16:20:45、17:43:49〜17:50:11。完全な同時測定ではありません。',
'- 15分の約14°ピークの見かけ半値幅は0.228→0.363°、約12.7°/14°の局所背景差引き面積比は0.610→0.541。ピークの形状は変化していますが、相割合や結晶粒径の変化とそのまま同一視しません。',
'- 同じ15分の画像変化は下表です。背景の影響も大きく、両者が同時に変わったという記述を超えて、画像でXRD変化を予測できるとはいえません。',
'- 最新の公称2h/3hに対応するXRDはまだないため、最新画像の変化が結晶変化を表すかは未確認です。','']
r=[r for r in rows if int(r['anneal_min'])==15][1]
lines+=['| 15分膜の0→1h | ΔR | ΔG | ΔB |','|---|---:|---:|---:|']
for prefix,label in [('delta_','画像・補正前'),('bg_normalized_delta_','画像・背景で簡易補正')]:lines.append('| '+label+' | '+' | '.join(f'{float(r[prefix+c]):+.2f}' for c in 'RGB')+' |')
lines+=['','[1h画像とXRDの対応図](../01_sn10_xrd_image_comparison/02_1h画像とXRD.png)、[XRD数値](../01_sn10_xrd_image_comparison/xrd_features.csv)、[相候補の照合](../02_xrd_phase_candidates/README.md)。','',
'## 方法・限界','',
'- 9組のJPEG/JSON。9枚すべて固定設定照合成功、同じプロファイル、露光・AnalogueGain・ColourGains・LensPositionの実測値一致を確認。これは照明や合焦の安定性の証明ではありません。',
'- 基板の四隅を検出し256×256へ射影変換。各辺18%を除く中央領域が主解析。中央楕円は除外していません。12/18/24%の感度結果をroi_sensitivity.csvへ保存。ピクセル単位で完全な位置合わせはしていないため、画素差マップは作っていません。',
'- 平均RGB＝領域の平均。色むら＝同じ画像内の画素標準偏差で、撮り直し誤差や試料間誤差ではありません。細かな模様＝2種類のGaussianぼかし(σ0.7/3px)の差の標準偏差で、結晶粒径ではありません。',
'- 横軸は各膜の最初の写真からの実時間。5/10分は公称1h、15分は0hが開始。3条件の横軸0が同じ成膜後時刻ではありません。最後は撮り直し画像を採用し、撮影時刻を更新しました。公称時点はユーザー指定のままです。',
'- 各条件1膜・各時点1枚。統計的な条件差や一般的な相関は検定せず、良否・寿命の予測もしません。',
'- 数値はmetrics.csv、解析条件はanalysis_config.json、入力ハッシュ・検出四隅はinput_manifest.json。元画像は変更していません。','',
'## 次の判断につなげること','',
'背景色変化の原因を確認し、照明の設定・試料の高さや向き・レンズ面の状態を記録します。状態が安定していると確認できた画像と、近い時刻のXRDを対応させることで、膜の変化と撮影の変化を切り分けます。撮り直す場合も今回の原本は残し、別撮影として記録します。']
(P/'README.md').write_text('\n'.join(lines)+'\n')
# Descriptive linkage table for the one available paired change, with no correlation claim.
rs=[r for r in rows if int(r['anneal_min'])==15][:2]
xrd=list(csv.DictReader(Path('data/processed/20261112/01_sn10_xrd_image_comparison/xrd_features.csv').open(encoding='utf-8-sig')))
linked=[]
for r in rs:
 x=next(x for x in xrd if x['anneal_min']=='15' and x['elapsed_label']==r['label'])
 linked.append({**r,'xrd_main_angle_deg':x['main_angle_deg'],'xrd_main_apparent_fwhm_deg':x['main_apparent_fwhm_deg'],'xrd_low_over_main_net_area':x['low_over_main_net_area'],'note':'nominal time pairing, not simultaneous; only one film with image0h/1h'})
with (P/'15min_image_xrd_time_pairs.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(linked[0]));w.writeheader();w.writerows(linked)
f=Path('data/processed/20261112/README.md');s=f.read_text();link='\n[3膜・9枚の画像経時変化とXRDとの対応](03_image_time_series/README.md)\n';f.write_text(s+link if link not in s else s)
for m in [5,10,15]:
 r=[r for r in rows if int(r['anneal_min'])==m][-1];print(m, {c:round(float(r['delta_'+c]),2) for c in 'RGB'}, {c:round(float(r['bg_normalized_delta_'+c]),2) for c in 'RGB'})
