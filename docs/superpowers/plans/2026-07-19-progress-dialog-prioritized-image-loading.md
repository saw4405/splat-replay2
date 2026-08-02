# 進捗ダイアログ画像優先読み込み Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 進捗ダイアログのメイン動画枠とシークバー画像を、キャッシュに依存せず優先順に表示し、画像処理の成否から編集処理を切り離す。

**Architecture:** フロントエンドに同時実行数1の明示的画像キューを置き、表示対象を5段階の優先度へ変換する。バックエンドは要求ごとに元動画からPNGを抽出して `no-store` で返し、編集オーケストレーターからフレーム事前生成と待機を削除する。

**Tech Stack:** Svelte 5、TypeScript 5、Vitest 4、Playwright、FastAPI、Python 3.12、asyncio、FFmpeg、pytest。

**Approved design:** `docs/superpowers/specs/2026-07-19-progress-dialog-prioritized-image-loading-design.md`

## Global Constraints

- 画像要求の優先度は、メイン現在フレーム、操作中クリップ、操作中項目の残り、次の項目、それ以降の項目の順とする。
- フロントエンドとバックエンドのプレビュー抽出は同時に1件だけ実行し、実行中要求を優先度更新だけで中断しない。
- 同じ表示枠では最新URLだけを要求し、古い要求が遅れて成功しても表示へ反映しない。
- `fetch` は `cache: 'no-store'`、API応答は `Cache-Control: no-store` とする。
- 合計3回試行し、再試行前の待機は250ミリ秒、750ミリ秒とする。中止は失敗回数へ含めない。
- `.progress_frames` その他の永続キャッシュを参照・生成しない。既存ディレクトリの一括削除は行わない。
- 画像の取得、デコード、再試行、失敗を編集ジョブから待たず、画像失敗で編集状態を失敗へ変更しない。
- 元動画の保持期間と削除タイミング、進捗ダイアログのレイアウト・色・文言・アニメーションを変更しない。
- 新しい依存パッケージを追加しない。
- `docs/test_strategy.md` の `0. AI エージェント実行契約` をテスト判断のSSoTとし、Windowsでは `task.exe` を使う。
- 作業ツリーにはユーザーの既存差分がある。`git reset`、`git checkout --`、ファイル単位の無条件ステージを禁止し、各コミットは `git add -p -- <paths>` と `git diff --cached` で今回のハンクだけを選ぶ。

## File Responsibility Map

- `backend/src/splat_replay/application/services/editing/auto_editor.py`: 編集オーケストレーション。プレビュー依存と事前生成待機を除去する。
- `backend/src/splat_replay/application/interfaces/video.py`: `FramePreviewPort.extract_frame` だけを外部契約として残す。
- `backend/src/splat_replay/application/interfaces/__init__.py`: 削除する `FramePreviewRequest` の再公開を除去する。
- `backend/src/splat_replay/infrastructure/adapters/video/ffmpeg_processor.py`: 元動画からのオンデマンド抽出と並列数1を担う。
- `backend/src/splat_replay/interface/web/routers/assets.py`: フレームAPIの404/500と `no-store` 契約を担う。
- `frontend/src/main/components/progress/progressImageLoader.ts`: 優先キュー、重複排除、再試行、デコード、所有権解放を担う。
- `frontend/src/main/components/progress/ProgressDialog.svelte`: 画面状態を画像要求へ変換し、準備済みObject URLだけを表示する。
- `frontend/src/main/components/progress/ProgressDialog.integration.test.ts`: SSE状態と実ローダーを結ぶ代表導線を検証する。
- `frontend/tests/e2e/edit-upload-workflow.spec.ts`: 実ブラウザーで画像成功後に画像APIが失敗しても編集・アップロードが完了することを検証する。

仕様書末尾の `frontend/src/main/components/ProgressDialog.svelte` は簡略表記であり、実在する変更先は `frontend/src/main/components/progress/ProgressDialog.svelte` とする。`frontend/src/main/api/assets.ts`、`progressStateMachine.ts`、`package.json`、lockfile、共通Vitest設定へ画像取得責務を追加しない。

---

### Task 1: 編集処理からフレーム事前生成待機を除去する

**Files:**
- Modify: `backend/tests/logic/application/test_auto_editor.py:184-288`
- Modify: `backend/src/splat_replay/application/services/editing/auto_editor.py:18-69, 241-252, 354-378`

**Interfaces:**
- Consumes: `VideoEditorPort`、`VideoAssetRepositoryPort`、既存の `AutoEditor.execute()`。
- Produces: `AutoEditor.__init__(..., file_system: FileSystemPort, progress: ProgressReporter)`。`FramePreviewPort` を受け取らず、`execute()` は保存後すぐ録画削除と進捗通知へ進む。

- [ ] **Step 1: 事前生成がなくても保存・削除まで進む失敗テストへ変更する**

`test_execute_reports_generated_title_when_group_is_saved` を `test_execute_saves_group_without_frame_preview_dependency` へ改名する。既存fixtureは維持し、`_Repo` と末尾assertを次の形へ変更する。

```python
deleted_videos: list[Path] = []

class _Repo:
    def list_recordings(self) -> list[object]:
        return [asset]

    def save_edited(self, target: Path) -> Path:
        return target

    def delete_recording(self, video: Path) -> None:
        deleted_videos.append(video)
```

次のno-op差し替えをテストから削除する。

```python
async def fake_warm_progress_preview_frames(group: list[object]) -> None:
    _ = group

editor._warm_progress_preview_frames = fake_warm_progress_preview_frames
```

既存の `progress.item_stage_calls` assertに加えて次を置く。

```python
assert deleted_videos == [source_video]
```

- [ ] **Step 2: 対象テストが現実装で失敗することを確認する**

Run from `backend/`:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ..\scripts\run-backend-pytest.ps1 -q tests/logic/application/test_auto_editor.py::test_execute_saves_group_without_frame_preview_dependency
```

Expected: `FAIL`。現実装は `_warm_progress_preview_frames()` から未設定の `_frame_preview` へ到達し、`deleted_videos` が空のままになる。

- [ ] **Step 3: `AutoEditor` のプレビュー依存と待機を削除する**

`FramePreviewPort`、`FramePreviewRequest` のimportと `PROGRESS_FRAME_MAX_WIDTH` を削除する。コンストラクターを次のシグネチャにする。

```python
def __init__(
    self,
    logger: LoggerPort,
    config: ConfigPort,
    paths: PathsPort,
    video_editor: VideoEditorPort,
    subtitle_editor: SubtitleEditorPort,
    image_selector: ImageSelector,
    text_to_speech: TextToSpeechPort,
    repo: VideoAssetRepositoryPort,
    file_system: FileSystemPort,
    progress: ProgressReporter,
) -> None:
```

`self._frame_preview = frame_preview` を削除し、保存後の処理を次の形にする。

```python
target = self.repo.save_edited(Path(target))
for asset in group:
    self.logger.info(
        "録画済み動画を削除します",
        path=str(asset.video),
    )
    self.repo.delete_recording(asset.video)
```

`_warm_progress_preview_frames()` と `_progress_frame_seconds()` は呼び出し元ごと削除する。元動画削除、保存進捗、後続項目の順序は変えない。

- [ ] **Step 4: AutoEditor logicを再実行して成功を確認する**

Run from `backend/`:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ..\scripts\run-backend-pytest.ps1 -q tests/logic/application/test_auto_editor.py
```

Expected: 対象ファイルがすべて `PASS`。

- [ ] **Step 5: 今回のハンクだけをコミットする**

```powershell
git add -p -- backend/src/splat_replay/application/services/editing/auto_editor.py backend/tests/logic/application/test_auto_editor.py
git diff --cached --check
git diff --cached --name-status
git diff --cached -- backend/src/splat_replay/application/services/editing/auto_editor.py backend/tests/logic/application/test_auto_editor.py
git commit -m "fix: decouple editing from preview frames"
```

Expected: コミット対象は上記2ファイルのプレビュー待機除去ハンクだけ。

---

### Task 2: FFmpegフレーム抽出をキャッシュ非依存・直列実行へ変更する

**Files:**
- Modify: `backend/tests/logic/infrastructure/test_frame_preview_port.py:1-72`
- Modify: `backend/src/splat_replay/application/interfaces/video.py:1-39`
- Modify: `backend/src/splat_replay/application/interfaces/__init__.py:101-102, 169-170`
- Modify: `backend/src/splat_replay/infrastructure/adapters/video/ffmpeg_processor.py:5-37, 381-460, 946-995`

**Interfaces:**
- Consumes: `FFmpegProcessor._run_binary(command, timeout=8)`。
- Produces: `FramePreviewPort.extract_frame(video: Path, seconds: float, *, max_width: int | None = None) -> bytes | None` のみ。毎要求で元動画を確認し、1プロセス内で1件ずつFFmpegを実行する。

- [ ] **Step 1: 永続キャッシュ不使用と直列実行の失敗テストを書く**

`_FramePreviewProcessor` に実行中件数を追加する。

```python
class _FramePreviewProcessor(FFmpegProcessor):
    def __init__(self) -> None:
        super().__init__(MagicMock())
        self.commands: list[list[str]] = []
        self.active_runs = 0
        self.max_active_runs = 0

    async def _run_binary(
        self,
        command: Sequence[str],
        *,
        input_bytes: bytes | None = None,
        timeout: float | None = None,
    ) -> CompletedProcess[bytes]:
        _ = input_bytes, timeout
        self.commands.append(list(command))
        self.active_runs += 1
        self.max_active_runs = max(self.max_active_runs, self.active_runs)
        try:
            await asyncio.sleep(0.01)
            return CompletedProcess(
                args=list(command),
                returncode=0,
                stdout=b"png-bytes",
                stderr=b"",
            )
        finally:
            self.active_runs -= 1
```

旧2テストを次の3テストへ置き換える。

```python
@pytest.mark.asyncio
async def test_extract_frame_runs_ffmpeg_for_each_request_without_persistent_cache(
    tmp_path: Path,
) -> None:
    processor = _FramePreviewProcessor()
    video = tmp_path / "videos" / "recorded" / "sample.mkv"
    video.parent.mkdir(parents=True)
    video.write_bytes(b"video")

    first = await processor.extract_frame(video, 60, max_width=960)
    second = await processor.extract_frame(video, 60, max_width=960)

    assert first == b"png-bytes"
    assert second == b"png-bytes"
    assert len(processor.commands) == 2
    assert "scale=960:-2" in processor.commands[0]
    assert not (tmp_path / "videos" / ".progress_frames").exists()


@pytest.mark.asyncio
async def test_extract_frame_returns_none_after_source_video_is_removed(
    tmp_path: Path,
) -> None:
    processor = _FramePreviewProcessor()
    video = tmp_path / "videos" / "recorded" / "sample.mkv"
    video.parent.mkdir(parents=True)
    video.write_bytes(b"video")

    first = await processor.extract_frame(video, 60, max_width=960)
    video.unlink()
    second = await processor.extract_frame(video, 60, max_width=960)

    assert first == b"png-bytes"
    assert second is None
    assert len(processor.commands) == 1
    assert not (tmp_path / "videos" / ".progress_frames").exists()


@pytest.mark.asyncio
async def test_extract_frame_serializes_preview_requests(tmp_path: Path) -> None:
    processor = _FramePreviewProcessor()
    video = tmp_path / "videos" / "recorded" / "sample.mkv"
    video.parent.mkdir(parents=True)
    video.write_bytes(b"video")

    results = await asyncio.gather(
        processor.extract_frame(video, 0, max_width=960),
        processor.extract_frame(video, 60, max_width=960),
        processor.extract_frame(video, 120, max_width=960),
    )

    assert results == [b"png-bytes"] * 3
    assert processor.max_active_runs == 1
```

- [ ] **Step 2: 新契約が現実装で失敗することを確認する**

Run from `backend/`:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ..\scripts\run-backend-pytest.ps1 -q tests/logic/infrastructure/test_frame_preview_port.py
```

Expected: `FAIL`。同一要求はキャッシュで1回に畳まれ、削除後もキャッシュからbytesを返し、異なる時刻の並列実行数は2になる。

- [ ] **Step 3: プレビューポートをオンデマンド抽出だけに縮小する**

`application/interfaces/video.py` から `FramePreviewRequest`、`Sequence`、`warm_frames()` を削除し、次だけを残す。

```python
class FramePreviewPort(Protocol):
    """進捗表示用フレーム画像を提供するポート。"""

    async def extract_frame(
        self,
        video: Path,
        seconds: float,
        *,
        max_width: int | None = None,
    ) -> bytes | None:
        """元動画から指定秒数のPNGフレームを抽出する。"""
        ...
```

`application/interfaces/__init__.py` のimportと `__all__` から `FramePreviewRequest` だけを削除する。

- [ ] **Step 4: FFmpegProcessorからディスクキャッシュとwarm-upを削除する**

`hashlib`、`FramePreviewRequest`、`_frame_preview_locks`、`warm_frames()`、`_frame_preview_cache_path()`、`_read_frame_preview_cache()`、`_write_frame_preview_cache()` を削除する。`Sequence` は他のコマンド実行シグネチャで使うため残す。セマフォを次へ変更する。

```python
self._frame_preview_semaphore = asyncio.Semaphore(1)
```

`extract_frame()` を次の処理へ置き換える。

```python
async def extract_frame(
    self,
    video: Path,
    seconds: float,
    *,
    max_width: int | None = None,
) -> bytes | None:
    """元動画から進捗表示用PNGフレームを抽出する。"""
    abs_video = video.resolve()
    normalized_seconds = max(0, int(seconds))
    normalized_width = (
        max_width if max_width is not None and max_width > 0 else None
    )
    if not abs_video.is_file():
        return None

    command = [
        "ffmpeg",
        "-y",
        "-ss",
        str(normalized_seconds),
        "-i",
        str(abs_video),
        "-vframes",
        "1",
    ]
    if normalized_width is not None:
        command.extend(["-vf", f"scale={normalized_width}:-2"])
    command.extend(["-f", "image2", "-vcodec", "png", "pipe:1"])

    try:
        async with self._frame_preview_semaphore:
            result = await self._run_binary(command, timeout=8)
    except (OSError, subprocess.TimeoutExpired) as exc:
        self.logger.warning(
            "FFmpeg preview frame extraction failed",
            path=str(abs_video),
            seconds=normalized_seconds,
            width=normalized_width,
            error=str(exc),
        )
        return None

    if result.returncode != 0 or not result.stdout:
        self._log_failure("FFmpeg preview frame extraction failed", result)
        return None
    return result.stdout
```

- [ ] **Step 5: logicテストと静的参照確認を通す**

Run from `backend/`:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ..\scripts\run-backend-pytest.ps1 -q tests/logic/infrastructure/test_frame_preview_port.py
$symbolMatches = rg -n "FramePreviewRequest|warm_frames|frame_preview_cache" src tests
if ($LASTEXITCODE -eq 0) { $symbolMatches; throw 'Removed preview symbols remain' }
if ($LASTEXITCODE -gt 1) { exit $LASTEXITCODE }
$cacheMatches = rg -n "progress_frames" src
if ($LASTEXITCODE -eq 0) { $cacheMatches; throw 'Production cache reference remains' }
if ($LASTEXITCODE -gt 1) { exit $LASTEXITCODE }
```

Expected: pytestはすべて `PASS`。`rg` は一致なしで終了コード1となり、`.progress_frames` の参照も残らない。

- [ ] **Step 6: 今回のハンクだけをコミットする**

```powershell
git add -p -- backend/src/splat_replay/application/interfaces/video.py backend/src/splat_replay/application/interfaces/__init__.py backend/src/splat_replay/infrastructure/adapters/video/ffmpeg_processor.py backend/tests/logic/infrastructure/test_frame_preview_port.py
git diff --cached --check
git diff --cached --name-status
git diff --cached -- backend/src/splat_replay/application/interfaces/video.py backend/src/splat_replay/application/interfaces/__init__.py backend/src/splat_replay/infrastructure/adapters/video/ffmpeg_processor.py backend/tests/logic/infrastructure/test_frame_preview_port.py
git commit -m "fix: extract progress frames without cache"
```

Expected: コミット対象は上記4ファイルのフレーム抽出契約ハンクだけ。

---

### Task 3: 動画フレームAPIを `no-store`・厳密エラー契約へ変更する

**Files:**
- Modify: `backend/tests/contract/test_assets_router_contract.py:379-435`
- Modify: `backend/src/splat_replay/interface/web/routers/assets.py:31, 96-156`

**Interfaces:**
- Consumes: `FramePreviewPort.extract_frame(...) -> bytes | None`。
- Produces: `GET /api/assets/recorded/{video_id:path}/frame?t=<seconds>&w=<width>`。成功はPNG + `no-store`、元動画なしは404、抽出不能・例外は500。

- [ ] **Step 1: APIの失敗契約を表すテストstubへ拡張する**

既存stubを次へ置き換える。

```python
class _FramePreviewStub:
    def __init__(
        self,
        result: bytes | None = b"png-bytes",
        error: Exception | None = None,
    ) -> None:
        self.result = result
        self.error = error
        self.calls: list[tuple[str, float, int | None]] = []

    async def extract_frame(
        self,
        video: Any,
        seconds: float,
        *,
        max_width: int | None = None,
    ) -> bytes | None:
        self.calls.append((str(video), seconds, max_width))
        if self.error is not None:
            raise self.error
        return self.result
```

既存のFastAPI組み立てを次のhelperへ抽出する。

```python
def _create_frame_test_app(
    base_dir: Any,
    frame_preview: _FramePreviewStub,
) -> FastAPI:
    app = FastAPI()
    app.include_router(
        create_assets_router(
            cast(
                Any,
                SimpleNamespace(
                    base_dir=base_dir,
                    frame_preview=frame_preview,
                    logger=SimpleNamespace(
                        error=lambda *args, **kwargs: None
                    ),
                ),
            )
        )
    )
    return app
```

`TestRecordedFrameEndpoint` を次の4ケースへ置き換える。

```python
class TestRecordedFrameEndpoint:
    """進捗表示用フレームAPIの契約テスト。"""

    def test_recorded_frame_returns_requested_png_with_no_store(
        self, tmp_path: Any
    ) -> None:
        base_dir = tmp_path / "videos"
        recorded_dir = base_dir / "recorded"
        recorded_dir.mkdir(parents=True)
        (recorded_dir / "sample.mkv").write_bytes(b"video")
        frame_preview = _FramePreviewStub()

        with TestClient(
            _create_frame_test_app(base_dir, frame_preview)
        ) as client:
            response = client.get(
                "/api/assets/recorded/sample.mkv/frame?t=60&w=960"
            )

        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        assert response.headers["cache-control"] == "no-store"
        assert response.content == b"png-bytes"
        assert frame_preview.calls == [
            (str((recorded_dir / "sample.mkv").resolve()), 60.0, 960)
        ]

    def test_recorded_frame_returns_404_when_source_video_is_missing(
        self, tmp_path: Any
    ) -> None:
        base_dir = tmp_path / "videos"
        (base_dir / "recorded").mkdir(parents=True)
        frame_preview = _FramePreviewStub(result=b"stale-cache")

        with TestClient(
            _create_frame_test_app(base_dir, frame_preview)
        ) as client:
            response = client.get(
                "/api/assets/recorded/missing.mkv/frame?t=0&w=960"
            )

        assert response.status_code == 404
        assert frame_preview.calls == []

    def test_recorded_frame_returns_500_when_extraction_fails(
        self, tmp_path: Any
    ) -> None:
        base_dir = tmp_path / "videos"
        recorded_dir = base_dir / "recorded"
        recorded_dir.mkdir(parents=True)
        (recorded_dir / "sample.mkv").write_bytes(b"video")
        (recorded_dir / "sample.png").write_bytes(b"sidecar-fallback")
        frame_preview = _FramePreviewStub(result=None)

        with TestClient(
            _create_frame_test_app(base_dir, frame_preview)
        ) as client:
            response = client.get(
                "/api/assets/recorded/sample.mkv/frame?t=60&w=960"
            )

        assert response.status_code == 500
        assert response.content != b"sidecar-fallback"

    def test_recorded_frame_does_not_fallback_to_unrelated_png_on_exception(
        self, tmp_path: Any
    ) -> None:
        base_dir = tmp_path / "videos"
        recorded_dir = base_dir / "recorded"
        recorded_dir.mkdir(parents=True)
        (recorded_dir / "sample.mkv").write_bytes(b"video")
        (recorded_dir / "other.png").write_bytes(b"unrelated-fallback")
        frame_preview = _FramePreviewStub(error=RuntimeError("ffmpeg failed"))

        with TestClient(
            _create_frame_test_app(base_dir, frame_preview)
        ) as client:
            response = client.get(
                "/api/assets/recorded/sample.mkv/frame?t=60&w=960"
            )

        assert response.status_code == 500
        assert response.content != b"unrelated-fallback"

    def test_recorded_frame_returns_404_for_disallowed_path(
        self, tmp_path: Any
    ) -> None:
        base_dir = tmp_path / "videos"
        (base_dir / "recorded").mkdir(parents=True)
        frame_preview = _FramePreviewStub()

        with TestClient(
            _create_frame_test_app(base_dir, frame_preview)
        ) as client:
            response = client.get(
                "/api/assets/recorded/..%2F..%2Foutside.mkv/frame?t=0&w=960"
            )

        assert response.status_code == 404
        assert frame_preview.calls == []
```

- [ ] **Step 2: 変更前の契約違反を確認する**

Run from `backend/`:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ..\scripts\run-backend-pytest.ps1 -q tests/contract/test_assets_router_contract.py::TestRecordedFrameEndpoint
```

Expected: `FAIL`。成功応答はimmutable cacheで、元動画がなくても抽出stubを呼び、同名または無関係PNGへフォールバックする。

- [ ] **Step 3: フレームAPIを元動画・抽出結果だけで判定する**

ヘッダー定数を次へ変更する。

```python
FRAME_RESPONSE_HEADERS = {"Cache-Control": "no-store"}
```

エンドポイント本体を次の順序へ変更する。

```python
try:
    video_path = _resolve_recorded_video_path(video_id)
except HTTPException as exc:
    if exc.status_code == 400:
        raise HTTPException(
            status_code=404,
            detail="Video file not found",
        ) from exc
    raise
if not video_path.is_file():
    raise HTTPException(status_code=404, detail="Video file not found")

frame = await server.frame_preview.extract_frame(
    video_path,
    t,
    max_width=w,
)
if frame is None:
    server.logger.error(
        "フレーム切り出し失敗",
        path=str(video_path),
        seconds=t,
        width=w,
    )
    raise HTTPException(status_code=500, detail="Failed to extract frame")

return Response(
    content=frame,
    media_type="image/png",
    headers=FRAME_RESPONSE_HEADERS,
)
```

同名PNGフォールバック、recorded配下の最初のPNGフォールバックを削除する。予期しない例外はパス、秒、幅、`exc_info=True` をログへ含め、固定detailの500へ変換する。`HTTPException` はそのまま再送出する。

```python
except HTTPException:
    raise
except Exception as exc:
    server.logger.error(
        "フレーム切り出しエラー",
        video_id=video_id,
        seconds=t,
        width=w,
        error=str(exc),
        exc_info=True,
    )
    raise HTTPException(
        status_code=500,
        detail="Failed to extract frame",
    ) from exc
```

- [ ] **Step 4: API契約テストを通す**

Run from `backend/`:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ..\scripts\run-backend-pytest.ps1 -q tests/contract/test_assets_router_contract.py::TestRecordedFrameEndpoint
```

Expected: `TestRecordedFrameEndpoint` がすべて `PASS`。

- [ ] **Step 5: 今回のハンクだけをコミットする**

```powershell
git add -p -- backend/src/splat_replay/interface/web/routers/assets.py backend/tests/contract/test_assets_router_contract.py
git diff --cached --check
git diff --cached --name-status
git diff --cached -- backend/src/splat_replay/interface/web/routers/assets.py backend/tests/contract/test_assets_router_contract.py
git commit -m "fix: serve progress frames without cache fallback"
```

Expected: コミット対象は上記2ファイルのフレームAPI契約ハンクだけ。

---

### Task 4: 優先度付き画像ローダーを実装する

**Files:**
- Create: `frontend/src/main/components/progress/progressImageLoader.ts`
- Create: `frontend/src/main/components/progress/progressImageLoader.test.ts`

**Interfaces:**
- Consumes: browser `fetch`、`AbortController`、`Blob`、`URL.createObjectURL`、`Image.decode()`。
- Produces: `ProgressImageLoader.request()`、`releaseSlot()`、`releaseOwner()`、`clear()`、`dispose()` と5段階の `PROGRESS_IMAGE_PRIORITY`。

- [ ] **Step 1: キューの外部契約をテストに固定する**

テスト先頭に、保留中Promiseと依存注入を作るhelperを置く。

```ts
import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  PROGRESS_IMAGE_PRIORITY,
  ProgressImageLoader,
  type ProgressImageReady,
  type ProgressImageRequest,
} from './progressImageLoader';

function deferred<T>(): {
  promise: Promise<T>;
  resolve: (value: T) => void;
  reject: (reason: unknown) => void;
} {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

function pngResponse(): Response {
  return new Response(new Blob(['png'], { type: 'image/png' }), {
    status: 200,
    headers: { 'Content-Type': 'image/png' },
  });
}

function requestFor(
  overrides: Partial<ProgressImageRequest> & Pick<ProgressImageRequest, 'url' | 'onReady'>
): ProgressImageRequest {
  return {
    ownerId: 'owner',
    slotId: 'slot',
    priority: PROGRESS_IMAGE_PRIORITY.LATER_ITEM,
    sequence: 0,
    onError: vi.fn(),
    ...overrides,
  };
}
```

次のケースを同じファイルへ実装する。各テストは `fetchFn`、`decodeImage`、`createObjectUrl`、`revokeObjectUrl`、`sleep` を注入し、ネットワーク・時計・DOMへ依存させない。

```ts
describe('ProgressImageLoader', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('実行中の1件を中断せず完了後に最新の優先度と投入順で次を取得する', async () => {
    const first = deferred<Response>();
    const fetchFn = vi
      .fn<typeof fetch>()
      .mockImplementationOnce(() => first.promise)
      .mockResolvedValue(pngResponse());
    let objectUrlIndex = 0;
    const loader = new ProgressImageLoader({
      fetchFn,
      decodeImage: vi.fn().mockResolvedValue(undefined),
      createObjectUrl: vi.fn(() => `blob:${++objectUrlIndex}`),
      revokeObjectUrl: vi.fn(),
      sleep: vi.fn().mockResolvedValue(undefined),
    });

    loader.request(
      requestFor({ url: '/later', slotId: 'later', sequence: 0, onReady: vi.fn() })
    );
    await vi.waitFor(() => expect(fetchFn).toHaveBeenCalledTimes(1));
    loader.request(
      requestFor({
        url: '/next',
        slotId: 'next',
        priority: PROGRESS_IMAGE_PRIORITY.NEXT_ITEM,
        sequence: 1,
        onReady: vi.fn(),
      })
    );
    loader.request(
      requestFor({
        url: '/main',
        slotId: 'main',
        priority: PROGRESS_IMAGE_PRIORITY.MAIN,
        sequence: 2,
        onReady: vi.fn(),
      })
    );

    first.resolve(pngResponse());
    await vi.waitFor(() => expect(fetchFn).toHaveBeenCalledTimes(3));

    expect(fetchFn.mock.calls.map(([url]) => url)).toEqual(['/later', '/main', '/next']);
    loader.dispose();
  });

  it('同じURLを1回だけ取得し複数slotへ同じObject URLを通知する', async () => {
    const fetchFn = vi.fn<typeof fetch>().mockResolvedValue(pngResponse());
    const firstReady = vi.fn<(image: ProgressImageReady) => void>();
    const secondReady = vi.fn<(image: ProgressImageReady) => void>();
    const loader = new ProgressImageLoader({
      fetchFn,
      decodeImage: vi.fn().mockResolvedValue(undefined),
      createObjectUrl: vi.fn(() => 'blob:shared'),
      revokeObjectUrl: vi.fn(),
      sleep: vi.fn().mockResolvedValue(undefined),
    });

    loader.request(requestFor({ url: '/same', slotId: 'a', onReady: firstReady }));
    loader.request(requestFor({ url: '/same', slotId: 'b', onReady: secondReady }));

    await vi.waitFor(() => expect(secondReady).toHaveBeenCalledTimes(1));
    expect(fetchFn).toHaveBeenCalledTimes(1);
    expect(firstReady.mock.calls[0][0].objectUrl).toBe('blob:shared');
    expect(secondReady.mock.calls[0][0].objectUrl).toBe('blob:shared');
    loader.dispose();
  });

  it('同じslotへ同じURLを再登録しても再取得・再通知しない', async () => {
    const fetchFn = vi.fn<typeof fetch>().mockResolvedValue(pngResponse());
    const onReady = vi.fn<(image: ProgressImageReady) => void>();
    const loader = new ProgressImageLoader({
      fetchFn,
      decodeImage: vi.fn().mockResolvedValue(undefined),
      createObjectUrl: vi.fn(() => 'blob:stable'),
      revokeObjectUrl: vi.fn(),
      sleep: vi.fn().mockResolvedValue(undefined),
    });
    const request = requestFor({ url: '/stable', onReady });

    loader.request(request);
    await vi.waitFor(() => expect(onReady).toHaveBeenCalledTimes(1));
    loader.request(request);

    expect(fetchFn).toHaveBeenCalledTimes(1);
    expect(onReady).toHaveBeenCalledTimes(1);
    loader.dispose();
  });

  it('同じslotのURL更新後に旧要求が成功しても通知しない', async () => {
    const oldResponse = deferred<Response>();
    const fetchFn = vi
      .fn<typeof fetch>()
      .mockImplementationOnce(() => oldResponse.promise)
      .mockResolvedValue(pngResponse());
    const onReady = vi.fn<(image: ProgressImageReady) => void>();
    const loader = new ProgressImageLoader({
      fetchFn,
      decodeImage: vi.fn().mockResolvedValue(undefined),
      createObjectUrl: vi.fn((blob: Blob) => `blob:${blob.size}:${fetchFn.mock.calls.length}`),
      revokeObjectUrl: vi.fn(),
      sleep: vi.fn().mockResolvedValue(undefined),
    });

    loader.request(requestFor({ url: '/old', onReady }));
    await vi.waitFor(() => expect(fetchFn).toHaveBeenCalledTimes(1));
    loader.request(requestFor({ url: '/new', onReady }));
    oldResponse.resolve(pngResponse());

    await vi.waitFor(() => expect(fetchFn).toHaveBeenCalledTimes(2));
    await vi.waitFor(() => expect(onReady).toHaveBeenCalledTimes(1));
    expect(onReady.mock.calls[0][0].sourceUrl).toBe('/new');
    loader.dispose();
  });

  it('失敗時に250msと750msを待って合計3回試行する', async () => {
    const fetchFn = vi
      .fn<typeof fetch>()
      .mockRejectedValueOnce(new TypeError('network-1'))
      .mockResolvedValueOnce(new Response(null, { status: 500 }))
      .mockResolvedValueOnce(pngResponse());
    const sleep = vi.fn().mockResolvedValue(undefined);
    const onReady = vi.fn<(image: ProgressImageReady) => void>();
    const loader = new ProgressImageLoader({
      fetchFn,
      decodeImage: vi.fn().mockResolvedValue(undefined),
      createObjectUrl: vi.fn(() => 'blob:retry'),
      revokeObjectUrl: vi.fn(),
      sleep,
    });

    loader.request(requestFor({ url: '/retry', onReady }));

    await vi.waitFor(() => expect(onReady).toHaveBeenCalledTimes(1));
    expect(fetchFn).toHaveBeenCalledTimes(3);
    expect(sleep.mock.calls.map(([delay]) => delay)).toEqual([250, 750]);
    expect(fetchFn).toHaveBeenCalledWith(
      '/retry',
      expect.objectContaining({ cache: 'no-store', signal: expect.any(AbortSignal) })
    );
    loader.dispose();
  });

  it('デコード失敗時は候補Object URLを解放して同じ上限で再試行する', async () => {
    const decodeImage = vi
      .fn()
      .mockRejectedValueOnce(new Error('decode failed'))
      .mockResolvedValueOnce(undefined);
    const revokeObjectUrl = vi.fn();
    const sleep = vi.fn().mockResolvedValue(undefined);
    let objectUrlIndex = 0;
    const onReady = vi.fn<(image: ProgressImageReady) => void>();
    const loader = new ProgressImageLoader({
      fetchFn: vi.fn<typeof fetch>().mockResolvedValue(pngResponse()),
      decodeImage,
      createObjectUrl: vi.fn(() => `blob:decode-${++objectUrlIndex}`),
      revokeObjectUrl,
      sleep,
    });

    loader.request(requestFor({ url: '/decode', onReady }));

    await vi.waitFor(() => expect(onReady).toHaveBeenCalledTimes(1));
    expect(decodeImage).toHaveBeenCalledTimes(2);
    expect(revokeObjectUrl).toHaveBeenCalledWith('blob:decode-1');
    expect(sleep).toHaveBeenCalledWith(250, expect.any(AbortSignal));
    loader.dispose();
  });

  it('最後の購読者を実行中に解放するとabortしonErrorへ通知しない', async () => {
    let observedSignal: AbortSignal | undefined;
    const fetchFn = vi.fn<typeof fetch>((_input, init) => {
      observedSignal = init?.signal ?? undefined;
      return new Promise<Response>((_resolve, reject) => {
        observedSignal?.addEventListener(
          'abort',
          () => reject(new DOMException('Aborted', 'AbortError')),
          { once: true }
        );
      });
    });
    const onError = vi.fn<(error: Error) => void>();
    const loader = new ProgressImageLoader({
      fetchFn,
      decodeImage: vi.fn().mockResolvedValue(undefined),
      createObjectUrl: vi.fn(() => 'blob:unused'),
      revokeObjectUrl: vi.fn(),
      sleep: vi.fn().mockResolvedValue(undefined),
    });

    loader.request(requestFor({ url: '/pending', onReady: vi.fn(), onError }));
    await vi.waitFor(() => expect(fetchFn).toHaveBeenCalledTimes(1));
    loader.releaseSlot('owner', 'slot');

    expect(observedSignal?.aborted).toBe(true);
    await vi.waitFor(() => expect(onError).not.toHaveBeenCalled());
    loader.dispose();
  });

  it('共有Object URLは最後の購読者を解放した時だけ一度解放する', async () => {
    const revokeObjectUrl = vi.fn();
    const loader = new ProgressImageLoader({
      fetchFn: vi.fn<typeof fetch>().mockResolvedValue(pngResponse()),
      decodeImage: vi.fn().mockResolvedValue(undefined),
      createObjectUrl: vi.fn(() => 'blob:shared'),
      revokeObjectUrl,
      sleep: vi.fn().mockResolvedValue(undefined),
    });
    const ready = vi.fn<(image: ProgressImageReady) => void>();

    loader.request(requestFor({ url: '/same', slotId: 'a', onReady: ready }));
    loader.request(requestFor({ url: '/same', slotId: 'b', onReady: ready }));
    await vi.waitFor(() => expect(ready).toHaveBeenCalledTimes(2));

    loader.releaseSlot('owner', 'a');
    expect(revokeObjectUrl).not.toHaveBeenCalled();
    loader.releaseSlot('owner', 'b');
    expect(revokeObjectUrl).toHaveBeenCalledTimes(1);
    loader.dispose();
    expect(revokeObjectUrl).toHaveBeenCalledTimes(1);
  });
});
```

- [ ] **Step 2: 新規logicテストがmodule未存在で失敗することを確認する**

Run from repository root:

```powershell
npm --prefix frontend run test:logic -- src/main/components/progress/progressImageLoader.test.ts
```

Expected: `FAIL` with module resolution error for `./progressImageLoader`。

- [ ] **Step 3: 公開型とブラウザー依存の既定実装を書く**

`progressImageLoader.ts` の公開契約を次に固定する。

```ts
export const PROGRESS_IMAGE_PRIORITY = {
  MAIN: 0,
  ACTIVE_CLIP: 1,
  ACTIVE_ITEM_REMAINDER: 2,
  NEXT_ITEM: 3,
  LATER_ITEM: 4,
} as const;

export type ProgressImagePriority =
  (typeof PROGRESS_IMAGE_PRIORITY)[keyof typeof PROGRESS_IMAGE_PRIORITY];

export interface ProgressImageReady {
  sourceUrl: string;
  objectUrl: string;
}

export interface ProgressImageRequest {
  url: string;
  ownerId: string;
  slotId: string;
  priority: ProgressImagePriority;
  sequence: number;
  onReady: (image: ProgressImageReady) => void;
  onError: (error: Error) => void;
}

export interface ProgressImageLoaderDependencies {
  fetchFn?: typeof fetch;
  decodeImage?: (objectUrl: string) => Promise<void>;
  createObjectUrl?: (blob: Blob) => string;
  revokeObjectUrl?: (objectUrl: string) => void;
  sleep?: (delayMs: number, signal: AbortSignal) => Promise<void>;
}
```

既定のデコードと待機を次で実装する。

```ts
const RETRY_DELAYS_MS = [250, 750] as const;

async function decodeImage(objectUrl: string): Promise<void> {
  const image = new Image();
  image.src = objectUrl;
  await image.decode();
}

function sleepWithAbort(delayMs: number, signal: AbortSignal): Promise<void> {
  if (signal.aborted) {
    return Promise.reject(new DOMException('Aborted', 'AbortError'));
  }
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      signal.removeEventListener('abort', onAbort);
      resolve();
    }, delayMs);
    const onAbort = (): void => {
      clearTimeout(timer);
      reject(new DOMException('Aborted', 'AbortError'));
    };
    signal.addEventListener('abort', onAbort, { once: true });
  });
}
```

- [ ] **Step 4: slotとURL entryを分離した単一実行キューを書く**

内部状態は次の形にする。

```ts
type EntryStatus = 'queued' | 'loading' | 'ready' | 'failed';

interface SlotState {
  key: string;
  request: ProgressImageRequest;
  displayedEntry: QueueEntry | null;
}

interface QueueEntry {
  sourceUrl: string;
  status: EntryStatus;
  controller: AbortController;
  objectUrl: string | null;
  error: Error | null;
  desiredSlots: Set<string>;
  displayedSlots: Set<string>;
  errorNotifiedSlots: Set<string>;
}

function slotKey(ownerId: string, slotId: string): string {
  return `${ownerId}\u0000${slotId}`;
}

function toError(error: unknown): Error {
  return error instanceof Error ? error : new Error(String(error));
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError';
}
```

`ProgressImageLoader` は次の完全な状態遷移で実装する。

```ts
export interface ProgressImageLoaderContract {
  request(request: ProgressImageRequest): void;
  releaseSlot(ownerId: string, slotId: string): void;
  releaseOwner(ownerId: string): void;
  clear(): void;
  dispose(): void;
}

export class ProgressImageLoader implements ProgressImageLoaderContract {
  private readonly slots = new Map<string, SlotState>();
  private readonly entries = new Map<string, QueueEntry>();
  private readonly fetchFn: typeof fetch;
  private readonly decodeImage: (objectUrl: string) => Promise<void>;
  private readonly createObjectUrl: (blob: Blob) => string;
  private readonly revokeObjectUrl: (objectUrl: string) => void;
  private readonly sleep: (delayMs: number, signal: AbortSignal) => Promise<void>;
  private runningEntry: QueueEntry | null = null;
  private disposed = false;

  constructor(dependencies: ProgressImageLoaderDependencies = {}) {
    this.fetchFn = dependencies.fetchFn ?? globalThis.fetch.bind(globalThis);
    this.decodeImage = dependencies.decodeImage ?? decodeImage;
    this.createObjectUrl =
      dependencies.createObjectUrl ?? URL.createObjectURL.bind(URL);
    this.revokeObjectUrl =
      dependencies.revokeObjectUrl ?? URL.revokeObjectURL.bind(URL);
    this.sleep = dependencies.sleep ?? sleepWithAbort;
  }

  request(request: ProgressImageRequest): void {
    if (this.disposed || request.url === '') return;
    const key = slotKey(request.ownerId, request.slotId);
    let slot = this.slots.get(key);
    if (slot !== undefined && slot.request.url !== request.url) {
      this.detachDesired(slot, false);
    }
    if (slot === undefined) {
      slot = { key, request, displayedEntry: null };
      this.slots.set(key, slot);
    } else {
      slot.request = request;
    }

    const entry = this.getOrCreateEntry(request.url);
    entry.desiredSlots.add(key);
    if (entry.status === 'ready' && slot.displayedEntry !== entry) {
      this.commitReadyEntry(key, entry);
    } else if (entry.status === 'failed') {
      this.notifyError(key, entry);
    } else {
      this.pump();
    }
  }

  releaseSlot(ownerId: string, slotId: string): void {
    const key = slotKey(ownerId, slotId);
    const slot = this.slots.get(key);
    if (slot === undefined) return;

    this.detachDesired(slot, true);
    if (slot.displayedEntry !== null) {
      slot.displayedEntry.displayedSlots.delete(key);
      this.cleanupEntry(slot.displayedEntry, true);
    }
    this.slots.delete(key);
  }

  releaseOwner(ownerId: string): void {
    for (const slot of [...this.slots.values()]) {
      if (slot.request.ownerId === ownerId) {
        this.releaseSlot(ownerId, slot.request.slotId);
      }
    }
  }

  clear(): void {
    for (const entry of this.entries.values()) {
      entry.controller.abort();
      if (entry.objectUrl !== null) {
        this.revokeObjectUrl(entry.objectUrl);
        entry.objectUrl = null;
      }
    }
    this.slots.clear();
    this.entries.clear();
    this.runningEntry = null;
  }

  dispose(): void {
    if (this.disposed) return;
    this.disposed = true;
    this.clear();
  }

  private getOrCreateEntry(sourceUrl: string): QueueEntry {
    const existing = this.entries.get(sourceUrl);
    if (existing !== undefined) return existing;

    const created: QueueEntry = {
      sourceUrl,
      status: 'queued',
      controller: new AbortController(),
      objectUrl: null,
      error: null,
      desiredSlots: new Set(),
      displayedSlots: new Set(),
      errorNotifiedSlots: new Set(),
    };
    this.entries.set(sourceUrl, created);
    return created;
  }

  private detachDesired(slot: SlotState, abortIfOrphaned: boolean): void {
    const entry = this.entries.get(slot.request.url);
    if (entry === undefined) return;
    entry.desiredSlots.delete(slot.key);
    entry.errorNotifiedSlots.delete(slot.key);
    this.cleanupEntry(entry, abortIfOrphaned);
  }

  private cleanupEntry(entry: QueueEntry, abortIfOrphaned: boolean): void {
    if (entry.desiredSlots.size > 0 || entry.displayedSlots.size > 0) return;
    if (entry.status === 'loading') {
      if (abortIfOrphaned) entry.controller.abort();
      return;
    }
    if (entry.objectUrl !== null) {
      this.revokeObjectUrl(entry.objectUrl);
      entry.objectUrl = null;
    }
    this.entries.delete(entry.sourceUrl);
  }

  private entryRank(entry: QueueEntry): readonly [number, number] {
    let priority = Number.MAX_SAFE_INTEGER;
    let sequence = Number.MAX_SAFE_INTEGER;
    for (const key of entry.desiredSlots) {
      const request = this.slots.get(key)?.request;
      if (request === undefined) continue;
      if (
        request.priority < priority ||
        (request.priority === priority && request.sequence < sequence)
      ) {
        priority = request.priority;
        sequence = request.sequence;
      }
    }
    return [priority, sequence];
  }

  private pump(): void {
    if (this.disposed || this.runningEntry !== null) return;
    const next = [...this.entries.values()]
      .filter((entry) => entry.status === 'queued' && entry.desiredSlots.size > 0)
      .sort((left, right) => {
        const [leftPriority, leftSequence] = this.entryRank(left);
        const [rightPriority, rightSequence] = this.entryRank(right);
        return leftPriority - rightPriority || leftSequence - rightSequence;
      })[0];
    if (next === undefined) return;

    next.status = 'loading';
    this.runningEntry = next;
    void this.load(next);
  }

  private async load(entry: QueueEntry): Promise<void> {
    try {
      for (let attempt = 0; attempt < 3; attempt += 1) {
        let candidateObjectUrl: string | null = null;
        try {
          const response = await this.fetchFn(entry.sourceUrl, {
            cache: 'no-store',
            signal: entry.controller.signal,
          });
          if (!response.ok) {
            throw new Error(`Image request failed: ${response.status}`);
          }
          const blob = await response.blob();
          candidateObjectUrl = this.createObjectUrl(blob);
          await this.decodeImage(candidateObjectUrl);
          if (entry.controller.signal.aborted) {
            throw new DOMException('Aborted', 'AbortError');
          }
          entry.objectUrl = candidateObjectUrl;
          candidateObjectUrl = null;
          entry.status = 'ready';
          for (const key of [...entry.desiredSlots]) {
            this.commitReadyEntry(key, entry);
          }
          return;
        } catch (error) {
          if (candidateObjectUrl !== null) {
            this.revokeObjectUrl(candidateObjectUrl);
          }
          if (isAbortError(error) || entry.desiredSlots.size === 0) return;
          if (attempt === 2) {
            entry.status = 'failed';
            entry.error = toError(error);
            for (const key of entry.desiredSlots) {
              this.notifyError(key, entry);
            }
            return;
          }
          await this.sleep(RETRY_DELAYS_MS[attempt], entry.controller.signal);
        }
      }
    } finally {
      if (entry.status === 'loading') entry.status = 'failed';
      if (this.runningEntry === entry) this.runningEntry = null;
      this.cleanupEntry(entry, false);
      this.pump();
    }
  }

  private commitReadyEntry(key: string, entry: QueueEntry): void {
    const slot = this.slots.get(key);
    if (
      slot === undefined ||
      slot.request.url !== entry.sourceUrl ||
      entry.objectUrl === null
    ) {
      return;
    }

    const previous = slot.displayedEntry;
    slot.displayedEntry = entry;
    entry.displayedSlots.add(key);
    try {
      slot.request.onReady({
        sourceUrl: entry.sourceUrl,
        objectUrl: entry.objectUrl,
      });
    } catch (error) {
      void error;
    }

    if (previous !== null && previous !== entry) {
      previous.displayedSlots.delete(key);
      this.cleanupEntry(previous, true);
    }
  }

  private notifyError(key: string, entry: QueueEntry): void {
    if (entry.error === null || entry.errorNotifiedSlots.has(key)) return;
    const slot = this.slots.get(key);
    if (slot === undefined || slot.request.url !== entry.sourceUrl) return;
    entry.errorNotifiedSlots.add(key);
    try {
      slot.request.onError(entry.error);
    } catch (error) {
      void error;
    }
  }
}
```

この実装では、同一slotのURL変更は旧表示参照を維持しつつ旧実行結果を通知せず、owner/slotの明示解放だけが不要な実行中entryをabortする。

- [ ] **Step 5: logicテストを通す**

Run from repository root:

```powershell
npm --prefix frontend run test:logic -- src/main/components/progress/progressImageLoader.test.ts
```

Expected: 8ケースがすべて `PASS`。未処理Promise、unhandled rejection、Object URL二重解放、同一requestによる再通知ループがない。

- [ ] **Step 6: 今回の新規2ファイルだけをコミットする**

```powershell
git add -- frontend/src/main/components/progress/progressImageLoader.ts frontend/src/main/components/progress/progressImageLoader.test.ts
git diff --cached --check
git diff --cached --name-status
git diff --cached -- frontend/src/main/components/progress/progressImageLoader.ts frontend/src/main/components/progress/progressImageLoader.test.ts
git commit -m "feat: add prioritized progress image loader"
```

Expected: 新規2ファイルだけがコミットされ、既存のProgressDialog差分は含まれない。

---

### Task 5: ProgressDialogを明示キューと準備済み画像へ接続する

**Files:**
- Modify: `frontend/src/main/components/progress/ProgressDialog.component.test.ts:1-52, 283-374, 535-654, 783-987`
- Create: `frontend/src/main/components/progress/ProgressDialog.integration.test.ts`
- Modify: `frontend/src/main/components/progress/ProgressDialog.svelte:1-87, 307-403, 447-496, 615-638, 711-851, 954-973, 1196-1203, 1270-1440, 1564-1670`

**Interfaces:**
- Consumes: Task 4の `ProgressImageLoader`、`ProgressImageRequest`、`ProgressImageReady`、`PROGRESS_IMAGE_PRIORITY`。
- Produces: SSE状態から5段階の画像要求を作り、取得・デコード済みObject URLだけをメイン枠、シークバー、完了カードへ渡すUI。

- [ ] **Step 1: componentテストでローダー通知前後の表示契約を固定する**

`ProgressDialog.component.test.ts` ではローダーmoduleをstub化し、既存のstatus API用 `fetchMock` と画像取得を混在させない。ファイル先頭へ次のharnessを追加する。

```ts
const imageLoaderHarness = vi.hoisted(() => ({
  requests: new Map<string, {
    url: string;
    ownerId: string;
    slotId: string;
    onReady: (image: { sourceUrl: string; objectUrl: string }) => void;
    onError: (error: Error) => void;
  }>(),
  releaseSlot: vi.fn(),
  releaseOwner: vi.fn(),
  clear: vi.fn(),
  dispose: vi.fn(),
}));

vi.mock('./progressImageLoader', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./progressImageLoader')>();
  return {
    ...actual,
    ProgressImageLoader: class {
      request(request: {
        url: string;
        ownerId: string;
        slotId: string;
        onReady: (image: { sourceUrl: string; objectUrl: string }) => void;
        onError: (error: Error) => void;
      }): void {
        imageLoaderHarness.requests.set(`${request.ownerId}\u0000${request.slotId}`, request);
      }

      releaseSlot(ownerId: string, slotId: string): void {
        imageLoaderHarness.requests.delete(`${ownerId}\u0000${slotId}`);
        imageLoaderHarness.releaseSlot(ownerId, slotId);
      }

      releaseOwner(ownerId: string): void {
        imageLoaderHarness.releaseOwner(ownerId);
      }

      clear(): void {
        imageLoaderHarness.requests.clear();
        imageLoaderHarness.clear();
      }

      dispose(): void {
        imageLoaderHarness.requests.clear();
        imageLoaderHarness.dispose();
      }
    },
  };
});
```

`beforeEach` で `requests` と各mockをclearする。既存の「動画枠とシークバーは1分刻みの同じ縮小フレームURLを使う」を次へ置き換える。

```ts
it('デコード成功通知前はメイン画像を切り替えず通知後にObject URLを表示する', async () => {
  mockIdleStatusResponse();
  render(ProgressDialog, { props: { isOpen: true } });
  emitProgressEvent({
    kind: 'start',
    total: 1,
    completed: 0,
    items: ['テスト動画'],
    clips: [
      {
        group_index: 0,
        date_label: '06/27\n00:00～',
        match_name: 'Xマッチ',
        rule_name: 'ガチエリア',
        video_assets: [
          {
            video_id: 'recorded/sample.mkv',
            duration_seconds: 240,
            judgement: 'WIN',
            stage_name: 'SCORCH_GORGE',
            kill: 5,
            death: 2,
            special: 3,
            gold_medals: 1,
            silver_medals: 2,
            rate: null,
          },
        ],
      },
    ],
  });
  emitProgressEvent({
    kind: 'item_stage',
    total: 1,
    completed: 0,
    message: '結合中',
    item_index: 0,
    item_key: 'concat',
    item_label: '動画結合',
    progress_percent: 25,
  });

  await vi.waitFor(() => {
    expect(imageLoaderHarness.requests.has('progress-dialog\u0000main-live')).toBe(true);
  });
  expect(screen.queryByTestId('progress-main-image')).not.toBeInTheDocument();

  const request = imageLoaderHarness.requests.get('progress-dialog\u0000main-live');
  request?.onReady({ sourceUrl: request.url, objectUrl: 'blob:main-ready' });

  await vi.waitFor(() => {
    expect(screen.getByTestId('progress-main-image')).toHaveAttribute('src', 'blob:main-ready');
  });
});
```

次のcomponentケースも追加・更新する。

- `新しいメイン画像の取得中と最終失敗後も最後の成功画像を維持する`
- `シークバー画像の失敗は他の成功画像を消さない`
- `項目完了とダイアログ終了で画像slotを解放する`
- `完成サムネイルの成功時だけ差し替え失敗時は最後のゲームフレームを維持する`

各ケースは次の通知順とassertへ固定する。

- 最後の成功画像保持: `main-live` のt=0要求へ `blob:live-0` を通知し、進捗を25%から50%へ更新する。新しい `main-live` 要求へ成功通知を送らず `onError()` を送り、`progress-main-image` が `blob:live-0` のままであることをassertする。
- 局所失敗: 2クリップfixtureでメインと `clip:0` を成功させ、`clip:1` だけ `onError()` にする。メインと `clip:0` のObject URLが残り、`clip:1` の前景画像だけが存在しないことをassertする。
- 解放: `item_finish` で対象行をdismissした後にそのownerの全slotが `releaseSlot()` され、ダイアログを閉じると `clear()`、componentをunmountすると `dispose()` が各1回呼ばれることをassertする。
- 完成サムネイル: `main-live` を成功させた後にthumbnail stageを送り、`main-final` の失敗時はliveを維持する。その後の新しいitemで `main-final` を成功させた時だけfinalのObject URLへ切り替わることをassertする。

- [ ] **Step 2: 実ローダーとの5段階順序をintegrationテストへ固定する**

新規 `ProgressDialog.integration.test.ts` はmoduleをmockせず、componentテストと同じEventSource helperをローカル定義する。`Image`、Object URL、status APIと画像APIを次の形でstubする。

```ts
const imageRequestUrls: string[] = [];
let objectUrlIndex = 0;

vi.stubGlobal(
  'Image',
  class {
    src = '';
    async decode(): Promise<void> {}
  }
);
vi.spyOn(URL, 'createObjectURL').mockImplementation(() => `blob:image-${++objectUrlIndex}`);
vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined);
vi.stubGlobal(
  'fetch',
  vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.includes('/frame') || url.startsWith('/thumbnails/')) {
      expect(init?.cache).toBe('no-store');
      expect(init?.signal).toBeInstanceOf(AbortSignal);
      imageRequestUrls.push(url);
      return new Response(new Blob(['png'], { type: 'image/png' }), { status: 200 });
    }
    return new Response(
      JSON.stringify({
        state: 'idle',
        sleepAfterUploadEnabled: false,
        sleepAfterUploadEffective: false,
      }),
      { status: 200, headers: { 'Content-Type': 'application/json' } }
    );
  })
);
```

3項目・計4クリップの進捗payloadは次へ固定する。

```ts
function videoAsset(videoId: string) {
  return {
    video_id: videoId,
    duration_seconds: 240,
    judgement: 'WIN',
    stage_name: 'SCORCH_GORGE',
    kill: 5,
    death: 2,
    special: 3,
    gold_medals: 1,
    silver_medals: 2,
    rate: null,
  };
}

emitProgressEvent({
  kind: 'start',
  total: 3,
  completed: 0,
  items: ['active', 'next', 'later'],
  clips: [
    {
      group_index: 0,
      date_label: '06/27\n00:00～',
      match_name: 'Xマッチ',
      rule_name: 'ガチエリア',
      video_assets: [
        videoAsset('recorded/active-a.mkv'),
        videoAsset('recorded/active-b.mkv'),
      ],
    },
    {
      group_index: 1,
      date_label: '06/27\n01:00～',
      match_name: 'Xマッチ',
      rule_name: 'ガチエリア',
      video_assets: [videoAsset('recorded/next.mkv')],
    },
    {
      group_index: 2,
      date_label: '06/27\n02:00～',
      match_name: 'Xマッチ',
      rule_name: 'ガチエリア',
      video_assets: [videoAsset('recorded/later.mkv')],
    },
  ],
});
emitProgressEvent({
  kind: 'item_stage',
  total: 3,
  completed: 0,
  message: '結合中',
  item_index: 0,
  item_key: 'concat',
  item_label: '動画結合',
  progress_percent: 0,
});
```

同一microtask内で上記2イベントを送ってから、次をassertする。

```ts
await vi.waitFor(() => expect(imageRequestUrls).toHaveLength(5));
expect(imageRequestUrls).toEqual([
  '/api/assets/recorded/recorded%2Factive-a.mkv/frame?t=0&w=960',
  '/api/assets/recorded/recorded%2Factive-a.mkv/frame?t=60&w=960',
  '/api/assets/recorded/recorded%2Factive-b.mkv/frame?t=60&w=960',
  '/api/assets/recorded/recorded%2Fnext.mkv/frame?t=60&w=960',
  '/api/assets/recorded/recorded%2Flater.mkv/frame?t=60&w=960',
]);
```

2ケース目では画像応答を500にした後、次の完了イベントを送り、閉じるボタンが有効になることをassertする。

```ts
emitProgressEvent({
  kind: 'finish',
  total: 3,
  completed: 3,
  success: true,
  message: '自動編集が完了しました',
});
await vi.waitFor(() => {
  expect(screen.getByRole('button', { name: '閉じる' })).toBeEnabled();
});
```

- [ ] **Step 3: componentとintegrationの新契約が現実装で失敗することを確認する**

Run from repository root:

```powershell
npm --prefix frontend run test:component -- src/main/components/progress/ProgressDialog.component.test.ts
npm --prefix frontend run test:integration -- src/main/components/progress/ProgressDialog.integration.test.ts
```

Expected: componentはローダーrequestも `progress-main-image` も存在せず `FAIL`。integrationは生URLをDOMへ直接渡して同時取得するため順序・`no-store` 契約で `FAIL`。

- [ ] **Step 4: 準備済み画像状態と要求reconcileを追加する**

`ProgressDialog.svelte` へ次をimportする。

```ts
import {
  PROGRESS_IMAGE_PRIORITY,
  ProgressImageLoader,
  type ProgressImageReady,
  type ProgressImageRequest,
} from './progressImageLoader';
```

`CompletedVideo` はsource URLを保持し、描画時だけ準備済みObject URLを引く形へ変更する。

```ts
interface CompletedVideo {
  id: string;
  title: string;
  thumbnailSourceUrl: string;
  fallbackSourceUrl: string;
  dateLabel: string;
}

interface RequestedImageSlot {
  ownerId: string;
  slotId: string;
}

let readyImages = $state<Record<string, ProgressImageReady>>({});
let requestedImageSlots = new Map<string, RequestedImageSlot>();
const progressImageLoader = new ProgressImageLoader();

function progressImageKey(ownerId: string, slotId: string): string {
  return `${ownerId}\u0000${slotId}`;
}

function setReadyImage(ownerId: string, slotId: string, image: ProgressImageReady): void {
  readyImages = { ...readyImages, [progressImageKey(ownerId, slotId)]: image };
}

function readyImageUrl(ownerId: string, slotId: string): string {
  return readyImages[progressImageKey(ownerId, slotId)]?.objectUrl ?? '';
}
```

要求の登録と不要slot解放を1関数へ集約する。

```ts
function reconcileProgressImageRequests(requests: ProgressImageRequest[]): void {
  const nextSlots = new Map<string, RequestedImageSlot>();
  for (const request of requests) {
    const key = progressImageKey(request.ownerId, request.slotId);
    nextSlots.set(key, { ownerId: request.ownerId, slotId: request.slotId });
    progressImageLoader.request(request);
  }

  const nextReadyImages = { ...readyImages };
  for (const [key, slot] of requestedImageSlots) {
    if (nextSlots.has(key)) continue;
    progressImageLoader.releaseSlot(slot.ownerId, slot.slotId);
    delete nextReadyImages[key];
  }
  requestedImageSlots = nextSlots;
  readyImages = nextReadyImages;
}
```

- [ ] **Step 5: 画面状態を5段階の要求へ変換する**

`buildProgressImageRequests()` を追加する。メインはliveとfinalを別slotにし、final失敗時にもlive参照を保持する。

```ts
function buildProgressImageRequests(): ProgressImageRequest[] {
  const requests: ProgressImageRequest[] = [];
  let sequence = 0;
  const addRequest = (
    ownerId: string,
    slotId: string,
    url: string,
    priority: ProgressImageRequest['priority']
  ): void => {
    if (!url) return;
    requests.push({
      ownerId,
      slotId,
      url,
      priority,
      sequence: sequence++,
      onReady: (image) => setReadyImage(ownerId, slotId, image),
      onError: (error) => {
        void error;
      },
    });
  };

  addRequest(
    'progress-dialog',
    'main-live',
    currentMergingInfo.image,
    PROGRESS_IMAGE_PRIORITY.MAIN
  );
  const finalSourceUrl =
    currentItem && finalThumbnailReady ? getEditedThumbnailUrl(currentItem) : '';
  addRequest(
    'progress-dialog',
    'main-final',
    finalSourceUrl,
    PROGRESS_IMAGE_PRIORITY.MAIN
  );

  for (const item of visibleEditItems) {
    const itemIndex = editItems.indexOf(item);
    const ownerId = `edit-item:${item.clips?.video_assets[0]?.video_id ?? item.title}`;
    const clips = item.clips?.video_assets ?? [];
    for (const [clipIndex, clip] of clips.entries()) {
      let priority = PROGRESS_IMAGE_PRIORITY.LATER_ITEM;
      if (itemIndex === activeIndex && clipIndex === currentMergingInfo.clipIndex) {
        priority = PROGRESS_IMAGE_PRIORITY.ACTIVE_CLIP;
      } else if (itemIndex === activeIndex) {
        priority = PROGRESS_IMAGE_PRIORITY.ACTIVE_ITEM_REMAINDER;
      } else if (activeIndex !== null && itemIndex === activeIndex + 1) {
        priority = PROGRESS_IMAGE_PRIORITY.NEXT_ITEM;
      }
      addRequest(
        ownerId,
        `clip:${clipIndex}:${clip.video_id}`,
        buildProgressFrameUrl(clip.video_id, getReusableClipFrameSeconds(clip)),
        priority
      );
    }
  }

  for (const video of completedVideos) {
    const ownerId = `completed:${video.id}`;
    addRequest(
      ownerId,
      'fallback',
      video.fallbackSourceUrl,
      PROGRESS_IMAGE_PRIORITY.LATER_ITEM
    );
    addRequest(
      ownerId,
      'final-thumbnail',
      video.thumbnailSourceUrl,
      PROGRESS_IMAGE_PRIORITY.LATER_ITEM
    );
  }
  return requests;
}
```

`$effect` で `isOpen`、表示項目、active index、current frame、final thumbnail、completed videosの変化を読み、`untrack()` 内でreconcileする。閉じた場合は `progressImageLoader.clear()`、`requestedImageSlots.clear()`、`readyImages = {}`、`lastPreviewImage = ''` を実行する。`onDestroy()` では `progressImageLoader.dispose()` を追加する。

- [ ] **Step 6: 準備済みObject URLだけを表示する**

`activePreview` は生URLでなく次のready画像を選ぶ。

```ts
const activePreview = $derived.by<PreviewState | null>(() => {
  if (!currentItem) return null;
  const liveReady = readyImages[progressImageKey('progress-dialog', 'main-live')];
  const finalReady = readyImages[progressImageKey('progress-dialog', 'main-final')];
  const finalSourceUrl = finalThumbnailReady ? getEditedThumbnailUrl(currentItem) : '';
  const ready = finalReady?.sourceUrl === finalSourceUrl ? finalReady : liveReady;
  if (!ready) return null;

  const videoId = currentItem.clips?.video_assets[0]?.video_id ?? `group_${activeIndex}`;
  const isFinalImage = Boolean(finalSourceUrl && ready.sourceUrl === finalSourceUrl);
  const revealProgress = isFinalImage ? finalThumbnailRevealProgress : 1;
  return {
    id: videoId,
    image: ready.objectUrl,
    isFinal: isFinalImage,
    revealProgress,
    finalSettled: isFinalImage && revealProgress >= 1,
    fallbackImage: isFinalImage ? liveReady?.objectUrl : undefined,
  };
});
```

メインの `<img>` に `data-testid="progress-main-image"` を付け、`rememberPreviewImage`、`handlePreviewImageError`、`handleFinalThumbnailError` とDOM `onload` / `onerror` を削除する。最後の成功画像はloaderの `onReady` 通知からだけ更新する。

シークバーの `thumbnailUrl` は次へ変更する。

```ts
{@const ownerId = `edit-item:${item.clips?.video_assets[0]?.video_id ?? item.title}`}
{@const slotId = `clip:${clipIdx}:${clip.video_id}`}
{@const thumbnailUrl = readyImageUrl(ownerId, slotId)}
```

`thumbnailUrl` が空なら `border-image-source` を指定せず、2枚の前景 `<img>` も描画しない。成功した1つのObject URLを既存の背景・暗色前景・明色前景で共有する。

完了カードの画像は次のhelperで選ぶ。

```ts
function completedVideoImage(video: CompletedVideo): string {
  const ownerId = `completed:${video.id}`;
  return (
    readyImageUrl(ownerId, 'final-thumbnail') ||
    readyImageUrl(ownerId, 'fallback')
  );
}
```

`video.thumbnail` を使う全描画・style計算を `completedVideoImage(video)` へ置き換える。`completedVideos` 追加時の値は次へ固定する。

```ts
const liveReady = readyImages[progressImageKey('progress-dialog', 'main-live')];
completedVideos = [
  ...completedVideos,
  {
    id: videoId,
    title: item.title,
    thumbnailSourceUrl: getEditedThumbnailUrl(item),
    fallbackSourceUrl: liveReady?.sourceUrl ?? '',
    dateLabel: item.clips?.date_label.replace('\n', ' ') ?? '',
  },
];
```

954–967行の `new Image()` effectと1196–1203行の隠しpreload `<img>` を削除する。生の `/frame` URLまたは `/thumbnails/` URLを `src`、`background-image`、`border-image-source` へ直接渡す箇所を残さない。

- [ ] **Step 7: componentとintegrationを通す**

Run from repository root:

```powershell
npm --prefix frontend run test:component -- src/main/components/progress/ProgressDialog.component.test.ts
npm --prefix frontend run test:integration -- src/main/components/progress/ProgressDialog.integration.test.ts
```

Expected: 両ファイルがすべて `PASS`。画像失敗時も進捗イベント処理は継続し、画像のfetchは常に1件ずつ実行される。

- [ ] **Step 8: 今回のハンクだけをコミットする**

```powershell
git add -- frontend/src/main/components/progress/ProgressDialog.integration.test.ts
git add -p -- frontend/src/main/components/progress/ProgressDialog.svelte frontend/src/main/components/progress/ProgressDialog.component.test.ts
git diff --cached --check
git diff --cached --name-status
git diff --cached -- frontend/src/main/components/progress/ProgressDialog.svelte frontend/src/main/components/progress/ProgressDialog.component.test.ts frontend/src/main/components/progress/ProgressDialog.integration.test.ts
git commit -m "fix: load progress images by display priority"
```

Expected: 新規integrationテストと、既存2ファイルの画像読み込みハンクだけ。responsive layout、upload animation、cancel APIの既存差分を含めない。

---

### Task 6: 実ブラウザーで画像失敗が編集完了を止めないことを証明する

> **実装時の計画修正（2026-07-20）:** 「最初のframe成功後に後続frameを失敗」させる方式は、
> 同じ動画のメイン枠とシークバーが別時刻を要求すること、および実行中の結合進捗で優先要求が変わることから、
> 表示すべきメイン画像まで失敗対象にし得る。さらに完成サムネイル要求を表示確認までgateすると、1件直列の
> loaderを占有してシークバー待ちと相互待ちになる。このためworkflow保証は、frame APIをすべてno-store成功、
> 完成サムネイルAPIを即時500とし、同一処理内で「可視メイン枠と可視シークバーがblob表示」「画像500が実発生」
> 「process statusがsucceeded」を順不同で確認する方式へ変更した。厳密な優先順と再試行順はlogic/integrationで担保する。

**Files:**
- Modify: `frontend/tests/e2e/edit-upload-workflow.spec.ts:1-61`

**Interfaces:**
- Consumes: 実ブラウザーの進捗ダイアログと編集・アップロードworkflow。
- Produces: 最初のフレーム成功後に後続フレームAPIを500へしても完了ダイアログへ到達する回帰保証。

- [ ] **Step 1: frame routeを成功から失敗へ切り替えるworkflowテストを書く**

有効な1×1 PNGを定数化する。

```ts
const previewPng = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=',
  'base64'
);
let frameRequestCount = 0;
```

`beforeEach` に次のrouteを追加する。

```ts
frameRequestCount = 0;
await page.route('**/api/assets/recorded/**/frame?*', async (route) => {
  frameRequestCount += 1;
  if (frameRequestCount === 1) {
    await route.fulfill({
      status: 200,
      contentType: 'image/png',
      headers: { 'Cache-Control': 'no-store' },
      body: previewPng,
    });
    return;
  }
  await route.fulfill({ status: 500, contentType: 'application/json', body: '{}' });
});
```

既存テスト名を `進捗ダイアログはフレーム表示後に画像APIが失敗しても編集・アップロードを完了する` へ変更し、進捗ダイアログ表示後に次を追加する。

```ts
await expect(progressDialog.getByTestId('progress-main-image')).toHaveAttribute(
  'src',
  /^blob:/,
  { timeout: 60_000 }
);
```

既存の完了ダイアログassert後に次を追加する。

```ts
expect(frameRequestCount).toBeGreaterThan(1);
```

厳密な5段階順、250/750ミリ秒、Object URL解放はlogic/integrationの責務とし、このworkflowでは重複assertしない。

- [ ] **Step 2: 対象workflowを実行する**

Run from repository root:

```powershell
$env:SPLAT_REPLAY_E2E_MODE = 'smoke'
try {
  npm --prefix frontend run test:e2e -- tests/e2e/edit-upload-workflow.spec.ts -g "進捗ダイアログはフレーム表示後に画像APIが失敗しても編集・アップロードを完了する"
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally {
  Remove-Item Env:SPLAT_REPLAY_E2E_MODE -ErrorAction SilentlyContinue
}
```

Expected: `PASS`。少なくとも1枚がblob URLで表示され、その後の画像500と再試行中にも編集・アップロードが進み、完了ダイアログへ到達する。workflow自体は現実装でも完了まで進む可能性があるため、REDを強制せずcharacterization結果を記録する。

- [ ] **Step 3: workflow変更だけをコミットする**

```powershell
git add -p -- frontend/tests/e2e/edit-upload-workflow.spec.ts
git diff --cached --check
git diff --cached --name-status
git diff --cached -- frontend/tests/e2e/edit-upload-workflow.spec.ts
git commit -m "test: keep editing through preview image failures"
```

Expected: `edit-upload-workflow.spec.ts` のframe routeとassertだけ。他のE2E差分を含めない。

---

### Task 7: 意味ベース入口と全体ゲートを通す

**Files:**
- Verify only: production、logic、component、integration、contract、workflowの全変更

**Interfaces:**
- Consumes: Tasks 1–6のコミット。
- Produces: 静的整合、分類別保証、主要workflowがすべて成功した検証記録。

- [ ] **Step 1: 速い意味ベース入口から順に実行する**

Run from repository root:

```powershell
task.exe test:frontend:logic
task.exe test:backend
task.exe test:frontend:component
task.exe test:frontend:integration
task.exe test:contract
```

Expected: すべて `PASS`。`FramePreviewRequest` / `warm_frames` の残存import、TypeScript `any`、画像キューの未解放Promiseがない。

- [ ] **Step 2: 基本テスト入口と最低完了ゲートを実行する**

Run from repository root:

```powershell
task.exe test
task.exe verify
```

Expected: 両方 `PASS`。`verify` のformat、lint、type-check、import-lint、testsに警告・失敗がない。

- [ ] **Step 3: workflow smokeを最後に実行する**

Run from repository root:

```powershell
task.exe test:workflow:smoke
```

Expected: `PASS`。進捗画像が成功時に段階表示され、画像失敗時にも編集・アップロード完了へ到達する。

- [ ] **Step 4: 差分とキャッシュ非依存を最終確認する**

```powershell
git diff --check
git status --short
$symbolMatches = rg -n "FramePreviewRequest|warm_frames|frame_preview_cache" backend/src backend/tests
if ($LASTEXITCODE -eq 0) { $symbolMatches; throw 'Removed preview symbols remain' }
if ($LASTEXITCODE -gt 1) { exit $LASTEXITCODE }
$cacheMatches = rg -n "progress_frames" backend/src
if ($LASTEXITCODE -eq 0) { $cacheMatches; throw 'Production cache reference remains' }
if ($LASTEXITCODE -gt 1) { exit $LASTEXITCODE }
$preloadMatches = rg -n "new Image\(|alt=\"preload first clip\"" frontend/src/main/components/progress/ProgressDialog.svelte
if ($LASTEXITCODE -eq 0) { $preloadMatches; throw 'Implicit preload remains' }
if ($LASTEXITCODE -gt 1) { exit $LASTEXITCODE }
git log -6 --oneline
```

Expected:

- `git diff --check` は出力なし。
- `rg` 3件は一致なしで終了コード1。
- 今回のコミットはTasks 1–6の意図したファイルだけを含む。
- 作業開始前から存在したユーザー差分は未ステージのまま保持される。
- `.progress_frames` の既存ディレクトリを削除した差分、新しい依存、生成物、一時デバッグファイルがない。

- [ ] **Step 5: 完了報告を作る**

`docs/test_strategy.md` の完了契約に従い、次を日本語で報告する。

- 変更分類: `static / logic / component / integration / contract / workflow`
- 守った保証: 5段階優先、同時実行1、no-store、キャッシュ非依存、画像失敗時の編集継続
- 実行した個別テスト・意味ベース入口・全体ゲートと結果
- 省略した入口: performance、benchmark、release、workflow full、coverage。性能閾値・リリース総合・網羅率変更ではないため
- 未確認事項がある場合は、対象と理由を明示する
