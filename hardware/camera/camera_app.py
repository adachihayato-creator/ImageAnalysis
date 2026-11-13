# camera_app.py
# Raspberry Pi 3 Model B + カメラ Module 3
# タッチパネル操作のフルスクリーン・カメラアプリ（キーボード不要）。
#   ・画面いっぱいにライブ映像
#   ・大きな「撮影」ボタンをタップ → 高解像度で保存
#   ・「終了」ボタンでアプリを閉じる
# 保存先: ~/captures/
#
# 必要パッケージ: python3-picamera2, python3-pil, python3-pil.imagetk
import os
import time
import tkinter as tk
from tkinter import messagebox
from pathlib import Path
from datetime import datetime
from importlib.metadata import PackageNotFoundError, version
import platform

import cv2
from PIL import Image, ImageTk
from picamera2 import Picamera2
from capture_metadata import save_request_metadata, json_value
from fixed_settings import LockSession, load_profile, save_profile, validate_profile
from libcamera import controls
from position_guide import (load_guide, make_guide, guide_record, viewport,
                            display_mapping, widget_to_normalized, overlay_preview,
                            translate_corners)


def software_versions():
    result = {"python": platform.python_version()}
    for package in ("picamera2", "Pillow", "numpy"):
        try:
            result[package] = version(package)
        except PackageNotFoundError:
            result[package] = "unknown"
    result["opencv"] = cv2.__version__
    return result

# ===== 設定 =====
# 撮影と表示を同じ main(RGB888) ストリームから取り出す。
# 同じ映像なので画角(ズーム)も色も撮影結果と必ず一致する（表示はウィンドウに縮小するだけ）。
CAPTURE_SIZE = (2304, 1296)   # 撮影/表示の解像度(約3MP・16:9)。重い場合は (1536, 864) 等へ
SAVE_DIR = os.path.expanduser("~/captures")
SETTINGS_FILE = Path.home() / ".config/film_camera/camera_settings.json"
GUIDE_FILE = SETTINGS_FILE.with_name('position_guide.json')
GUIDE_CANDIDATE = Path(__file__).with_name('position_guide_candidate.json')
os.makedirs(SAVE_DIR, exist_ok=True)

# ===== デザイントークン =====
MAIN = "#01A0E9"          # メイン
MAIN_ACTIVE = "#007fbb"
RED = "#FD000F"           # 終了
RED_ACTIVE = "#c40009"
BG = "#f4f5f7"            # 背景
TEXT = "#1c1c1e"
SUBTEXT = "#86868b"
FONT = "LINE Seed JP"     # 無ければ自動で代替フォントになる


class RoundedButton(tk.Canvas):
    """枠線を使わない角丸ボタン。押下時は背景色を濃くするだけ（ボーダーレス原則）。"""
    def __init__(self, parent, text, command, width, height,
                 bg=MAIN, active=MAIN_ACTIVE, fg="#ffffff",
                 radius=16, font_size=20, bold=True):
        super().__init__(parent, width=width, height=height,
                         highlightthickness=0, bd=0, bg=parent["bg"])
        self.command = command
        self.bg, self.active, self.fg = bg, active, fg
        self.radius, self._bw, self._bh, self.text = radius, width, height, text
        self.font = (FONT, font_size, "bold" if bold else "normal")
        self.enabled = True
        self._draw(bg)
        self.bind("<ButtonPress-1>", lambda e: self._draw(self.active) if self.enabled else None)
        self.bind("<ButtonRelease-1>", self._on_release)

    def _round_rect(self, x1, y1, x2, y2, r, **kw):
        pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
               x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
               x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        return self.create_polygon(pts, smooth=True, **kw)

    def _draw(self, color):
        self.delete("all")
        self._round_rect(1, 1, self._bw - 1, self._bh - 1, self.radius,
                         fill=color, outline=color)
        self.create_text(self._bw / 2, self._bh / 2, text=self.text,
                         fill=self.fg, font=self.font)

    def _on_release(self, e):
        self._draw(self.bg if self.enabled else "#aaaaaa")
        if self.enabled and self.command:
            self.command()

    def set_enabled(self, enabled):
        if self.enabled != enabled:
            self.enabled = enabled
            self._draw(self.bg if enabled else "#aaaaaa")

    def set_text(self, text):
        self.text = text
        self._draw(self.bg if self.enabled else "#aaaaaa")


class CameraApp:
    def __init__(self, root):
        self.root = root
        self.capturing = False
        self._running = True
        self._after_id = None
        self.latest_metadata = None
        self._reported_error = None
        self.guide = None
        self.guide_registered = False
        self.guide_error = ''
        self.guide_zoom = False
        self.editing_guide = False
        self.guide_edit_mode = None
        self.move_points = None
        self.move_offset = [0.0,0.0]
        self.move_step = 20
        self.move_view = None
        self.zoom_before_move = False
        self.edit_points = []
        self.registration_frame = None
        self.latest_frame = None
        self.display_map = None

        root.configure(bg=BG)
        root.attributes("-fullscreen", True)
        root.bind("<Escape>", lambda e: self.quit())   # 念のためのキー終了
        root.protocol("WM_DELETE_WINDOW", self.quit)

        # --- 上部バー（タイトル＋終了ボタン） ---
        top = tk.Frame(root, bg=BG)
        top.pack(fill="x", padx=16, pady=(12, 6))
        tk.Label(top, text="Pi Camera", bg=BG, fg=TEXT,
                 font=(FONT, 16, "bold")).pack(side="left")
        # 右側に [撮影][終了] を同じ大きさで並べる（終了の左隣が撮影）
        RoundedButton(top, "終了", self.quit, width=96, height=44,
                      bg=RED, active=RED_ACTIVE, radius=12,
                      font_size=14).pack(side="right")
        self.capture_button = RoundedButton(top, "撮影", self.capture, width=96, height=44,
                                            radius=12, font_size=14)
        self.capture_button.pack(side="right", padx=(0, 8))
        self.capture_button.set_enabled(False)

        tools = tk.Frame(root, bg=BG)
        self.tools = tools
        tools.pack(fill="x", padx=16, pady=4)
        self.calibrate_button = RoundedButton(tools, "基準で調整", self.calibrate,
                                              width=138, height=44, font_size=13)
        self.calibrate_button.pack(side="left", padx=(0,8))
        self.save_button = RoundedButton(tools, "設定を保存", self.save_settings,
                                         width=138, height=44, font_size=13)
        self.save_button.pack(side="left", padx=(0,8))
        self.save_button.set_enabled(False)
        self.restore_button = RoundedButton(tools, "保存設定を使う", self.restore_settings,
                                            width=160, height=44, font_size=13)
        self.restore_button.pack(side="left")
        self.guide_button = RoundedButton(tools, "位置を登録", self.guide_options,
                                           width=112, height=44, font_size=13)
        self.guide_button.pack(side="left", padx=(8,0))
        self.zoom_button = RoundedButton(tools, "拡大／全体", self.toggle_zoom,
                                          width=104, height=44, font_size=12)
        self.zoom_button.pack(side="left", padx=(8,0))

        self.status = tk.Label(root, text="準備中", bg=BG, fg=TEXT,
                               font=(FONT,12), wraplength=740, justify="left")
        self.status.pack(fill="x", padx=16)

        # Replaces the normal toolbar while moving; does not cover the preview.
        self.move_tools = tk.Frame(root,bg=BG)
        self.move_step_button=RoundedButton(self.move_tools,'粗く 20px',self.toggle_move_step,
                                            width=110,height=44,font_size=12)
        self.move_step_button.pack(side='left',padx=(0,6))
        for label,dx,dy in [('←',-1,0),('→',1,0),('↑',0,-1),('↓',0,1)]:
            RoundedButton(self.move_tools,label,lambda x=dx,y=dy:self.nudge_guide(x,y),
                          width=58,height=44,font_size=19).pack(side='left',padx=(0,4))
        RoundedButton(self.move_tools,'保存',self.save_moved_guide,width=82,height=44,
                      font_size=14).pack(side='left',padx=(6,4))
        RoundedButton(self.move_tools,'取消',self.cancel_guide_edit,width=82,height=44,
                      font_size=14).pack(side='left')

        # --- 撮影直後の確認テキスト ---
        self.toast = tk.Label(root, text="", bg=BG, fg=SUBTEXT,
                              font=(FONT, 14))
        self.toast.pack(side="bottom", pady=(0, 8))

        # --- ライブ映像（残りの領域いっぱいに表示） ---
        self.preview = tk.Label(root, bg="#000000", bd=0, highlightthickness=0)
        self.preview.pack(side="top", expand=True, fill="both", padx=16, pady=6)
        self.preview.bind('<ButtonRelease-1>', self.guide_tap)

        # --- カメラ初期化 ---
        # 撮影と表示を同じ main(RGB888) ストリームから取り出す。
        # 同じ映像なので画角(ズーム)も色も撮影結果と必ず一致する。
        self.picam2 = Picamera2()
        self.config = self.picam2.create_preview_configuration(
            main={"size": CAPTURE_SIZE, "format": "RGB888"},
            queue=False,
        )
        self.picam2.configure(self.config)
        self.camera_properties = dict(self.picam2.camera_properties)
        self.software_versions = software_versions()
        self.context = {"model": self.camera_properties.get("Model"),
                        "camera_id": Picamera2.global_camera_info()[0].get("Id"),
                        "capture_size": list(CAPTURE_SIZE), "format": "RGB888"}
        try:
            if GUIDE_FILE.exists():
                self.guide = load_guide(GUIDE_FILE, self.context)
                self.guide_registered = True
            elif GUIDE_CANDIDATE.exists():
                self.guide = load_guide(GUIDE_CANDIDATE, self.context)
        except Exception as e:
            self.guide_error = str(e)
        self.lock = LockSession(self.context)
        self.camera_controls = dict(self.picam2.camera_controls)
        # Saved values are applied before start; no continuous AF overrides them.
        if SETTINGS_FILE.exists():
            try:
                self.apply_profile(load_profile(SETTINGS_FILE, self.context,
                                                self.camera_controls), persisted=True)
            except Exception as e:
                self.lock.fail("保存設定を読めません：" + str(e))
        self.picam2.start()
        self.refresh_status()
        self.update_frame()

    def apply_profile(self, profile, persisted):
        values = validate_profile(profile, self.context, self.camera_controls)
        values['ColourGains'] = tuple(values['ColourGains'])
        self.picam2.set_controls({"AeEnable": False, "AwbEnable": False,
                                 "AfMode": controls.AfModeEnum.Manual, **values})
        self.lock.begin_apply(profile, time.monotonic(), persisted)

    def toggle_zoom(self):
        if not self.editing_guide:
            self.guide_zoom = not self.guide_zoom

    def guide_options(self):
        if self.editing_guide:
            self.cancel_guide_edit()
            return
        if self.capturing or self.latest_frame is None:
            return
        dialog = tk.Toplevel(self.root)
        dialog.title('位置枠の登録')
        dialog.configure(bg=BG)
        dialog.transient(self.root)
        tk.Label(dialog, text='白枠は基板の外形を合わせる目印です。\n'
                 '位置だけ変える場合は「枠を移動」を選んでください。\n'
                 '露光・色・ピントの保存設定は変わりません。',
                 bg=BG,fg=TEXT,font=(FONT,13)).pack(padx=16,pady=16)
        def use_current():
            dialog.destroy()
            if self.guide and messagebox.askyesno('位置枠を保存',
                    '白枠の位置・大きさを今後の共通基準として保存しますか？\n'
                    '膜ごとには変更しません。',parent=self.root):
                self.persist_guide(make_guide(self.guide['corners_normalized'],self.context,
                    {'method':'operator_confirmed_existing_outline',
                     'previous_profile_sha256':guide_record(self.guide,self.guide_registered)['profile_sha256']}))
        button=RoundedButton(dialog,'この枠を保存',use_current,width=260,height=48,font_size=15)
        button.pack(pady=5);button.set_enabled(self.guide is not None)
        def move():
            dialog.destroy()
            self.begin_guide_move()
        button=RoundedButton(dialog,'枠を移動（矢印）',move,width=260,height=48,font_size=15)
        button.pack(pady=5);button.set_enabled(self.guide is not None)
        def manual():
            dialog.destroy()
            self.begin_guide_edit()
        RoundedButton(dialog,'四隅をタップして指定',manual,width=260,height=48,font_size=15).pack(pady=5)
        RoundedButton(dialog,'戻る',dialog.destroy,width=260,height=48,font_size=15).pack(pady=(5,16))
        dialog.grab_set()

    def begin_guide_move(self):
        if self.guide is None or self.capturing:return
        self.editing_guide=True
        self.guide_edit_mode='move'
        self.move_points=[list(point) for point in self.guide['corners_normalized']]
        self.move_offset=[0.0,0.0]
        self.move_step=20
        self.move_step_button.set_text('粗く 20px')
        self.zoom_before_move=self.guide_zoom
        # Keep the viewport stationary: following the frame would hide movement.
        self.move_view=(0,0,*CAPTURE_SIZE)
        self.edit_points=[]
        self.registration_frame=None
        self.display_map=None
        self.tools.pack_forget()
        self.move_tools.pack(fill='x',padx=16,pady=4,before=self.status)
        self.refresh_status()

    def toggle_move_step(self):
        self.move_step=1 if self.move_step==20 else 20
        self.move_step_button.set_text('細かく 1px' if self.move_step==1 else '粗く 20px')
        self.refresh_status()

    def nudge_guide(self,dx,dy):
        if not self.editing_guide or self.guide_edit_mode!='move':return
        self.move_points,moved=translate_corners(self.move_points,
            dx*self.move_step,dy*self.move_step,CAPTURE_SIZE)
        self.move_offset=[a+b for a,b in zip(self.move_offset,moved)]
        if moved==(0.0,0.0):
            self.toast.configure(text='画像の端です。枠の形・大きさは変えません。',fg=SUBTEXT)
        self.refresh_status()

    def save_moved_guide(self):
        if not self.editing_guide or self.guide_edit_mode!='move':return
        if not messagebox.askyesno('移動した枠を保存',
                'この位置を今後の共通の白枠として保存しますか？\n'
                '形・大きさと撮影設定は変更しません。',parent=self.root):return
        profile=make_guide(self.move_points,self.context,{'method':'operator_arrow_translation',
            'previous_profile_sha256':guide_record(self.guide,self.guide_registered)['profile_sha256'],
            'translation_pixels':list(self.move_offset)})
        self.persist_guide(profile)

    def persist_guide(self, profile):
        try:
            save_profile(GUIDE_FILE,profile)
            self.guide=profile
            self.guide_registered=True
            self.guide_error=''
            self.cancel_guide_edit()
            self.toast.configure(text='位置枠を保存しました。撮影設定は変更していません。',fg=SUBTEXT)
        except Exception as e:
            self.guide_error='位置枠の保存失敗：'+str(e)
            self.refresh_status()

    def begin_guide_edit(self):
        self.registration_frame=self.latest_frame.copy()
        self.editing_guide=True
        self.guide_edit_mode='corners'
        self.edit_points=[]
        self.guide_zoom=True
        self.display_map=None
        self.guide_button.set_text('登録を取消')
        self.refresh_status()

    def cancel_guide_edit(self):
        if self.guide_edit_mode=='move':
            self.move_tools.pack_forget()
            self.tools.pack(fill='x',padx=16,pady=4,before=self.status)
            self.guide_zoom=self.zoom_before_move
        self.editing_guide=False
        self.guide_edit_mode=None
        self.move_points=None
        self.move_view=None
        self.edit_points=[]
        self.registration_frame=None
        self.display_map=None
        self.guide_button.set_text('位置を登録')
        self.refresh_status()

    def guide_tap(self,event):
        if not self.editing_guide or self.guide_edit_mode!='corners' or self.display_map is None or len(self.edit_points)>=4:
            return
        point=widget_to_normalized((event.x,event.y),self.display_map)
        if point is None:return
        self.edit_points.append(point)
        if len(self.edit_points)==4:
            self.root.after(80,self.confirm_guide_corners)
        self.refresh_status()

    def confirm_guide_corners(self):
        if not self.editing_guide or self.guide_edit_mode!='corners' or len(self.edit_points)!=4:return
        try:
            profile=make_guide(self.edit_points,self.context,{'method':'operator_four_corner_taps'})
        except ValueError as e:
            messagebox.showerror('四隅の指定',str(e),parent=self.root)
            self.edit_points=[];self.refresh_status();return
        if messagebox.askyesno('位置枠を保存','指定した四隅を共通の位置枠として保存しますか？',parent=self.root):
            self.persist_guide(profile)
        else:
            self.edit_points=[];self.refresh_status()

    def calibrate(self):
        if self.editing_guide or self.capturing or self.lock.state in ("calibrating", "applying"):
            return
        if not messagebox.askyesno("基準で調整", "照明・距離を固定し、試料と同じ高さに\n"
                                  "無彩色の基準とピント確認用の模様を置いてください。\n"
                                  "既存の保存設定は上書きせず、自動調整を始めます。\n"
                                  "測定途中の膜に合わせて毎回調整しないでください。", parent=self.root):
            return
        try:
            required = ("AeEnable", "AwbEnable", "AfMode", "AfTrigger")
            if any(name not in self.camera_controls for name in required):
                raise ValueError("必要な自動調整制御がありません")
            self.picam2.set_controls({"AeEnable": True, "AwbEnable": True,
                                     "AfMode": controls.AfModeEnum.Auto,
                                     "AfTrigger": controls.AfTriggerEnum.Start})
            self.lock.begin_calibration(time.monotonic())
        except Exception as e:
            self.lock.fail(str(e))
        self.refresh_status()

    def restore_settings(self):
        if self.editing_guide or self.capturing or self.lock.state in ("calibrating", "applying"):
            return
        try:
            self.apply_profile(load_profile(SETTINGS_FILE, self.context,
                                            self.camera_controls), persisted=True)
        except Exception as e:
            self.lock.fail("保存設定を使えません：" + str(e))
        self.refresh_status()

    def save_settings(self):
        if self.editing_guide or self.lock.state != "confirm_preview":
            return
        values = self.lock.profile['values']
        if not messagebox.askyesno("固定プレビューの確認", "ピント・色・明るさを確認してください。\n"
                                  "白飛びや黒つぶれがなく、この設定を保存しますか？\n"
                                  f"露光 {values['ExposureTime']} μs\n"
                                  f"ゲイン {values['AnalogueGain']:.4f}\n"
                                  f"色ゲイン {values['ColourGains']}\n"
                                  f"レンズ位置 {values['LensPosition']:.4f}\n"
                                  "既存設定がある場合はバックアップします。", parent=self.root):
            return
        try:
            # Recheck the last frame; capture() also checks its own frame.
            if not self.lock.observe_fixed(self.latest_metadata, time.monotonic())['passed']:
                raise ValueError("設定値が逸脱しています")
            profile = dict(self.lock.profile)
            profile['operator_confirmed_at'] = datetime.now().astimezone().isoformat()
            profile['software_versions'] = self.software_versions
            save_profile(SETTINGS_FILE, profile)
            self.lock.profile = profile
            self.lock.mark_saved()
        except Exception as e:
            self.lock.fail("設定保存失敗：" + str(e))
        self.refresh_status()

    def refresh_status(self):
        state = self.lock.state
        if state == 'error' and self.lock.error != self._reported_error:
            self._reported_error = self.lock.error
            try:
                diagnostic = SETTINGS_FILE.parent / ("verification_error_" +
                    datetime.now().strftime('%Y%m%d_%H%M%S_%f') + ".json")
                save_profile(diagnostic, json_value({"error": self.lock.error,
                    "profile": self.lock.profile, "metadata": self.latest_metadata,
                    "comparison": self.lock.last_check, "context": self.context}))
            except Exception as e:
                print("検証失敗の記録も保存できませんでした:", e)
        elif state != 'error':
            self._reported_error = None
        text = {"unconfigured": "未設定：基準を置いて「基準で調整」を押してください。撮影はまだできません。",
                "calibrating": "基準で自動調整中：照明・基準を動かさずお待ちください。",
                "applying": "固定値の反映を確認中：5フレーム連続で照合します。",
                "confirm_preview": "固定プレビュー：ピント・色・明るさを確認し「設定を保存」。撮影は保存後です。",
                "locked": "保存設定で撮影可能：露光・色ゲイン・焦点の実値を照合済み（暫定許容差内）。",
                "error": "撮影停止：" + self.lock.error}[state]
        if self.editing_guide:
            if self.guide_edit_mode=='move':
                text+=f'\n枠を移動中：1回 {self.move_step}px／右 {self.move_offset[0]:.0f}px・下 {self.move_offset[1]:.0f}px（元画像の単位）'
            else:
                labels=('左上','右上','右下','左下')
                text+='\n静止画で登録：'+('保存を確認してください' if len(self.edit_points)==4 else labels[len(self.edit_points)]+'をタップ')
        else:
            text+='\n'+('位置枠：'+self.guide_error if self.guide_error else
                '白枠：登録済み。膜の外形を合わせてください（自動判定なし）。' if self.guide_registered else
                '白枠：10min・3hの候補。「位置を登録」で確認して保存。' if self.guide else '位置枠：未登録')
        self.status.configure(text=text, fg=RED if state=='error' else TEXT)
        self.capture_button.set_enabled(self.lock.can_capture and not self.editing_guide)
        self.save_button.set_enabled(state=='confirm_preview' and not self.editing_guide)
        self.calibrate_button.set_enabled(state not in ('applying','calibrating') and not self.editing_guide)
        self.restore_button.set_enabled(SETTINGS_FILE.exists() and state not in ('applying','calibrating') and not self.editing_guide)
        self.zoom_button.set_enabled(not self.editing_guide)

    def update_frame(self):
        """ライブ映像(main)を更新。撮影と同じ画角・同じ色。"""
        if not self._running:
            return
        if not self.capturing:
            try:
                request = self.picam2.capture_request()
                try:
                    frame = request.make_array("main").copy()
                    metadata = request.get_metadata()
                finally:
                    request.release()
                self.latest_metadata = metadata
                self.latest_frame = frame
                now = time.monotonic()
                if self.lock.state == 'calibrating':
                    focused = metadata.get('AfState') == controls.AfStateEnum.Focused
                    if self.lock.observe_calibration(metadata, now, focused):
                        self.apply_profile(self.lock.make_candidate(metadata), persisted=False)
                elif self.lock.state in ('applying','locked','confirm_preview'):
                    self.lock.observe_fixed(metadata, now)
                    if self.lock.state == 'applying' and self.lock.pending_exposure_correction is not None:
                        self.apply_profile(self.lock.corrected_exposure_profile(), persisted=False)
                self.refresh_status()
            except Exception as e:
                self.lock.fail("カメラ更新失敗：" + str(e))
                self.refresh_status()
                self._after_id = self.root.after(250, self.update_frame)
                return
            # The guide is drawn only on a separate display image.
            pw, ph = self.preview.winfo_width(), self.preview.winfo_height()
            if pw > 1 and ph > 1:
                moving=self.editing_guide and self.guide_edit_mode=='move'
                display_frame=self.registration_frame if self.editing_guide and not moving else frame
                ih,iw=display_frame.shape[:2]
                points=self.guide['corners_normalized'] if self.guide else None
                view=self.move_view if moving else viewport((iw,ih),points,self.guide_zoom)
                self.display_map=display_mapping((iw,ih),(pw,ph),view)
                rgb=cv2.cvtColor(display_frame,cv2.COLOR_BGR2RGB)
                img=Image.fromarray(rgb).crop(view).resize(self.display_map['display_size'])
                displayed_guide=dict(self.guide,corners_normalized=self.move_points) if moving else self.guide
                img=overlay_preview(img,displayed_guide,self.display_map,self.edit_points)
                self.photo=ImageTk.PhotoImage(img)
                self.preview.configure(image=self.photo)
        self._after_id = self.root.after(30, self.update_frame)

    def capture(self):
        if self.editing_guide or self.capturing or not self.lock.can_capture:
            return
        self.capturing = True
        self.toast.configure(text="撮影中...", fg=MAIN)
        self.root.update_idletasks()
        captured_at = datetime.now().astimezone()
        # Microseconds avoid collisions on repeated taps within one second.
        filename = captured_at.strftime("photo_%Y%m%d_%H%M%S_%f.jpg")
        filepath = os.path.join(SAVE_DIR, filename)
        image_saved = False
        try:
            # main ストリームから高解像度で保存（プレビューと同じ画角）
            request = self.picam2.capture_request()
            try:
                # Both JPEG and metadata MUST come from this same request.
                metadata = request.get_metadata()
                fixed_record = self.lock.capture_record(metadata, time.monotonic())
                request.save("main", filepath)
                image_saved = True
            finally:
                request.release()
            metadata_path = save_request_metadata(
                filepath, metadata, captured_at=captured_at.isoformat(),
                capture_size=CAPTURE_SIZE,
                camera_properties=self.camera_properties,
                software_versions=self.software_versions,
                fixed_settings=fixed_record,
                position_guide=guide_record(self.guide,self.guide_registered),
            )
            if fixed_record['fixed_settings_verified']:
                self.toast.configure(text="固定設定 JPEG・JSON保存: " + filename, fg=SUBTEXT)
            else:
                self.toast.configure(text="設定逸脱：診断用JPEG・JSON保存。固定撮影としては使えません。", fg=RED)
            print("保存しました:", filepath, metadata_path)
        except Exception as e:
            status = "JPEG保存済み・JSON保存失敗" if image_saved else "撮影失敗"
            self.toast.configure(text=status + ": " + str(e), fg=RED)
            print(status + ":", filepath, e)
        finally:
            self.capturing = False
            self.refresh_status()
        self.root.after(2500, lambda: self.toast.configure(text=""))

    def quit(self):
        # まず更新ループを止め、ボタンイベントを抜けてからカメラを停止する
        # （イベント処理中に stop() を待つと固まるため遅延実行する）
        self._running = False
        if self._after_id is not None:
            try:
                self.root.after_cancel(self._after_id)
            except Exception:
                pass
        self.root.after(50, self._teardown)

    def _teardown(self):
        try:
            self.picam2.stop()
        except Exception:
            pass
        try:
            self.picam2.close()
        except Exception:
            pass
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    root.title("Pi Camera")
    app = CameraApp(root)
    root.mainloop()
