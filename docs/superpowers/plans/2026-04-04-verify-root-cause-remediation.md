# Verify Root Cause Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `task.exe verify` 実行時に既知扱いされていた `DeprecationWarning` と frontend の `npm audit` 脆弱性表示について、根本原因を減らし、再発しにくい状態へ寄せる。

**Architecture:** backend は `speech_recognition` 系の import が bootstrap 時に不要に早期評価されているため、`infrastructure` / `adapters` の公開 API を lazy import 化して bootstrap import 経路から音声依存を切り離す。frontend はまず non-breaking な依存更新で audit を減らし、それでも残る `vite` / `svelte` / `@sveltejs/vite-plugin-svelte` 起因の脆弱性については major 更新を適用し、既存の型検査・Svelte 検査・unit test で回帰を確認する。

**Tech Stack:** Python 3.13, pytest, punq, Svelte, Vite, Vitest, npm

---

### Task 1: backend bootstrap import での DeprecationWarning を再現する回帰テストを追加する

**Files:**
- Create: `backend/tests/test_bootstrap_imports.py`
- Verify: `backend/src/splat_replay/bootstrap/web_app.py`
- Verify: `backend/src/splat_replay/infrastructure/__init__.py`
- Verify: `backend/src/splat_replay/infrastructure/adapters/__init__.py`

- [ ] **Step 1: 失敗する回帰テストを書く**

```python
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_import_web_app_with_deprecation_as_error_succeeds() -> None:
    backend_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(backend_root / "src")
    result = subprocess.run(
        [
            sys.executable,
            "-W",
            "error::DeprecationWarning",
            "-c",
            "from splat_replay.bootstrap.web_app import create_app; assert create_app",
        ],
        cwd=backend_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
```

- [ ] **Step 2: テストを実行して正しく失敗することを確認する**

Run: `uv run pytest -q backend/tests/test_bootstrap_imports.py`
Expected: `speech_recognition -> aifc` 由来の `DeprecationWarning` で FAIL

- [ ] **Step 3: lazy import で bootstrap import 経路を最小化する**

```python
# backend/src/splat_replay/infrastructure/__init__.py
from __future__ import annotations

from importlib import import_module
from typing import Any

from . import filesystem, logging

__all__ = [
    "filesystem",
    "logging",
    "MatcherRegistry",
    "AdaptiveCapture",
    "AdaptiveCaptureDeviceChecker",
    "AdaptiveVideoRecorder",
    "CaptureDeviceChecker",
    "CaptureDeviceEnumerator",
    "Capture",
    "NDICapture",
    "OBSRecorderController",
    "RecorderWithTranscription",
    "FFmpegProcessor",
    "YouTubeClient",
    "EventPublisherAdapter",
    "EventBusPortAdapter",
    "FramePublisherAdapter",
    "GuiRuntimePortAdapter",
    "SystemPower",
    "TesseractOCR",
    "SubtitleEditor",
    "ImageDrawer",
    "IntegratedSpeechRecognizer",
    "MicrophoneEnumerator",
    "SpeechTranscriber",
    "GoogleTextToSpeech",
    "BattleMedalRecognizerAdapter",
    "FileBattleHistoryRepository",
    "FileVideoAssetRepository",
    "SetupStateFileAdapter",
    "SystemCommandAdapter",
    "StructlogLoggerAdapter",
    "TomlConfigAdapter",
    "TomlSettingsRepository",
    "FileSystemPathsAdapter",
    "LocalFileSystemAdapter",
    "ProcessEnvironmentAdapter",
    "ReplayRecorderController",
    "VideoFileCapture",
    "WeaponRecognitionAdapter",
]

_LAZY_EXPORTS = {
    "AdaptiveCapture": (".adapters.capture.adaptive_capture", "AdaptiveCapture"),
    "AdaptiveCaptureDeviceChecker": (
        ".adapters.capture.adaptive_capture_device_checker",
        "AdaptiveCaptureDeviceChecker",
    ),
    "AdaptiveVideoRecorder": (
        ".adapters.video.adaptive_video_recorder",
        "AdaptiveVideoRecorder",
    ),
    "BattleMedalRecognizerAdapter": (
        ".adapters.medal_detection",
        "BattleMedalRecognizerAdapter",
    ),
    "Capture": (".adapters.capture.capture", "Capture"),
    "CaptureDeviceChecker": (
        ".adapters.capture.capture_device_checker",
        "CaptureDeviceChecker",
    ),
    "CaptureDeviceEnumerator": (
        ".adapters.capture.capture_device_checker",
        "CaptureDeviceEnumerator",
    ),
    "EventBusPortAdapter": (
        ".adapters.messaging.event_bus_adapter",
        "EventBusPortAdapter",
    ),
    "EventPublisherAdapter": (
        ".adapters.messaging.event_publisher_adapter",
        "EventPublisherAdapter",
    ),
    "FFmpegProcessor": (".adapters.video.ffmpeg_processor", "FFmpegProcessor"),
    "FileBattleHistoryRepository": (
        ".repositories.file_battle_history_repository",
        "FileBattleHistoryRepository",
    ),
    "FileSystemPathsAdapter": (
        ".adapters.system.cross_cutting",
        "FileSystemPathsAdapter",
    ),
    "FileVideoAssetRepository": (
        ".repositories.file_video_asset_repository",
        "FileVideoAssetRepository",
    ),
    "FramePublisherAdapter": (
        ".adapters.messaging.frame_publisher_adapter",
        "FramePublisherAdapter",
    ),
    "GoogleTextToSpeech": (
        ".adapters.audio.google_text_to_speech",
        "GoogleTextToSpeech",
    ),
    "GuiRuntimePortAdapter": (
        ".adapters.system.gui_runtime_port_adapter",
        "GuiRuntimePortAdapter",
    ),
    "ImageDrawer": (".adapters.image.image_drawer", "ImageDrawer"),
    "IntegratedSpeechRecognizer": (
        ".adapters.audio.integrated_speech_recognition",
        "IntegratedSpeechRecognizer",
    ),
    "LocalFileSystemAdapter": (
        ".adapters.system.cross_cutting",
        "LocalFileSystemAdapter",
    ),
    "MatcherRegistry": (".matchers", "MatcherRegistry"),
    "MicrophoneEnumerator": (
        ".adapters.audio.microphone_enumerator",
        "MicrophoneEnumerator",
    ),
    "NDICapture": (".adapters.capture.ndi_capture", "NDICapture"),
    "OBSRecorderController": (
        ".adapters.obs.recorder_controller",
        "OBSRecorderController",
    ),
    "ProcessEnvironmentAdapter": (
        ".adapters.system.cross_cutting",
        "ProcessEnvironmentAdapter",
    ),
    "RecorderWithTranscription": (
        ".adapters.video.recorder_with_transcription",
        "RecorderWithTranscription",
    ),
    "ReplayRecorderController": (
        ".adapters.video.replay_recorder_controller",
        "ReplayRecorderController",
    ),
    "SetupStateFileAdapter": (
        ".adapters.storage.setup_state_file_adapter",
        "SetupStateFileAdapter",
    ),
    "SpeechTranscriber": (
        ".adapters.audio.speech_transcriber",
        "SpeechTranscriber",
    ),
    "StructlogLoggerAdapter": (
        ".adapters.system.cross_cutting",
        "StructlogLoggerAdapter",
    ),
    "SubtitleEditor": (".adapters.text.subtitle_editor", "SubtitleEditor"),
    "SystemCommandAdapter": (
        ".adapters.system.system_command_adapter",
        "SystemCommandAdapter",
    ),
    "SystemPower": (".adapters.system.system_power", "SystemPower"),
    "TesseractOCR": (".adapters.text.tesseract_ocr", "TesseractOCR"),
    "TomlConfigAdapter": (
        ".adapters.system.cross_cutting",
        "TomlConfigAdapter",
    ),
    "TomlSettingsRepository": (
        ".adapters.storage.settings_repository",
        "TomlSettingsRepository",
    ),
    "VideoFileCapture": (
        ".adapters.capture.video_file_capture",
        "VideoFileCapture",
    ),
    "WeaponRecognitionAdapter": (
        ".adapters.weapon_detection",
        "WeaponRecognitionAdapter",
    ),
    "YouTubeClient": (".adapters.upload.youtube_client", "YouTubeClient"),
}


def __getattr__(name: str) -> Any:
    module_name, attr_name = _LAZY_EXPORTS[name]
    value = getattr(import_module(module_name, __name__), attr_name)
    globals()[name] = value
    return value
```

- [ ] **Step 4: `adapters` パッケージも同様に lazy import 化する**

```python
# backend/src/splat_replay/infrastructure/adapters/__init__.py
from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "AdaptiveCapture",
    "AdaptiveCaptureDeviceChecker",
    "AdaptiveVideoRecorder",
    "CaptureDeviceChecker",
    "CaptureDeviceEnumerator",
    "NDICapture",
    "Capture",
    "OBSRecorderController",
    "RecorderWithTranscription",
    "FFmpegProcessor",
    "YouTubeClient",
    "SystemPower",
    "TesseractOCR",
    "ImageEditor",
    "SubtitleEditor",
    "ImageDrawer",
    "IntegratedSpeechRecognizer",
    "MicrophoneEnumerator",
    "SpeechTranscriber",
    "GoogleTextToSpeech",
    "BattleMedalRecognizerAdapter",
    "EventPublisherAdapter",
    "EventBusPortAdapter",
    "FramePublisherAdapter",
    "GuiRuntimePortAdapter",
    "SetupStateFileAdapter",
    "SystemCommandAdapter",
    "StructlogLoggerAdapter",
    "TomlConfigAdapter",
    "FileSystemPathsAdapter",
    "LocalFileSystemAdapter",
    "ProcessEnvironmentAdapter",
    "TomlSettingsRepository",
    "WeaponRecognitionAdapter",
    "VideoFileCapture",
    "ReplayRecorderController",
]

_LAZY_EXPORTS = {
    "AdaptiveCapture": (".capture.adaptive_capture", "AdaptiveCapture"),
    "AdaptiveCaptureDeviceChecker": (
        ".capture.adaptive_capture_device_checker",
        "AdaptiveCaptureDeviceChecker",
    ),
    "AdaptiveVideoRecorder": (
        ".video.adaptive_video_recorder",
        "AdaptiveVideoRecorder",
    ),
    "BattleMedalRecognizerAdapter": (
        ".medal_detection",
        "BattleMedalRecognizerAdapter",
    ),
    "Capture": (".capture.capture", "Capture"),
    "CaptureDeviceChecker": (
        ".capture.capture_device_checker",
        "CaptureDeviceChecker",
    ),
    "CaptureDeviceEnumerator": (
        ".capture.capture_device_checker",
        "CaptureDeviceEnumerator",
    ),
    "EventBusPortAdapter": (
        ".messaging.event_bus_adapter",
        "EventBusPortAdapter",
    ),
    "EventPublisherAdapter": (
        ".messaging.event_publisher_adapter",
        "EventPublisherAdapter",
    ),
    "FFmpegProcessor": (".video.ffmpeg_processor", "FFmpegProcessor"),
    "FileSystemPathsAdapter": (
        ".system.cross_cutting",
        "FileSystemPathsAdapter",
    ),
    "FramePublisherAdapter": (
        ".messaging.frame_publisher_adapter",
        "FramePublisherAdapter",
    ),
    "GoogleTextToSpeech": (
        ".audio.google_text_to_speech",
        "GoogleTextToSpeech",
    ),
    "GuiRuntimePortAdapter": (
        ".system.gui_runtime_port_adapter",
        "GuiRuntimePortAdapter",
    ),
    "ImageDrawer": (".image.image_drawer", "ImageDrawer"),
    "ImageEditor": (".image.image_editor", "ImageEditor"),
    "IntegratedSpeechRecognizer": (
        ".audio.integrated_speech_recognition",
        "IntegratedSpeechRecognizer",
    ),
    "LocalFileSystemAdapter": (
        ".system.cross_cutting",
        "LocalFileSystemAdapter",
    ),
    "MicrophoneEnumerator": (
        ".audio.microphone_enumerator",
        "MicrophoneEnumerator",
    ),
    "NDICapture": (".capture.ndi_capture", "NDICapture"),
    "OBSRecorderController": (
        ".obs.recorder_controller",
        "OBSRecorderController",
    ),
    "ProcessEnvironmentAdapter": (
        ".system.cross_cutting",
        "ProcessEnvironmentAdapter",
    ),
    "RecorderWithTranscription": (
        ".video.recorder_with_transcription",
        "RecorderWithTranscription",
    ),
    "ReplayRecorderController": (
        ".video.replay_recorder_controller",
        "ReplayRecorderController",
    ),
    "SetupStateFileAdapter": (
        ".storage.setup_state_file_adapter",
        "SetupStateFileAdapter",
    ),
    "SpeechTranscriber": (".audio.speech_transcriber", "SpeechTranscriber"),
    "StructlogLoggerAdapter": (
        ".system.cross_cutting",
        "StructlogLoggerAdapter",
    ),
    "SubtitleEditor": (".text.subtitle_editor", "SubtitleEditor"),
    "SystemCommandAdapter": (
        ".system.system_command_adapter",
        "SystemCommandAdapter",
    ),
    "SystemPower": (".system.system_power", "SystemPower"),
    "TesseractOCR": (".text.tesseract_ocr", "TesseractOCR"),
    "TomlConfigAdapter": (".system.cross_cutting", "TomlConfigAdapter"),
    "TomlSettingsRepository": (
        ".storage.settings_repository",
        "TomlSettingsRepository",
    ),
    "VideoFileCapture": (".capture.video_file_capture", "VideoFileCapture"),
    "WeaponRecognitionAdapter": (
        ".weapon_detection",
        "WeaponRecognitionAdapter",
    ),
    "YouTubeClient": (".upload.youtube_client", "YouTubeClient"),
}


def __getattr__(name: str) -> Any:
    module_name, attr_name = _LAZY_EXPORTS[name]
    value = getattr(import_module(module_name, __name__), attr_name)
    globals()[name] = value
    return value
```

- [ ] **Step 5: 回帰テストと backend 基本検証を実行する**

Run: `uv run pytest -q backend/tests/test_bootstrap_imports.py`
Expected: PASS

Run: `uv run pytest -q`
Expected: PASS（少なくとも今回追加した import 経路で `DeprecationWarning` が出ない）


### Task 2: frontend の non-breaking 依存更新で audit を減らす

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`

- [ ] **Step 1: 依存の現状を audit で失敗として固定する**

Run: `npm audit --json`
Expected: `vitest` / `@vitest/ui` / `@vitest/coverage-v8` / `happy-dom` を含む high 脆弱性が残って FAIL

- [ ] **Step 2: non-breaking 更新を package.json に反映する**

```json
{
  "devDependencies": {
    "@vitest/coverage-v8": "^4.1.2",
    "@vitest/ui": "^4.1.2",
    "happy-dom": "^20.8.9",
    "vitest": "^4.1.2"
  }
}
```

- [ ] **Step 3: lock を更新する**

Run: `npm install`
Expected: `package-lock.json` が更新される

- [ ] **Step 4: audit を再実行して patch で消せる脆弱性が落ちたことを確認する**

Run: `npm audit --json`
Expected: `vitest` / `happy-dom` / `flatted` / `picomatch` 起因の high が減少または解消し、残件が `vite` / `svelte` / `@sveltejs/vite-plugin-svelte` 系に寄る


### Task 3: frontend ツールチェーンの major 更新で audit の根本原因を減らす

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`
- Verify: `frontend/svelte.config.js`
- Verify: `frontend/vite.config.ts`
- Verify: `frontend/vitest.base.config.ts`
- Verify: `frontend/eslint.config.js`

- [ ] **Step 1: major 更新後に解消すべき残件を確認する**

Run: `npm audit --json`
Expected: 残件の中心が `svelte` / `vite` / `@sveltejs/vite-plugin-svelte` 系になっている

- [ ] **Step 2: Svelte 5 / Vite 8 系へ更新する**

```json
{
  "devDependencies": {
    "@sveltejs/vite-plugin-svelte": "^7.0.0",
    "@testing-library/svelte": "^5.3.1",
    "eslint-plugin-svelte": "^3.17.0",
    "prettier-plugin-svelte": "^3.5.1",
    "svelte": "^5.55.1",
    "svelte-check": "^4.4.6",
    "svelte-eslint-parser": "^1.6.0",
    "vite": "^8.0.3"
  }
}
```

- [ ] **Step 3: install 後に必要最小限の設定差分を調整する**

```ts
// frontend/vitest.base.config.ts
import { defineConfig } from 'vitest/config';
import { svelte } from '@sveltejs/vite-plugin-svelte';

export const baseVitestConfig = defineConfig({
  plugins: [svelte({ hot: !process.env.VITEST })],
  cacheDir: 'node_modules/.vite-test',
  test: {
    globals: true,
    environment: 'happy-dom',
    setupFiles: ['./vitest.setup.ts'],
    exclude: ['node_modules', 'dist'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      exclude: [
        'node_modules/',
        'src/generated/',
        'tests/',
        '**/*.d.ts',
        '**/*.config.*',
        '**/mockData.ts',
      ],
    },
  },
});
```

- [ ] **Step 4: frontend の static / unit 入口で回帰確認する**

Run: `npm run format:check`
Expected: PASS

Run: `npm run type-check`
Expected: PASS

Run: `npm run check`
Expected: PASS

Run: `npm run test:unit`
Expected: PASS

- [ ] **Step 5: audit を再実行して major 更新の効果を確認する**

Run: `npm audit --json`
Expected: `vite` / `svelte` / `@sveltejs/vite-plugin-svelte` 系の脆弱性が解消、残件がある場合は個別依存と fixAvailable を確認できる状態になる


### Task 4: 最終 verify 入口で結果を確認する

**Files:**
- Verify: `Taskfile.yml`
- Verify: `docs/test_strategy.md`

- [ ] **Step 1: backend / frontend の意味ベース入口を再実行する**

Run: `uv run pytest -q backend/tests/test_bootstrap_imports.py`
Expected: PASS

Run: `uv run pytest -q`
Expected: PASS

Run: `npm run test:unit`
Expected: PASS

- [ ] **Step 2: 最終入口を実行する**

Run: `task.exe verify`
Expected: 今回の対応対象だった `DeprecationWarning` と audit 起因のノイズが減少した状態で完走する

- [ ] **Step 3: 差分を確認して報告する**

Run: `git diff -- backend frontend docs/superpowers/plans/2026-04-04-verify-root-cause-remediation.md`
Expected: backend import 経路修正、frontend 依存更新、計画書追加のみが含まれる
