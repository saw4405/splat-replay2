# 開発ガイド

このドキュメントは、Splat Replay の**開発環境構築・日常開発フロー・検証入口**をまとめた
how-to です。特別な注記がない限り、コマンドはリポジトリルートで実行してください。

> Windows 環境では `task` ではなく **`task.exe`** を使用します。

## この文書の責務

この文書で扱う内容:

- 開発に必要な前提ツール
- 初回セットアップ
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

- OS: Windows 11
- シェル: PowerShell
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

### 推奨: まず `task.exe install` を実行する

まずは推奨セットアップとして、次を実行してください。

```bat
task.exe install
```

このタスクは次を実行します。

- backend: `uv sync`
- frontend: `npm install`
- Git hooks の自動設定を試行
- Git LFS の初期化を試行

成功判定:

- エラーなく終了する
- backend の仮想環境と frontend の依存関係が解決される
- Git hooks / Git LFS は利用可能な環境で自動設定される

Git hooks や Git LFS を自動設定したくない場合は、次を使います。

```bat
task.exe install SKIP_HOOKS=1 SKIP_LFS=1
```

### Git hooks を有効化・再設定したい場合

`task.exe install` は既定で Git hooks の設定を試行します。スキップした場合や、
後からやり直したい場合は次を実行してください。

```bat
task.exe install:hooks
```

Git hooks では次を確認します。

- `pre-commit` では backend の `ruff` / `ty` と、frontend の staged files 向け `prettier` / `eslint` を走らせます。
- `pre-push` では frontend 全体の `type-check` / `svelte-check` と、backend の `import-lint` を走らせます。
- `task.exe test` は自動では走りません。
- 必須の品質確認は Git hooks ではなく、引き続き `task.exe verify` と CI で担保します。

### workflow E2E を使う場合

`frontend/tests/fixtures/e2e/**/*.mkv` は Git LFS 管理です。`task.exe install` は
既定で Git LFS の初期化を試行します。初期化をやり直したい場合は次を実行してください。

```bat
task.exe install:lfs
```

E2E 実行時の補足:

- `npm run test:e2e` の `pretest:e2e` で replay asset の実体化を確認します。
- 必要なら内部的に `git lfs pull` を実行します。

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
3. 実装後、まず `task.exe test`
4. 変更内容に応じて追加の入口を実行
5. 完了前に `task.exe verify`

原則:

- まず Taskfile の意味ベース入口を使います。
- 生の `npm` / `uv` / `pytest` コマンドは、Task がない場合か、低レベルの切り分け時だけ使います。
- テスト選定に迷ったら [`docs/test_strategy.md`](./test_strategy.md) を優先してください。

## 検証とテスト

### 基本入口

| 目的                 | コマンド                 | 補足                                                            |
| -------------------- | ------------------------ | --------------------------------------------------------------- |
| 日常の基本テスト     | `task.exe test`          | backend の既定テスト + frontend unit                            |
| 完了前の最低入口     | `task.exe verify`        | `format:check` / `lint` / `type-check` / `import-lint` / `test` |
| backend の既定テスト | `task.exe test:backend`  | `pytest` 既定設定に従い `perf` は除外                           |
| frontend unit 一括   | `task.exe test:frontend` | `logic + component + integration`                               |

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

```bat
task.exe build
```

成果物:

- 配布物: `dist/SplatReplay/`
- 中間生成物: `backend/build/`

補足:

- `backend/build/` は中間生成物です。実行対象ではありません。
- 配布物の実行は `dist/SplatReplay/SplatReplay.exe` を使います。

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
