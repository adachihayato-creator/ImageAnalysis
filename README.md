# ペロブスカイト薄膜の画像解析


## 2026年11月13日までの進捗

- [撮影アプリ：設定の保存・固定と再起動後の照合](hardware/camera/FIXED_SETTINGS_GUIDE.md)
- [白枠・位置合わせガイド](hardware/camera/POSITION_GUIDE.md)
- [写真・JSONの取り込み](hardware/camera/IMPORT_README.md)
- [画像15枚・XRD9測定の統合再解析](results/20261112/14_integrated_reanalysis/README.md)
- [撮り直し5回と経時変化の比較](results/20261112/16_reanalysis_with_repeats/README.md)
- [XRD副相候補と画像の明るい斑点](results/20261113/02_xrd_image_features_fullframe/README.md)
- [全体解析と中央解析の比較検証](results/20261113/03_fullframe_validation/README.md)
- [8×8・4×4の区画解析](results/20261113/04_mesh_8x8/README.md)
- [斑点しきい値5〜50%の感度解析](results/20261113/05_threshold_5to50/README.md)
- [斑点としきい値を使わない模様指標の比較](results/20261113/06_spot_texture_comparison/README.md)

今回の独立膜はアニール条件ごとに1枚で計3枚です。副相候補が強い15分膜で画像特徴も大きい傾向は探索結果で、画像中の斑点をPbI₂と同定した結果ではありません。区画・画像の反復を独立膜数とみなしていません。XRDのPC時計は不正確なため、申告された公称時点を使用しています。

元の写真・撮影JSON・XRDの `data/raw/` は保存しています。発表資料（PowerPoint・プレビュー・生成用ファイル）はローカルのみで管理し、GitHubには掲載しません。接続用の秘密鍵、バックアップ・一時ファイルもGit管理対象外です。


ペロブスカイト薄膜の色・均一性と、成膜後の外観変化を評価する研究用リポジトリです。
現在は4膜の成膜後0・1・2・3・4・5・24 h（計28画像）を対象に、背景に基づく相対色補正、位置合わせ、RGB変化の集計・可視化を行っています。

## 結果を見る

- [解析結果の全体案内](results/旧解析一覧.md)
- [2026-10-15実験の結果一覧](results/20261015/README.md)
- [最新：0〜24 hの画像解析](results/20261015/05_image_time_series_0to24h/README.md)
- [0〜24 hのRGBグラフ](results/20261015/05_image_time_series_0to24h/rgb_time_series_0to24h.png)
- [初期XRDと画像変化の探索的比較](results/20261015/03_xrd_comparison/report.md)

## 構成

```text
hardware/camera/                 タッチ式撮影アプリ・撮影設定のJSON記録
hardware/lighting/               ArduinoのLED制御コード
notebooks/                        既存の解析ノート・LED制御スケッチ
  film_time_series/               背景補正・位置合わせ・図作成のPythonコード
data/
  raw/                           元画像・元測定データ
  processed/
    20261015/
      01_crops/                  膜の切り抜き画像
      02_background_correction/  初期0〜3 hの背景補正
      03_xrd_comparison/         初期XRDの探索的比較
      04_image_time_series/      初期0〜3 hの位置合わせ後解析
      05_image_time_series_0to24h/  4・5・24 hを追加した解析
```

撮影アプリは、基準で決めた露光・色ゲイン・焦点の保存と再起動後の読み込み、撮影フレームごとの照合に対応しています。[固定版の使い方](hardware/camera/FIXED_SETTINGS_GUIDE.md)を参照してください。初回の設定値の決定と実機検証は別途必要です。

## 実行

Python環境に依存ライブラリをインストールし、リポジトリのルートから実行します。

```bash
python3 -m pip install -r requirements.txt
python3 notebooks/film_time_series/analyze_extended_time_series.py
```

実行には、ローカルの `data/raw/` に対応する元画像が必要です。元画像なしでも、保存済みのグラフ・CSV・レポートは閲覧できます。
元画像は `data/raw/{Tuji,Touma}/材料名/10_15/`、切り抜き画像は `results/20261015/01_crops/{Tuji,Touma}/材料名/` に保存し、`1枚目0h.jpg` などの命名を使用します。コードのGROUPSと各レポートを参照してください。
発表資料とその作成コードはローカルのみで管理します。日本語図のフォント指定にはWindows上のフォントパスを使用しているものがあります。

## 結果の解釈

- RGB変化は各膜の0 hからの差で、割合・劣化率ではありません。
- 主解析は外周18%を除いた中央領域に楕円内も含めた条件です。18%は暫定条件で、12/24%や楕円除外でも感度を確認しています。
- 背景補正は相対的なJPEG RGB補正です。反射・角度差を完全には除去できません。
- 24 hのBrRb系2膜は位置合わせが不確かなため、局所比較は暫定です。
- 初期XRDだけで経時的な構造劣化を証明したものではありません。
- 研究原本はGitに保存し、秘密鍵・接続設定・バックアップ・一時ファイルは対象外です。

## 2026-11-17〜18：画像時間変化の予測

[予測結果と方法](results/20261117/07_image_time_prediction/README.md)、[R²付きの変化量散布図](results/20261117/07_image_time_prediction/06_Ridge_実測と予測_変化量.png)。結果はresults/YYYYMMDDへ日付別に統一。旧data/processedのファイルは移行確認後に削除しています。

## 公開範囲

PowerPoint資料と発表資料用フォルダは、公開ブランチの過去の履歴から除外しています。ローカルの原本は保持し、コード・画像解析の結果・測定データと分けて管理します。
