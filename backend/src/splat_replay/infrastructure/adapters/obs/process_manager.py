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
from pathlib import Path
from types import ModuleType
from typing import List, Optional

import psutil
from structlog.stdlib import BoundLogger

from splat_replay.domain.exceptions import DeviceError

# Windows APIのオプショナルインポート
win32api: ModuleType | None = None
win32con: ModuleType | None = None
win32gui: ModuleType | None = None
win32process: ModuleType | None = None

try:
    import win32api as _win32api
    import win32con as _win32con
    import win32gui as _win32gui
    import win32process as _win32process

    win32api = _win32api
    win32con = _win32con
    win32gui = _win32gui
    win32process = _win32process
except Exception:
    pass


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
        self._process: subprocess.Popen[bytes] | None = None

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
                        if win32gui.IsWindowVisible(hwnd):
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
        self._logger.info("OBS 起動要求")
        if await self.is_running():
            self._logger.info("OBS は既に実行中")
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

            # OBS起動引数: クラッシュダイアログをスキップ
            args = [str(self._executable_path), "--disable-shutdown-check"]

            def _launch_process() -> subprocess.Popen[bytes]:
                """別スレッドでプロセスを起動"""
                return subprocess.Popen(
                    args,
                    cwd=str(working_dir),
                    creationflags=creation_flags,
                )

            # 別スレッドで起動（イベントループの制限を回避）
            self._process = await asyncio.to_thread(_launch_process)
            self._logger.info("OBS プロセス起動完了", pid=self._process.pid)

            # プロセスがすぐに終了していないか確認
            await asyncio.sleep(0.5)
            returncode = self._process.poll()
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
            await asyncio.sleep(1)
            if i % 5 == 0:
                self._logger.debug(
                    "OBS 起動待機中", elapsed=i, seconds_remaining=max_wait - i
                )

        self._logger.error(
            "OBS 起動タイムアウト（ウィンドウが表示されませんでした）"
        )
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
            if win32gui.IsWindowVisible(hwnd):
                _, found_pid = win32process.GetWindowThreadProcessId(hwnd)
                if found_pid == pid:
                    result.append(hwnd)
            return True

        win32gui.EnumWindows(callback, None)
        return result

    async def teardown(self) -> None:
        """OBSプロセスを終了。

        Windows環境ではWM_CLOSEメッセージで正常終了を試み、
        タイムアウトした場合は強制終了。
        """
        self._logger.info("OBS 終了要求")

        if not await self.is_running():
            self._logger.info("OBS は既に停止済み")
            self._process = None
            return

        if self._process is None:
            self._logger.warning(
                "OBS プロセスハンドルがありません（外部起動の可能性）"
            )
            return

        try:
            # Windows環境ではWM_CLOSEで正常終了
            if win32api is not None and win32con is not None:
                hwnds = self.find_window_by_pid(self._process.pid)
                self._logger.info(
                    "OBS ウィンドウを閉じる", window_count=len(hwnds)
                )
                for hwnd in hwnds:
                    win32api.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)

            # 最大10秒待機して終了しなければ強制終了
            try:
                self._logger.info("OBS 終了処理待機")
                # subprocess.Popen.wait() を別スレッドで実行
                await asyncio.wait_for(
                    asyncio.to_thread(self._process.wait), timeout=10.0
                )
                self._logger.info("OBS 終了処理完了")
            except asyncio.TimeoutError:
                self._logger.warning("OBS 強制終了")
                self._process.terminate()
                await asyncio.to_thread(self._process.wait)

        except Exception as exc:
            self._logger.error("OBS 終了失敗", error=str(exc))
        finally:
            self._process = None
