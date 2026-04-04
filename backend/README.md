# Splat Replay Backend

Splat Replay の backend パッケージです。Python 3.13 / uv を前提に、録画・編集・アップロードの業務ロジック、FastAPI ベースの API、各種外部連携を提供します。

この README では、backend のローカル開発・起動・検証だけを扱います。リポジトリ全体の開発フローは [`docs/DEVELOPMENT.md`](../docs/DEVELOPMENT.md)、利用者向けの外部ツール設定は [`docs/usage.md`](../docs/usage.md) を参照してください。

## この README の責務

- backend の依存関係インストール
- backend 開発サーバーの起動
- backend の検証・テスト
- backend の層構成と責務の概要

## バックエンドの役割

- 自動録画・編集・アップロードの業務ロジックを実行する
- FastAPI / SSE / プレビュー取得 API を通して UI や外部クライアントに機能を公開する
- OBS、FFmpeg、Tesseract、YouTube API などの外部システム連携を仲介する

## 前提条件

- Python 3.13
- `uv`
- Windows 前提の依存を含むため、主な開発環境は Windows 11

補足:

- Python バージョン要件は [`backend/.python-version`](./.python-version) と [`backend/pyproject.toml`](./pyproject.toml) に合わせています。
- 外部ツールや認証設定まで含む動作確認は backend README の範囲外です。必要になった場合は [`docs/usage.md`](../docs/usage.md) を参照してください。

## セットアップ

```powershell
cd backend
uv sync
```

リポジトリ全体をまとめてセットアップする場合は、ルートで `task.exe install` を使用してください。全体手順は [`docs/DEVELOPMENT.md`](../docs/DEVELOPMENT.md) にあります。

## 開発サーバー

### 推奨: ルートから backend 開発サーバーを起動する

```powershell
task.exe dev:backend
```

`uvicorn --reload` で `http://127.0.0.1:8000` に起動します。API ドキュメントは `http://127.0.0.1:8000/docs` です。

### backend ディレクトリから直接起動する

```powershell
cd backend
uv run python -m uvicorn splat_replay.bootstrap.web_app:app --factory --host 127.0.0.1 --port 8000 --reload
```

frontend と接続して動作確認する場合は、backend 単体起動ではなく [`docs/DEVELOPMENT.md`](../docs/DEVELOPMENT.md) の統合起動手順を参照してください。

## 層構成

backend は Clean Architecture を前提に、主に次の層で構成されています。

- `src/splat_replay/domain`: ビジネスルール、エンティティ、値オブジェクト、ドメインイベント
- `src/splat_replay/application`: ユースケース、アプリケーションサービス、ポート定義
- `src/splat_replay/interface`: Web API、CLI、GUI など外部入口
- `src/splat_replay/infrastructure`: 外部サービス・ファイル・OBS などのアダプタ実装
- `src/splat_replay/bootstrap`: DI と起動エントリポイント

依存方向は `interface -> application -> domain` です。詳細な実装ルールは各層の `AGENTS.md` を参照してください。

## 主要コマンド

```powershell
cd backend

uv run pytest -q
uv run ruff format . --check
uv run ruff check .
uv run ty check
uv run lint-imports --no-cache
```

リポジトリルートからの主要入口:

```powershell
task.exe test:backend
task.exe dev:backend
task.exe verify
```

補足:

- `task.exe verify` は frontend も含む全体確認です。
- backend 単体の切り分けでは `uv` 直叩きが便利ですが、日常運用では Taskfile の入口が優先です。

## テストと検証

- 既定の backend テスト: `task.exe test:backend` または `cd backend && uv run pytest -q`
- レイヤ依存の検証: `task.exe import-lint` または `cd backend && uv run lint-imports --no-cache`
- 型検査: `task.exe type-check:backend` または `cd backend && uv run ty check`

契約テストや性能テストを含む追加入口は [`docs/test_strategy.md`](../docs/test_strategy.md) を参照してください。

## トラブルシューティング

### `uv sync` が失敗する

```powershell
cd backend
uv sync --reinstall
```

### `8000` 番ポートが既に使用されている

```powershell
netstat -ano | findstr :8000
taskkill /PID <プロセスID> /F
```

### import-lint が失敗する

レイヤ逆依存の可能性があります。`domain`, `application`, `interface`, `infrastructure` の依存方向を見直してください。ルールの根拠は [`backend/pyproject.toml`](./pyproject.toml) の `tool.importlinter.contracts` と各層の `AGENTS.md` にあります。
