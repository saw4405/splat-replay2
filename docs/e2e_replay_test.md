# 動画リプレイ入力による E2E 回帰テスト

この文書は、replay asset を使った `workflow` テストの詳細仕様書です。
全体のテスト分類、入口選定、AI エージェント向け運用ルールは
[テスト戦略](./test_strategy.md) を参照してください。
この文書では、replay asset、sidecar、観測点、直接実行方法の詳細だけを扱います。

## 1. 目的

この E2E テスト基盤は、実機プレイを毎回やり直さずに、事前に保存した試合動画で UI を含む自動録画フローの回帰を確認するための仕組みです。

主な目的は次のとおりです。

- 設定画面の保存導線が壊れていないことを確認する
- 自動録画の準備、開始、停止、録画済み一覧反映が壊れていないことを確認する
- sidecar JSON がある場合、録画済み一覧に表示されたメタデータが期待値と一致することを確認する

## 2. この文書で扱う範囲

### 2.1. この詳細書で確認すること

- 通常設定の保存と再読込
- replay 入力アダプタでの録画準備
- フル動画 replay による自動録画開始
- メタデータ更新
- 録画済み一覧への新規追加
- 録画済み一覧の主要メタデータ表示

### 2.2. この詳細書で確認しないこと

- OBS 仮想カメラ / NDI / 実キャプチャデバイスの本番接続
- ブラウザ上のライブプレビュー映像そのものの画質評価
- OBS による実録画そのもの

未確認事項ではありませんが、上記はこの基盤の責務外です。replay 入力時の録画データは入力動画のコピーで代替しています。

## 3. 実装仕様

### 3.1. backend 側

- E2E 実行時の動画入力は、通常の `settings.toml` とは別の一時ファイル `e2e-replay-input.json` で注入します。
- このファイルには `video_path` だけを持たせます。
- `e2e-replay-input.json` は設定 UI や `/api/settings` には公開しません。
- replay 入力時は `CapturePort` が `VideoFileCapture` に切り替わります。
- `video_path` がディレクトリのときは、その中の `.mkv` を 1 本自動選択します。
  - 現在の実装では、ファイルサイズが最小の `.mkv` を優先します。
  - 同サイズならファイル名順です。
- `VideoRecorderPort` は `ReplayRecorderController` に切り替わり、停止時に入力動画を一時出力へコピーします。
- `CaptureDevicePort.is_connected()` は、replay 入力時は `video_path` の存在で判定します。
- 自動録画の開始条件は OBS 入力と replay 入力で共通です。
  - マッチング/開始検知を通過したときだけ録画を開始します。
  - replay 専用の強制開始や開始条件の緩和は持ちません。
- replay 入力では、録画ロジックの時間判定を壁時計ではなく入力動画の再生位置で評価します。
  - ブキ検出窓、早期中断判定、録画時間上限は live_capture と同じ秒数設定です。
  - ただし経過時間の算出元だけが動画基準に切り替わります。
- replay 入力向けの E2E asset は、開始検知を通せるフル動画だけを `frontend/tests/fixtures/e2e/auto-recording/` に置きます。
  - 途中から始まる短いクリップは auto-recording E2E の対象にしません。

### 3.2. frontend 側

- replay 入力時は `VideoPreview` が `getUserMedia` を呼びません。
- 代わりに `/api/recorder/preview-mode` で入力種別を取得し、replay 入力かどうかを判定します。
- 代わりに backend の `/api/recorder/preview-frame` から、解析中の最新フレーム JPEG を定期取得してプレビュー表示します。
- このプレビューは「入力動画の通常再生」ではなく、backend が実際に処理している最新フレームです。
- E2E のメタデータ照合先は「メタデータ編集ダイアログ」ではなく「録画済み一覧」です。
  - 録画済み一覧は保存済みアセットの表示を見ているため、E2E の回帰確認対象として安定しています。

### 3.3. Playwright 実行時の環境変数

- Playwright が自動設定する値
  - `SPLAT_REPLAY_SETTINGS_FILE=<tmp>/settings.toml`
- replay asset の対象数を切り替える内部環境変数
  - `SPLAT_REPLAY_E2E_MODE=smoke|full`
  - `smoke` は bundled replay asset の先頭 1 件だけを対象にする
  - `full` は bundled replay asset をすべて対象にする
- replay 供給速度を切り替える内部環境変数
  - `SPLAT_REPLAY_E2E_FRAME_STRIDE=<整数>`
  - 既定では `smoke=3`, `full=1`
  - `smoke` は `VideoFileCapture` が 3 フレームごとに 1 フレームを処理し、
    開発時の反復を優先する
  - `full` は全フレームを対象にし、release 前の回帰確認を優先する

ユーザーが動画パス用の環境変数を設定する必要はありません。標準実行では、リポジトリ内の replay asset を自動で使います。

- `frontend/tests/fixtures/e2e/auto-recording/`
- この中にあるすべての `.mkv` を検出し、各動画ごとに E2E テストケースを生成します。
- 同名 `.json` sidecar があれば、その動画の期待値として使います。

### 3.4. 一時設定と保存先

- E2E 実行時は一時ディレクトリ配下に `settings.toml` を生成します。
- E2E 実行時は同じ一時ディレクトリ配下に `e2e-replay-input.json` も生成します。
- `storage.base_dir` も一時ディレクトリに切り替わります。
- そのため、通常のユーザー設定や既存録画データは汚しません。
- 各テストケースの開始前に、保存先ディレクトリを空にし、`settings.toml` を既定状態へ戻します。
- `auto-recording-workflow` は対象動画のファイルパスを `e2e-replay-input.json` に直接書き込みます。
- `settings-persistence` は UI から通常設定を保存し、再読込を確認します。
- replay input は E2E 実行のための内部注入値であり、設定保存 E2E の検証対象にも設定 UI にも含めません。
- `settings-persistence` は replay asset 数に依存せず 1 回だけ実行します。

### 3.5. sidecar JSON の扱い

- 選択された動画と同じベース名の `.json` があれば、期待値として読み込みます。
- 比較対象は次のメタデータです。
  - `game_mode`
  - `match`
  - `rule`
  - `stage`
  - `rate`
  - `judgement`
  - `kill`
  - `death`
  - `special`
  - `gold_medals`
  - `silver_medals`
- `allies` / `enemies` は workflow E2E では「4 スロットが UI に有効値として表示されること」を確認します。
- exact な武器識別の正しさは backend の recognizer / fixture テストで担保し、workflow E2E では責務に含めません。

## 4. テストケース

現在の E2E は 2 本です。

- `tests/e2e/settings-persistence.spec.ts`
  - `behavior.edit_after_power_off`
  - 上記が保存後も保持されることを確認
- `tests/e2e/auto-recording-workflow.spec.ts`
  - `frontend/tests/fixtures/e2e/auto-recording/` の asset ごとに replay input を事前投入
  - 録画準備
  - 自動録画開始
  - 自動録画停止
  - 録画済み一覧への追加
  - sidecar があれば一覧表示との照合

## 5. 使い方

### 5.1. 前提

- backend の依存がインストール済みであること
- frontend の依存がインストール済みであること
- Playwright が実行可能であること
- `frontend/tests/fixtures/e2e/auto-recording/` にフル動画 replay asset が存在すること

### 5.2. 意味ベース入口で実行する

通常運用では、親文書で定義した意味ベース入口を使います。
`workflow` の日常確認と release 前確認は、次を基準にします。

```bat
cd /d C:\Users\shogo\repo\splat-replay2
task.exe test:workflow:smoke
task.exe test:workflow:full
```

- `test:workflow:smoke`
  - 軽量確認用です
  - replay asset は 1 件だけを対象にします
- `test:workflow:full`
  - release 前または広範囲変更向けです
  - replay asset を全件対象にし、clean-run 前提で実行します

入口選定そのものは [テスト戦略](./test_strategy.md) を参照してください。

### 5.3. replay E2E を直接実行する

この節は、replay E2E 自体を直接動かしたいときの下位入口です。
個別デバッグや Playwright 挙動確認に使います。

#### Taskfile 経由（推奨）

`task.exe` を使う場合は、リポジトリルートで実行します。

```bat
cd /d C:\Users\shogo\repo\splat-replay2
task.exe test:e2e
```

内部的には frontend の Playwright を起動します。

ブラウザを表示したまま確認したい場合は、headed 用タスクを使います。

```bat
cd /d C:\Users\shogo\repo\splat-replay2
task.exe test:e2e:headed
```

### 5.4. frontend で直接実行

`frontend` ディレクトリで実行します。

#### cmd.exe

```bat
cd /d C:\Users\shogo\repo\splat-replay2\frontend
npm run test:e2e
```

#### PowerShell

```powershell
Set-Location C:\Users\shogo\repo\splat-replay2\frontend
npm run test:e2e
```

### 5.5. 個別実行

#### Taskfile 経由

```bat
task.exe test:frontend:e2e:settings
task.exe test:frontend:e2e:auto-recording
task.exe test:frontend:e2e:settings:headed
task.exe test:frontend:e2e:auto-recording:headed
```

#### 設定保存だけ確認する

```bat
npm run test:e2e -- tests/e2e/settings-persistence.spec.ts
```

#### 自動録画フローだけ確認する

```bat
npm run test:e2e -- tests/e2e/auto-recording-workflow.spec.ts
```

### 5.6. CI 相当で再利用中サーバを避けたい場合

通常は `task.exe test:workflow:full` を使えば十分です。
この節は、frontend で直接 Playwright を起動して挙動確認したい場合の下位手順です。

```bat
set CI=1
npm run test:e2e
```

## 6. 実行時の挙動

- Playwright が backend の `uvicorn` と frontend の `vite` を自動起動します。
- 標準では `frontend/tests/fixtures/e2e/auto-recording/` の replay asset を使います。
- `SPLAT_REPLAY_E2E_MODE=full` では、このディレクトリ内の `.mkv` ごとに
  `auto-recording-workflow` のケースが増えます。
- `SPLAT_REPLAY_E2E_MODE=smoke` では、ファイル名順で先頭の bundled asset 1 件だけを使います。
- `auto-recording-workflow` は対象動画の絶対パスを settings に直接書き込んでから開始します。
- そのため、動画パス指定を UI から毎回操作する必要はありません。
- `settings-persistence` は asset 数に関係なく 1 回だけ実行し、通常設定の保存導線だけを確認します。
- settings には初期値として次を投入します。
  - `edit_after_power_off = false`
  - `sleep_after_upload = false`
  - `record_battle_history = false`
- 録画終了後、録画済み一覧に 1 件追加されることを前提に検証します。

## 7. 失敗時の確認ポイント

### 7.1. 動画が見つからない

- `frontend/tests/fixtures/e2e/auto-recording/` に `.mkv` が存在するか確認してください。

### 7.2. sidecar 比較で落ちる

- 比較は一覧表示ベースです。
- `allies` / `enemies` も一覧表示ベースで厳密一致します。
- 落ちる場合は、実際の UI 表示と sidecar の期待値がずれている可能性があります。

### 7.3. 失敗時の成果物

- Playwright の失敗スクリーンショット
- Playwright の失敗動画
- `frontend/test-results/`

に出力されます。

## 8. 関連ファイル

- 全体戦略: `docs/test_strategy.md`
- Playwright 設定: `frontend/playwright.config.ts`
- E2E 環境初期化: `frontend/tests/e2e/support/e2eEnv.ts`
- E2E グローバルセットアップ: `frontend/tests/e2e/support/globalSetup.ts`
- 自動録画フロー検証: `frontend/tests/e2e/auto-recording-workflow.spec.ts`
- 設定保存検証: `frontend/tests/e2e/settings-persistence.spec.ts`

全体のテスト分類、意味ベース入口、AI エージェント向け運用ルールは
[テスト戦略](./test_strategy.md) を参照してください。
