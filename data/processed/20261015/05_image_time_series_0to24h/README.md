# 0–24 hの膜画像経時変化解析

4膜 × 0・1・2・3・4・5・24 h＝28枚。過去の02〜04結果は上書きしていません。時刻はファイル名による公称値で、実際の撮影間隔の精度・保存環境の同一性は未確認です。

## 主な図

- [RGB時間変化：0–24 h](rgb_time_series_0to24h.png)（横軸は実時間間隔）
- [RGB時間変化：0–5 h拡大](rgb_time_series_0to5h.png)
- [背景選択感度](background_sensitivity.png)
- [背景領域の確認](background_regions.png)

主解析は外周18%を除いた中央領域、楕円内も含む条件。膜の端までを測った全体解析ではありません。各膜で全時点共通の有効画素を使用。0–3 hの変換行列は以前の結果を再利用、4・5・24 hは同じ回転候補＋ECCアフィン法で位置合わせしました。

背景補正はrawの上下左右4領域の中央値から、各膜の0 hに対するRGB別係数の中央値を算出。未使用の斜め4領域で検証。線形反射率の校正ではありません。係数・領域・元ファイル・ハッシュはCSV/JSONに保存。

## 24 hの色変化（0 h基準、主解析領域）

|膜|ΔR|ΔG|ΔB|平均RGBの距離|位置合わせ相関|
|---|---:|---:|---:|---:|---:|
|BrRb_1|42.68|38.88|31.93|65.97|0.204|
|BrRb_2|43.40|51.96|47.35|82.62|0.264|
|Sn25_1|6.65|2.86|2.77|7.75|0.622|
|Sn25_2|5.92|5.36|4.50|9.17|0.787|

## 各膜のマップ

|膜|0–24 h一覧|0・4・5・24 h|大きな変化を見る広い尺度|G/Bも含む成分別マップ|
|---|---|---|---|---|
|BrRb_1|[全時点](BrRb_1/color_change_maps_with_ellipse_all_times.png)|[後半](BrRb_1/color_change_maps_with_ellipse_late_times.png)|[0–200](BrRb_1/color_change_maps_with_ellipse_late_times_extended_scale.png)|[R/G/B](BrRb_1/rgb_component_maps.png)|
|BrRb_2|[全時点](BrRb_2/color_change_maps_with_ellipse_all_times.png)|[後半](BrRb_2/color_change_maps_with_ellipse_late_times.png)|[0–200](BrRb_2/color_change_maps_with_ellipse_late_times_extended_scale.png)|[R/G/B](BrRb_2/rgb_component_maps.png)|
|Sn25_1|[全時点](Sn25_1/color_change_maps_with_ellipse_all_times.png)|[後半](Sn25_1/color_change_maps_with_ellipse_late_times.png)|[0–200](Sn25_1/color_change_maps_with_ellipse_late_times_extended_scale.png)|[R/G/B](Sn25_1/rgb_component_maps.png)|
|Sn25_2|[全時点](Sn25_2/color_change_maps_with_ellipse_all_times.png)|[後半](Sn25_2/color_change_maps_with_ellipse_late_times.png)|[0–200](Sn25_2/color_change_maps_with_ellipse_late_times_extended_scale.png)|[R/G/B](Sn25_2/rgb_component_maps.png)|

各膜フォルダには楕円除外条件（excluded）の同じマップも保存。Sn系は元々楕円を設定していないため一致します。マップは全て0 hとの差です。直前の時点との差ではありません。

## 背景検証

|膜|時点|未使用背景の偏差：補正前→後(%)|補正係数の場所依存(%)|
|---|---:|---:|---:|
|BrRb_1|4|6.06 → 1.31|1.54|
|BrRb_1|5|4.07 → 0.30|0.79|
|BrRb_1|24|4.45 → 0.75|1.15|
|BrRb_2|4|7.40 → 1.48|2.05|
|BrRb_2|5|7.53 → 1.49|3.28|
|BrRb_2|24|4.73 → 1.71|2.18|
|Sn25_1|4|4.99 → 1.80|2.70|
|Sn25_1|5|5.58 → 1.24|1.84|
|Sn25_1|24|4.14 → 1.51|2.42|
|Sn25_2|4|6.43 → 1.15|1.46|
|Sn25_2|5|6.66 → 1.04|1.73|
|Sn25_2|24|6.29 → 1.09|2.23|

## 位置合わせの注意

|膜|時点|相関|判定|粗回転(反時計回り)|
|---|---:|---:|---|---:|
|BrRb_1|0|1.000|参考基準以上|0|
|BrRb_1|1|0.264|LOW ALIGNMENT|270|
|BrRb_1|2|0.483|参考基準以上|0|
|BrRb_1|3|0.463|参考基準以上|0|
|BrRb_1|4|0.397|LOW ALIGNMENT|0|
|BrRb_1|5|0.391|LOW ALIGNMENT|0|
|BrRb_1|24|0.204|LOW ALIGNMENT|0|
|BrRb_2|0|1.000|参考基準以上|0|
|BrRb_2|1|0.824|参考基準以上|0|
|BrRb_2|2|0.802|参考基準以上|0|
|BrRb_2|3|0.768|参考基準以上|0|
|BrRb_2|4|0.770|参考基準以上|0|
|BrRb_2|5|0.751|参考基準以上|0|
|BrRb_2|24|0.264|LOW ALIGNMENT|0|
|Sn25_1|0|1.000|参考基準以上|0|
|Sn25_1|1|0.761|参考基準以上|270|
|Sn25_1|2|0.755|参考基準以上|270|
|Sn25_1|3|0.754|参考基準以上|270|
|Sn25_1|4|0.751|参考基準以上|270|
|Sn25_1|5|0.725|参考基準以上|270|
|Sn25_1|24|0.622|参考基準以上|270|
|Sn25_2|0|1.000|参考基準以上|0|
|Sn25_2|1|0.930|参考基準以上|0|
|Sn25_2|2|0.916|参考基準以上|0|
|Sn25_2|3|0.912|参考基準以上|0|
|Sn25_2|4|0.912|参考基準以上|0|
|Sn25_2|5|0.907|参考基準以上|0|
|Sn25_2|24|0.787|参考基準以上|0|

位置合わせ後の高域画像相関0.4未満を暫定的にLOW ALIGNMENTと表示。これは実測した位置誤差の基準ではありません。24 hの見た目が大きく変わる場合、相関低下は実変化と位置ずれの両方を含み、局所比較は参考です。相関0.25未満の候補は回転誤判定の恐れがあるため採用せず、撮影時の向きを維持したリサイズのみの暫定結果（REVIEW_REQUIRED）としました。FAILEDもリサイズのみ。24 hの辻2膜が該当し、細かな画素位置の一致は保証しません。

## 解釈と表示上の限界

- RGB変化は材料の劣化の証明ではありません。相変化・PbI2量・性能低下は判定しません。傷の自動判定も行っていません。
- 比較用のマップは前回と同じRGB距離0–50、符号付きRは−30〜30。24 hで色尺度が飽和し得るので、RGB距離0–200の図も保存しました。成分別マップはR/G/B共通−100〜100です。表示上の飽和率はCSVに記録、NPZは未クリップの数値。
- 補正画像PNGは0–255に丸めて保存。集計と差分NPZは丸め前の値を使用。背景補正で反射や撮影角度の差は除去できません。
- グラフは5→24 hの間を線で結びますが、この間の変化開始時刻・経路は観察していません。
- 12/18/24%の外周除外と楕円あり/なし、背景4領域の単独選択による感度を保存。帯は信頼区間ではありません。
- 切り抜き画像寸法は約240 px角。倍率・解像度の制約があり、細かな局所模様の判定に限界があります。

## 保存ファイル

- aligned_rgb.csv：楕円含む／除外両条件の補正前後RGB・0 h差分（56行）
- roi_sensitivity.csv：解析領域を変えた結果（168行）
- background_validation.csv / background_patches.csv：背景補正の測定・検証
- background_sensitivity.csv：背景単独選択によるRGB変化
- registration.json / metadata.json / input_manifest.json：変換・入力・領域・ハッシュ
- 各膜/*h_corrected.png：背景補正のみ（28枚）
- 各膜/*h_aligned_corrected.png：位置合わせ後（28枚）
- 各膜/*h_color_difference.npz：RGB差分・距離・両解析マスク（28個）
- 各図はPNG/PDF両形式。再実行：python3 notebooks/film_time_series/analyze_extended_time_series.py（numpy、Pillow、OpenCV、matplotlibが必要）。