"""必須セットアップ条件の共有モデル。"""

from __future__ import annotations

from splat_replay.application.interfaces import RequiredSetupIssue


class RequiredSetupIncompleteError(Exception):
    """必須設定が不足した状態で完了を要求した。"""

    def __init__(self, issues: list[RequiredSetupIssue]) -> None:
        super().__init__("アプリの利用に必要な設定が不足しています。")
        self.issues = tuple(issues)
