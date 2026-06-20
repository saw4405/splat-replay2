# テスト戦略

この文書は、Splat Replay のテスト判断の SSoT です。
目的は「どの runner を使うか」ではなく、「何を保証するか」を短く決めることです。

## 0. AI エージェント実行契約

テストに関する作業では、最初に次を決めます。

1. 変更分類: `static / logic / component / integration / contract / workflow / performance`
   - 1 変更に複数分類が必要な場合は、下位の fast test を先に選び、境界・導線・性能の変更だけを追加する。
2. 新規テスト判断: 追加、更新、削除、または不要
3. 検証入口: `task.exe` の意味ベース入口
4. 完了報告: 保証したこと、未確認のこと

優先順位:

- 本文書を、汎用 TDD 手順、既存テストの慣習、カバレッジ率目標より優先する。
- 新規関数や新規メソッドを追加しただけでは、テスト追加理由にしない。
- カバレッジ率を上げること自体を目的にしたテストを追加しない。
- `workflow:full` や release 系入口を初手にしない。必要性を分類で説明できる場合だけ使う。
- 未確認の点を「通るはず」「影響なしのはず」と言い換えない。
- `skip`、期待値緩和、marker 変更、テスト削除で green にした場合は、保証を落としていないかを必ず説明する。
- `--list`、構文確認、型チェック、format check は部分検証です。テストの成功として報告しない。

完了報告には、最低限これを書く。

```text
- 参照した方針: docs/test_strategy.md
- 変更分類:
- 新規テスト判断:
- テスト実行判断:
- 実行した入口:
- 省略した入口と理由:
- 未確認事項:
- 追加で必要な確認:
```

広範レビュー時:

- 対象が複数層・多数ファイルにまたがる場合は、サブエージェントや並列レビューを分類単位で使ってよい。
- 分割単位は `backend contract`、`backend performance`、`frontend component / integration`、`workflow` のように、保証したい性質で切る。
- サブエージェントの所見は未確定情報として扱い、メインエージェントが本文書の分類・禁止事項・偽合格防止に照らして統合判断する。
- 最終対応は個別テストの好みではなく、保証を落とす変更がないか、偽合格になっていないかで決める。

## 1. 基本方針

- テストは実装単位ではなく、保証したい性質で分類する。
- 開発時は fast-to-slow で、必要最小限から始める。
- リリース時だけ重い回帰確認を必須にする。
- 入口は raw command ではなく Taskfile の意味ベース名を主語にする。
- 分類は runner や配置ではなく、観測境界で決める。
- 境界契約が変わる変更は `contract` を更新する。
- ユーザー主要導線は `workflow` で守る。
- 性能回帰は `performance` で別枠管理する。通常のマージ必須 gate には含めず、性能影響のある変更時とリリース前に使う。
- `benchmark` と `coverage` は補助測定であり、保証分類ではない。

## 2. 分類と入口

| 分類 | 守るもの | 主な入口 |
| ---- | -------- | -------- |
| `static` | 形式、型、依存方向 | `task.exe format:check`, `task.exe lint`, `task.exe type-check`, `task.exe import-lint` |
| `logic` | 純粋関数、変換、軽量 adapter、内部ロジック | `task.exe test`, `task.exe test:backend`, `task.exe test:frontend:logic` |
| `component` | UI コンポーネント単体のユーザー可視振る舞い | `task.exe test:frontend:component` |
| `integration` | 複数コンポーネント、state、adapter の連携 | `task.exe test:frontend:integration` |
| `contract` | API、schema、公開 JSON、DTO、settings の境界契約 | `task.exe test:contract` |
| `workflow` | UI を含むユーザー主要導線 | `task.exe test:workflow:smoke`, `task.exe test:workflow:full` |
| `performance` | 実行時の時間予算を持つ処理の閾値付き性能回帰 | `task.exe test:performance` |

補助入口:

- `task.exe verify`: 全体 gate。分類の代替ではなく、完了判定として扱う。
- `task.exe test:benchmark`: 時間予算が未確定な探索・診断向けの観測専用。release 判定には含めない。
- `task.exe coverage`, `task.exe coverage:backend`, `task.exe coverage:frontend`: 未テスト分岐の発見に使う。
- `task.exe doctor`, `task.exe doctor:json`: checkout 前提の診断。変更内容の保証には使わない。

frontend の命名:

- logic: `.test.ts`
- component: `.component.test.ts`
- integration: `.integration.test.ts`
- workflow: `.spec.ts`

frontend の component / integration では、`role`、`label`、`title`、可視テキストを第一選択にします。
`data-testid` は複数同型要素の識別など、アクセシブル名だけでは曖昧な場合に限ります。

backend の配置と marker:

- `contract` は `backend/tests/contract/**` に置き、`pytest.mark.contract` で選別できるようにする。
- `performance` は `backend/tests/performance/**` に置き、閾値付き回帰は `pytest.mark.perf`、観測専用は `pytest.mark.benchmark` で release 判定から分ける。
- `perf` / `benchmark` は現在の実装手法ではなく、あるべき時間予算で決める。OCR、画像マッチング、外部 adapter 呼び出しでも、録画中・録画終了直後・メタデータ確定などの実行時導線に入るなら `perf` として扱う。
- `logic` と `contract` / `performance` を同一テストファイルに混ぜない。例外はテスト名かコメントで分類理由を書く。

## 3. 変更別の選定

| 変更内容 | 必須 | 条件付き |
| -------- | ---- | -------- |
| ドキュメントのみ | リンク、入口名、方針間の整合確認 | 追加のテスト runner は不要。完了判定の扱いは `AGENTS.md` に従う |
| backend 内部ロジック、変換、軽量 adapter | `logic` | public 契約に触れるなら `contract` |
| frontend 純粋 TS ロジック、mapper、state 整形 | `logic` | なし |
| frontend UI 単体 | `component` | 複数部品連携なら `integration` |
| frontend 状態管理、複数コンポーネント連携 | `integration` | 主要導線なら `workflow:smoke` |
| API、schema、settings 入出力 | `contract` | 振る舞い変更があれば `logic`、UI 影響があれば `workflow:smoke` |
| UI 表示、録画導線、録画済み一覧、preview 周辺 | 最小の `component / integration / workflow:smoke` | 破壊的変更や広範囲変更なら `workflow:full` |
| 認識、解析、録画時間判定、閾値 | `logic` | 時間予算を持つ処理は `performance`、release 前に `test:release:performance` |
| 責務移動、フォルダ再編、アーキテクチャ変更 | `static` | 影響した分類を追加 |

リリース前:

- 基本入口: `task.exe test:release`
- 認識、解析、録画時間判定、閾値に関係する場合: `task.exe test:release:performance`

## 4. テスト追加判断

新規テストを書くとき:

- バグ修正: 失敗を再現する回帰テストを、最も安定した下位レイヤに追加する。
- 新機能: happy path に加え、主要分岐、入力異常、状態不整合の代表点を fast test で守る。
- 外部公開境界の追加・変更: `contract` を更新する。
- ユーザー主要導線の追加・変更: `workflow:smoke` を追加または更新する。
- 永続化、ファイル操作、非同期処理: 成功系、代表的な失敗系、cleanup / rollback / state reset のいずれかを確認する。
- 認識、解析、閾値: 代表入力を fixture として固定する。

新規テストを書かないとき:

- 振る舞い不変で、分岐や境界も増えない純粋移動。
- 既存テストで保証されている薄い委譲。
- 言語、標準ライブラリ、フレームワークの標準動作。
- カバレッジ率だけを上げるためのテスト。

不要判断をした場合は、完了報告に「既存テストで守られる範囲」または「新しい分岐がないこと」を短く書きます。

## 5. 禁止・注意

- `logic` を `workflow` だけで守らない。
- 内部呼び出し回数だけのテストにしない。
- 実装をなぞるだけの snapshot を追加しない。
- ソース文字列を読み、CSS/HTML の断片だけを assert しない。
- 特別な要件がない限り、ログ文言や `mock_logger` 呼び出しを assert しない。
- 戻り値で確認できるユースケースは、戻り値の性質を assert し、内部 repository 呼び出しに寄せない。
- 設定ファイルのチューニング値をテストにハードコードしない。構造やパースを確認する。
- `backend/tests/logic/**` に `pytest.mark.contract` や `pytest.mark.perf` を置かない。
- 同じ振る舞いを複数ファイルで重複検証しない。必要なら parametrize / each でまとめる。
- 失敗するテストを、根拠なく `skip`、期待値緩和、広い例外許容、marker 変更で「通る」状態にしない。

偽合格防止:

- `skip` は合格ではありません。外部バイナリやハードウェアなど実行前提が無い場合だけ使い、skip した保証を完了報告に書く。
- ファイル全体を `skip` しない。実バイナリが必要なケースだけに絞り、同じファイル内の stub で検証できる分岐は実行し続ける。
- テスト対象の代表 fixture が無い場合、主要導線テストは無言で skip しない。安定した fixture を明示的に選ぶか、前提不足として失敗させる。
- `perf` から `benchmark` へ marker を変えると release gate から外れます。閾値付き assert があるなら `perf`、観測記録だけなら `benchmark` とし、分類変更で保証を失っていないかを確認する。
- 処理が遅い、または現実装が外部ツールに依存することだけを理由に `benchmark` へ落とさない。実行時導線の時間予算を満たすべき処理なら、遅さは実装改善対象として `perf` で検知する。
- `contract smoke` は route 存在確認だけを保証します。これを API 契約全体の合格として扱わない。
- テスト名と assert が一致しないテストは、テスト名を変えるのではなく、まず保証したい性質を確認し、必要なら観測可能な assert を追加する。
- テストを削る場合は、削除後もどの既存テストが同じ保証を持つかを確認する。代替保証が無い削除は行わない。

Flaky 防止:

- async テスト内で `threading.Event.wait()` などの同期ブロッキング待機を直接呼ばない。
- 実行順制御に `sleep` を使わず、`asyncio.Event` など明示的な同期を使う。
- 固定時間の `sleep` は避け、シグナリング待機とタイムアウトを使う。Playwright では `expect.poll` のように条件と失敗理由が残る待機を使う。
- Tesseract、NDI、OBS など外部環境依存は stub 化する。実バイナリが必要なら `skipif` を使うが、依存しない分岐まで巻き込まない。

Contract:

- 正常系 contract テストは期待ステータスを 1 つに絞る。
- 複数ステータスを許すのは、状態依存が仕様として許容される場合だけ。
- ルート存在スイープは `contract smoke` と明記し、schema / status / body 契約テストの代替にしない。
- `404 以外ならよい`、`200/400/500 のどれでもよい` という正常系 contract は避ける。状態を fixture / monkeypatch で固定し、正常系と失敗系を分ける。

Performance:

- `performance` は閾値付き回帰テストにする。
- 単に時間を記録するだけなら `benchmark` と呼び、release 判定から分ける。
- 閾値には理由を書く。
- 録画ループ、フレーム判定、録画終了直後の結果抽出、メタデータ確定、録画中バックグラウンド認識は `performance` の候補にする。
- 診断レポート出力、将来の閾値設計のための探索、ユーザー導線の時間予算をまだ置けない測定だけを `benchmark` にする。

Workflow:

- `workflow:smoke` は軽量でも、代表的なユーザー主要導線を実際に守る必要があります。
- smoke 用 fixture の選択で対象導線が全て skip される場合は偽合格です。recordable / no-video / error recovery など、導線ごとの前提に合う fixture を明示的に選ぶ。
- `test:e2e -- --list` は spec の読み込みとテスト列挙だけを確認する入口です。workflow の成功として扱わない。
- E2E を通すためだけに sidecar 期待値を緩めない。sidecar の変更は、仕様変更または実 fixture の source of truth 更新として説明できる場合だけ行う。

## 6. カバレッジ

カバレッジは補助指標です。固定目標値は置きません。

- Backend は主に `splat_replay/domain/` と `splat_replay/application/` の重要分岐を見る。
- `splat_replay/infrastructure/` は外部依存が強いため、数値低下だけで追加テストを要求しない。
- Frontend は純粋ロジック、mapper、state 整形、ユーザー可視の状態遷移を見る。
- カバレッジ率だけで新規テストを追加しない。

入口:

- `task.exe coverage`
- `task.exe coverage:backend`
- `task.exe coverage:frontend`

## 7. 更新時のルール

- `static / logic / component / integration / contract / workflow / performance` の分類を維持する。
- 新しい test layer は、まず既存分類へ割り当てられるか検討する。
- runner や配置を変える場合は、分類の意味を保ち、Taskfile と対応表を同時に更新する。
- 分類を増やすときは、README、Taskfile、repo-local skill、関連ドキュメントを同一変更で更新する。

## 8. 関連ドキュメント

- [動画リプレイ入力による E2E 回帰テスト](./e2e_replay_test.md)
- `AGENTS.md`
- `frontend/AGENTS.md`
- `.codex/skills/test-ops/SKILL.md`
- `Taskfile.yml`
- `backend/pyproject.toml`
- `frontend/package.json`
