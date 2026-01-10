# AGENTS.md

このドキュメントは、コーディングエージェントが本リポジトリを**安全かつ高速**に変更するための最小ルールを定義する。
**短く・強い**指示のみ残し、詳細は関連ドキュメントへ委譲する。

## 役割 / 目的
- 目的: スプラトゥーン 3 のプレイ映像を自動で録画・編集・アップロードするアプリを安全に改善する。
- 文章・コメントは**日本語**で記述する。
- **不明な事実は断定しない**（TODO: 確認 を明記）。

## プロジェクトマップ（主要ディレクトリ）
- `backend/`: Python バックエンド（Clean Architecture）。
- `frontend/`: Svelte + Vite のフロントエンド。
- `docs/`: 開発・運用ドキュメント。
- `Taskfile.yml`: 主要コマンドの統合窓口。

## 設計・品質（普遍ルール）
- **Clean Architecture 準拠**（依存方向: `interface → application → domain`）。
- **レイヤ逆依存を禁止**（import-lint で検出される）。
- **型注釈は必須**（Python は暗黙 Any を作らない / TypeScript は `any` 回避）。
- 既存設計の意図が不明な場合は**調査優先**。独断で設計を確定しない。

詳細ルールは各レイヤの `AGENTS.md` を参照:
- `backend/src/splat_replay/domain/AGENTS.md`
- `backend/src/splat_replay/application/AGENTS.md`
- `backend/src/splat_replay/interface/AGENTS.md`
- `backend/src/splat_replay/infrastructure/AGENTS.md`

## 変更の置き場所 / 手本 / 避けるべきレガシー
- 新規実装は原則 `backend/src/splat_replay/<layer>/` または `frontend/src/` に配置。
- 手本の所在: TODO: 確認（既存の代表実装を `docs/agent/` などに集約する案を検討）。
- 避けるべきレガシー: TODO: 確認（該当箇所が見つかり次第明記）。
- 生成物・一時物はコミットしない（例: `dist/`, `backend/build/`, `frontend/dist/`, `frontend/src/generated/`）。

## 一時ファイル/デバッグコードの扱い
- **作成時に必ず削除方法を明記**する（例: 変更手順やコミット前チェックリストに記載）。
- **作業終了前に必ず撤去**し、`git status` で残骸がないことを確認する。

## コマンド（未検証は TODO 明記）
> **未検証のため TODO**。実行前に環境整備を確認すること。

### 最小（単一チェック）
- TODO: `task lint:backend`
- TODO: `task lint:frontend`

### 中（領域別）
- TODO: `task format:backend`
- TODO: `task format:frontend`
- TODO: `task type-check:backend`
- TODO: `task type-check:frontend`

### 全体（重い）
- TODO: `task verify`（format / lint / type-check / import-lint / test）

## 安全境界（Always / Ask First / Never）
### Always
- 変更前に**目的・責務・層**を言語化し、影響範囲を推定する。
- 秘密情報・認証情報は**絶対にコミットしない**。
- 失敗モード（破壊的変更・外部依存）を明示する。

### Ask First（例）
- 大規模リファクタ（層横断、命名の一括変更）。
- 依存追加・削除、ビルド/CI 変更、外部 API 仕様の変更。
- 永続データのスキーマ変更や破壊的な設定変更。

### Never
- レイヤ逆依存の import。
- 主要ループへの長時間ブロッキング I/O 直書き。
- 一時的なデバッグコードの放置。
- フォーマッター / リンター / 型チェックの**警告放置**。

## セルフレビュー（必須）
- 曖昧語を具体化したか（例: 「適切に」→ 何をどうするか明記）。
- 不明な事実を断定していないか（TODO: 確認 を付与）。
- 長すぎる説明を分割・圧縮したか（普遍ルールのみ残したか）。
- 根本原因への対処になっているか（注意書きの増量だけになっていないか）。

## 参考（一次情報）
- `README.md`（全体概要 / 開発環境）
- `Taskfile.yml`（タスク定義）
- `backend/pyproject.toml`（依存・import-lint 設定）
- `frontend/package.json`（フロントエンドコマンド）
