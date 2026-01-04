"""OBS Studio制御アダプタ群。

責務分離:
- process_manager: プロセス起動・終了・監視
- websocket_client: WebSocket通信・再接続
- recorder_controller: 録画制御（VideoRecorderPort実装）
"""

from splat_replay.infrastructure.adapters.obs.process_manager import (
    OBSProcessManager,
)
from splat_replay.infrastructure.adapters.obs.recorder_controller import (
    OBSRecorderController,
)
from splat_replay.infrastructure.adapters.obs.websocket_client import (
    OBSWebSocketClient,
)

__all__ = [
    "OBSProcessManager",
    "OBSWebSocketClient",
    "OBSRecorderController",
]
