"""Infrastructure runtime layer - Application runtime management.

Phase 2 リファクタリングにより messaging/ から分離。
アプリケーション全体のライフサイクル管理に特化。
"""

from splat_replay.infrastructure.runtime.app_runtime import AppRuntime

__all__ = ["AppRuntime"]
