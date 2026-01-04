"""TOMLファイルのI/O操作。

Clean Architectureの責務分離原則に基づき、
ファイル読み書きのみを担当し、ビジネスロジックを含まない。
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Dict

import tomli_w
from structlog.stdlib import BoundLogger

from splat_replay.domain.repositories import RepositoryError
from splat_replay.infrastructure.logging import get_logger


class SetupStateFileIO:
    """TOMLファイルの読み書きを担当。

    シリアライゼーションやビジネスロジックは含まず、
    純粋なファイルI/O操作のみを行う。
    """

    def __init__(
        self, file_path: Path, logger: BoundLogger | None = None
    ) -> None:
        """ファイルI/Oオブジェクトを初期化する。

        Args:
            file_path: TOMLファイルのパス
            logger: ログ出力用。Noneの場合はデフォルトロガーを使用
        """
        self._file_path = file_path
        self._logger = logger or get_logger()

    def exists(self) -> bool:
        """ファイルが存在するかチェックする。

        Returns:
            存在する場合True
        """
        return self._file_path.exists()

    def read(self) -> Dict[str, object]:
        """TOMLファイルを読み込む。

        Returns:
            TOML辞書形式のデータ

        Raises:
            RepositoryError: 読み込みに失敗した場合
        """
        try:
            with self._file_path.open("rb") as f:
                data = tomllib.load(f)

            self._logger.debug(
                "TOML file read successfully",
                file_path=str(self._file_path),
            )
            return data

        except Exception as e:
            error_msg = f"Failed to read TOML file from {self._file_path}: {e}"
            self._logger.error(error_msg, exc_info=True)
            raise RepositoryError(error_msg, cause=e)

    def write(self, data: Dict[str, object]) -> None:
        """TOMLファイルに書き込む。

        Args:
            data: TOML辞書形式のデータ

        Raises:
            RepositoryError: 書き込みに失敗した場合
        """
        try:
            # ディレクトリが存在しない場合は作成
            self._file_path.parent.mkdir(parents=True, exist_ok=True)

            # TOML文字列に変換して書き込み
            toml_text = tomli_w.dumps(data)
            self._file_path.write_text(toml_text, encoding="utf-8")

            self._logger.debug(
                "TOML file written successfully",
                file_path=str(self._file_path),
            )

        except Exception as e:
            error_msg = f"Failed to write TOML file to {self._file_path}: {e}"
            self._logger.error(error_msg, exc_info=True)
            raise RepositoryError(error_msg, cause=e)
