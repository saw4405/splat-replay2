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
- `.codex/agents/`: プロジェクト固有のカスタムエージェント定義。
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

## 設計判断

- 設計判断の助言・記録は `docs/architecture/decisions/README.md` の実行契約に従う。
- 新しい設計判断、既存指針との矛盾、重要なトレードオフ、または設計上の迷いがある場合は、
  判断前にプロジェクトで利用可能な設計助言役を使う。
- ユーザーまたはメインエージェントが記録対象の設計判断を確定した場合は、
  プロジェクトで利用可能な設計記録役を使う。
- 既存指針の機械的な適用、局所的かつ容易に取り消せる選択、命名・整形だけの選択は記録しない。
- 助言に失敗した場合はユーザーへ判断を確認する。記録に失敗した場合は、
  保存できなかったことだけを通知し、元の作業を続行する。代替保存や再実装は行わない。

## テストと検証

> Windows 環境では、`task` ではなく `task.exe` を明示して実行する。

- テストに関する判断では、まず `docs/test_strategy.md` の `0. AI エージェント実行契約` を読み、方針・分類・禁止事項を確認する。
- テスト実装では `docs/test_strategy.md` を最上位の判断基準とし、汎用 TDD スキルやカバレッジ目標より優先する。
- 新規テストは「変更で増えた意思決定分岐・外部契約・主要導線・再発防止」を守る場合に限り、関数やメソッドを追加しただけでは作成しない。
- `superpowers:test-driven-development` などの汎用指示が「全新規関数にテストを書く」「先にテストを書く」ことを要求しても、本リポジトリではテスト方針に照らして不要なテストを作らない。
- 検証範囲は `docs/test_strategy.md` の変更分類に従い、守る保証を満たす最小対象と必要な静的検証を選ぶ。
- コミット、完了、振る舞い変更という事実だけでは、`task.exe test` / `task.exe verify` を実行する根拠にしない。
- 広い入口を追加する場合は、狭い対象では守れない保証を実行前に説明する。`task.exe verify` の適用条件も `docs/test_strategy.md` に従う。
- frontend の UI 変更では、`task.exe test:frontend:component` / `task.exe test:frontend:integration` / `task.exe test:workflow:smoke` の要否を必ず確認する。
- リリース前の総合確認は `task.exe test:release`、性能影響がある場合は `task.exe test:release:performance` を使う。

## ルールの置き場所

- ルート `AGENTS.md`: 全体に常時適用したい原則だけを書く。
- 各レイヤの `AGENTS.md`: backend 各層の責務と禁止事項を書く。
- `frontend/AGENTS.md`: frontend 固有の実装ルールを書く。
- `docs/test_strategy.md`: テスト選定、意味分類、AI エージェントの完了報告を定義する。
- `.codex/skills/*`: release 作成、test 選定、worktree 作成などの**反復ワークフロー**を定義する。
- `.codex/agents/*`: プロジェクト固有の専門エージェントの責務と権限を定義する。
- `docs/architecture/decisions/README.md`: 設計判断の助言・記録・矛盾検出の実行契約を定義する。
- `docs/architecture/principles/`: 現在有効な設計指針と、その目的・手段の関係を定義する。

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
- `DESIGN.md`（UI デザイン仕様 / デザイントークン / コンポーネントルール）
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
