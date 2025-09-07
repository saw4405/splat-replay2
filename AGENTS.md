# AGENTS.md ガイド

エージェント / Copilot が安全に変更するための最小限ルール集。詳細な設計や数値目標は別ドキュメントへ委譲し、ここでは原則のみを列挙する。

---

## 1. 目的

Clean Architecture と型完全性を守りつつ自動化開発を高速化する共通リファレンス。

## 2. アプリ概要

Nintendo Switch『スプラトゥーン 3』プレイを Windows 11 上で以下を自動化:

- 録画準備 → 自動録画 (画面状態判定 + メタ情報抽出)
- 自動編集 (不要区間トリミング等)
- 自動アップロード (YouTube)
- 終了後スリープ (オプション)
  モード: フル自動 / 既存録画の編集+アップロード / GUI 手動操作 (開始・中断・再開・停止)。

### 2.1 ランタイム

- OS / Shell: Windows 11 + PowerShell
- Python: `.python-version` を参照 (その記載バージョンに追随)
- 仮想環境: `./.venv` を有効化後 `uv sync`
- 主要コマンド:

```
uv sync
uv run ruff check .
uv run mypy --strict src
uv run pytest -q
```

## 3. 基本原則

- 層依存: interface → application → domain。infrastructure はポート実装として注入。
- `uv` で依存管理。`pip install` 禁止。
- 型注釈 100% 必須 (公開 / 非公開 / ローカル関数含む)。`Any` / 無理由 `# type: ignore` 禁止。
- フォーマット & Lint: Ruff。型検査: `mypy --strict`。テスト: `pytest`。
- ログ: `structlog` JSON。過剰ログ禁止。
- 設定: `config/` 下の `*.toml` / `*.yaml`。Pydantic `BaseSettings` 使用。
- 一時/デバッグコードをコミットしない。

### 3.1 レイヤ / パス規則

- `src/domain` は `application` / `infrastructure` を import 禁止
- `src/application` は `infrastructure` を import 禁止
- `src/interface` は application のユースケース呼び出しのみ (infrastructure 直接参照禁止)
- ポート定義: `application.interfaces.*`
- アダプタ実装: `infrastructure.adapters.*`

### 3.2 ディレクトリ確認

コマンド実行前に `pwd` / `Get-Location` でリポジトリルートにいることを必ず確認し、相対パスはルート基準で記述する。

## 4. 作業フロー

前 (着手前):

1. ルートにいるか確認 (`pwd` / `Get-Location`)。
2. 仮想環境有効化 → `uv sync`。
3. `uv run pytest -q` Green。
4. 既存ポート/型の再利用を検索。
5. 仕様書 (`docs/*.md`) をざっと確認。

後 (PR 前):

1. `uv run ruff format .` 差分なし。
2. `uv run ruff check .` / `uv run mypy --strict src` エラーゼロ。
3. `uv run pytest -q` Green 維持。
4. 変更が大きければ ADR & CHANGELOG 更新。
5. 不要ファイル/ログ削除。

## 5. 禁止事項

- 無理由 `# type: ignore` / 安易な `Any`
- `pip install` / グローバル環境前提コード
- 層逆方向 import
- 長時間ブロッキング I/O を主要ループへ直書き
- 過剰ログ (特に高頻度ループ内)
- 編集理由のみのコメントをコードへ残す行為

## 6. キーワード

Clean Architecture / uv / Ruff / mypy --strict / structlog / no Any / no type:ignore / Pydantic settings / adapters & ports
