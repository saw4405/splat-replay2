"""
ビデオプレビューウィジェット

AutoRecorder からのリアルタイム映像を表示する
"""

import base64
import time
import tkinter as tk
from typing import Dict, Optional

import cv2
import ttkbootstrap as ttk
from PIL import Image, ImageTk
from ttkbootstrap.tooltip import ToolTip

from splat_replay.domain.models import Frame
from splat_replay.domain.services import RecordState
from splat_replay.gui.controllers.application_controller import (
    GUIApplicationController,
)
from splat_replay.gui.widgets.card_widget import CardWidget
from splat_replay.gui.widgets.recording_controls_widget import (
    RecordingControlsWidget,
)


class VideoPreviewCard(CardWidget):
    """ビデオプレビュー表示ウィジェット"""

    def __init__(
        self,
        parent: ttk.Frame,
        controller: GUIApplicationController,
    ):
        title = "　▶️ ライブプレビュー　"
        title = "　▶ ライブプレビュー　"
        super().__init__(parent, title)
        self.controller = controller
        self.colors: ttk.Colors = ttk.Style().colors  # type: ignore

        # Canvas を作成（16:9）
        self.canvas = tk.Canvas(
            self.content,
            width=720,
            height=405,
            relief="flat",
        )
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        ToolTip(
            self.canvas,
            text="アプリ動作状態確認のための簡易プレビュー映像です。\nOBSで録画しているため、このプレビュー映像にカクツキがあっても録画映像には影響しません。",
            padding=3,
            bootstyle="light",  # type: ignore
        )
        self.recording_controls = RecordingControlsWidget(
            self.footer, controller
        )

        # 状態管理
        self.update_job: Optional[str] = None
        self.last_frame_time = 0.0
        self.frame_count = 0
        self.fps_display_time = time.time()
        self.current_fps = 0.0
        self.canvas_image: Optional[ImageTk.PhotoImage] = None
        self.record_state = self.controller.get_current_record_state()
        self.border_width = 10
        self.border_color: str = self.colors.border
        self._image_item_id: Optional[int] = None
        self._border_item_id: Optional[int] = None
        self._fps_items: list[int] = []  # 背景とテキスト
        self._record_state_items: list[int] = []
        self._message_items: list[int] = []
        self._current_message: Optional[str] = None
        self._last_frame_received_at = 0.0
        self._no_signal_threshold_sec = 0.5
        self._last_record_state_drawn: Optional[RecordState] = None
        self._last_fps_text: str = ""
        self._no_signal_job_id: Optional[str] = None
        # --- performance optimization additions ---
        self._target_draw_width: int | None = None
        self._target_draw_height: int | None = None
        self._last_canvas_size: tuple[int, int] | None = None
        self._last_src_size: tuple[int, int] | None = None
        self._perf_frame_counter = 0
        self._perf_accum_time = 0.0
        self._perf_last_report = time.time()
        self._target_frame_interval = 1 / 60
        self._dynamic_interval_ms = 1000.0 * self._target_frame_interval
        # 自動スケール適応 (負荷が高いとき解像度を下げ FPS を稼ぐ)
        self._adaptive_scale: float = 1.0
        self._min_scale: float = 0.5
        self._max_scale: float = 1.0
        self._last_scale_adjust_time: float = time.time()
        self._perf_window_frames: int = 0
        self._perf_window_time: float = 0.0
        # PhotoImage 再利用用サイズ記録
        self._photoimage_width: int | None = None
        self._photoimage_height: int | None = None
        # 直接 PhotoImage(base64+PPM) 方式は Windows でオーバーヘッドが大きい可能性 -> デフォ無効
        self._use_direct_photoimage: bool = False

        # コールバック登録
        self.controller.add_record_state_changed_listener(
            self._on_state_change
        )

        # プレビュー開始
        self._init_canvas_items()
        # 初期化ログ（UTF-8）
        self.logger.info("VideoPreviewCard を初期化しました")
        # Controller 経由でフレーム購読（GUI スレッドで呼び出し）
        if not self.controller.on_preview_frame(self._on_frame_push):
            self.logger.warning("ランタイム未接続のためプレビューは無効です")
            # ランタイム未接続時は明示的にメッセージ表示
            self._show_center_message("キャプチャボードが接続されていません")
        self.logger.info("VideoPreviewWidget が初期化されました")
        # デバイス未接続の監視を開始（フレーム未受信が一定時間続いたら表示）
        self._schedule_no_signal_watch()

    # 初期 Canvas アイテム生成（以後は itemconfig / coords で更新）
    def _init_canvas_items(self) -> None:
        self.canvas.update_idletasks()  # 早期にサイズ確定
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        # 画像プレースホルダ
        self._image_item_id = self.canvas.create_image(
            cw // 2,
            ch // 2,
            image=None,
            anchor=tk.CENTER,
            tags=("frame_image",),
        )
        # 枠（最初はゼロサイズ）
        self._border_item_id = self.canvas.create_rectangle(
            0,
            0,
            0,
            0,
            outline=self.border_color,
            width=self.border_width,
            tags=("frame_border",),
        )

    def _on_frame_push(self, frame: Frame) -> None:
        self._last_frame_received_at = time.time()
        self._display_frame(frame)
        # self._maybe_update_fps_overlay()
        self._maybe_update_record_state_overlay(force=False)
        self._clear_message_overlay()

    def _display_frame(self, frame: Frame) -> None:
        """フレームを Canvas に表示 (高速化: PIL 再利用デフォ)"""
        try:
            t0 = time.time()
            cw = self.canvas.winfo_width()
            ch = self.canvas.winfo_height()
            if cw <= 2 or ch <= 2:
                return
            size_changed = False
            if self._last_canvas_size != (cw, ch):
                self._compute_target_draw_size(cw, ch)
                self._last_canvas_size = (cw, ch)
                size_changed = True

            bgr = frame
            src_h, src_w = bgr.shape[:2]
            self._last_src_size = (src_w, src_h)
            tw = self._target_draw_width or src_w
            th = self._target_draw_height or src_h
            scale = min(tw / src_w, th / src_h, 1.0)
            dst_w = int(src_w * scale)
            dst_h = int(src_h * scale)
            if dst_w != src_w or dst_h != src_h:
                bgr = cv2.resize(
                    bgr,
                    (dst_w, dst_h),
                    interpolation=cv2.INTER_AREA
                    if scale < 1.0
                    else cv2.INTER_LINEAR,
                )
            t_resize = time.time()

            # BGR->RGB (numpy スライス copy)
            rgb = bgr[..., ::-1].copy()
            t_conv = time.time()

            created_new = False
            if self._use_direct_photoimage:
                try:
                    header = f"P6 {dst_w} {dst_h} 255\n".encode("ascii")
                    ppm_bytes = header + rgb.tobytes()
                    b64 = base64.b64encode(ppm_bytes)
                    self.canvas_image = tk.PhotoImage(data=b64)  # type: ignore[assignment]
                    created_new = True
                    self._photoimage_width = dst_w
                    self._photoimage_height = dst_h
                except Exception:
                    self._use_direct_photoimage = False  # Fallback

            if not self._use_direct_photoimage:
                # PIL 経由 (再利用)
                pil_img = None
                need_new = (
                    self.canvas_image is None
                    or self._photoimage_width != dst_w
                    or self._photoimage_height != dst_h
                    or not isinstance(self.canvas_image, ImageTk.PhotoImage)
                )
                if need_new or self.canvas_image is None:
                    pil_img = Image.fromarray(rgb)
                    self.canvas_image = ImageTk.PhotoImage(pil_img)
                    self._photoimage_width = dst_w
                    self._photoimage_height = dst_h
                    created_new = True
                else:
                    try:
                        pil_img = Image.fromarray(rgb)
                        self.canvas_image.paste(pil_img)
                    except Exception:
                        pil_img = Image.fromarray(rgb)
                        self.canvas_image = ImageTk.PhotoImage(pil_img)
                        created_new = True
            t_img = time.time()

            if (
                self._image_item_id is not None
                and self.canvas_image is not None
            ):
                if created_new:
                    self.canvas.itemconfig(
                        self._image_item_id, image=self.canvas_image
                    )
                self.canvas.coords(self._image_item_id, cw // 2, ch // 2)

            # 枠はサイズ変わった時のみ更新
            if size_changed or created_new:
                img_w = self._photoimage_width or dst_w
                img_h = self._photoimage_height or dst_h
                left = (cw - img_w) // 2
                top = (ch - img_h) // 2
                right = left + img_w
                bottom = top + img_h
                if self._border_item_id is not None:
                    try:
                        self.canvas.itemconfig(
                            self._border_item_id, outline=self.border_color
                        )
                        self.canvas.coords(
                            self._border_item_id, left, top, right, bottom
                        )
                    except tk.TclError:
                        pass

            total = time.time() - t0
            self._perf_frame_counter += 1
            self._perf_accum_time += total

            target = self._target_frame_interval
            remaining = (target - total) * 1000.0
            if remaining < 1.0:
                self._dynamic_interval_ms = 1.0
            else:
                # 緩やかな平滑化 (作業量抑制)
                self._dynamic_interval_ms = (
                    0.8 * self._dynamic_interval_ms + 0.2 * remaining
                )
                self._dynamic_interval_ms = max(
                    1.0, min(self._dynamic_interval_ms, 25.0)
                )

            now = time.time()
            if now - self._perf_last_report >= 2.0:
                avg = (
                    (self._perf_accum_time / self._perf_frame_counter)
                    if self._perf_frame_counter
                    else 0.0
                )
                approx_fps = 1.0 / avg if avg > 0 else 0.0
                self.logger.debug(
                    "video_preview_perf",
                    frames=self._perf_frame_counter,
                    avg_ms=f"{avg * 1000:.2f}",
                    approx_fps=f"{approx_fps:.1f}",
                    next_interval_ms=f"{self._dynamic_interval_ms:.1f}",
                    resize_ms=f"{(t_resize - t0) * 1000:.2f}",
                    conv_ms=f"{(t_conv - t_resize) * 1000:.2f}",
                    img_ms=f"{(t_img - t_conv) * 1000:.2f}",
                    new=created_new,
                    direct=self._use_direct_photoimage,
                    w=dst_w,
                    h=dst_h,
                )
                self._perf_frame_counter = 0
                self._perf_accum_time = 0.0
                self._perf_last_report = now
        except Exception as e:
            self.logger.error(f"フレーム表示でエラー: {e}")
            self._show_center_message(f"フレーム表示エラー: {e}")

    def _resize_with_aspect_ratio(
        self, image: Image.Image, max_width: int, max_height: int
    ) -> Image.Image:
        """
        アスペクト比を維持してリサイズ

        Args:
            image: リサイズする画像
            max_width: 最大幅
            max_height: 最大高さ

        Returns:
            リサイズされた画像
        """
        original_width, original_height = image.size

        # アスペクト比を計算
        aspect_ratio = original_width / original_height

        if max_width / max_height > aspect_ratio:
            # 高さに合わせる
            new_height = max_height
            new_width = int(max_height * aspect_ratio)
        else:
            # 幅に合わせる
            new_width = max_width
            new_height = int(max_width / aspect_ratio)

        return image.resize((new_width, new_height), Image.Resampling.LANCZOS)

    def _update_fps_counter(self) -> None:
        """FPS カウンターを更新"""
        current_time = time.time()

        if self.last_frame_time > 0:
            self.frame_count += 1

            # 1秒ごとに FPS を計算
            if current_time - self.fps_display_time >= 1.0:
                self.current_fps = self.frame_count / (
                    current_time - self.fps_display_time
                )
                self.frame_count = 0
                self.fps_display_time = current_time

        self.last_frame_time = current_time

    def _maybe_update_fps_overlay(self) -> None:
        """FPS オーバーレイを必要時のみ更新 (1秒毎)。削除再生成でのちらつきを避け更新インプレース。"""
        prev_fps_text = self._last_fps_text
        before_second = int(self.fps_display_time)
        self._update_fps_counter()
        if int(self.fps_display_time) == before_second and prev_fps_text:
            return
        fps_text = f"FPS: {self.current_fps:.1f}"
        if fps_text == prev_fps_text:
            return
        self._last_fps_text = fps_text

        pad_x, pad_y = 6, 3
        if len(self._fps_items) == 2:
            bg_id, text_id = self._fps_items
            # 既存テキスト更新
            try:
                self.canvas.itemconfig(text_id, text=fps_text)
                # bbox 取得のため一旦更新
                self.canvas.update_idletasks()
                bbox = self.canvas.bbox(text_id)
                if bbox:
                    x0, y0, x1, y1 = bbox
                    width = x1 - x0
                    height = y1 - y0
                    self.canvas.coords(
                        bg_id,
                        5,
                        5,
                        5 + width + pad_x * 2,
                        5 + height + pad_y * 2,
                    )
                    # テキスト位置維持
                    self.canvas.coords(text_id, 5 + pad_x, 5 + pad_y)
                return
            except tk.TclError:
                # 再生成 fallback
                pass

        # ここまで来たら再生成
        for item in self._fps_items:
            try:
                self.canvas.delete(item)
            except tk.TclError:
                pass
        self._fps_items.clear()

        tmp_id = self.canvas.create_text(
            -1000, -1000, text=fps_text, anchor="nw"
        )
        bbox = self.canvas.bbox(tmp_id)
        self.canvas.delete(tmp_id)
        if not bbox:
            return
        x0, y0, x1, y1 = bbox
        width = x1 - x0
        height = y1 - y0
        bg_id = self.canvas.create_rectangle(
            5,
            5,
            5 + width + pad_x * 2,
            5 + height + pad_y * 2,
            fill="#000000",
            outline="",
        )
        text_id = self.canvas.create_text(
            5 + pad_x,
            5 + pad_y,
            text=fps_text,
            fill="#ffffff",
            anchor="nw",
        )
        self._fps_items.extend([bg_id, text_id])
        self.canvas.tag_raise(text_id)

    def _maybe_update_record_state_overlay(self, force: bool) -> None:
        """録画/一時停止ラベルを状態変化時のみ更新。インプレースでちらつき低減。"""
        if not force and self.record_state == self._last_record_state_drawn:
            return

        state_label_map = {
            RecordState.RECORDING: ("⏺️ REC", self.colors.success),
            RecordState.PAUSED: ("⏸️ PAUSE", self.colors.warning),
        }
        if self.record_state not in state_label_map:
            # ラベル無し状態なら既存を消す
            if self._record_state_items:
                for item in self._record_state_items:
                    try:
                        self.canvas.delete(item)
                    except tk.TclError:
                        pass
                self._record_state_items.clear()
            self._last_record_state_drawn = self.record_state
            return

        label, color = state_label_map[self.record_state]
        pad_x, pad_y = 6, 3
        margin = 5
        canvas_width = self.canvas.winfo_width()

        if len(self._record_state_items) == 2:
            bg_id, text_id = self._record_state_items
            try:
                self.canvas.itemconfig(
                    text_id, text=label, fill=self.colors.fg
                )
                self.canvas.itemconfig(bg_id, fill=color)
                self.canvas.update_idletasks()
                bbox = self.canvas.bbox(text_id)
                if bbox:
                    x0, y0, x1, y1 = bbox
                    width = x1 - x0
                    height = y1 - y0
                    rect_left = canvas_width - margin - width - pad_x * 2
                    rect_top = margin
                    rect_right = canvas_width - margin
                    rect_bottom = margin + height + pad_y * 2
                    self.canvas.coords(
                        bg_id,
                        rect_left,
                        rect_top,
                        rect_right,
                        rect_bottom,
                    )
                    self.canvas.coords(
                        text_id,
                        rect_right - pad_x,
                        rect_top + pad_y,
                    )
                self._last_record_state_drawn = self.record_state
                return
            except tk.TclError:
                pass  # 再生成 fallback

        # 再生成
        for item in self._record_state_items:
            try:
                self.canvas.delete(item)
            except tk.TclError:
                pass
        self._record_state_items.clear()

        tmp_id = self.canvas.create_text(-1000, -1000, text=label, anchor="ne")
        bbox = self.canvas.bbox(tmp_id)
        self.canvas.delete(tmp_id)
        if not bbox:
            return
        x0, y0, x1, y1 = bbox
        width = x1 - x0
        height = y1 - y0

        rect_left = canvas_width - margin - width - pad_x * 2
        rect_top = margin
        rect_right = canvas_width - margin
        rect_bottom = margin + height + pad_y * 2

        bg_id = self.canvas.create_rectangle(
            rect_left,
            rect_top,
            rect_right,
            rect_bottom,
            fill=color,
            outline="",
        )
        text_id = self.canvas.create_text(
            rect_right - pad_x,
            rect_top + pad_y,
            text=label,
            fill=self.colors.fg,
            anchor="ne",
        )
        self._record_state_items.extend([bg_id, text_id])
        self.canvas.tag_raise(text_id)
        self._last_record_state_drawn = self.record_state

    def _clear_message_overlay(self) -> None:
        for item in self._message_items:
            try:
                self.canvas.delete(item)
            except tk.TclError:
                pass
        self._message_items.clear()
        self._current_message = None

    def _show_center_message(self, message: str) -> None:
        # 既存メッセージを差し替え
        self._clear_message_overlay()
        canvas_width = (
            self.canvas.winfo_width() or self.canvas.winfo_reqwidth()
        )
        canvas_height = (
            self.canvas.winfo_height() or self.canvas.winfo_reqheight()
        )
        text_id = self.canvas.create_text(
            canvas_width // 2,
            canvas_height // 2,
            text=message,
            fill=self.colors.fg,
            anchor=tk.CENTER,
            justify=tk.CENTER,
            width=max(canvas_width - 40, 10),
        )
        self._message_items.append(text_id)
        self._current_message = message

    def _schedule_no_signal_watch(self) -> None:
        """フレーム未受信が続く場合、未接続メッセージを表示する。"""

        def _tick() -> None:
            try:
                now = time.time()
                # 一度も受信していない or しばらく受信がない
                if (
                    self._last_frame_received_at <= 0.0
                    or (now - self._last_frame_received_at)
                    > self._no_signal_threshold_sec
                ):
                    # 既に同一メッセージなら再描画はスキップ
                    if (
                        self._current_message
                        != "キャプチャボードが接続されていません"
                    ):
                        self._show_center_message(
                            "キャプチャボードが接続されていません"
                        )
                # 次回も監視
            finally:
                self._no_signal_job_id = self.canvas.after(250, _tick)

        # 初回キック
        self._no_signal_job_id = self.canvas.after(250, _tick)

    def _on_state_change(self, state: RecordState) -> None:
        """録画状態に応じて Canvas の枠色を更新。"""
        self.record_state = state
        default = self.colors.border
        color_map: Dict[RecordState, str] = {
            RecordState.RECORDING: self.colors.success,
            RecordState.PAUSED: self.colors.warning,
            RecordState.STOPPED: default,
        }
        self.border_color = color_map.get(state) or default
        # 枠色即時反映
        if self._border_item_id is not None:
            try:
                self.canvas.itemconfig(
                    self._border_item_id, outline=self.border_color
                )
            except tk.TclError:
                pass
        # ラベル更新
        self._maybe_update_record_state_overlay(force=True)

    def _compute_target_draw_size(self, canvas_w: int, canvas_h: int) -> None:
        """キャンバスサイズから描画ターゲットサイズを計算しキャッシュ"""
        # 余白分を少し確保 (border line 分)
        pad = 2
        self._target_draw_width = max(1, canvas_w - pad * 2)
        self._target_draw_height = max(1, canvas_h - pad * 2)

    def _on_canvas_configure(self, event) -> None:  # type: ignore[no-untyped-def]
        cw = event.width
        ch = event.height
        if (cw, ch) != self._last_canvas_size:
            self._compute_target_draw_size(cw, ch)
            self._last_canvas_size = (cw, ch)
            # 枠だけ座標更新 (画像は次フレームで更新) でちらつき回避
            if (
                self._border_item_id is not None
                and self.canvas_image is not None
            ):
                img_w = self.canvas_image.width()
                img_h = self.canvas_image.height()
                left = (cw - img_w) // 2
                top = (ch - img_h) // 2
                right = left + img_w
                bottom = top + img_h
                try:
                    self.canvas.coords(
                        self._border_item_id, left, top, right, bottom
                    )
                except tk.TclError:
                    pass
            # メッセージが出ていれば中央に再配置
            if self._current_message:
                try:
                    self._show_center_message(self._current_message)
                except Exception:
                    pass

        # パフォーマンス計測リセットは維持
        self._perf_frame_counter = 0
        self._perf_accum_time = 0.0
        self._perf_last_report = time.time()
