# AGENTS.md

このドキュメントは、コーディングエージェントが本リポジトリを**安全かつ高速**に変更するための
**always-on ルール**だけを定義する。
詳細な手順や反復ワークフローは、関連ドキュメントと repo-local skill に委譲する。

## 役割 / 目的

- 目的: スプラトゥーン 3 のプレイ映像を自動で録画・編集・アップロードするアプリを安全に改善する。
- 文章・コメントは**日本語**で記述する。
- **不明な事実は断定しない**（`未確認` / `推測` / `暫定` を明記）。

## プロジェクトマップ（主要ディレクトリ）

- `backend/`: Python バックエンド（Clean Architecture）。
- `frontend/`: Svelte + Vite のフロントエンド。
- `docs/`: 開発・運用ドキュメント。
- `.codex/skills/`: repo 固有の反復ワークフロー。
- `Taskfile.yml`: 主要コマンドの統合窓口。

## Always-On ルール

- 変更前に**目的・成功条件・責務・層**を言語化し、影響範囲を推定する。
- **Clean Architecture 準拠**（依存方向: `interface → application → domain`）。
- **レイヤ逆依存を禁止**（import-lint で検出される）。
- **型注釈は必須**（Python は暗黙 Any を作らない / TypeScript は `any` 回避）。
- 既存設計の意図が不明な場合は**調査優先**。独断で設計を確定しない。
- 新規実装は原則 `backend/src/splat_replay/<layer>/` または `frontend/src/` に配置する。
- 生成物・一時物はコミットしない（例: `dist/`, `backend/build/`, `frontend/dist/`, `frontend/src/generated/`, `frontend/test-results/`）。
- 一時ファイルやデバッグコードは、作成時に削除方法を明記し、作業終了前に撤去する。
- 秘密情報・認証情報は**絶対にコミットしない**。
- 失敗モード（破壊的変更・外部依存）を明示する。

## テストと検証

> Windows 環境では、`task` ではなく `task.exe` を明示して実行する。

- `task.exe verify` は完了判定の**最低入口**とする。
- `task.exe test` は backend + frontend unit の**基本テスト入口**とする。
- 振る舞い変更時は、まず `task.exe test` を起点にし、`docs/test_strategy.md` に従って追加の意味ベース入口を選ぶ。
- frontend の UI 変更では、`task.exe test:frontend:component` / `task.exe test:frontend:integration` / `task.exe test:workflow:smoke` の要否を必ず確認する。
- リリース前の総合確認は `task.exe test:release`、性能影響がある場合は `task.exe test:release:performance` を使う。

## ルールの置き場所

- ルート `AGENTS.md`: 全体に常時適用したい原則だけを書く。
- 各レイヤの `AGENTS.md`: backend 各層の責務と禁止事項を書く。
- `frontend/AGENTS.md`: frontend 固有の実装ルールを書く。
- `docs/test_strategy.md`: テスト選定、意味分類、AI エージェントの完了報告を定義する。
- `.codex/skills/*`: release 作成、test 選定、worktree 作成などの**反復ワークフロー**を定義する。

## Ask First（例）

- 大規模リファクタ（層横断、命名の一括変更）。
- 依存追加・削除、ビルド/CI 変更、外部 API 仕様の変更。
- 永続データのスキーマ変更や破壊的な設定変更。

## Never

- レイヤ逆依存の import。
- 主要ループへの長時間ブロッキング I/O 直書き。
- 一時的なデバッグコードの放置。
- フォーマッター / リンター / 型チェックの**警告放置**。

## セルフレビュー（必須）

- 曖昧語を具体化したか（例: 「適切に」→ 何をどうするか明記）。
- 不明な事実を断定していないか（`未確認` / `推測` / `暫定` を付与）。
- 長すぎる説明を分割・圧縮したか。
- 根本原因への対処になっているか。

## 参考（一次情報）

- `README.md`（全体概要 / エンドユーザー向け情報）
- `docs/DEVELOPMENT.md`（開発環境 / テスト実行 / 品質確認）
- `docs/test_strategy.md`（テスト選定の SSOT）
- `Taskfile.yml`（タスク定義）
- `backend/pyproject.toml`（依存・import-lint 設定）
- `frontend/package.json`（frontend コマンド）
- `frontend/AGENTS.md`（frontend 固有ルール）
- `backend/src/splat_replay/domain/AGENTS.md`
- `backend/src/splat_replay/application/AGENTS.md`
- `backend/src/splat_replay/interface/AGENTS.md`
- `backend/src/splat_replay/infrastructure/AGENTS.md`
