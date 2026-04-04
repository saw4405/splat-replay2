# task dev 2画面起動 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `task.exe dev` と `uv run splat-replay web --dev` で、frontend / backend を別ウィンドウ起動しつつホットリロードを維持する。

**Architecture:** `task.exe dev` は backend CLI の `web --dev` に委譲する。Windows では `backend/src/splat_replay/bootstrap/dev_server.py` が PowerShell ウィンドウを 2 つ起動し、frontend は `npm run dev`、backend は `uvicorn --reload` をそれぞれ独立して実行する。

**Tech Stack:** Python 3.13, pytest, PowerShell, Taskfile, Markdown

---

## File Structure

- `backend/tests/test_dev_server.py`
  - Windows 向け起動コマンドの unit test。
- `backend/src/splat_replay/bootstrap/dev_server.py`
  - 実際の 2 画面起動ロジック。
- `Taskfile.yml`
  - `task.exe dev` の入口を CLI 委譲へ更新。
- `docs/DEVELOPMENT.md`
  - 開発フロー説明の更新。
- `frontend/README.md`
  - `web --dev` の Windows 挙動の補足。

### Task 1: Windows 起動仕様を failing test で固定する

**Files:**
- Create: `backend/tests/test_dev_server.py`
- Test: `backend/tests/test_dev_server.py`

- [ ] **Step 1: failing test を追加する**

```python
def test_build_windows_dev_launch_specs_include_reload() -> None:
    ...

def test_launch_windows_dev_servers_open_two_powershell_windows(...) -> None:
    ...
```

- [ ] **Step 2: fail を確認する**

Run: `cd backend && uv run pytest -q tests/test_dev_server.py`

Expected: `ImportError` または `AttributeError` で FAIL。

### Task 2: dev server 本体を最小実装で通す

**Files:**
- Modify: `backend/src/splat_replay/bootstrap/dev_server.py`
- Test: `backend/tests/test_dev_server.py`

- [ ] **Step 1: Windows 向け helper を追加する**

```python
@dataclass(frozen=True)
class DevLaunchSpec:
    ...

def build_windows_dev_launch_specs(repo_root: Path) -> tuple[DevLaunchSpec, ...]:
    ...

def launch_windows_dev_servers(repo_root: Path) -> None:
    ...
```

- [ ] **Step 2: `start_dev_server()` から Windows 分岐で helper を使う**

```python
if os.name == "nt":
    launch_windows_dev_servers(repo_root)
    return
```

- [ ] **Step 3: green を確認する**

Run: `cd backend && uv run pytest -q tests/test_dev_server.py`

Expected: PASS。

### Task 3: `task.exe dev` とドキュメントを実挙動へ更新する

**Files:**
- Modify: `Taskfile.yml`
- Modify: `docs/DEVELOPMENT.md`
- Modify: `frontend/README.md`

- [ ] **Step 1: `task.exe dev` を CLI 委譲に切り替える**

```yaml
dev:
  dir: "{{.BACKEND_DIR}}"
  cmds:
    - uv run splat-replay web --dev
```

- [ ] **Step 2: ドキュメントの注意書きを実挙動へ更新する**

```md
`task.exe dev` は Windows では PowerShell を 2 つ開きます。
```

### Task 4: 検証を実行する

**Files:**
- Test: `backend/tests/test_dev_server.py`
- Test: `Taskfile.yml`
- Test: `docs/DEVELOPMENT.md`

- [ ] **Step 1: unit test を再実行する**

Run: `cd backend && uv run pytest -q tests/test_dev_server.py`

- [ ] **Step 2: 手動起動確認を行う**

Run: `task.exe dev`

Expected: frontend / backend の 2 ウィンドウが開き、backend 側は `--reload` 付きで起動する。

- [ ] **Step 3: 既存品質ゲートを実行する**

Run: `task.exe verify`

Expected: exit code 0。
