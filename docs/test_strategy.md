# テスト戦略

この文書は、Splat Replay のテスト判断の SSoT です。
目的は「どの runner を使うか」ではなく、「何を保証するか」を短く決めることです。

## 0. AI エージェント実行契約

テストに関する作業では、最初に次を決めます。

1. 変更分類: `static / logic / component / integration / contract / workflow / performance`
   - 1 変更に複数分類が必要な場合は、下位の fast test を先に選び、境界・導線・性能の変更だけを追加する。
2. 保証対象: 何を守るか、どのファイル・テスト・境界まで確認すれば十分か
3. 新規テスト判断: 追加、更新、削除、または不要
4. 検証入口: 保証対象に合う最小の意味ベース入口または repo 管理ラッパー
5. 完了報告: 保証したこと、未確認のこと

優先順位:

- 本文書を、汎用 TDD 手順、既存テストの慣習、カバレッジ率目標より優先する。
- 新規関数や新規メソッドを追加しただけでは、テスト追加理由にしない。
- カバレッジ率を上げること自体を目的にしたテストを追加しない。
- コミット、完了、振る舞い変更という事実だけを、`task.exe test` / `task.exe verify` の実行理由にしない。
- まず変更分類を守る最小対象を実行する。広い入口は、狭い対象では守れない保証を実行前に説明できる場合だけ追加する。
- `workflow:full` や release 系入口を初手にしない。必要性を分類で説明できる場合だけ使う。
- 未確認の点を「通るはず」「影響なしのはず」と言い換えない。
- `skip`、期待値緩和、marker 変更、テスト削除で green にした場合は、保証を落としていないかを必ず説明する。
- `--list`、構文確認、型チェック、format check は部分検証です。テストの成功として報告しない。

完了報告には、最低限これを書く。

```text
- 参照した方針: docs/test_strategy.md
- 変更分類:
- 保証対象:
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
- 適切な粒度の既存 Task があれば、Taskfile の意味ベース入口を使う。
- 既存 Task が保証対象より過広い場合は、repo 管理ラッパーまたは package script に対象ファイルや node ID を渡す。対象ごとの Task 追加は必須にしない。
- 生の runner は、既存 Task・repo 管理ラッパー・package scriptでも表現できない低レベル切り分けに限定する。
- 分類は runner や配置ではなく、観測境界で決める。
- 境界契約が変わる変更は `contract` を更新する。
- ユーザー主要導線は `workflow` で守る。
- 性能回帰は `performance` で別枠管理する。通常のマージ必須 gate には含めず、性能影響のある変更時とリリース前に使う。
- `benchmark` と `coverage` は補助測定であり、保証分類ではない。
- テスト件数、カバレッジ率、アプリが一度起動した事実だけでは、保証対象の振る舞い・配布物・各 OS の受け入れを示しません。

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

- `task.exe verify`: リポジトリ既定品質 gate。次のいずれかに該当する場合だけ使い、変更分類の代替にはしない。
  - リリース前の確認である。
  - 複数層・複数の保証分類にまたがり、個別入口の組み合わせでは不足する。
  - 調査しても影響範囲を安全に絞れない。
  - ユーザーが全体検証を明示的に依頼した。
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
| ドキュメントのみ | リンク、入口名、方針間の整合確認 | 追加のテスト runner は不要 |
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

### リリース検査の保証範囲

各検査の合格は、その行に書いた対象だけを保証します。未実施の環境・導線は未確認として扱います。

| 検査 | 保証する範囲 | 保証しない範囲・実行条件 |
| ---- | ------------ | ------------------------ |
| `test:release` | `verify` の静的検査・backend/frontend の通常テストと、全 bundled asset を使う `workflow:full` | ビルド済み配布物、実機、OS 権限、外部認証・外部サービスの実動作 |
| `test:release:performance` | 上記と同じ release 回帰に、閾値付き `performance` を加えた範囲 | `test:release` の全工程を含むため、両方を続けて実行する必要はない |
| replay workflow | replay 観測を受けた後の状態遷移、保存、API/UI、および対象 workflow で通る実 FFmpeg 編集・隔離 storage 処理（個々の assert 範囲は spec ごと） | REPLAY が固定観測に置き換える OBS/DistroAV/NDI の存在・構成、実機音声・キャプチャ、OS 権限、実 YouTube 認証・アップロード。詳細は [E2E の境界](./e2e_replay_test.md) を参照 |
| 固定入力の lower integration / performance | 固定フレームに対する OCR/CV の認識結果・閾値・時間予算 | 動画全体や実機入力での認識品質、ユーザー workflow |
| 配布物検査 | macOS の `build:macos:candidate` / `verify:macos:dmg` は arm64、識別子、署名、必須 asset、DMG 構造を検査。Windows の `task.exe build` は package を生成 | 構造検査はアプリ起動や実機連携を保証しない。Windows の `task.exe build` に macOS と同等の package 検証はない |
| 実 OS・実機での受け入れ | 確認した OS・利用者 session・機器・導線で実際に観測した結果 | 他 OS、未操作の権限や機器、別 artifact へ一般化しない。認証情報の入力・新たな OS 権限の許可判断は本人が行う。実ゲーム・機器操作や実スリープは、本人操作または明示許可の範囲で実施する |
| VM / WSL2 | 記録した VM/WSL2 構成での再現性・可搬性 | 実機、別 OS、最新候補の受け入れ。過去の候補・VM の結果を現候補の合格へ読み替えない |

リリースの判定では、現候補の自動検査と実機での利用者確認を別々に記録し、revision / artifact、OS、実行した導線、未確認範囲を対応づけます。検査後にコードまたは artifact が変わった場合は、影響する検査を変更後の対象で再実行します。確認していない OS・外部連携・初回導入は、他の gate の成功から推定しません。同じ一般業務ロジックを Windows と macOS で全件重ねて実行する必要はありませんが、OS 固有の OCR / FFmpeg 条件、ファイルロック、分岐、package import / load は対象 OS ごとに確認します。常に全 OS で同じ実機確認を重ねるのではなく、変更とリリースで主張する保証に対応する検査を選びます。

## 4. テスト追加判断

新規テストを書くとき:

- バグ修正: 失敗を再現する回帰テストを、最も安定した下位レイヤに追加する。
- 新機能: happy path に加え、主要分岐、入力異常、状態不整合の代表点を fast test で守る。
- 外部公開境界の追加・変更: `contract` を更新する。
- ユーザー主要導線の追加・変更: `workflow:smoke` を追加または更新する。
- 永続化、ファイル操作、非同期処理: 成功系、代表的な失敗系、cleanup / rollback / state reset のいずれかを確認する。
- 認識、解析、閾値: 代表入力を fixture として固定する。
- 必須 setup 判定を追加・変更するとき: 有効な保存設定 fixture では不足なしとなり、新たに必須とした項目の不足 fixture では不足 issue が返り gate が拒否することを `SetupService` の実判定で確認する。外部 checker の結果は fixture 化できるが、service 全体を mock して判定を通したことにしない。実機への導入・権限・外部認証は別の保証範囲として扱う。

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
- replay workflow では fixture 観測を既存ポート境界で供給し、その後の状態遷移・保存・API・UI を実経路で検証する。実 OCR / CV の精度・性能は固定入力の lower test に分離する。

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
- 起動成功、ready、HTTP 200 だけで workflow を合格にしない。対象導線に応じて UI の状態遷移と保存後の状態を確認し、録画なら生成ファイルと metadata、編集なら編集結果、失敗・キャンセルなら必要なデータの保持や復旧後の状態を観測する。毎回すべてを重複させず、その workflow が守る結果を assert する。
- workflow の storage・設定・入力は隔離領域を使い、実利用者の設定・録画を変更しない。実アップロードを行わない E2E は明示した no-op 境界を使い、成功を外部サービスの成功に読み替えない。
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
