"""配置先を分離した Windows 制御オブジェクトの実動作。"""

import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows 専用")


def test_only_same_installation_receives_command(tmp_path: Path) -> None:
    from splat_replay.infrastructure.adapters.system.desktop_instance import (
        DesktopInstance,
    )

    owner = DesktopInstance(tmp_path / "app.exe")
    client = DesktopInstance(tmp_path / "app.exe", client_only=True)
    other = DesktopInstance(tmp_path / "other.exe")
    try:
        assert owner.owner and other.owner and not client.owner
        assert client.status() == 3
        owner.state("ready", True)
        assert client.status() == 0
        assert client.send("update")
        assert owner.take("update")
        assert not owner.take("update")
        assert not other.take("update")
    finally:
        other.close()
        client.close()
        owner.close()
