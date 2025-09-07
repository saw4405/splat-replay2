"""
Splat Replay GUI メインアプリケーション

tkinter ベースの GUI アプリケーションのエントリーポイント
"""

from splat_replay.gui.windows.main_window import MainWindow
from splat_replay.shared.logger import get_logger


class SplatReplayGUI:
    """GUI アプリケーションのエントリーポイント"""

    def __init__(self) -> None:
        self.logger = get_logger()
        self.logger.info("SplatReplayGUI が初期化されました")

    def run(self) -> None:
        """
        アプリケーションを開始

        GUI メインループとアプリ処理ループを起動する
        """
        try:
            main = MainWindow()
            main.run_loop()

        except Exception as e:
            self.logger.error(f"GUI アプリケーション実行中にエラーが発生: {e}")


if __name__ == "__main__":
    app = SplatReplayGUI()
    app.run()
