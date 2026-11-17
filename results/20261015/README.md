# 2026-10-15：4膜の初期経時変化

画像とXRDの対応付けを練習する資料は [06_xrd_image_practice/README.md](06_xrd_image_practice/README.md) にあります。同じ膜の初期画像と初期XRDを並べ、ピークの位置・見かけ幅・面積を数値化しています。

BrRb系2膜とSn25%系2膜。各膜について0・1・2・3 hを撮影。XRDは成膜直後のみ。

## 画像を見る

各比較画像の上段は補正前、下段は補正後。左から0・1・2・3 hです。

|試料|補正前後の比較|
|---|---|
|BrRb・1枚目|[comparison.png](02_background_correction/BrRb_1/comparison.png)|
|BrRb・2枚目|[comparison.png](02_background_correction/BrRb_2/comparison.png)|
|Sn25%・1枚目|[comparison.png](02_background_correction/Sn25_1/comparison.png)|
|Sn25%・2枚目|[comparison.png](02_background_correction/Sn25_2/comparison.png)|

- [背景の測定領域](02_background_correction/background_regions.png)
- [切り抜き画像：Tuji](01_crops/Tuji/FACsPbI3_BrRb_5mol_per_gram)
- [切り抜き画像：Touma](01_crops/Touma/FACsSnPbI3%28Sn25mol%25%29/)

`01_crops` 内のTXTは元から同居していたXRDのコピーです。移動時に維持しています。XRD解析コードは `data/raw` の元測定データを読みます。

## グラフ・数値を見る

|内容|図|数値・説明|
|---|---|---|
|背景補正|[RGB変化](02_background_correction/rgb_changes.svg)|[RGB集計CSV](02_background_correction/rgb_summary.csv)・[方法と検証](02_background_correction/report.md)|
|初期XRD|[生データ](03_xrd_comparison/01_xrd_raw.png)・[拡大比較](03_xrd_comparison/02_xrd_zoom.png)|[特徴量CSV](03_xrd_comparison/paired_features.csv)|
|画像の時間変化|[補正済みRGB](03_xrd_comparison/04_color_time_series.png)|[解析説明](03_xrd_comparison/report.md)|
|XRDと画像の対応|[散布図](03_xrd_comparison/05_xrd_vs_color.png)|同上。4膜の探索的比較で、因果関係の証明ではありません。|

XRD関連の各図は同名のPDFも保存しています。

## 再実行

リポジトリのルートから順番に実行します（numpy、Pillow、matplotlibが必要）。

```bash
python3 notebooks/film_time_series/background_correction.py
python3 notebooks/film_time_series/xrd_image_comparison.py
```

元画像は変更せず、上記フォルダに結果を再生成します。背景基準の相対色補正であり、反射や角度差を完全に除去した結果ではありません。


## 位置合わせ後の解析（最新・XRDなし）

まず [解析結果と注意点](04_image_time_series/report.md) を参照してください。

- [位置合わせ後のRGB時間変化・解析領域による感度](04_image_time_series/rgb_time_series.png)
- [背景領域の選び方による感度](04_image_time_series/background_sensitivity.png)
- 色変化マップ：[BrRb・1枚目](04_image_time_series/BrRb_1/color_change_maps.png)、[BrRb・2枚目](04_image_time_series/BrRb_2/color_change_maps.png)、[Sn25%・1枚目](04_image_time_series/Sn25_1/color_change_maps.png)、[Sn25%・2枚目](04_image_time_series/Sn25_2/color_change_maps.png)
- [数値CSV](04_image_time_series/aligned_rgb.csv)

従来の02/03フォルダのグラフは位置合わせ前の結果として残しています。現在の画像比較は04の結果を使用してください。

## 楕円の除外あり／なしを直接比較する図

各図は **行＝外周12/18/24%除外、列＝R/G/B**。橙破線は楕円を含む、青実線は楕円を除外。

|膜|時間変化の比較|実際の解析領域|
|---|---|---|
|BrRb・1枚目|[比較図](04_image_time_series/BrRb_1/roi_inclusion_comparison.png)|[領域図](04_image_time_series/BrRb_1/roi_regions.png)|
|BrRb・2枚目|[比較図](04_image_time_series/BrRb_2/roi_inclusion_comparison.png)|[領域図](04_image_time_series/BrRb_2/roi_regions.png)|
|Sn25%・1枚目|[比較図](04_image_time_series/Sn25_1/roi_inclusion_comparison.png)|[領域図](04_image_time_series/Sn25_1/roi_regions.png)|
|Sn25%・2枚目|[比較図](04_image_time_series/Sn25_2/roi_inclusion_comparison.png)|[領域図](04_image_time_series/Sn25_2/roi_regions.png)|

Sn系には楕円を設定していないため、除外あり／なしの線は一致します。縦軸の範囲は同じ膜の同じ色成分では3行共通ですが、異なる膜・色成分では異なります。元のroi_sensitivity.csvを可視化したもので、新たな測定値への変更はありません。各図は同名のPDFも保存しています。

## 楕円内も含めた色変化マップ

外周18%を除く中央領域は従来と同じで、楕円内を除外しない条件です。膜の端まで含む全体解析ではありません。上段：補正済み画像と解析領域、中段：RGB距離、下段：Rの増減。従来図と共通の色尺度です。

- [BrRb・1枚目](04_image_time_series/BrRb_1/color_change_maps_with_ellipse.png)
- [BrRb・2枚目](04_image_time_series/BrRb_2/color_change_maps_with_ellipse.png)
- [Sn25%・1枚目](04_image_time_series/Sn25_1/color_change_maps_with_ellipse.png)
- [Sn25%・2枚目](04_image_time_series/Sn25_2/color_change_maps_with_ellipse.png)

Sn系は元々楕円除外がないため、従来のマップと解析内容は同じです。既存図は上書きせず保存。再作成：`python3 notebooks/film_time_series/plot_maps_with_ellipse.py`。元の数値マップを再利用し、CSVの楕円除外なし条件との一致を検証しています。


## 追加：4・5・24 hを含めた解析（05）

[05_image_time_series_0to24h/README.md](05_image_time_series_0to24h/README.md) に、28枚の結果と確認事項をまとめています。

- [0–24 hのRGB時間変化](05_image_time_series_0to24h/rgb_time_series_0to24h.png)
- [0–5 hの拡大](05_image_time_series_0to24h/rgb_time_series_0to5h.png)
- 各膜の色変化マップは上記READMEから参照できます。

主解析は楕円内も含み、外周18%を除く中央領域。全て0 hとの差。02〜04は以前の結果として維持しています。24 hの辻2膜は外観が大きく変化して位置合わせが不確かなため、局所比較は暫定です。
