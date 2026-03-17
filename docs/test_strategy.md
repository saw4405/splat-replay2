# テスト戦略

## 1. 目的

この文書は、Splat Replay のテスト戦略を「個別ツール」ではなく
「何を保証するか」で整理するための親文書です。
人間の開発者だけでなく、AI エージェントが変更分類から
必要な確認を選ぶときの一次参照としても使います。

今回の戦略は、次の 3 点を同時に満たすことを目的とします。

- 開発時は、変更範囲に応じて最小限の確認だけを素早く回せること
- リリース時は、重い回帰確認を含めて品質重視で確認できること
- 将来、runner、ディレクトリ構成、アーキテクチャが変わっても、
  運用の主語を保てること

## 2. 基本原則

- テストは実装技法ではなく、保証したい性質で分類する
- 開発時は `fast-to-slow` で実行し、必要最小限から始める
- リリース時だけ重い回帰確認を必須にする
- 入口は raw command ではなく Taskfile の意味ベース名を主語にする
- 境界契約が変わる変更は contract テストを先に更新する
- UI を含む主要フローは workflow テストで守る
- 性能回帰は performance テストで別枠管理する

## 3. テスト分類

| 分類          | 守るもの                                   | 現在の主な実装                                                                                                                                   | 備考                                                                                                                                   |
| ------------- | ------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------- |
| `static`      | 形式、型、依存方向                         | `task.exe format`, `task.exe lint`, `task.exe type-check`, `task.exe verify` 内の `import-lint`                                                  | 実装言語や runner が変わっても分類は維持する                                                                                           |
| `logic`       | 純粋関数、変換、軽量 adapter、内部ロジック | backend の通常 `pytest`、frontend の `node:test`                                                                                                 | 高速反復の主力                                                                                                                         |
| `contract`    | API、schema、境界契約                      | `backend/tests/integration/test_api_contract.py`、`backend/tests/test_metadata_contracts.py`、`backend/tests/test_recording_preview_api.py` など | 破壊的変更の早期検知に使う                                                                                                             |
| `workflow`    | UI を含む主要フロー回帰                    | Playwright replay E2E                                                                                                                            | 現在は frontend の component/integration 層未整備のため、この層が UI 回帰も広く担う。smoke は replay を加速し、full は全フレームで回す |
| `performance` | 閾値付き性能回帰                           | `pytest -m perf`                                                                                                                                 | 常時ではなく影響変更時とリリース前に使う                                                                                               |

### 3.1. frontend のテスト層

frontend は **Vitest + @testing-library/svelte** に統一し、以下の 3 層構成でテストを実施します。

- `logic`: 純粋な TypeScript ロジック（`.test.ts` / Vitest）
- `component`: UI コンポーネント単体（`.component.test.ts` / Vitest + Testing Library）
- `integration`: 複数コンポーネント連携（`.integration.test.ts` / Vitest + Testing Library）
- `workflow`: 主要フローの E2E 回帰（`.spec.ts` / Playwright）

**注記**: 以前は logic テストに node:test を使用していましたが、ベストプラクティスに沿って Vitest に統一しました。これによりテストフレームワークの一元化、設定・実行コマンドの統一、カバレッジの統合管理が可能になりました。

## 4. 現在の実装への対応表

### 4.1. backend

- `logic`
  - `uv run pytest -q`
  - 既定で `-m 'not perf'` が有効
- `contract`
  - `backend/tests/integration/test_api_contract.py`
  - `backend/tests/test_metadata_contracts.py`
  - `backend/tests/test_recording_preview_api.py`
- `performance`
  - `uv run pytest -m perf -q`

### 4.2. frontend

- `logic`
  - `npm run test` / `npm run test:logic`
  - 対象は `.test.ts` の純粋ロジックテスト（Vitest）
- `component` / `integration`
  - `npm run test:component` / `npm run test:integration`
  - 対象は `.component.test.ts` / `.integration.test.ts`（Vitest + @testing-library/svelte）
  - `npm run test:unit` で logic + component + integration を一括実行
- `workflow`
  - `npm run test:e2e`
  - replay asset を使う Playwright E2E

### 4.3. 主要な意味ベース入口

現在の運用では、Taskfile に次の意味ベース入口を持ちます。

- `task.exe verify`
- `task.exe test:contract`
- `task.exe test:frontend:logic`
- `task.exe test:frontend:component`
- `task.exe test:frontend:integration`
- `task.exe test:frontend:unit`
- `task.exe test:workflow:smoke`
- `task.exe test:workflow:full`
- `task.exe test:performance`
- `task.exe test:release`
- `task.exe test:release:performance`

これらの名前は、内部実装が変わっても維持する前提です。
runner や対象ファイルが変わる場合は、Task の中身だけを差し替えます。

## 5. 変更分類ごとの選定ルール

### 5.1. 日常開発

日常開発では、一律に重いテストを回すのではなく、
変更の性質に応じて必要最小限を選びます。

| 変更内容                                        | 必須                       | 条件付き                                                                      |
| ----------------------------------------------- | -------------------------- | ----------------------------------------------------------------------------- |
| ドキュメントのみ                                | リンクとコマンドの整合確認 | なし                                                                          |
| backend の内部ロジック、変換、軽量 adapter      | `logic`                    | public 契約に触れるなら `contract`                                            |
| frontend の純粋 TS ロジック、mapper、state 整形 | `logic`                    | なし                                                                          |
| frontend の UI コンポーネント単体               | `component`                | 複数コンポーネント連携なら `integration`                                      |
| frontend の複数コンポーネント連携、状態管理     | `integration`              | 主要フローに影響するなら `workflow:smoke`                                     |
| API、schema、settings の入出力                  | `contract`                 | 振る舞い変更があれば `logic` と `workflow:smoke`                              |
| UI 表示、録画導線、録画済み一覧、preview 周辺   | `workflow:smoke`           | 破壊的変更や広範囲変更なら `workflow:full`                                    |
| 認識・解析・録画時間判定・閾値                  | `logic`                    | release 前に `performance`                                                    |
| アーキテクチャ変更、責務移動、フォルダ再編      | `static`                   | 影響した意味分類ごとに `logic / contract / workflow / performance` を追加する |

### 5.2. リリース前

リリース前は `task.exe test:release` を基本入口とします。

認識・解析・録画時間判定・閾値に関係する変更では、
`task.exe test:release:performance` を使います。

性能確認だけを単独で回したい場合は、`task.exe test:performance` を使います。

`test:release:performance` の対象例:

- 画像認識
- フレーム解析
- 録画開始/停止判定
- replay 入力の時間評価
- 性能閾値に関係する実装変更

## 5.3. テスト実装の到達基準

### 5.3.1. 変更種類ごとの最低ライン

- バグ修正
  - 失敗を再現する回帰テストを、最も安定した下位レイヤへ追加する
  - API や UI に症状が出る不具合なら、`contract` または `workflow` も追加する
- 新機能
  - happy path だけでなく、主要な分岐、入力異常、状態不整合のいずれかを fast test で守る
  - 外部公開境界が増えるなら `contract`、主要導線が増えるなら `workflow:smoke` を追加する
- リファクタ
  - 既存テスト green だけで完了とせず、新しい責務境界で壊れやすい分岐が増えたなら `logic` を追加する
  - 振る舞い不変で分岐も増えない純粋移動だけは、新規テスト不要とする
- 永続化、ファイル操作、非同期処理
  - 成功系
  - 代表的な失敗系
  - cleanup、rollback、state reset のいずれかを確認する
- 認識、解析、閾値
  - `logic` で代表入力を固定し、release 前は `performance` を追加する

### 5.3.2. Definition of Done

- Done と見なす条件
  - 変更で増えた意思決定分岐に対して、最低 1 つは fast test がある
  - 外部契約変更には `contract` がある
  - ユーザー主要導線変更には `workflow` guard がある
  - バグ修正には再発防止テストがある
  - rollback や cleanup がある処理は失敗系も検証している
- Done と見なさない例
  - happy path のみ
  - 内部呼び出し回数だけを確認する
  - 実装をなぞるだけの snapshot
  - `logic` を `workflow` だけで守る
  - assertion が曖昧で、何を保証したいかが読めない

### 5.3.3. 中途半端なテストを避ける原則

- 1 bug fix 1 regression test を原則にする
- 1 public contract change 1 contract update を原則にする
- 1 user-visible flow change 1 workflow guard を原則にする
- 類似ケースの大量追加より、branch、boundary、failure の代表点を優先する
- 速い層で守れるものは速い層で守り、`workflow` は統合確認に絞る

## 6. AI エージェント向け運用ルール

### 6.1. 基本動作

- 最初にこの文書を読み、変更の意味を分類してから着手する
- まず変更ファイルではなく、変更の意味を `static / logic / contract / workflow / performance`
  のどれに当たるかで分類する
- raw command を直接記憶するのではなく、意味ベース入口を優先する
- 重い `workflow:full` を初手で回さない
- 未確認の点は `未確認`、判断を置いた点は `暫定` と明記する

### 6.2. frontend 固有ルール

- すべての frontend テストは Vitest + @testing-library/svelte で実行する（テストフレームワークの統一）
- logic テスト: `.test.ts` （純粋 TS ロジック）
- component テスト: `.component.test.ts` （UI コンポーネント単体）
- integration テスト: `.integration.test.ts` （複数コンポーネント連携）
- workflow テスト: `.spec.ts` （Playwright E2E）
- selector は `data-testid` を契約として扱う
- `frontend/test-results/` は失敗成果物であり、コミット対象にしない

### 6.3. replay asset / sidecar 運用

- replay asset を増やすと `workflow:full` の実行時間が増える
- sidecar JSON の期待値変更は、UI 表示と仕様変更の両方を確認してから行う
- 「E2E を通すためだけの緩い期待値」へ変更しない

### 6.4. マルチエージェント運用

- メインエージェントは目的、成功条件、優先順位、停止条件を管理する
- サブエージェントは、責務が分離されたファイル単位または論点単位で割り当てる
- 読み取り系の探索を先に行い、実装系は境界が固まってから動かす
- 共通の実行計画がある場合は、それを single source of truth として参照する

### 6.5. 完了報告

- AI エージェントの完了報告には、少なくとも変更分類、実行した意味ベース入口、未確認事項、追加で必要な検証を含める
- 「何を変えたか」だけでなく、「何を保証したか」を短く添える

## 7. 将来変更時の更新点

### 7.1. 変更しても維持すべきもの

- `static / logic / contract / workflow / performance` の分類
- `task.exe test:contract` など意味ベース入口の名前
- 親文書と子文書の責務分離

### 7.2. 変更時に見直すべきもの

- Taskfile の各入口が何を実行するか
- 現在の実装への対応表
- replay asset の smoke/full 切り分け方法
- frontend に component/integration 基盤が追加された場合の分類表
- AI エージェント向け運用ルールで前提にしている入口名や報告形式
- 親文書と `docs/e2e_replay_test.md` の責務境界

### 7.3. 追加ルール

- 新しい test layer を追加する場合は、既存分類へ割り当てられるかを先に検討する
- 既存分類へ収まらない場合だけ、新分類追加を検討する
- runner や配置を変える場合は、まず Taskfile の意味ベース入口を維持し、その後で対応表を更新する
- 分類を増やすときは、README、Taskfile、スキル、関連ドキュメントを同一変更で更新する

## 8. 関連ドキュメント

- [動画リプレイ入力による E2E 回帰テスト](./e2e_replay_test.md)
- `AGENTS.md`
- `Taskfile.yml`
- `backend/pyproject.toml`
- `frontend/package.json`

## 9. このドキュメントを参照しているファイル

このドキュメントは、テスト戦略の詳細版（Single Source of Truth）として以下から参照されています：

- `.codex/skills/test-ops/SKILL.md` - test-ops スキルの一次参照
- `frontend/AGENTS.md` - フロントエンド固有のテスト実装ガイド
- `backend/src/splat_replay/domain/AGENTS.md` - ドメイン層ガイドライン
- `backend/src/splat_replay/application/AGENTS.md` - アプリケーション層ガイドライン
- `backend/src/splat_replay/interface/AGENTS.md` - インターフェース層ガイドライン
- `backend/src/splat_replay/infrastructure/AGENTS.md` - インフラストラクチャ層ガイドライン
