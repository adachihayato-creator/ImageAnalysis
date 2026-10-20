# ペロブスカイト薄膜の画像解析

ペロブスカイト薄膜の色・均一性と、成膜後の外観変化を評価する研究用リポジトリです。
現在は4膜の成膜後0・1・2・3・4・5・24 h（計28画像）を対象に、背景に基づく相対色補正、位置合わせ、RGB変化の集計・可視化を行っています。

## 結果を見る

- [解析結果の全体案内](data/processed/README.md)
- [2026-10-15実験の結果一覧](data/processed/20261015/README.md)
- [最新：0〜24 hの画像解析](data/processed/20261015/05_image_time_series_0to24h/README.md)
- [0〜24 hのRGBグラフ](data/processed/20261015/05_image_time_series_0to24h/rgb_time_series_0to24h.png)
- [初期XRDと画像変化の探索的比較](data/processed/20261015/03_xrd_comparison/report.md)
- [発表資料 M1_10_15_全体.pptx](presentations/20261015/M1_10_15_全体.pptx)

## 構成

```text
notebooks/                        既存の解析ノート・LED制御スケッチ
  film_time_series/               背景補正・位置合わせ・図作成のPythonコード
data/
  raw/                           元画像・元測定データ（Git管理対象外）
  processed/
    20261015/
      01_crops/                  膜の切り抜き画像
      02_background_correction/  初期0〜3 hの背景補正
      03_xrd_comparison/         初期XRDの探索的比較
      04_image_time_series/      初期0〜3 hの位置合わせ後解析
      05_image_time_series_0to24h/  4・5・24 hを追加した解析
presentations/20261015/           発表資料と作成コード・画像素材
```

## 実行

Python環境に依存ライブラリをインストールし、リポジトリのルートから実行します。

```bash
python3 -m pip install -r requirements.txt
python3 notebooks/film_time_series/analyze_extended_time_series.py
```

実行には、ローカルの `data/raw/` に対応する元画像が必要です。元画像なしでも、保存済みのグラフ・CSV・レポートは閲覧できます。
元画像は `data/raw/{Tuji,Touma}/材料名/10_15/`、切り抜き画像は `data/processed/20261015/01_crops/{Tuji,Touma}/材料名/` に保存し、`1枚目0h.jpg` などの命名を使用します。コードのGROUPSと各レポートを参照してください。
発表資料作成コードはローカルのテンプレート・バックアップを必要とします。日本語図のフォント指定にはWindows上のフォントパスを使用しているものがあります。

## 結果の解釈

- RGB変化は各膜の0 hからの差で、割合・劣化率ではありません。
- 主解析は外周18%を除いた中央領域に楕円内も含めた条件です。18%は暫定条件で、12/24%や楕円除外でも感度を確認しています。
- 背景補正は相対的なJPEG RGB補正です。反射・角度差を完全には除去できません。
- 24 hのBrRb系2膜は位置合わせが不確かなため、局所比較は暫定です。
- 初期XRDだけで経時的な構造劣化を証明したものではありません。
- 元画像・元測定データ、バックアップ、一時ファイルはGit管理対象外です。
