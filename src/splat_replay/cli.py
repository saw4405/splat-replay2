"""コマンドラインインターフェース定義。"""

from __future__ import annotations

import typer

app = typer.Typer(help="Splat Replay ツール群")


@app.callback()
def main() -> None:
    """Splat Replay CLI のエントリーポイント。"""


if __name__ == "__main__":
    app()
