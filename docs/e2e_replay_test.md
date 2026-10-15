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

`*.json` は replay fixture の sidecar にある `expected` だけを recorded metadata として保存します。
`scenario` と `observations` は replay 入力専用であり、recorded seed へ混在させません。
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

## 6. replay 実行プロファイル

Playwright の backend は `SPLAT_REPLAY_RUNTIME_PROFILE=replay` で起動します。有効な replay 入力が無ければ起動時に失敗します。この profile は録画・キャプチャ・電源の入力を replay adapter に置き換えます。OBS/NDI、実機キャプチャデバイス・マイク、OS の電源操作を使った録画確認ではありません。

spec 実行中に `configureReplayAsset()` が replay 入力を切り替える既存の挙動は維持します。入力が無くなった場合に実機入力へ黙って戻ることはありません。

WSL2 / Linux での `workflow:full` 合格は、その環境で bundled replay workflow が通ることを示す可搬性ゲートです。別 OS の製品配布、初回導入、OS 権限、実機との接続を検証するものではありません。VM / WSL2 の結果は記録した構成・候補に限り、別候補や実機へ一般化しません。

sidecar は `schema_version`、`scenario`、`observations`、`expected` を分離します。
replay backend には `scenario` と `observations` だけを渡し、`expected` は UI の独立した期待値です。

`scenario` と `observations` で差し替えるのは外部入力です。武器認識・OCR・表彰認識の結果は既存ポートから返し、その後の録画状態遷移、メタデータ更新、実 storage への保存、API/UI は実装を通ります。編集 workflow は実 FFmpeg とファイル副作用を通ります。`backend/tests/contract/test_ffmpeg_output_contract.py`（contract）は、ffmpeg / ffprobe がある環境で実出力の連結順・期間・title metadata とキャンセル時の子プロセス終了を確認します。外部観測結果が後段へ伝播する結線は保証しますが、実 OBS/NDI/音声・キャプチャ機器、OS 権限、実 Tesseract / CV の精度・性能は保証しません。実 Tesseract / CV の精度・性能は固定フレームの lower integration / performance テストで測ります。実 OCR 統合テストには OS 側の `tesseract` コマンドが必要です。

Playwright backend は `SPLAT_REPLAY_E2E_NOOP_UPLOAD=1` で起動し、アップロード先を `NoOpUploadPort` にします。`edit-upload-workflow.spec.ts` は完了 UI、成功状態、録画・編集済み asset 一覧が空であることを確認します。これはアプリ内処理と削除結果までを示し、YouTube 外部認証や実アップロードを示しません。

E2E helper は一時 root の設定と storage を使い、spec 間の初期化もその storage 内に限定します。REPLAY の `SPLAT_REPLAY_E2E_ROOT` は絶対パスにし、`SPLAT_REPLAY_SETTINGS_FILE` または `SPLAT_REPLAY_E2E_STORAGE_DIR` を上書きする場合も、絶対 root 配下の隔離先を指定してください。root 外・相対の設定先や保存先は拒否されます。LIVE の保存先仕様には適用されません。

セットアップ gate の範囲も分けて扱います。`RuntimeProfile.REPLAY` でも `SetupService` / `SystemCheckService` の必須判定・集約経路を維持し、LIVE の必須 gate を無効にしません。Composition Root で REPLAY adapter に差し替えるのは OBS / DistroAV / NDI 等の外部観測 checker だけです。Playwright の E2E 環境は導入履歴を完了状態で用意するため、通常 workflow は初回導入全体を検証しません。`required-setup-gate.spec.ts` は setup API を stub して不足時の UI 表示・修復先を検証します。backend の `test_required_setup_service.py` は有効設定 fixture と不足条件を使って `SetupService` の判定を確認しますが、外部 checker を制御するため実 OS への導入確認ではありません。新しい必須条件を加えるときは、有効 fixture で不足なしとなることと、その条件を欠く fixture で gate が拒否することを service の実判定で確認します。

## 7. 実行コマンド

以下は Windows の実行例です。macOS / WSL2 / Linux ではチェックアウトの場所に読み替え、`cd /d` を `cd` に、Task コマンドの `task.exe` を `task` に置き換えてください。

### 7.1. suite 全体

```bat
cd /d C:\path\to\splat-replay2
task.exe test:e2e
task.exe test:e2e:headed
task.exe test:workflow:smoke
task.exe test:workflow:full
```

### 7.2. replay を使う spec

```bat
cd /d C:\path\to\splat-replay2\frontend
npm run test:e2e -- tests/e2e/auto-recording-workflow.spec.ts
npm run test:e2e -- tests/e2e/recording-metadata-edit-workflow.spec.ts
npm run test:e2e -- tests/e2e/error-recovery-recording-live.spec.ts
```

### 7.3. recorded seed の spec

```bat
cd /d C:\path\to\splat-replay2\frontend
npm run test:e2e -- tests/e2e/edit-upload-workflow.spec.ts
npm run test:e2e -- tests/e2e/multi-video-management.spec.ts
npm run test:e2e -- tests/e2e/recorded-metadata-edit-workflow.spec.ts
npm run test:e2e -- tests/e2e/error-recovery-recorded-assets.spec.ts
```

### 7.4. no-video の spec

```bat
cd /d C:\path\to\splat-replay2\frontend
npm run test:e2e -- tests/e2e/settings-persistence.spec.ts
```

## 8. 保守ルール

新しい E2E を追加するときは、先に次の基準で判定します。

- 実 backend / 実 storage / replay 録画状態を跨ぐ workflow か
- 既存の lower test では拾いにくい結線バグを狙っているか
- 既存 E2E と user-visible な成功 / 失敗パターンが重複していないか

追加しない方がよいケースは次のとおりです。

- field 単位のフォーム操作差分
- `500` と validation error のように、同じ recovery UX を別 spec で重ねるケース
- replay を前提データ作成のためだけに流すケース

迷った場合は、先に lower test で担保できないかを確認してから E2E を増やします。
