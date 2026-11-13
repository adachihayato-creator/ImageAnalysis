# Raspberry Pi撮影アプリ：設定保存・固定版

**使い方は [FIXED_SETTINGS_GUIDE.md](FIXED_SETTINGS_GUIDE.md) を開いてください。**

この版では、基準で調整した露光・アナログゲイン・色ゲイン・焦点を保存し、次の起動でも読み込みます。起動時と各撮影フレームで値を照合し、保存・検証前は研究用の撮影を許可しません。設定ファイルがない場合に勝手な数値を採用しません。

必要なアプリのファイルは `camera_app.py`、`capture_metadata.py`、`fixed_settings.py` の3つです。同じフォルダに置いてください。タッチUI、撮影・終了ボタン、`~/captures/`へのJPEG＋JSON保存を維持しています。

位置合わせ枠版では、さらに `position_guide.py` と初回候補の `position_guide_candidate.json` も同じフォルダに置きます。[白枠の使い方](POSITION_GUIDE.md)を参照してください。

## これまでの版

- `backups/camera_app_before_metadata_20261105.py`：元のアプリ。
- `backups/before_fixed_settings_20261110/`：JSON記録のみの版。撮影設定は固定していませんでした。
- `fixed_settings_design.md`：実装の概要。

## Raspberry Piで実行

```bash
sudo apt install python3-picamera2 python3-opencv python3-pil python3-pil.imagetk python3-tk
python3 camera_app.py
```

Piのローカル画面で実行します。起動アイコンの実行先がcamera_pero/camera_app.pyなら、同じ場所に更新すればアイコンはそのまま使えます。

## テスト

```bash
python3 -m unittest discover -s hardware/camera/tests -v
```

カメラと画面を模擬して保存・再起動・反映待ち・逸脱時の停止を確認します。実機での照明・ピント・色の確認は別に必要です。

自動取り込みは [IMPORT_README.md](IMPORT_README.md) を参照してください。JPEGの画像名と同名JSONの形式は維持しているため、既存の取り込み処理を使えます。
