# 研究結果（日付別）

解析結果の保存先をresultsへ統一しました。日付を選び、各解析の図・CSV・説明を開いてください。

- [20260717](20260717/INDEX.md)：7月の切り抜き画像・XRD対応資料
- [20261015](20261015/INDEX.md)：4膜の経時画像・背景補正・初期XRD
- [20261110](20261110/INDEX.md)：撮影の再現性と固定設定
- [20261111](20261111/INDEX.md)：白枠・置き直し再現性と5分/10分比較
- [20261112](20261112/INDEX.md)：Sn10%の経時画像・XRDと撮影ばらつき
- [20261113](20261113/INDEX.md)：斑点・区画解析・1日後の画像とXRD
- [20261117](20261117/INDEX.md)：今日の撮影整理・XRD対応・予測試作

## 保存場所

- data/raw：原画像・撮影JSON・XRD原本と試料条件。
- results/YYYYMMDD：解析結果、検証、切り抜き・補正画像、予測、数値CSV。
- notebooks：解析コード。

各日の00_主要結果は主要図の閲覧用コピーです。詳細は同日内の各解析フォルダに保存しています。旧data/processedの全ファイルは移行・照合済みで、旧フォルダは削除しました。記録：data/results_migration_20261117.json。

最新の画像時間変化予測：[20261117/07_image_time_prediction/README.md](20261117/07_image_time_prediction/README.md)。

今回のXRD予測：[20261117/06_xrd_ratio_prediction/README.md](20261117/06_xrd_ratio_prediction/README.md)。

一覧更新：python3 scripts/collect_results.py。
