# 解析結果の入口

## 今回の研究：2026年10月15日・4膜の0–3 h経時変化

**まず [20261015/README.md](20261015/README.md) を開いてください。**

| 保存先 | 内容 |
|---|---|
| [20261015/01_crops](20261015/01_crops/) | 補正前の膜の切り抜き画像：4膜×4時点＝16枚 |
| [20261015/02_background_correction](20261015/02_background_correction/) | 背景基準による補正画像、比較画像、RGB集計 |
| [20261015/03_xrd_comparison](20261015/03_xrd_comparison/) | 初期XRDのグラフと画像経時変化との比較 |

## 過去の結果（保存場所を維持）

- `Yamamoto/`：過去の山本試料の画像。
- `Tuji/前期/`、`Touma/前期/`：前期の切り抜き画像。
- `xrd_image_comparison/`：過去のXRD・画像対応資料。今回の4膜の比較は **20261015/03_xrd_comparison/**。
- `Suzuki/`：既存の保存先。

## 今後の保存ルール

実験日を `YYYYMMDD/` とし、その下に `01_crops/` → `02_background_correction/` → `03_xrd_comparison/` の順で保存します。
元画像・元測定データは `data/raw/` に残し、解析用コードは `notebooks/` に置きます。

今回の移動前後の対応は [reorganization.json](20261015/reorganization.json) に記録しています。
以前の会話にある旧パスのリンクは移動により無効になっているため、この案内のリンクをご利用ください。

最新の画像経時変化解析は [20261015/04_image_time_series/report.md](20261015/04_image_time_series/report.md) です（位置合わせ後・XRDなし）。
