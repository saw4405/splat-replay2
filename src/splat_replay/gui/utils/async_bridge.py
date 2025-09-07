"""
非同期処理と GUI の橋渡し

tkinter の同期的な GUI と asyncio の非同期処理を統合するためのブリッジクラス
"""

import asyncio
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Callable, Coroutine, Optional, TypeVar

from splat_replay.shared.logger import get_logger

T = TypeVar("T")


class AsyncGUIError(Exception):
    """GUI 非同期ブリッジ関連の例外 (後方互換用)."""


class AsyncGUIBridge:
    """非同期処理と GUI の橋渡しクラス"""

    def __init__(self):
        """
        ブリッジを初期化

        Args:
            logger: ログ出力用のロガー
        """
        self.logger = get_logger()

        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.executor = ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="AsyncGUI"
        )
        self._loop_thread: Optional[threading.Thread] = None
        self._shutdown_event = threading.Event()

    def start_async_loop(self, loop_start_timeout: float = 5.0) -> None:
        """別スレッドで asyncio ループを開始"""
        if self._loop_thread is not None and self._loop_thread.is_alive():
            self.logger.warning("AsyncGUIBridge は既に開始されています")
            return

        def run_loop():
            """asyncio ループを実行する内部関数"""
            try:
                self.loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self.loop)
                self.logger.info("AsyncGUIBridge ループを開始")
                # None チェック（以降 monitor_shutdown で Optional 扱いを避ける）
                loop = self.loop
                assert loop is not None

                # シャットダウンイベントを監視するタスクを作成
                async def monitor_shutdown():
                    # シャットダウンシグナルを待機
                    while not self._shutdown_event.is_set():
                        await asyncio.sleep(0.1)

                    # 現在のタスク（自分自身）を除いてキャンセル
                    current = asyncio.current_task()
                    pending = [
                        t
                        for t in asyncio.all_tasks(loop)
                        if t is not current and not t.done()
                    ]
                    if pending:
                        self.logger.info(
                            f"残り {len(pending)} 個のタスクをキャンセル中"
                        )
                        for t in pending:
                            t.cancel()
                        await asyncio.gather(*pending, return_exceptions=True)

                    # 全タスクのキャンセル完了後にループ停止
                    loop.call_soon(loop.stop)

                # 監視タスクを開始
                self.loop.create_task(monitor_shutdown())

                # ループを実行
                self.loop.run_forever()

            except Exception as e:
                self.logger.error(f"AsyncGUIBridge でエラーが発生: {e}")
            finally:
                if self.loop and not self.loop.is_closed():
                    self.loop.close()
                self.logger.info("AsyncGUIBridge ループを終了")

        self._loop_thread = threading.Thread(target=run_loop, daemon=True)
        self._loop_thread.start()

        # ループが開始されるまで少し待機
        start_time = time.time()
        while (
            self.loop is None
            and (time.time() - start_time) < loop_start_timeout
        ):
            time.sleep(0.01)

        if self.loop is None:
            raise RuntimeError("AsyncGUIBridge の開始がタイムアウトしました")

    def run_async(
        self, coro: Coroutine[Any, Any, T], timeout: float = 30.0
    ) -> T:
        """
        非同期関数を GUI スレッドから実行（同期待機）

        Args:
            coro: 実行する非同期関数
            timeout: タイムアウト時間（秒）

        Returns:
            非同期関数の実行結果

        Raises:
            RuntimeError: ループが開始されていない場合
            TimeoutError: タイムアウトした場合
            Exception: 非同期関数内で発生した例外
        """
        if (
            self.loop is None
            or not self._loop_thread
            or not self._loop_thread.is_alive()
        ):
            raise RuntimeError("AsyncGUIBridge が開始されていません")

        try:
            future = asyncio.run_coroutine_threadsafe(coro, self.loop)
            return future.result(timeout=timeout)
        except asyncio.TimeoutError as e:
            self.logger.error(f"非同期処理がタイムアウト: {timeout}秒")
            raise TimeoutError(
                f"非同期処理が {timeout} 秒でタイムアウトしました"
            ) from e
        except Exception as e:
            self.logger.error(f"非同期処理でエラーが発生: {e}")
            raise

    def run_async_background(self, coro: Coroutine[Any, Any, T]) -> Future[T]:
        """
        非同期関数をバックグラウンドで実行（非同期）

        Args:
            coro: 実行する非同期関数

        Returns:
            Future オブジェクト

        Raises:
            RuntimeError: ループが開始されていない場合
        """
        if (
            self.loop is None
            or not self._loop_thread
            or not self._loop_thread.is_alive()
        ):
            raise RuntimeError("AsyncGUIBridge が開始されていません")

        try:
            future = asyncio.run_coroutine_threadsafe(coro, self.loop)

            # エラーハンドリング用のコールバックを追加
            def handle_exception(fut: Future[T]):
                try:
                    fut.result()  # 例外があれば発生させる
                except asyncio.CancelledError:
                    self.logger.info(
                        "バックグラウンド処理をキャンセルしました"
                    )
                except Exception as e:
                    self.logger.error(
                        f"バックグラウンド処理でエラーが発生: {e}"
                    )

            future.add_done_callback(handle_exception)
            return future

        except Exception as e:
            self.logger.error(f"バックグラウンド処理の開始でエラーが発生: {e}")
            raise

    def run_background(
        self, func: Callable[..., T], /, *args: Any, **kwargs: Any
    ) -> Future[T]:
        """
        同期関数をバックグラウンドで実行（非同期ループ配下のスレッドプール）

        Args:
            func: バックグラウンド実行する同期関数（ブロッキング可）

        Returns:
            concurrent.futures.Future[T]: 結果取得やキャンセルに使える Future

        Raises:
            RuntimeError: ループが開始されていない場合
            Exception: スケジュール時のその他エラー
        """
        coro = asyncio.to_thread(func, *args, **kwargs)
        return self.run_async_background(coro)

    def is_running(self) -> bool:
        """
        ブリッジが実行中かどうかを確認

        Returns:
            実行中の場合 True
        """
        return (
            self.loop is not None
            and self._loop_thread is not None
            and self._loop_thread.is_alive()
            and not self.loop.is_closed()
        )

    def shutdown(self) -> None:
        """
        ブリッジを安全にシャットダウン
        """
        self.logger.info("AsyncGUIBridge をシャットダウン中")

        # シャットダウンイベントを設定
        self._shutdown_event.set()

        # ループを停止
        if self.loop is not None and not self.loop.is_closed():
            # 直接 stop() せず monitor_shutdown に停止させることで
            # タスクキャンセルが完了する前にループが閉じられる競合を防ぐ
            self.loop.call_soon_threadsafe(lambda: None)

        # スレッドの終了を待機
        if self._loop_thread is not None and self._loop_thread.is_alive():
            self._loop_thread.join(timeout=5.0)
            if self._loop_thread.is_alive():
                self.logger.warning(
                    "AsyncGUIBridge スレッドの終了がタイムアウト"
                )

        # エグゼキューターをシャットダウン
        self.executor.shutdown(wait=True)

        self.logger.info("AsyncGUIBridge のシャットダウンが完了")

    def __enter__(self):
        """コンテキストマネージャーのエントリー"""
        self.start_async_loop()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """コンテキストマネージャーの終了"""
        self.shutdown()


__all__ = ["AsyncGUIBridge", "AsyncGUIError"]
