# Architecture Phase0 Inventory

Goal: map current entry points to application flows, surface redundant modules, and
call out boundary deviations before cleanup. This is a snapshot of current code
paths and is intentionally implementation-focused.

## Entry Points and Composition Root

- CLI: `backend/src/splat_replay/interface/cli/main.py`
  - `auto` -> `AutoUseCase.wait_for_device()` then `AutoUseCase.execute()`
  - `upload` -> `UploadUseCase.execute()`
  - `web` -> FastAPI app from `bootstrap.web_app:create_app`
  - `webview` -> `SplatReplayWebViewApp` (starts FastAPI via uvicorn)
- Web API (FastAPI): `backend/src/splat_replay/bootstrap/web_app.py`
  - Builds a `WebAPIServer` with application services + use cases
  - App factory: `backend/src/splat_replay/interface/web/app_factory.py`
- WebView (desktop): `backend/src/splat_replay/interface/gui/webview_app.py`
  - Spawns uvicorn using `splat_replay.bootstrap.web_app:app`

## Web API Route Mapping (current)

- `/api/events/*` -> `EventBusPort` subscriptions (SSE)
  - `interface/web/routers/events.py`
- `/api/recorder/*` -> `AutoRecorder` service methods
  - `interface/web/routers/recording.py`
  - `enable-auto` builds `AutoRecordingUseCase` directly (no DI)
- `/api/preview/*` -> placeholder (no use case yet)
  - `interface/web/routers/recording.py`
- `/api/assets/*` -> asset use cases
  - list/delete recorded + edited
  - edit-upload trigger + status
  - `interface/web/routers/assets.py`
- `/api/subtitles/recorded/*` -> subtitle use cases
  - `interface/web/routers/metadata.py`
- `/api/assets/recorded/{video_id}/metadata` -> returns 501 (unimplemented)
  - `interface/web/routers/metadata.py`
- `/setup/*` -> setup and system services
  - `interface/web/routers/setup.py`
- `/api/settings/*` -> settings + device + setup service
  - `interface/web/routers/settings.py`

## Application Use Cases and Services (used by entry points)

- Use cases:
  - `AutoUseCase`, `UploadUseCase`
  - `ListRecordedVideosUseCase`, `DeleteRecordedVideoUseCase`
  - `ListEditedVideosUseCase`, `DeleteEditedVideoUseCase`
  - `GetEditUploadStatusUseCase`, `StartEditUploadUseCase`
  - `GetRecordedSubtitleStructuredUseCase`, `UpdateRecordedSubtitleStructuredUseCase`
- Services:
  - `AutoRecorder`, `RecordingPreparationService`
  - `SetupService`, `SystemCheckService`, `SystemSetupService`
  - `SettingsService`, `DeviceChecker`, `ErrorHandler`

## Messaging Runtime

- `AppRuntime` registers command handlers for:
  - `AutoRecorder.command_handlers()`
  - `AssetQueryService.command_handlers()`
- `CommandDispatcher` is implemented by `GuiRuntimePortAdapter`, but current web
  routes do not use it. Legacy `EditingAPI` and `MetadataAPI` are the only
  consumers of `CommandDispatcher`.

## Redundant or Legacy Components

- `backend/src/splat_replay/infrastructure/di.py`
  - Duplicated the DI package at `backend/src/splat_replay/infrastructure/di/`
  - Created ambiguous import resolution for `splat_replay.infrastructure.di`
  - Status: removed in phase0 cleanup
- `backend/src/splat_replay/interface/web/editing_api.py`
  - Not referenced by routers; duplicated assets + edit-upload logic with direct
    file I/O
  - Status: removed in phase0 cleanup
- `backend/src/splat_replay/interface/web/metadata_api.py`
  - Not referenced by routers; duplicated subtitle/metadata logic with direct
    file I/O and OpenCV usage
  - Status: removed in phase0 cleanup

## Boundary Deviations (not yet fixed)

- `interface/web/routers/recording.py` constructs `AutoRecordingUseCase` inline
  and calls `AutoRecorder` directly; bypasses DI and use case boundaries.
  - Status: resolved by injecting an AutoRecordingUseCase factory (phase1)
- Metadata update endpoint is stubbed (501) despite a use case existing for
  `UpdateRecordedMetadataUseCase`.
  - Status: resolved by implementing UpdateRecordedMetadataUseCase + router (phase1)
- Asset routes return `has_thumbnail=True` without checking actual existence.

## Phase1+ Targets (decision points)

- Remove legacy modules and duplicate DI to make the canonical path unambiguous.
- Decide whether to keep `CommandDispatcher` as a public interface port or
  replace it with direct use cases for GUI/Web.
- Align `/api/recorder` and metadata update flows to use cases (single entry
  path) and move any file I/O to ports.
- Consolidate event types: string events vs domain events for SSE.
