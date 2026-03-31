# replay 動画を使う E2E テスト

`frontend/tests/e2e/` で運用している workflow E2E のうち、どの spec が replay 動画を使うか、どの spec が recorded seed / no-video で十分かを整理したドキュメントです。

## 1. 方針

E2E は次のような「実境界をまたぐ代表 workflow」に限定します。

- replay を使う E2E
  - 自動録画の制御
  - 録画早期終了
  - 録画中 UI を前提にした代表操作
  - 録画中 UI を前提にした代表的なエラー復旧
- recorded seed を使う E2E
  - 録画済み動画が存在すれば成立する workflow
  - 一覧表示、処理開始、複数動画の独立性、録画済み一覧の再取得復旧
- no-video の E2E
  - 実 storage / 実 backend の永続化確認など、動画状態に依存しない workflow

逆に、次のような UI ローカル挙動は E2E へ増やさず lower test で担保します。

- 録画中フォームの `Now` / `リセット` / 再マウント時の未保存破棄
- 録画済みメタデータ編集ダイアログの cancel / reopen / field 単位の操作
- 録画済み一覧の metadata save retry / delete success / delete failure
- 設定保存失敗時のフィードバック

## 2. 現在の E2E 構成

### 2.1. replay を使う spec

- `frontend/tests/e2e/auto-recording-workflow.spec.ts`
  - 自動録画の開始、録画保存、録画早期終了を replay 経由で検証します。
  - `自動録画制御` と `録画早期終了` は必ず E2E に残します。
- `frontend/tests/e2e/recording-metadata-edit-workflow.spec.ts`
  - 録画中メタデータ編集の代表保存 workflow を replay 経由で検証します。
- `frontend/tests/e2e/error-recovery-recording-live.spec.ts`
  - 録画中 UI を前提にした代表的なエラー復旧を replay 経由で検証します。

### 2.2. recorded seed を使う spec

- `frontend/tests/e2e/edit-upload-workflow.spec.ts`
  - 録画済み 1 件を前提に、編集・アップロード開始から完了までを検証します。
- `frontend/tests/e2e/multi-video-management.spec.ts`
  - 複数動画でのメタデータ編集が対象動画だけに反映されることを検証します。
- `frontend/tests/e2e/recorded-metadata-edit-workflow.spec.ts`
  - 録画済みメタデータ編集の代表保存を検証します。
- `frontend/tests/e2e/error-recovery-recorded-assets.spec.ts`
  - 録画済み一覧の取得失敗から再読込で復旧できることを検証します。

これらの spec は replay を再生せず、E2E 用 `storage/recorded` に直接 seed した録画済み動画を使います。  
spec 側で `/api/recorder/enable-auto` を監視し、動画再生 API を踏んでいないことを guard します。

### 2.3. 動画ファイル不要の spec

- `frontend/tests/e2e/settings-persistence.spec.ts`
  - 設定保存後に実 backend / 実 storage へ永続化されることを検証します。

`error-recovery-settings.spec.ts` は削除済みです。  
設定保存失敗の UI は lower test と backend contract で担保します。

## 3. lower test へ移した責務

### 3.1. 録画中メタデータ UI

- `frontend/src/main/components/metadata/MetadataOverlay.component.test.ts`
  - `Now` ボタン
  - `リセット`
  - 再マウント時の未保存変更破棄
- `frontend/src/main/components/metadata/MetadataForm.component.test.ts`
  - field 単位の入力・select 操作
- `frontend/src/main/components/metadata/metadata-edit-flow.integration.test.ts`
  - 録画済みメタデータ編集ダイアログの save / cancel / reopen

### 3.2. 録画済み一覧 UI

- `frontend/src/main/components/assets/RecordedDataList.component.test.ts`
  - metadata save error からの retry
  - delete success の refresh 通知
  - delete failure の error 表示

### 3.3. 設定 UI

- `frontend/src/main/components/settings/settings-flow.integration.test.ts`
  - 設定 save / failure feedback / reopen

## 4. recorded seed の仕組み

recorded seed は frontend 側 helper で E2E 用一時 storage に録画済み asset を直接配置します。

- 実装: `frontend/tests/e2e/support/recordedSeed.ts`
- 呼び出し: `frontend/tests/e2e/support/appHelpers.ts`
- 配置先: `<temp storage>/recorded/`

作るファイルは次の 2 種類です。

- `*.mkv` または `*.mp4`
- 同名の `*.json`

`*.json` は replay fixture の sidecar をベースにしつつ、`scenario` を除外した recorded metadata として保存します。  
必要に応じて `fileStem` と `metadataOverride` を指定して、同じ replay fixture から複数の recorded seed を作れます。

## 5. replay fixture とモード

replay fixture は次のディレクトリに配置しています。

- `frontend/tests/fixtures/e2e/auto-recording/`

モード解決は `frontend/tests/e2e/support/e2eEnv.ts` が担当します。

- `SPLAT_REPLAY_E2E_MODE=smoke`
  - 最小の bundled replay asset だけを使います。
- `SPLAT_REPLAY_E2E_MODE=full`
  - bundled replay asset をすべて使います。

既定値は `full` です。

## 6. 実行コマンド

### 6.1. suite 全体

```bat
cd /d C:\Users\shogo\repo\splat-replay2
task.exe test:e2e
task.exe test:e2e:headed
task.exe test:workflow:smoke
task.exe test:workflow:full
```

### 6.2. replay を使う spec

```bat
cd /d C:\Users\shogo\repo\splat-replay2\frontend
npm run test:e2e -- tests/e2e/auto-recording-workflow.spec.ts
npm run test:e2e -- tests/e2e/recording-metadata-edit-workflow.spec.ts
npm run test:e2e -- tests/e2e/error-recovery-recording-live.spec.ts
```

### 6.3. recorded seed の spec

```bat
cd /d C:\Users\shogo\repo\splat-replay2\frontend
npm run test:e2e -- tests/e2e/edit-upload-workflow.spec.ts
npm run test:e2e -- tests/e2e/multi-video-management.spec.ts
npm run test:e2e -- tests/e2e/recorded-metadata-edit-workflow.spec.ts
npm run test:e2e -- tests/e2e/error-recovery-recorded-assets.spec.ts
```

### 6.4. no-video の spec

```bat
cd /d C:\Users\shogo\repo\splat-replay2\frontend
npm run test:e2e -- tests/e2e/settings-persistence.spec.ts
```

## 7. 保守ルール

新しい E2E を追加するときは、先に次の基準で判定します。

- 実 backend / 実 storage / replay 録画状態を跨ぐ workflow か
- 既存の lower test では拾いにくい結線バグを狙っているか
- 既存 E2E と user-visible な成功 / 失敗パターンが重複していないか

追加しない方がよいケースは次のとおりです。

- field 単位のフォーム操作差分
- `500` と validation error のように、同じ recovery UX を別 spec で重ねるケース
- replay を前提データ作成のためだけに流すケース

迷った場合は、先に lower test で担保できないかを確認してから E2E を増やします。
