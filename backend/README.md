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
- Windows 11 または Apple Silicon 搭載 macOS（Windows 専用の実行依存は Windows にのみインストールされます）
- macOS は PyAudio のビルドに PortAudio が必要です。[macOS の開発環境セットアップ](../docs/DEVELOPMENT.md#apple-silicon-搭載-macos-での開発環境セットアップ)を参照してください。

以下の Task コマンドは Windows では `task.exe`、macOS では `task` を使います。

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

uv run python ../scripts/run-backend-pytest.py -q
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

- `task.exe verify` は frontend も含む全体確認です。実行条件は [テスト戦略](../docs/test_strategy.md) に従います。
- 対象を絞る場合は、`scripts/run-backend-pytest.py` にテストファイルや node ID を指定します。

## テストと検証

- 既定の backend テスト: `task.exe test:backend`。対象指定は `backend` で `uv run python ../scripts/run-backend-pytest.py -q <対象>` を実行します。
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

Windows:

```powershell
netstat -ano | findstr :8000
```

macOS:

```sh
lsof -nP -iTCP:8000 -sTCP:LISTEN
```

使用中のアプリを確認してください。Splat Replay が稼働中の場合は、録画・後処理の完了を待ってメニューから完全終了します。別のアプリを使い続ける場合は、開発サーバーのポートを変更してください。

### import-lint が失敗する

レイヤ逆依存の可能性があります。`domain`, `application`, `interface`, `infrastructure` の依存方向を見直してください。ルールの根拠は [`backend/pyproject.toml`](./pyproject.toml) の `tool.importlinter.contracts` と各層の `AGENTS.md` にあります。
