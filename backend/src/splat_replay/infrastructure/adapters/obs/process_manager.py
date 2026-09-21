"""OBS Studio プロセス管理。

責務:
- OBSプロセスの起動・終了
- プロセス/ウィンドウの存在確認
- プロセス優先度制御
"""

from __future__ import annotations

import asyncio
import re
import subprocess
import sys
import time
from pathlib import Path
from types import ModuleType
from typing import Any, List, Optional, cast

import psutil
from structlog.stdlib import BoundLogger

from splat_replay.domain.exceptions import DeviceError

# Windows APIのオプショナルインポート
win32api: ModuleType | None = None
win32com_client: ModuleType | None = None
win32con: ModuleType | None = None
win32gui: ModuleType | None = None
win32process: ModuleType | None = None

if sys.platform == "win32":
    try:
        import win32api as _win32api
        import win32com.client as _win32com_client
        import win32con as _win32con
        import win32gui as _win32gui
        import win32process as _win32process

        win32api = _win32api
        win32com_client = _win32com_client
        win32con = _win32con
        win32gui = _win32gui
        win32process = _win32process
    except Exception:
        pass

UIA_TREE_SCOPE_CHILDREN = 0x2
UIA_TREE_SCOPE_DESCENDANTS = 0x4
UIA_INVOKE_PATTERN_ID = 10000
UIA_PROCESS_ID_PROPERTY_ID = 30002
UIA_CONTROL_TYPE_PROPERTY_ID = 30003
UIA_BUTTON_CONTROL_TYPE_ID = 50000
OBS_MAIN_WINDOW_TITLE = re.compile(
    r"^OBS(?:\s+Studio)?\s+\d+(?:\.\d+){1,2}", re.IGNORECASE
)

ManagedOBSProcess = subprocess.Popen[bytes] | psutil.Process


class OBSProcessManager:
    """OBS Studioプロセスのライフサイクル管理。

    責務:
    - プロセスの起動・終了
    - プロセス/ウィンドウの存在確認
    - プロセス優先度制御（Windows）
    """

    def __init__(self, executable_path: Path, logger: BoundLogger) -> None:
        """初期化。

        Args:
            executable_path: OBS実行ファイルのパス
            logger: ロガー
        """
        self._executable_path = executable_path
        self._logger = logger
        self._process: ManagedOBSProcess | None = None
        self._preserve_running_on_teardown = False
        self._lifecycle_lock = asyncio.Lock()

    def _has_managed_live_process(self) -> bool:
        return self._process is not None and self._is_managed_process_alive(
            self._process
        )

    async def _find_existing_obs_process(self) -> psutil.Process | None:
        file_name = self._executable_path.name.lower()

        def _impl() -> psutil.Process | None:
            matches: list[psutil.Process] = []
            for proc in psutil.process_iter(["name", "exe"]):
                try:
                    name_obj = proc.info.get("name")
                    if not (
                        isinstance(name_obj, str)
                        and name_obj.lower() == file_name
                    ):
                        continue
                    exe_obj = proc.info.get("exe")
                    if not isinstance(exe_obj, str) or not exe_obj:
                        continue
                    try:
                        if (
                            Path(exe_obj).resolve()
                            != self._executable_path.resolve()
                        ):
                            continue
                    except OSError:
                        continue
                    matches.append(proc)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            if len(matches) > 1:
                self._logger.warning(
                    "OBS 自動復旧対象を一意に特定できません",
                    matching_process_count=len(matches),
                )
                return None
            return matches[0] if matches else None

        return await asyncio.to_thread(_impl)

    def _is_managed_process_alive(self, process: ManagedOBSProcess) -> bool:
        if hasattr(process, "poll"):
            return cast(Any, process).poll() is None
        try:
            return (
                process.is_running()
                and process.status() != psutil.STATUS_ZOMBIE
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False

    async def _wait_managed_process(self, process: ManagedOBSProcess) -> None:
        try:
            await asyncio.to_thread(process.wait)
        except psutil.NoSuchProcess:
            return

    def _terminate_managed_process(self, process: ManagedOBSProcess) -> None:
        try:
            process.terminate()
        except psutil.NoSuchProcess:
            return

    async def is_running(self) -> bool:
        """OBSが実行中かどうかを確認。

        プロセスとウィンドウの両方が存在する場合のみTrueを返す。

        Returns:
            実行中ならTrue
        """
        file_name = self._executable_path.name.lower()

        async def exists_process_async() -> bool:
            """プロセスリストから検索。"""

            def _impl() -> bool:
                for proc in psutil.process_iter(["name"]):
                    try:
                        name_obj = proc.info.get("name")
                        if (
                            isinstance(name_obj, str)
                            and name_obj.lower() == file_name
                        ):
                            return True
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                return False

            return await asyncio.to_thread(_impl)

        async def exists_window_async() -> bool:
            """ウィンドウリストから検索。"""
            if win32gui is None:
                self._logger.warning("win32gui が利用できません")
                return False

            def _impl() -> tuple[bool, list[str]]:
                if win32gui is None:  # pragma: no cover - defensive
                    return False, []

                handles: list[int] = []
                all_titles: list[str] = []

                def enum_window(hwnd: int, _param: Optional[int]) -> bool:
                    if win32gui is None:  # pragma: no cover - defensive
                        return False
                    try:
                        if win32gui.IsWindowVisible(
                            hwnd
                        ) or self._is_obs_main_window(hwnd):
                            title = win32gui.GetWindowText(hwnd)
                            # デバッグ用：OBSを含むすべてのタイトルを記録
                            if "obs" in title.lower():
                                all_titles.append(title)

                            # "OBS" + バージョン番号（例: "OBS 30.2.1"）にマッチ
                            # バージョン番号が接頭辞として付くパターンを優先
                            if re.match(
                                r"^OBS\s+\d+(?:\.\d+){1,2}",
                                title,
                                re.IGNORECASE,
                            ):
                                handles.append(hwnd)
                    except Exception:  # pragma: no cover - defensive
                        return True
                    return True

                try:
                    win32gui.EnumWindows(enum_window, None)
                except Exception:  # pragma: no cover - defensive
                    return False, []
                return bool(handles), all_titles

            found, titles = await asyncio.to_thread(_impl)
            if not found and titles:
                # マッチしなかった場合、検出されたタイトルをログ出力
                self._logger.debug("OBS関連ウィンドウ検出", titles=titles)
            return found

        proc_ok, win_ok = await asyncio.gather(
            exists_process_async(), exists_window_async()
        )
        return proc_ok and win_ok

    async def launch(self) -> None:
        """OBSプロセスを起動。

        既に実行中の場合は何もしない。
        Windows環境では優先度「高」で起動。

        Raises:
            DeviceError: 起動失敗時
        """
        async with self._lifecycle_lock:
            await self._launch_locked()

    async def restart_for_recovery(self) -> bool:
        """管理中または設定パスと一意に一致する OBS を再起動する。"""
        async with self._lifecycle_lock:
            managed = self._has_managed_live_process()
            process = (
                self._process
                if managed
                else await self._find_existing_obs_process()
            )
            if process is None:
                self._logger.info(
                    "OBS 自動復旧を見送りました",
                    reason="matching_process_not_found",
                )
                return False

            preserve_running = (
                self._preserve_running_on_teardown or not managed
            )
            self._process = process
            await self._teardown_locked()
            if self._is_managed_process_alive(process):
                self._logger.error(
                    "OBS 自動復旧を中止しました",
                    reason="process_still_running",
                    pid=process.pid,
                )
                raise DeviceError(
                    "OBS の終了を確認できないため自動復旧を中止しました",
                    "OBS_RECOVERY_STOP_FAILED",
                )

            await self._launch_locked()
            self._preserve_running_on_teardown = preserve_running
            return True

    async def _launch_locked(self) -> None:
        """OBSプロセスを起動。呼び出し元で lifecycle lock を保持する。"""
        self._logger.info("OBS 起動要求")
        if await self.is_running():
            self._logger.info("OBS は既に実行中")
            return
        if self._has_managed_live_process():
            self._logger.info(
                "OBS は起動処理中またはメインウィンドウ待機中です",
                pid=self._process.pid if self._process is not None else None,
            )
            return

        try:
            # Windows環境では優先度「高」でプロセスを起動
            creation_flags = 0
            if win32process is not None:
                # HIGH_PRIORITY_CLASS = 0x00000080
                creation_flags = 0x00000080
                self._logger.info("OBS を優先度「高」で起動します")

            working_dir = self._resolve_working_dir()

            # 起動前チェック
            exe_exists = self._executable_path.exists()
            exe_is_file = self._executable_path.is_file()
            wd_exists = working_dir.exists()
            wd_is_dir = working_dir.is_dir()

            self._logger.info(
                "OBS 起動準備",
                executable=str(self._executable_path),
                exe_exists=exe_exists,
                exe_is_file=exe_is_file,
                working_dir=str(working_dir),
                wd_exists=wd_exists,
                wd_is_dir=wd_is_dir,
                creation_flags=creation_flags,
            )

            if not exe_exists or not exe_is_file:
                raise FileNotFoundError(
                    f"実行ファイルが見つかりません: {self._executable_path}"
                )
            if not wd_exists or not wd_is_dir:
                raise FileNotFoundError(
                    f"ワーキングディレクトリが見つかりません: {working_dir}"
                )

            args = [str(self._executable_path), "--minimize-to-tray"]

            def _launch_process() -> subprocess.Popen[bytes]:
                """別スレッドでプロセスを起動"""
                return subprocess.Popen(
                    args,
                    cwd=str(working_dir),
                    creationflags=creation_flags,
                )

            # 別スレッドで起動（イベントループの制限を回避）
            launched_process = await asyncio.to_thread(_launch_process)
            self._process = launched_process
            self._logger.info("OBS プロセス起動完了", pid=launched_process.pid)

            # プロセスがすぐに終了していないか確認
            await asyncio.sleep(0.5)
            returncode = launched_process.poll()
            if returncode is not None:
                # プロセスが既に終了している
                self._logger.error(
                    "OBS プロセスがすぐに終了しました",
                    returncode=returncode,
                )
                raise RuntimeError(
                    f"OBSプロセスが終了コード {returncode} で終了しました"
                )

        except Exception as exc:  # pragma: no cover - process launch failure
            self._logger.error(
                "OBS 起動失敗", error=str(exc), error_type=type(exc).__name__
            )
            import traceback

            self._logger.error(
                "スタックトレース", trace=traceback.format_exc()
            )
            raise DeviceError(
                "OBS 起動に失敗しました", "OBS_LAUNCH_FAILED", cause=exc
            ) from exc

        # プロセス立ち上げを待機（ウィンドウが表示されるまで）
        max_wait = 30
        self._logger.info("OBS ウィンドウ表示待機開始")
        for i in range(max_wait):
            is_running = await self.is_running()
            if is_running:
                self._logger.info("OBS 起動確認完了（プロセス＋ウィンドウ）")
                return
            if launched_process.poll() is None:
                self._handle_launch_dialogs(launched_process.pid)
            await asyncio.sleep(1)
            if i % 5 == 0:
                self._logger.debug(
                    "OBS 起動待機中", elapsed=i, seconds_remaining=max_wait - i
                )

        self._logger.error(
            "OBS 起動タイムアウト（ウィンドウが表示されませんでした）"
        )
        if self._has_managed_live_process() and self._process is not None:
            self._logger.warning(
                "OBS 起動タイムアウト後の残留プロセスを終了します",
                pid=self._process.pid,
            )
            self._terminate_managed_process(self._process)
            await self._wait_managed_process(self._process)
            self._process = None
        raise DeviceError(
            "OBS 起動がタイムアウトしました", "OBS_LAUNCH_TIMEOUT"
        )

    def _resolve_working_dir(self) -> Path:
        """OBS実行ファイルのあるディレクトリを返す。

        OBSはロケールファイルなどを正しく読み込むため、
        実行ファイルのあるディレクトリから起動する必要がある。

        Returns:
            実行ファイルの親ディレクトリ
        """
        return self._executable_path.parent

    def find_window_by_pid(self, pid: int) -> List[int]:
        """指定PIDのウィンドウハンドルを検索。

        Args:
            pid: プロセスID

        Returns:
            ウィンドウハンドルのリスト
        """
        if win32gui is None or win32process is None:
            self._logger.warning("win32gui が利用できません")
            return []

        result = []

        def callback(hwnd: int, _param: object) -> bool:
            if win32gui is None or win32process is None:
                return False
            if win32gui.IsWindowVisible(hwnd) or self._is_obs_main_window(
                hwnd
            ):
                _, found_pid = win32process.GetWindowThreadProcessId(hwnd)
                if found_pid == pid:
                    result.append(hwnd)
            return True

        win32gui.EnumWindows(callback, None)
        return result

    def _get_window_text(self, hwnd: int) -> str:
        if win32gui is None:
            return ""
        try:
            title = win32gui.GetWindowText(hwnd)
        except Exception:  # pragma: no cover - defensive
            return ""
        return title if isinstance(title, str) else ""

    def _is_obs_main_window(self, hwnd: int) -> bool:
        title = self._get_window_text(hwnd)
        return OBS_MAIN_WINDOW_TITLE.match(title) is not None

    def _find_button_by_labels(
        self, hwnd: int, labels: tuple[str, ...]
    ) -> int | None:
        if win32gui is None:
            return None

        candidates: list[int] = []

        def callback(child_hwnd: int, _param: object) -> bool:
            if win32gui is None:  # pragma: no cover - defensive
                return False
            try:
                class_name = win32gui.GetClassName(child_hwnd)
                text = win32gui.GetWindowText(child_hwnd).strip()
            except Exception:  # pragma: no cover - defensive
                return True
            if class_name == "Button" and text:
                normalized = text.replace("&", "").lower()
                if any(label in normalized for label in labels):
                    candidates.append(child_hwnd)
                    return False
            return True

        try:
            win32gui.EnumChildWindows(hwnd, callback, None)
        except Exception:  # pragma: no cover - defensive
            return None
        return candidates[0] if candidates else None

    def _find_affirmative_button(self, hwnd: int) -> int | None:
        return self._find_button_by_labels(
            hwnd,
            ("はい", "yes", "ok", "終了", "exit", "quit"),
        )

    def _press_enter_on_window(self, hwnd: int) -> bool:
        if win32api is None or win32con is None or win32gui is None:
            return False

        try:
            win32gui.SetForegroundWindow(hwnd)
            time.sleep(0.05)
            vk_return = getattr(win32con, "VK_RETURN", 0x0D)
            key_up = getattr(win32con, "KEYEVENTF_KEYUP", 0x0002)
            win32api.keybd_event(vk_return, 0, 0, 0)
            win32api.keybd_event(vk_return, 0, key_up, 0)
        except (
            Exception
        ) as exc:  # pragma: no cover - depends on foreground state
            self._logger.debug(
                "OBS ダイアログへの Enter 送信をスキップ",
                hwnd=hwnd,
                error=str(exc),
            )
            return False
        return True

    def _invoke_uia_button_by_labels(
        self,
        pid: int,
        labels: tuple[str, ...],
        *,
        window_title_tokens: tuple[str, ...] = (),
        window_class_names: tuple[str, ...] = (),
        exclude_obs_main_window: bool = False,
    ) -> tuple[str, str] | None:
        if win32com_client is None:
            return None

        try:
            uia = win32com_client.Dispatch("UIAutomationClient.CUIAutomation")
            root = uia.GetRootElement()
            process_condition = uia.CreatePropertyCondition(
                UIA_PROCESS_ID_PROPERTY_ID, pid
            )
            windows = root.FindAll(UIA_TREE_SCOPE_CHILDREN, process_condition)
            button_condition = uia.CreatePropertyCondition(
                UIA_CONTROL_TYPE_PROPERTY_ID, UIA_BUTTON_CONTROL_TYPE_ID
            )
            normalized_labels = tuple(label.lower() for label in labels)
            normalized_title_tokens = tuple(
                token.lower() for token in window_title_tokens
            )
            expected_classes = set(window_class_names)

            for window_index in range(windows.Length):
                window = windows.GetElement(window_index)
                window_name = str(window.CurrentName or "")
                window_class_name = str(window.CurrentClassName or "")
                normalized_window_name = window_name.lower()
                if exclude_obs_main_window and OBS_MAIN_WINDOW_TITLE.match(
                    window_name
                ):
                    continue
                if normalized_title_tokens or expected_classes:
                    title_matched = any(
                        token in normalized_window_name
                        for token in normalized_title_tokens
                    )
                    class_matched = window_class_name in expected_classes
                    if not title_matched and not class_matched:
                        continue

                buttons = window.FindAll(
                    UIA_TREE_SCOPE_DESCENDANTS, button_condition
                )
                for button_index in range(buttons.Length):
                    button = buttons.GetElement(button_index)
                    button_name = str(button.CurrentName or "")
                    normalized_button_name = button_name.replace(
                        "&", ""
                    ).lower()
                    if not any(
                        label in normalized_button_name
                        for label in normalized_labels
                    ):
                        continue
                    invoke_pattern = button.GetCurrentPattern(
                        UIA_INVOKE_PATTERN_ID
                    )
                    invoke_pattern.Invoke()
                    return window_name, button_name
        except Exception as exc:  # pragma: no cover - depends on Windows UIA
            self._logger.debug(
                "OBS UI Automation ボタン操作をスキップ",
                pid=pid,
                error=str(exc),
            )
            return None
        return None

    def _handle_launch_dialogs(self, pid: int) -> None:
        clicked = self._invoke_uia_button_by_labels(
            pid,
            ("通常", "normal", "run normally"),
            window_title_tokens=("クラッシュ", "crash"),
            window_class_names=("QMessageBox",),
        )
        if clicked is not None:
            window_name, button_name = clicked
            self._logger.warning(
                "OBS クラッシュ検出ダイアログを通常モードで続行",
                title=window_name,
                button=button_name,
            )
            return

        if win32api is None or win32con is None:
            return
        for hwnd in self.find_window_by_pid(pid):
            title = self._get_window_text(hwnd)
            if not any(
                token in title.lower() for token in ("クラッシュ", "crash")
            ):
                continue
            button_hwnd = self._find_button_by_labels(
                hwnd, ("通常", "normal", "run normally")
            )
            if button_hwnd is not None:
                bm_click = getattr(win32con, "BM_CLICK", 0x00F5)
                win32api.PostMessage(button_hwnd, bm_click, 0, 0)
                self._logger.warning(
                    "OBS クラッシュ検出ダイアログを通常モードで続行",
                    title=title,
                )
                return
            if self._press_enter_on_window(hwnd):
                self._logger.warning(
                    "OBS クラッシュ検出ダイアログを Enter で通常モード続行",
                    title=title,
                )
                return

    def _confirm_exit_dialog_if_present(
        self, pid: int, hwnds: list[int]
    ) -> bool:
        """OBS の終了確認ダイアログなら肯定ボタンを押す。"""
        clicked = self._invoke_uia_button_by_labels(
            pid,
            ("はい", "yes", "ok", "終了", "exit", "quit"),
            exclude_obs_main_window=True,
        )
        if clicked is not None:
            window_name, button_name = clicked
            self._logger.info(
                "OBS 終了確認ダイアログを承認",
                title=window_name,
                button=button_name,
            )
            return True

        if win32api is None or win32con is None:
            return False

        for hwnd in hwnds:
            if self._is_obs_main_window(hwnd):
                continue

            title = self._get_window_text(hwnd)
            button_hwnd = self._find_affirmative_button(hwnd)
            if button_hwnd is None:
                if self._press_enter_on_window(hwnd):
                    self._logger.info(
                        "OBS 終了確認ダイアログを Enter で承認",
                        title=title,
                    )
                    return True
                continue

            bm_click = getattr(win32con, "BM_CLICK", 0x00F5)
            win32api.PostMessage(button_hwnd, bm_click, 0, 0)
            self._logger.info("OBS 終了確認ダイアログを承認", title=title)
            return True
        return False

    async def teardown(self) -> None:
        """OBSプロセスを終了。

        Windows環境ではWM_CLOSEメッセージで正常終了を試み、
        タイムアウトした場合は強制終了。
        """
        async with self._lifecycle_lock:
            if (
                self._preserve_running_on_teardown
                and self._has_managed_live_process()
            ):
                self._logger.info(
                    "アプリ起動前から存在した OBS を実行したまま残します",
                    pid=self._process.pid
                    if self._process is not None
                    else None,
                )
                self._process = None
                return
            await self._teardown_locked()

    async def _teardown_locked(self) -> None:
        """OBSプロセスを終了。呼び出し元で lifecycle lock を保持する。"""
        self._logger.info("OBS 終了要求")

        running = await self.is_running()
        owned_live_process = self._has_managed_live_process()
        existing_process: psutil.Process | None = None
        if not owned_live_process:
            existing_process = await self._find_existing_obs_process()

        if not running and not owned_live_process and existing_process is None:
            self._logger.info("OBS は既に停止済み")
            self._process = None
            return
        if not running and owned_live_process:
            self._logger.warning(
                "OBS メインウィンドウは未検出ですが、管理中の OBS プロセスが残っています",
                pid=self._process.pid if self._process is not None else None,
            )
        if not running and existing_process is not None:
            self._logger.warning(
                "OBS メインウィンドウは未検出ですが、実行中の OBS プロセスが残っています",
                pid=existing_process.pid,
            )

        process: ManagedOBSProcess | None = self._process
        if process is None and existing_process is not None:
            self._logger.info(
                "OBS はアプリ起動前から実行中のため、プロセス終了をスキップします",
                pid=existing_process.pid,
            )
            return

        if process is None:
            self._logger.warning("OBS プロセスハンドルがありません")
            return

        try:
            # Windows環境ではWM_CLOSEで正常終了
            timeout_seconds = 10.0
            deadline = asyncio.get_running_loop().time() + timeout_seconds
            close_logged_windows: set[int] = set()

            self._logger.info("OBS 終了処理待機")
            while self._is_managed_process_alive(process):
                if win32api is not None and win32con is not None:
                    hwnds = self.find_window_by_pid(process.pid)
                    handled_dialog = self._confirm_exit_dialog_if_present(
                        process.pid, hwnds
                    )
                    main_hwnds = [
                        hwnd
                        for hwnd in hwnds
                        if self._is_obs_main_window(hwnd)
                    ]
                    if main_hwnds:
                        unlogged_hwnds = [
                            hwnd
                            for hwnd in main_hwnds
                            if hwnd not in close_logged_windows
                        ]
                        if unlogged_hwnds:
                            self._logger.info(
                                "OBS ウィンドウを閉じる",
                                window_count=len(unlogged_hwnds),
                                pid=process.pid,
                            )
                            close_logged_windows.update(unlogged_hwnds)
                        for hwnd in main_hwnds:
                            win32api.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
                    elif handled_dialog:
                        await asyncio.sleep(0.2)
                        continue

                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    break
                await asyncio.sleep(min(0.2, remaining))

            if self._is_managed_process_alive(process):
                self._logger.warning("OBS 強制終了")
                self._terminate_managed_process(process)
            await self._wait_managed_process(process)
            self._logger.info("OBS 終了処理完了")

        except Exception as exc:
            self._logger.error("OBS 終了失敗", error=str(exc))
        finally:
            self._process = None
