# 開発ガイド

このドキュメントは、Splat Replay の**開発環境構築・日常開発フロー・検証入口**をまとめた
how-to です。特別な注記がない限り、コマンドはリポジトリルートで実行してください。

> Windows 環境では `task` ではなく **`task.exe`** を使用します。macOS / WSL2 / Linux では `task` を使用します。

## この文書の責務

この文書で扱う内容:

- 開発に必要な前提ツール
- 初回セットアップ
- checkout の状態診断
- 開発サーバーの起動方法
- 日常開発で使う主要コマンド
- 完了前に通すべき検証入口

この文書で詳述しない内容:

- プロジェクト概要: [`README.md`](../README.md)
- アプリ利用者向けセットアップや外部ツール設定: [`docs/usage.md`](./usage.md)
- テスト選定の SSOT: [`docs/test_strategy.md`](./test_strategy.md)
- replay ベース E2E の詳細: [`docs/e2e_replay_test.md`](./e2e_replay_test.md)
- 実装ルール・レイヤ責務: [`AGENTS.md`](../AGENTS.md) と各層の `AGENTS.md`

## サポート環境と前提ツール

### 製品の実行・配布

- OS: Windows 11、Apple Silicon 搭載 macOS
- 開発コマンドのシェル: Windows は PowerShell、macOS は zsh / bash
- 配布版の導入・利用手順: [ユーザーガイド](./usage.md)

### 開発と replay E2E 可搬性ゲート

- OS: Windows 11、Apple Silicon 搭載 macOS、Linux（WSL2 を含む）
- Linux では、実機 NDI / OBS を使わない replay E2E を実行できます。
- この Linux 合格は、macOS の製品実行・配布を保証するものではありません。

共通の前提ツール:

- Python: `3.13`
  - 根拠: `backend/.python-version`, `backend/pyproject.toml`
- Node.js: `>=24.12.0`
  - 根拠: `frontend/package.json#engines`
- 必須ツール:
  - [uv](https://docs.astral.sh/uv/getting-started/installation/)
  - [Task](https://taskfile.dev/installation/)
  - Git
- 条件付きで必要:
  - [Git LFS](https://docs.github.com/en/repositories/working-with-files/managing-large-files/installing-git-large-file-storage)
    - replay ベースの Playwright E2E を実行する場合に必要です。
- 推奨:
  - [pre-commit](https://pre-commit.com/)
    - backend の dev dependency として Git hooks 設定に使います。追加のグローバル導入は不要です。

WSL2 の replay E2E では、Windows 側の `node_modules` や `.venv` を共有せず、Linux 側の checkout に依存関係を作成してください。

以下は診断用の生コマンド例です。これらは Task 化対象外です。

```bat
python --version
node --version
uv --version
task.exe --version
git --version
git lfs version
```

## 初回セットアップ

### Apple Silicon 搭載 macOS での開発環境セットアップ

Python 3.13、Node.js 24.12 以上、npm、uv、Task、Git を用意します。音声入力用の PyAudio をビルドするため、先に [PortAudio](https://pypi.org/project/PyAudio/) を導入します。Homebrew を使う場合は `brew install portaudio` です。replay workflow E2E を行う場合は Git LFS と FFmpeg も必要です。

```sh
task install:backend
task install:frontend
task install:hooks
task doctor
```

Git LFS と replay asset を用意した後、`task install:lfs` を実行してください。`task install` は hooks と LFS も含めて実行する入口です。アプリ開発サーバーは `task dev`、frontend と backend を分ける場合は `task dev:frontend` / `task dev:backend` で起動します。これらは開発用の入口であり、macOS の製品版の動作確認にはなりません。

### 推奨: まず `task.exe install` を実行する

まずは推奨セットアップとして、次を実行してください。

```bat
task.exe install
```

このタスクは次を実行します。

- backend: `uv sync`
- frontend: `npm ci --prefer-offline --no-audit`
- Git hooks を `.githooks` launcher に設定
- Git LFS の初期化と replay asset の実体化

成功判定:

- エラーなく終了する
- backend の仮想環境と frontend の依存関係が解決される
- Git hooks / Git LFS / replay asset が、この checkout でも親 repo と同じ通常フローで使える

Git hooks や Git LFS を自動設定したくない場合は、次を使います。

```bat
task.exe install SKIP_HOOKS=1 SKIP_LFS=1
```

この指定は一時的な切り分け用です。`SKIP_HOOKS=1` または `SKIP_LFS=1` により
commit / push hooks や workflow E2E の前提が欠けます。切り分け後は
`task.exe install:hooks` / `task.exe install:lfs` で通常フローに戻してください。

### WSL2 で replay E2E を実行する場合

WSL2 では Windows 専用の Git hooks 初期化を含む `task install` ではなく、必要な依存だけを準備します。

replay workflow E2E には Linux 側の FFmpeg が必要です。OCR / ブキ / 表彰認識は fixture 観測を
ポート境界で供給するため、workflow E2E 自体は Tesseract を必要としません。
Ubuntu / WSL2 では一度だけ次を実行します。

```bash
sudo apt-get update
sudo apt-get install --yes ffmpeg
```

実 Tesseract を使う固定フレームの OCR 統合テストを実行する場合だけ、追加で
`sudo apt-get install --yes tesseract-ocr` を実行します。これは OCR の精度・性能を
別保証として確認する入口であり、replay workflow の可搬性ゲートとは分けます。

`pytesseract` の Python パッケージだけでは OCR は実行されません。`tesseract` コマンドを
Linux 側の `PATH` から実行できることを確認してください。

```bash
git lfs pull --include="frontend/tests/fixtures/e2e/**"
task install:backend
task install:frontend
task test:workflow:full
```

`task test:workflow:full` は Playwright の backend を `SPLAT_REPLAY_RUNTIME_PROFILE=replay` で起動します。replay 入力が無い場合は失敗し、NDI・OBS・実機デバイス列挙へフォールバックしません。

### checkout の状態を診断したい場合

Codex worktree などで親 repo と違う挙動が出た場合や、通常フローに入る前提を機械的に
確認したい場合は、次で診断します。

```bat
task.exe doctor
```

Codex や CI など機械可読の結果が必要な場合は次を使います。

```bat
task.exe doctor:json
```

`doctor` は通常開発の主入口ではなく、修復を行わない非破壊の診断コマンドです。
通常の開発フローは `task.exe install`、変更分類に応じた検証入口、Git hooks です。
`doctor` は、その前提がこの checkout で崩れていないかを `fail` / `warn` / `pass` で報告します。
`fail` が 1 件でもあれば終了コードは non-zero です。`warn` は通常フロー自体を壊さない注意事項です。
たとえば dirty worktree は `warn` として扱い、依存関係や hooks の故障とは分けて報告します。

### Git hooks を有効化・再設定したい場合

`task.exe install` は既定で Git hooks を必須 gate として設定します。スキップした場合や、
後からやり直したい場合は次を実行してください。

```bat
task.exe install:hooks
```

このタスクは worktree-local config として `core.hooksPath=.githooks` を設定します。`.githooks/pre-commit` と
`.githooks/pre-push` はリポジトリで管理する portable launcher で、特定 checkout の
`backend\.venv` 絶対パスには依存しません。

Git hooks では次を確認します。

- `pre-commit` では backend の `ruff` / `ty` と、frontend の staged files 向け `prettier` / `eslint` を走らせます。
- `pre-push` では frontend 全体の `type-check` / `svelte-check` と、backend の `import-lint` を走らせます。
- `task.exe test` は自動では走りません。
- Git hooks は commit / push 前の必須品質 gate です。失敗した場合は握りつぶさず、原因を直してください。
- `task.exe verify` は無条件の完了 gate ではありません。適用条件は [`docs/test_strategy.md`](./test_strategy.md) に従います。

### workflow E2E を使う場合

`frontend/tests/fixtures/e2e/**/*.mkv` は Git LFS 管理です。`task.exe install` は
既定で Git LFS の初期化と replay asset の実体化を行います。初期化をやり直したい場合は次を実行してください。

```bat
task.exe install:lfs
```

E2E 実行時の補足:

- checkout 診断では replay asset が Git LFS pointer のままなら `fail` として報告します。
- `npm run test:e2e` の `pretest:e2e` でも replay asset の実体化を確認し、必要なら内部的に `git lfs pull` を実行します。

### 生成物を更新する場合

OpenAPI や frontend の生成型を更新する必要がある場合だけ、手編集ではなく次を使います。

```bat
task.exe generate
```

対象:

- `frontend/src/generated/openapi.json`
- `frontend/src/generated/api.d.ts`

## 開発サーバーの起動

### 推奨: `task.exe dev` でまとめて起動する

```bat
task.exe dev
```

Windows では frontend / backend 用の PowerShell が 2 つ開きます。

起動後の導線:

- frontend: `http://127.0.0.1:5173`
- backend: `http://127.0.0.1:8000`
- API docs: `http://127.0.0.1:8000/docs`

補足:

- frontend 側の `/api`, `/setup`, `/ws` は Vite から backend へプロキシされます。
- backend 側は `uvicorn --reload` で起動するため、`task.exe dev` でもホットリロードされます。
- `task.exe dev` 実行後の停止は、それぞれのウィンドウで `Ctrl+C` を使います。

### 個別に起動したい場合は frontend / backend を別ターミナルで起動する

ターミナル 1:

```bat
task.exe dev:backend
```

ターミナル 2:

```bat
task.exe dev:frontend
```

- `task.exe dev:backend` は `uvicorn --reload` を使うため、backend 単体の反復に向いています。

## 日常開発の基本フロー

1. 依存関係や lockfile が変わっていれば `task.exe install`
2. `task.exe dev` を実行
   必要に応じて `task.exe dev:backend` と `task.exe dev:frontend` を個別起動
3. 実装前に変更分類、守る保証、最小の検証対象を決める
4. 実装後、変更分類に応じた最小の入口から実行する
5. 狭い対象では守れない保証がある場合だけ、根拠を示して広い入口を追加する
6. commit / push 時は Git hooks を通し、失敗した場合は原因を直す
7. Codex worktree と親 repo で挙動が違う場合は `task.exe doctor` で checkout 状態を診断する

原則:

- 適切な粒度の既存 Task があれば、Taskfile の意味ベース入口を使います。
- 既存 Task が過広い場合は、repo 管理ラッパーまたは package script に対象ファイルや node ID を渡します。
- 生の `npm` / `uv` / `pytest` コマンドは、既存の入口やラッパーでも表現できない低レベルの切り分け時だけ使います。
- テスト選定に迷ったら [`docs/test_strategy.md`](./test_strategy.md) を優先してください。

### backend pytest の一時ディレクトリ

backend pytest の Taskfile 入口は `scripts/run-backend-pytest.py` を通し、
worktree 内の一時ディレクトリと pytest cache 無効化を指定して実行します。
Taskfile 入口が保証対象より過広い場合は、この repo 管理ラッパーへ対象ファイルや node ID を渡します。
低レベル切り分け以外では、生の `pytest` を直接使わないでください。

## 検証とテスト

### 基本入口

| 目的                         | コマンド                 | 補足                                                                    |
| ---------------------------- | ------------------------ | ----------------------------------------------------------------------- |
| checkout 状態診断            | `task.exe doctor`        | 親 repo と同じ通常フローに入る前提の診断                                |
| backend + frontend unit 一括 | `task.exe test`          | 複数層をまとめて確認する根拠がある場合                                   |
| リポジトリ既定品質 gate      | `task.exe verify`        | 適用条件は `docs/test_strategy.md`。コミット・完了だけでは実行理由にしない |
| backend の既定テスト         | `task.exe test:backend`  | backend 全体を確認する根拠がある場合。`perf` は除外                      |
| frontend unit 一括           | `task.exe test:frontend` | `logic + component + integration` をまとめて確認する根拠がある場合      |

### 変更内容ごとの追加入口

| 変更内容                                    | 追加で見る入口                       |
| ------------------------------------------- | ------------------------------------ |
| API / schema / 境界契約                     | `task.exe test:contract`             |
| frontend の純粋ロジック                     | `task.exe test:frontend:logic`       |
| frontend の UI コンポーネント単体           | `task.exe test:frontend:component`   |
| 複数コンポーネント連携 / 状態管理           | `task.exe test:frontend:integration` |
| replay を使う主要 workflow の軽量回帰       | `task.exe test:workflow:smoke`       |
| bundled replay asset 全件での workflow 回帰 | `task.exe test:workflow:full`        |
| 性能影響がある変更                          | `task.exe test:performance`          |

### リリース前の入口

| 目的                   | コマンド                            |
| ---------------------- | ----------------------------------- |
| リリース前の総合回帰   | `task.exe test:release`             |
| 性能影響を含む総合回帰 | `task.exe test:release:performance` |

補足:

- `workflow:full` と `test:release*` は重いため、初手には向きません。
- `task.exe test:workflow:*` は Playwright 側で backend / frontend を自動起動するため、
  通常は事前に `task.exe dev:*` を立ち上げる必要はありません。
- replay ベース E2E の詳しい運用は [`docs/e2e_replay_test.md`](./e2e_replay_test.md) を参照してください。
- テスト選定の正本は [`docs/test_strategy.md`](./test_strategy.md) です。

## 生成・ビルド・カバレッジ

### 生成

```bat
task.exe generate
```

使う場面:

- backend の OpenAPI 変更を frontend に反映したいとき
- `frontend/src/generated/` を再生成したいとき

### ビルド

Windows:

```bat
task.exe build
```

Apple Silicon macOS（固定した自己署名証明書で署名し、公証なし）:

```sh
task build:macos
```

成果物:

- Windows: `dist/SplatReplay/`
- macOS: `dist/SplatReplay.app/`（再ビルド時は同じ場所を更新）
- macOS DMG: `dist/SplatReplay.dmg`
- 中間生成物: `backend/build/`

補足:

- `backend/build/` は中間生成物です。実行対象ではありません。
- `task build` / `task build:macos` は固定出力先の `.app` と DMG を更新し、時刻別のアプリを追加しません。更新先のアプリが起動中なら、ビルドを開始せず中止します（アプリを終了して再実行してください）。ビルド失敗時の旧成果物保持は保証しません。`/Applications` にコピーしたアプリはこのコマンドの更新対象外です。
- 比較検証で旧成果物を保持する場合だけ、`task build:macos:candidate` を明示します。候補は `dist/macos-candidates/<UTC時刻>/`、中間生成物は `backend/build/macos-candidates/<UTC時刻>/` に作成し、同名の出力先が既に存在すれば停止します。既存の候補は自動削除しません。
- `task clean:macos` は明示実行用で、既定の `dist`、`backend/build`、`frontend/dist` を削除します。既存 `.app` からの DMG 再生成は `task build:macos:dmg`、既存 DMG の検証は `task verify:macos:dmg` です。
- 固定証明書は SHA-256 `2b617e1206573418df294b7cb8f256f0aa0ee5ed556df9be32064774de8d20b5` の `Splat Replay Local Code Signing` です。ビルド前に login Keychain の証明書と対応する秘密鍵を照合し、有効期間と Code Signing 用途を確認します。PyInstaller の中間 `.app` は ad hoc のまま生成し、最終 `.app` 外側だけを同じ証明書で署名します。ビルドは証明書を生成・更新せず、Keychain の信頼設定や ACL も変更しません。初回に `codesign` が秘密鍵を使う時、macOS がアクセス確認を表示する場合があります。表示された実行元と対象鍵を確認し、本人が許可を判断してください。
- この helper の `preflight` / `verify` は署名ビルド用 Mac の login Keychain に同じ証明書と秘密鍵があることを要求します。配布先での公開署名検査とは別の、ビルド元の固定identity検査です。固定自己署名証明書は公証済み Developer ID ではないため、初回起動で Gatekeeper の手動許可が必要になる場合があります。署名を固定しても Gatekeeper、カメラ/マイク等のOS許可、YouTube Keychain 項目の許可が一度化する保証はありません。Windows のビルド経路には変更を加えていません。
- Windows の実行は `dist/SplatReplay/SplatReplay.exe`、通常の macOS `task run` は `dist/SplatReplay.app` を使います。新しい候補を起動する場合は候補の `.app` を直接開くか、`task run DIST_ROOT=dist/macos-candidates/<UTC時刻>` を指定します。Windows は `task.exe run` で起動できます。
- macOS 版の設定・ログ・動画は `~/Library/Application Support/io.github.saw4405.splatreplay/` に保存します。`.app` 内のファイルはユーザーデータとして編集しません。

### ビルド済みアプリの起動

```bat
task.exe run
```

### カバレッジ

```bat
task.exe coverage
task.exe coverage:backend
task.exe coverage:frontend
task.exe coverage:report
```

レポート出力先:

- backend: `backend/htmlcov/index.html`
- frontend: `frontend/coverage/index.html`

## 現在の実装・検証状況（2026-10-25）

- 元録画と編集済み動画の保持、Switch の動画保存通知、通常処理の進捗復帰、音声・字幕処理、Mac 更新手順は `7a3ec33` に記録した。ファイル取込みの UI/API と、利用条件・第三者通知の閲覧・同梱検査には未コミットの作業が残る。
- 外部送信の説明は「基本設定」と「すべての設定」の両方に一度だけ表示する。切替時の表示は設定画面の component テストで確認する。
- 保全・復旧の実行確認では、本人録画と同一 SHA-256 の入力から2秒のコピーを2本作り、既存の AutoEditor・FFmpeg・サムネイル生成・ファイルリポジトリで約4.02秒の動画を作成した。正常時の保持、保持途中の失敗、再起動を模した新しいインスタンスからの再開を確認した。再開時は再結合・再埋込みを許可しない条件でも完了し、確定出力と保持元録画のハッシュが一致した。
- この試験は隔離した保存先だけを使用し、原本のハッシュ・サイズ・更新時刻は試験前後で一致した。外部接続は拒否し、通信の試行はなかった。実録画・長尺性能・主観的な全編視聴・実アップロード成功後の保持は、この短い試験では保証しない。
- Windows の確認先は既存の spectre SSH 接続とする。2026-10-25 の確認では Tailscale 上でオフライン、SSH が接続タイムアウトのため未実施。Mac の合格を Windows の合格へ転用しない。
- 新規の事業・権利・roadmap 文書は作業用として保持し、今回のコミットには含めない。配布適合と機能テストの結果は分けて扱う。

## 設計ルールと注意事項

- backend は Clean Architecture 前提です。
  - 依存方向は `interface -> application -> domain`
  - `import-lint` でレイヤ違反を検出します
- 型注釈は必須です。
  - Python では暗黙 `Any` を作らない
  - TypeScript では `any` を避ける
- 生成物や一時物はコミットしません。
  - 例: `dist/`, `backend/build/`, `frontend/dist/`, `frontend/src/generated/`, `frontend/test-results/`
- 秘密情報や認証情報はコミットしません。
- OBS / FFmpeg / Tesseract / YouTube 認証など、アプリ利用者向けの外部ツール設定は
  [`docs/usage.md`](./usage.md) を参照してください。
- 実行コマンドの正本は [`Taskfile.yml`](../Taskfile.yml) です。

## よくある補足

### `task.exe dev` を実行しても画面が増えない

Windows では PowerShell が 2 つ開く想定です。開かない場合は `task.exe dev` の標準出力にエラーが出ていないか確認してください。
個別に切り分けたい場合は `task.exe dev:backend` と `task.exe dev:frontend` を別ターミナルで実行してください。

### Playwright E2E で replay asset 関連のエラーが出る

まず `git lfs version` で Git LFS が使えるか確認し、必要なら次を実行してください。

```bat
task.exe install:lfs
```

そのうえで E2E を再実行してください。`pretest:e2e` が必要な取得処理を補助します。

### frontend の生成型が古い

`frontend/src/generated/` を手で直さず、次を実行してください。

```bat
task.exe generate
```

### どの Task があるか確認したい

```bat
task.exe help
```

## 関連ドキュメント

- [`README.md`](../README.md) - プロジェクト概要
- [`docs/usage.md`](./usage.md) - 利用者向けセットアップと外部ツール設定
- [`docs/test_strategy.md`](./test_strategy.md) - テスト選定の SSOT
- [`docs/e2e_replay_test.md`](./e2e_replay_test.md) - replay ベース E2E の詳細
- [`docs/internal_design.md`](./internal_design.md) - 内部設計
- [`docs/external_spec.md`](./external_spec.md) - 外部仕様
- [`AGENTS.md`](../AGENTS.md) - プロジェクト全体の実装ルール
- [`backend/src/splat_replay/domain/AGENTS.md`](../backend/src/splat_replay/domain/AGENTS.md) - domain 層のルール
- [`backend/src/splat_replay/application/AGENTS.md`](../backend/src/splat_replay/application/AGENTS.md) - application 層のルール
- [`backend/src/splat_replay/interface/AGENTS.md`](../backend/src/splat_replay/interface/AGENTS.md) - interface 層のルール
- [`backend/src/splat_replay/infrastructure/AGENTS.md`](../backend/src/splat_replay/infrastructure/AGENTS.md) - infrastructure 層のルール
- [`frontend/AGENTS.md`](../frontend/AGENTS.md) - frontend 固有ルール
