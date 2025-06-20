"""CLI エントリーポイント。"""

from __future__ import annotations

from splat_replay.cli import app


def main() -> None:
    """コマンドラインから実行するための関数。"""

    app()


if __name__ == "__main__":
    main()
