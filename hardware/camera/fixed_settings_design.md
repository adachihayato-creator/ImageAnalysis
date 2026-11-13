# 設定保存・固定機能：2026-11-10実装

詳細な操作・制約は [FIXED_SETTINGS_GUIDE.md](FIXED_SETTINGS_GUIDE.md) を参照してください。

- 実装：camera_app.py（タッチUI）、fixed_settings.py（設定保存・状態管理・メタデータ照合）、capture_metadata.py（同じ撮影フレームのJPEGとJSON）。
- 設定先：~/.config/film_camera/camera_settings.json。設定がない場合、過去の実験値や仮の露光・ゲイン・ピントを採用しない。
- 基準調整：無彩色・ピント用模様を試料面に置く。自動露光・AWB・1回のAFを実行。AF成功と複数フレームの安定を確認後、候補値を手動制御として適用。実値が5フレーム連続で暫定許容差内なら固定プレビューにする。
- 保存：操作者がピント・色・明るさを確認して保存ボタンを押す。既存設定をバックアップし、設定ファイルを原子的に置換。
- 起動：機器ID・モデル・解像度・形式と制御範囲を確認し、保存値をカメラ開始前に適用。AE/AWBを無効化、AFをManualにする。5フレームの検証まで撮影不可。保存設定が壊れていても自動撮影へ黙って戻らない。
- 毎画像：保存するrequestのget_metadata()を照合。逸脱時は撮影不可に遷移し、診断用JPEG/JSONを保存する。JSONには要求設定、設定ハッシュ、比較許容差、差分、判定、実際の全メタデータを記録。
- 制約：許容差は暫定的な数値比較。光学的な校正精度や自動制御無効の独立した証明ではない。DigitalGainや色変換行列は記録するが直接固定しない。装置側の照明・距離・角度の固定と反復撮影が別途必要。

参照：
- https://datasheets.raspberrypi.com/camera/picamera2-manual.pdf
- https://github.com/raspberrypi/picamera2/discussions/592
