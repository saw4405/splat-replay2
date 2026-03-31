# E2E YouTube no-op upload Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Playwright E2E 実行時だけ `UploadPort` を no-op 実装へ差し替え、実際の YouTube アップロードを防ぎつつ既存の成功系 E2E フローを維持する。

**Architecture:** backend の依存注入で `SPLAT_REPLAY_E2E_NOOP_UPLOAD=1` を検出した場合のみ `UploadPort` を `NoOpUploadPort` に差し替える。`AutoUploader` やユースケースは変更せず、frontend の Playwright 設定から backend に専用環境変数を渡す。

**Tech Stack:** Python (`pytest`, `punq`, `structlog`), TypeScript (`Vitest`, Playwright), FastAPI backend, Svelte frontend

---

### Task 1: NoOpUploadPort を TDD で追加する

**Files:**
- Create: `backend/tests/test_noop_upload_port.py`
- Create: `backend/src/splat_replay/infrastructure/adapters/upload/noop_upload_port.py`
- Modify: `backend/src/splat_replay/infrastructure/adapters/upload/__init__.py`
- Test: `backend/tests/test_noop_upload_port.py`

- [ ] **Step 1: 失敗するテストを書く**

```python
from pathlib import Path
from unittest.mock import MagicMock

from splat_replay.application.interfaces import Caption
from splat_replay.infrastructure.adapters.upload.noop_upload_port import (
    NoOpUploadPort,
)


def test_upload_logs_and_returns_without_external_calls() -> None:
    logger = MagicMock()
    uploader = NoOpUploadPort(logger=logger)

    result = uploader.upload(
        path=Path("/tmp/test-video.mp4"),
        title="E2E title",
        description="E2E description",
        tags=["e2e", "upload"],
        privacy_status="unlisted",
        thumb=Path("/tmp/thumb.png"),
        caption=Caption(
            subtitle=Path("/tmp/subtitle.srt"),
            caption_name="E2E subtitle",
            language="ja",
        ),
        playlist_id="playlist-123",
    )

    assert result is None
    logger.info.assert_called_once_with(
        "E2E no-op upload を実行しました",
        path="/tmp/test-video.mp4",
        title="E2E title",
        privacy_status="unlisted",
        has_thumbnail=True,
        has_caption=True,
        playlist_id="playlist-123",
    )
```

- [ ] **Step 2: テストが期待どおり失敗することを確認する**

Run: `uv run pytest backend/tests/test_noop_upload_port.py -q`

Expected: `ModuleNotFoundError` または `ImportError` で `noop_upload_port.py` が未作成のため失敗する。

- [ ] **Step 3: 最小実装を書く**

```python
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from structlog.stdlib import BoundLogger

from splat_replay.application.interfaces import (
    Caption,
    PrivacyStatus,
    UploadPort,
)


class NoOpUploadPort(UploadPort):
    """E2E 実行時に外部アップロードを抑止する UploadPort 実装。"""

    def __init__(self, logger: BoundLogger) -> None:
        self.logger = logger

    def upload(
        self,
        path: Path,
        title: str,
        description: str,
        tags: List[str] = [],
        privacy_status: PrivacyStatus = "private",
        thumb: Optional[Path] = None,
        caption: Optional[Caption] = None,
        playlist_id: str = "",
    ) -> None:
        _ = description, tags
        self.logger.info(
            "E2E no-op upload を実行しました",
            path=str(path),
            title=title,
            privacy_status=privacy_status,
            has_thumbnail=thumb is not None,
            has_caption=caption is not None,
            playlist_id=playlist_id,
        )
```

```python
from __future__ import annotations

from splat_replay.infrastructure.adapters.upload.noop_upload_port import (
    NoOpUploadPort,
)
from splat_replay.infrastructure.adapters.upload.youtube_client import (
    YouTubeClient,
)

__all__ = [
    "NoOpUploadPort",
    "YouTubeClient",
]
```

- [ ] **Step 4: テストが通ることを確認する**

Run: `uv run pytest backend/tests/test_noop_upload_port.py -q`

Expected: `1 passed`

- [ ] **Step 5: コミットする**

```bash
git add backend/tests/test_noop_upload_port.py backend/src/splat_replay/infrastructure/adapters/upload/noop_upload_port.py backend/src/splat_replay/infrastructure/adapters/upload/__init__.py
git commit -m "feat: add noop upload port for e2e"
```

### Task 2: DI で UploadPort を切り替える

**Files:**
- Create: `backend/tests/test_upload_port_registration.py`
- Modify: `backend/src/splat_replay/infrastructure/di/adapters.py`
- Test: `backend/tests/test_upload_port_registration.py`

- [ ] **Step 1: 失敗する DI テストを書く**

```python
from unittest.mock import MagicMock

import punq
from structlog.stdlib import BoundLogger

from splat_replay.application.interfaces import (
    AuthenticatedClientPort,
    EnvironmentPort,
    UploadPort,
)
from splat_replay.infrastructure.adapters.upload import (
    NoOpUploadPort,
    YouTubeClient,
)
from splat_replay.infrastructure.di.adapters import register_adapters


class _StubEnvironment:
    def __init__(self, values: dict[str, str]) -> None:
        self._values = values

    def get(self, name: str, default: str | None = None) -> str | None:
        return self._values.get(name, default)

    def set(self, name: str, value: str) -> None:
        self._values[name] = value


def _build_container(environment: _StubEnvironment) -> punq.Container:
    container = punq.Container()
    container.register(BoundLogger, instance=MagicMock())
    container.register(EnvironmentPort, instance=environment)
    register_adapters(container)
    return container


def test_register_adapters_uses_noop_upload_port_when_flag_enabled() -> None:
    container = _build_container(
        _StubEnvironment({"SPLAT_REPLAY_E2E_NOOP_UPLOAD": "1"})
    )

    uploader = container.resolve(UploadPort)

    assert isinstance(uploader, NoOpUploadPort)


def test_register_adapters_keeps_youtube_client_when_flag_disabled() -> None:
    container = _build_container(_StubEnvironment({}))

    uploader = container.resolve(UploadPort)

    assert isinstance(uploader, YouTubeClient)


def test_authenticated_client_port_still_uses_youtube_client() -> None:
    container = _build_container(
        _StubEnvironment({"SPLAT_REPLAY_E2E_NOOP_UPLOAD": "1"})
    )

    client = container.resolve(AuthenticatedClientPort)

    assert isinstance(client, YouTubeClient)
```

- [ ] **Step 2: テストが期待どおり失敗することを確認する**

Run: `uv run pytest backend/tests/test_upload_port_registration.py -q`

Expected: `UploadPort` がまだ `YouTubeClient` を返すため、`NoOpUploadPort` を期待するテストが失敗する。

- [ ] **Step 3: 最小実装を書く**

```python
from splat_replay.application.interfaces import (
    AuthenticatedClientPort,
    BattleHistoryRepositoryPort,
    CaptureDeviceEnumeratorPort,
    CaptureDevicePort,
    CapturePort,
    ClockPort,
    DomainEventPublisher,
    EnvironmentPort,
    EventBusPort,
    EventPublisher,
    FramePublisher,
    ImageSelector,
    MicrophoneEnumeratorPort,
    PowerPort,
    ReplayBootstrapResolverPort,
    RecorderWithTranscriptionPort,
    SettingsRepositoryPort,
    SpeechTranscriberPort,
    SubtitleEditorPort,
    SystemCommandPort,
    WeaponRecognitionPort,
    TextToSpeechPort,
    UploadPort,
    VideoAssetRepositoryPort,
    VideoEditorPort,
    VideoRecorderPort,
)
```

```python
from splat_replay.infrastructure import (
    AdaptiveCapture,
    AdaptiveCaptureDeviceChecker,
    AdaptiveVideoRecorder,
    BattleMedalRecognizerAdapter,
    CaptureDeviceEnumerator,
    EventBusPortAdapter,
    EventPublisherAdapter,
    FFmpegProcessor,
    FileBattleHistoryRepository,
    FileVideoAssetRepository,
    FramePublisherAdapter,
    GoogleTextToSpeech,
    GuiRuntimePortAdapter,
    ImageDrawer,
    IntegratedSpeechRecognizer,
    MatcherRegistry,
    MicrophoneEnumerator,
    RecorderWithTranscription,
    SetupStateFileAdapter,
    SpeechTranscriber,
    SubtitleEditor,
    SystemCommandAdapter,
    SystemPower,
    TesseractOCR,
    TomlSettingsRepository,
    WeaponRecognitionAdapter,
)
from splat_replay.infrastructure.adapters.upload.noop_upload_port import (
    NoOpUploadPort,
)
from splat_replay.infrastructure.adapters.upload.youtube_client import (
    YouTubeClient,
)
```

```python
def _is_e2e_noop_upload_enabled(environment: EnvironmentPort) -> bool:
    return environment.get("SPLAT_REPLAY_E2E_NOOP_UPLOAD", "0") == "1"
```

```python
    container.register(PowerPort, SystemPower)
    container.register(OCRPort, TesseractOCR)
    container.register(BattleMedalRecognizerPort, BattleMedalRecognizerAdapter)

    environment = container.resolve(EnvironmentPort)
    if _is_e2e_noop_upload_enabled(environment):
        container.register(UploadPort, NoOpUploadPort)
    else:
        container.register(UploadPort, YouTubeClient)

    container.register(AuthenticatedClientPort, YouTubeClient)
    container.register(SystemCommandPort, SystemCommandAdapter)
```

- [ ] **Step 4: テストが通ることを確認する**

Run: `uv run pytest backend/tests/test_upload_port_registration.py -q`

Expected: `3 passed`

- [ ] **Step 5: コミットする**

```bash
git add backend/tests/test_upload_port_registration.py backend/src/splat_replay/infrastructure/di/adapters.py
git commit -m "feat: switch e2e upload port in di"
```

### Task 3: Playwright backend 起動に no-op flag を配線して検証する

**Files:**
- Create: `frontend/src/playwright-config.test.ts`
- Modify: `frontend/playwright.config.ts`
- Test: `frontend/src/playwright-config.test.ts`
- Verify: `backend/tests/test_noop_upload_port.py`
- Verify: `backend/tests/test_upload_port_registration.py`

- [ ] **Step 1: 失敗する frontend テストを書く**

```typescript
import { describe, expect, it } from 'vitest';

import config from '../playwright.config';

describe('playwright config', () => {
  it('passes noop upload flag to backend webServer env', () => {
    const servers = Array.isArray(config.webServer)
      ? config.webServer
      : [config.webServer];
    const backendServer = servers[0];

    expect(backendServer?.env?.SPLAT_REPLAY_E2E_NOOP_UPLOAD).toBe('1');
  });
});
```

- [ ] **Step 2: テストが期待どおり失敗することを確認する**

Run: `cd frontend && npm run test -- src/playwright-config.test.ts`

Expected: `SPLAT_REPLAY_E2E_NOOP_UPLOAD` が `undefined` のため失敗する。

- [ ] **Step 3: 最小実装を書く**

```typescript
    {
      command:
        'uv run python -m uvicorn splat_replay.bootstrap.web_app:app --factory --host 127.0.0.1 --port 8000',
      cwd: backendDir,
      env: {
        ...process.env,
        SPLAT_REPLAY_SETTINGS_FILE: e2eEnvironment.settingsFile,
        SPLAT_REPLAY_E2E_NOOP_UPLOAD: '1',
      },
      timeout: 180_000,
      url: 'http://127.0.0.1:8000/api/settings',
      reuseExistingServer: !process.env.CI,
    },
```

- [ ] **Step 4: frontend テストが通ることを確認する**

Run: `cd frontend && npm run test -- src/playwright-config.test.ts`

Expected: `1 passed`

- [ ] **Step 5: 変更全体を検証する**

Run: `uv run pytest backend/tests/test_noop_upload_port.py backend/tests/test_upload_port_registration.py -q`

Expected: `4 passed`

Run: `cd frontend && npm run test -- src/playwright-config.test.ts`

Expected: `1 passed`

Run: `cd frontend && npm run test:e2e -- tests/e2e/edit-upload-workflow.spec.ts`

Expected: 既存の編集アップロード E2E が通り、backend ログに `E2E no-op upload を実行しました` が残る。YouTube 実アップロードは発生しない。

- [ ] **Step 6: コミットする**

```bash
git add frontend/playwright.config.ts frontend/src/playwright-config.test.ts
git commit -m "test: disable real youtube uploads in e2e"
```
