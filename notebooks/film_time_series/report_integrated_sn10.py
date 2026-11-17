from pathlib import Path
import csv,json
import numpy as np
P=Path('results/20261112/14_integrated_reanalysis')
def read(name):return list(csv.DictReader((P/name).open(encoding='utf-8-sig')))
rs=read('image_metrics.csv');summary=read('image_change_summary.csv');xs=read('xrd_low_peak_sensitivity.csv');xr=read('xrd_features.csv');v=read('held_out_background.csv');robust=[]
for m in [5,10,15]:
 r=[r for r in rs if r['anneal_min']==str(m)]
 for c in 'RGB':
  signs=[];slopes=[]
  for exclude in [False,True]:
   selected=[a for a in r if not(exclude and a['photo_index']=='2')]
   for correct in [False,True]:
    prefix='corrected_mean_' if correct else 'raw_mean_';x=np.array([float(a['hours_since_first_photo']) for a in selected]);y=np.array([float(a[prefix+c]) for a in selected]);slope=float(np.polyfit(x,y,1)[0]);slopes.append(slope);signs.append(np.sign(slope))
  robust.append({'anneal_min':m,'channel':c,'same_slope_sign_four_cases':len(set(signs))==1,'slopes_rgb_per_hour':slopes})
(P/'image_four_case_directions.json').write_text(json.dumps(robust,ensure_ascii=False,indent=2))
lines=['# 統合再解析：Sn10%膜の画像15枚とXRD9測定','',
'今回の主解析は**背景色に問題のある写真2を除いた写真1・3・4・5**。補正前後とROI12/18/24%で結果への影響を確認しました。XRDは申告された0h/1h/5hを使用し、不正確なPC時計からの時刻差は解釈しません。古い解析はそのまま残しています。','',
'## 今回見る図','',
'1. [主解析の補正後写真](01_主解析の写真.png)：各行がアニール条件、写真2は含みません。',
'2. [平均色・色むらの変化](02_主解析の色と色むら.png)：実線が主解析、左の薄い点線が写真2を含む参考、薄い帯はROI選択による範囲で誤差棒ではありません。',
'3. [XRD0h/1h/5h](03_XRDの再比較.png)：主相候補と副相候補を生パターンと規格化パターンで確認します。','',
'## 画像で分かったこと','',
'### 最初→最新の平均色','',
'| アニール | 補正前ΔR/G/B | 背景補正後ΔR/G/B | 補正後のROI感度範囲（R;G;B） |','|---|---|---|---|']
for m in [5,10,15]:
 ss=[r for r in summary if r['anneal_min']==str(m)];fmt=lambda key:' / '.join(f'{float(r[key]):+.2f}' for r in ss);ranges='; '.join(f"{float(r['roi_delta_min']):+.2f}〜{float(r['roi_delta_max']):+.2f}" for r in ss)
 lines.append(f'| {m}分 | {fmt("raw_first_to_last")} | {fmt("corrected_first_to_last")} | {ranges} |')
lines+=['','数値はJPEG RGB単位、％や劣化率ではありません。5分・10分は最初が公称1h、15分は0hで、同じ成膜後時間幅の条件比較ではありません。最新は前回の続きなら公称5h/5h/4hの暫定ラベル。横軸はカメラ記録の実時間です。','',
'- **5分：** 背景補正後の最初と最新の平均色差は各成分1未満。大きな平均色変化を示す結果ではありません。ただし検出限界や撮影誤差を超えたかは検証していません。',
'- **10分：** 背景補正後にもG/B低下が残り、ROIを変えても最初→最新の低下方向は変わりません。前回19:42→今回20:53にもG/Bの低下がありましたが、これだけで材料の劣化と認定しません。',
'- **15分：** R増加・B低下がROIを変えても残ります。Gは補正前後で符号が変わるため解釈を保留します。',
'- 全時点を1本の直線にした傾きは、写真2の有無・補正の有無で変わる場合があります。最初→最新の方向と、単調な経時変化を混同しません。小さな数値の符号に有意性を持たせません。','',
'### 模様・均一性','',
'特徴的な模様は写真間で対応しています。色むらや細かな模様は一律に増減しておらず、「全膜で均一性が改善した/悪化した」とは言えません。例えば補正後の細かな模様のB指標は5分3.32→3.34、10分3.56→3.79、15分4.07→4.61。広い領域の標準偏差とは異なる動きであり、1指標で良否は決めません。これらはJPEGの画像指標で、結晶粒径や欠陥量ではありません。照明・反射・ピント・変換補間も影響します。','',
'## 背景補正の確認','',
'| アニール | 問題の写真2・未使用背景のずれ（前→後） | 最新写真・未使用背景のずれ（前→後） |','|---|---|---|']
for m in [5,10,15]:
 rr=[r for r in v if r['anneal_min']==str(m)];fmt=lambda r:f"{float(r['raw_error_percent']):.2f}% → {float(r['corrected_error_percent']):.2f}%";lines.append(f'| {m}分 | {fmt(rr[1])} | {fmt(rr[-1])} |')
lines+=['','固定した紙4領域で係数を計算し、別の4領域の成分別相対差RMSの平均で検証。膜の誤差やΔEではありません。補正後もずれが残り、鏡面性のある膜まで正しく復元した保証はありません。','',
'## XRDで分かったこと','',
'- **3膜とも5hで約14°・28°の主相候補ピークが残る。** XRDで目的相が完全に消えたパターンではありませんが、性能維持を意味しません。',
'- **ピークの高さ・見かけ幅は単調には変わらない。** 3膜の約14°高さは0→1hで下がり、1→5hで部分的に増加。設置・配向・背景等の影響を切り分けず、結晶の劣化・回復に置き換えません。',
'- **15分の12.7°副相候補は全時点で明瞭。** 面積比の0→5h低下は今回試した3背景条件で共通。ただし0→1hの増減は背景によって変わり、単調低下は確定しません。',
'- **10分5hの小ピークは背景条件に敏感。** 従来法は抽出不成立でしたが、局所背景を変えると12.81°に抽出されます。「ピークが消えた」とは言えません。',
'- **5分1h/5hの副相候補の量は安定に数値化できない。** 5hは3条件中1条件だけ極小の正面積になり、検出や不存在の結論に使いません。',
'- 10分0hは他時点から複数ピークがずれています。角度校正・試料設置の確認なしに別相や格子変化と断定しません。','',
'### 15分：副相候補/主相候補の面積比の背景依存性','',
'| 背景条件 | 0h | 1h | 5h |','|---|---:|---:|---:|']
for variant in [1,2,3]:
 rr=[r for r in xs if r['anneal_min']=='15' and r['background_variant']==str(variant)];lines.append('| '+str(variant)+' | '+' | '.join(f"{float(r['low_over_main_area']):.3f}" for r in rr)+' |')
lines+=['','低角側の積分窓を12.25〜13.0°に統一し、背景の両側窓を3通り試しました。従来の12〜13°積分値と絶対値は同じではありません。主相側は同じ処理を使用。これは背景選択への感度であって、全ての処理法への頑健性や相含有率を示しません。ピークの帰属はPbI₂等の副相候補のままです。','',
'## 画像とXRDを結び付けて言えること','',
'**今回は「画像が変わるほどXRDも悪化する」という単純な関係は確認できません。** 10分膜で画像のG/Bは下がる一方、XRDの主ピークは1h→5hで狭くなります。15分膜の画像にR増加/B低下があっても、副相候補の面積比は0h→5hで増えていません。','',
'ただし、画像変化が無意味という結論でもありません。画像は表面の色・反射・模様、XRDは回折する結晶構造の特徴を観察しており、別の変化を捉える可能性があります。今回の結果はその対応を定義するための探索データです。各条件1膜、撮影差・測定差の推定がなく、相関・予測・最適条件は結論しません。','',
'## 条件と再現方法','',
'FA:Cs=9:1、Sn:Pb=1:9、SnF₂全体組成に対し0.1mol%、130℃、ガラス基板・下地なし。全15画像の固定露光/ゲイン/色ゲイン/レンズ位置一致を確認。XRD9測定のTXTとRASXプロファイルの一致を確認。XRDのPC時計はユーザー確認で不正確のため不使用。同じ時点の写真がない場合は補間して作らず、15分最新画像の時点とXRD5hを厳密な同時点と扱いません。','',
'基板四隅で256pxへ整形し、各辺18%除外・楕円除外なし。ROI12/18/24%で感度確認。未補正と補正の両方を保存。色むらは画素標準偏差、細かな模様はGaussianσ0.7−σ3の標準偏差。白い紙のRGB比による簡易補正で、反射スペクトルや照明色の物理校正ではありません。XRD半値幅は装置幅補正なし、配向・角度補正なし。','',
'元データの削除・上書きなし。input_manifest.jsonに原本SHA-256、analysis_config.jsonに条件。image_metrics.csv・image_change_summary.csv・image_roi_sensitivity.csv、xrd_features.csv・xrd_low_peak_sensitivity.csvに全数値。','',
'再実行（リポジトリ直下）：python3 notebooks/film_time_series/reanalyze_sn10.py → python3 notebooks/film_time_series/report_integrated_sn10.py。NumPy/OpenCV/Pillow/Matplotlibが必要。']
(P/'README.md').write_text('\n'.join(lines)+'\n')
f=Path('results/20261112/README.md');s=f.read_text();link='\n## 最新の統合再解析\n\n[写真15枚・XRD9測定の主解析と背景処理の感度確認](14_integrated_reanalysis/README.md)\n';f.write_text(s+link if link not in s else s)
print('統合レポートを作成')
