# Interface 層 - 実装ガイドライン

このドキュメントは、インターフェース層を変更する際の **最小ルール** を定義する。

---

## 1. インターフェース層の責務

インターフェース層は **外部からのリクエスト** を受け付け、アプリケーション層に委譲する。

**含むもの**：

- API コントローラー（Web API）
- CLI コマンド
- GUI イベントハンドラー
- WebSocket ハンドラー
- DTO（Data Transfer Object）
- リクエスト / レスポンス変換

**含まないもの**：

- ビジネスルール（domain 層に委譲）
- ユースケースの実装（application 層に委譲）
- 外部システム連携（infrastructure 層に委譲）

---

## 2. 依存関係のルール

### 許可事項

- application 層への依存（use_cases, services）
- domain 層への依存（DTO 変換のための models, events）
- interface 層内の相互参照（routers, schemas, converters）
- Web フレームワーク（fastapi, uvicorn など）

### 禁止事項（絶対 NG）

- infrastructure 層への直接依存（adapters, matchers など）
- DI コンテナの直接操作（bootstrap 以外で configure_container を呼ばない）

---

## 3. 依存性の注入（Composition Root）

- 依存解決は `backend/src/splat_replay/bootstrap` が担当する
- interface 層は **依存を受け取るだけ** にする
- Web では `WebAPIServer` を注入し、CLI では `CliDependencies` を注入する

---

## 4. 実装パターン

### 4.1 Web API（FastAPI）

- リクエスト → DTO → ユースケース
- レスポンス ← DTO ← ユースケース
- エラーは HTTP ステータスコードに変換

```python
from fastapi import APIRouter, HTTPException
from splat_replay.interface.web.schemas import RecordingResponse

# bootstrap から注入される WebAPIServer に依存する

def create_router(server: WebAPIServer) -> APIRouter:
    router = APIRouter(prefix="/api/recording")

    @router.post("/start", response_model=RecordingResponse)
    async def start_recording() -> RecordingResponse:
        try:
            await server.auto_recorder.execute()
            return RecordingResponse(status="started")
        except DomainError as e:
            raise HTTPException(status_code=400, detail=e.message)

    return router
```

### 4.2 CLI（Typer）

- `typer` でコマンド定義
- DI は `CliDependencies` で注入

```python
import typer

app = typer.Typer()

def build_app(deps: CliDependencies) -> typer.Typer:
    @app.command()
    def upload() -> None:
        uc = deps.upload_use_case()
        asyncio.run(uc.execute())

    return app
```

### 4.3 GUI イベントハンドラー

- イベントハンドラーは薄く保つ
- ユースケース呼び出しのみ
- UI 更新はイベントハンドラー内で実行

### 4.4 WebSocket ハンドラー

- イベントストリームをクライアントに転送
- DTO に変換してから送信
- エラーハンドリングを必ず実装

### 4.5 DTO（Data Transfer Object）

- `frozen=True` で不変
- `from_domain()` でドメイン → DTO
- `to_domain()` で DTO → ドメイン（必要な場合）
- `to_dict()` で JSON シリアライズ

---

## 5. エラーハンドリング

### 5.1 ドメイン例外の変換

- ValidationError → 400 Bad Request
- RepositoryError → 500 Internal Server Error
- ExternalServiceError → 503 Service Unavailable

### 5.2 ログ記録

すべてのリクエストとエラーをログに記録する（`structlog`）。

---

## 6. アンチパターン（やってはいけない）

### ❌ インフラ層への直接依存

```python
# NG: infrastructure を直接 import
from splat_replay.infrastructure.adapters import FileVideoRepository
```

### ❌ ビジネスロジックの実装

```python
# NG: バリデーションをコントローラに書く
@router.post("/upload")
async def upload_video(xp: float):
    if not (500 <= xp <= 5500):
        raise HTTPException(status_code=400)
```

---

## 7. チェックリスト

変更前に以下を確認：

- [ ] infrastructure 層をインポートしていないか
- [ ] ビジネスロジックを含んでいないか
- [ ] 依存は bootstrap から注入されているか
- [ ] ドメイン例外を UI 表示可能な形式に変換しているか
- [ ] すべてのリクエストとエラーをログに記録しているか

---

## 8. 参考資料

- ルート `AGENTS.md` - 全体方針とレイヤ間ルール
- `backend/src/splat_replay/domain/AGENTS.md` - ドメイン層ガイドライン
- `backend/src/splat_replay/application/AGENTS.md` - アプリケーション層ガイドライン
- `backend/src/splat_replay/infrastructure/AGENTS.md` - インフラ層ガイドライン
- `docs/internal_design.md` - 設計思想
