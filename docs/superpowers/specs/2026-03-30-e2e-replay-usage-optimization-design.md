# E2E replay 使用量適正化 設計
作成日: 2026-03-30

## 背景

現状の frontend E2E は、録画済み一覧・削除・録画済みメタデータ編集・編集アップロード開始のような「録画結果が存在すれば成立する検証」でも、前提データ作成のために replay 動画を再生している。

ローカル実装の確認では、`task.exe test:e2e` 相当の Playwright E2E 全体で replay 動画の再生開始が 33 回発生している。これは主に次の理由による。

- 1 本のバトル動画から録画済み asset を作るために、spec ごとに `ensureAutoRecordingEnabled()` を繰り返している
- 録画済みデータの存在確認が主題の spec でも、録画生成を毎回 replay に依存している
- `error-recovery.spec.ts` が「録画中前提」「録画済み前提」「設定保存前提」を 1 ファイルに混在させている

一方で、ユーザー要件は明確である。

- 動画ファイルを使うのは「自動録画の制御検証」だけに寄せたい
- ただし「録画中の操作を前提とする E2E」は動画ファイルありでよい
- 重複・不要と思われる E2E は、このタイミングで基準を定めたうえで除去したい

## 目的

- バトル 1 本分の動画ファイルを使う E2E を、「自動録画の制御」または「録画中の操作」が本質のものへ限定する
- 録画済み asset が存在すれば成立する E2E は filesystem seed で前提を作り、動画再生を不要にする
- E2E の責務境界を整理し、同じ失敗パターンや同じ UI 価値を重複検証しているケースを削減する
- Playwright の test isolation を損なわずに、失敗切り分けしやすい構成へ寄せる
- `docs/e2e_replay_test.md` の実行方法・責務境界・spec 構成を実装と一致させる

## 非目的

- 自動録画ロジック自体の仕様変更
- backend の recorded asset 永続仕様の再設計
- lower test で担保すべき詳細検証を、E2E 側へ追加すること
- すべての E2E を seed 化すること

## 制約

- 既存の E2E 一時環境構築 (`frontend/tests/e2e/support/e2eEnv.ts`) を前提にする
- backend recorded asset 一覧は `recorded_dir` 直下の `*.mkv` / `*.mp4` と同名 sidecar を列挙する現在仕様に従う
- Clean Architecture は維持し、seed 追加のために backend 本体の責務を E2E 専用へ汚染しない
- spec 間の依存は作らない

## 一次情報とベストプラクティス

- Playwright Best Practices
  - https://playwright.dev/docs/best-practices
  - ユーザー可視の挙動を検証すること
  - 各テストを可能な限り独立させること
  - 単純さと保守性を損なう重複共有を避けること
- Playwright Isolation
  - https://playwright.dev/docs/browser-contexts
  - 各テストは独立して実行される前提で設計し、前テストの状態に依存しないこと

この設計では、上記を次のように解釈して適用する。

- replay は「録画遷移を本当に通る必要がある」E2E に限定する
- replay を前提データ生成のためだけに使うケースは seed 化へ置き換える
- 異なる前提状態を 1 spec に混在させず、責務ごとに分割する
- 同一価値を別入力で繰り返している成功系 E2E は統合する

## 判定基準

### 1. replay を残す基準

次のいずれかに当てはまる場合は replay を残す。

- 実際の自動録画開始・継続・停止・中断の制御を通ること自体が検証対象
- 録画中状態でしか成立しない UI / API 操作が主題
- 録画中のメタデータや録画中イベント連携が主題

### 2. seed 化する基準

次のいずれかに当てはまる場合は replay を使わず recorded asset seed を使う。

- 録画済み一覧に asset が存在することだけが前提
- 録画済み動画の削除・編集・編集アップロード開始が主題
- 複数動画の並び・独立性・件数表示が主題
- 録画済み asset 向けエラー回復が主題

### 3. 動画不要の基準

次に当てはまる場合は動画も seed も不要とする。

- 設定保存・設定読み込みだけが主題
- backend / frontend の失敗が、録画中でも録画済みでもない初期状態で再現可能

### 4. 重複・不要 E2E の判定基準

この変更では、次の基準で重複・不要 E2E を判断する。

- 同じ前提状態、同じユーザー価値、同じ成功条件なら 1 本へ統合する
- 値だけ違い、通る画面遷移・保存経路・失敗時 UX が同じなら 1 本へ統合する
- `500` と通信遮断のように原因が違っても、ユーザー可視の失敗パターンと回復操作が同じなら代表 1 本だけ残す
- field ごとの差分確認が lower test で担保可能なら、E2E では代表項目だけ残す
- replay を前提生成のためだけに使っているケースは不要とみなす

## 現状 spec の再分類

### replay を維持する spec

- `frontend/tests/e2e/auto-recording-workflow.spec.ts`
  - 自動録画開始・停止・early abort そのものが主題
- `frontend/tests/e2e/recording-metadata-edit-workflow.spec.ts`
  - 録画中操作を前提としている
- `frontend/tests/e2e/error-recovery.spec.ts` のうち録画中前提のケース
  - 録画中メタデータオプション取得失敗
  - 録画中メタデータ保存失敗
  - 録画中ネットワーク障害からの回復

### seed 化する spec

- `frontend/tests/e2e/edit-upload-workflow.spec.ts`
  - 主題は編集・アップロード開始であり、録画済み asset があれば成立する
- `frontend/tests/e2e/multi-video-management.spec.ts`
  - 主題は複数 recorded asset の一覧・削除・独立性
- `frontend/tests/e2e/recorded-metadata-edit-workflow.spec.ts`
  - 主題は recorded asset の編集 UI
- `frontend/tests/e2e/error-recovery.spec.ts` のうち録画済み前提のケース
  - 録画済みメタデータ更新失敗
  - 録画済み一覧取得失敗
  - 録画済み削除 API 失敗
  - 録画済みメタデータのバリデーションエラー

### 動画不要の spec

- `frontend/tests/e2e/settings-persistence.spec.ts`
- `frontend/tests/e2e/error-recovery.spec.ts` の設定保存失敗ケース

## 設計方針

### 方針 A: replay は「録画遷移」と「録画中操作」へ限定する

採用する方針は次のとおり。

- replay helper は残す
- recorded asset seed helper を追加する
- replay と seed を spec の責務で使い分ける
- `error-recovery.spec.ts` は前提状態ごとに分割する
- 重複している成功系 / 失敗系 E2E は、この移行と同時に削減する

この方針を採用する理由は次のとおり。

- ユーザー条件と一致する
- 自動録画の重要経路は E2E で維持できる
- 録画済み asset ベースの UI テストを高速化できる
- Playwright の isolation 原則に沿って責務分割しやすい

## seed 化の方式

### 方式選定

recorded asset の seed 方式は、backend API 注入ではなく filesystem seed を採用する。

理由:

- backend の recorded asset 一覧は filesystem を真実源としており、実装仕様と一致する
- E2E 専用 API を追加せずに済む
- recorded asset の一覧・削除・編集 UI は filesystem 上の実物を使っても責務を損なわない
- frontend 側 helper だけで閉じやすい

### seed で用意するファイル

E2E seed は、E2E 一時 storage の `recorded/` へ以下を配置する。

- `*.mkv` または `*.mp4`
- 必要に応じて同名 `*.json`
- 必要に応じて同名 `*.srt`
- 必要に応じて同名 `*.png`

初回実装では、最低限 `video + json` を対象にする。`srt` と `png` は対象 spec が必要とする場合だけ後から追加する。

### seed 元

seed 元は、既存 replay fixture を再利用する。

- `frontend/tests/fixtures/e2e/auto-recording/*.mkv`
- 同名 sidecar `*.json`

recorded asset seed helper は、fixture から E2E temp storage へコピーまたはハードリンクで複製する。ファイル名は衝突回避のため一意化する。

### helper の責務

`frontend/tests/e2e/support/` に recorded seed helper を追加し、責務を次のように分ける。

- `prepareReplayAsset*`
  - replay input を設定する
  - 自動録画を実際に走らせる spec のみ使用
- `seedRecordedAsset*`
  - recorded/ に動画と sidecar を直接配置する
  - recorded asset が存在すれば成立する spec のみ使用
- `seedMultipleRecordedAssets`
  - 2 件以上の一覧前提を 1 回で作る

この分離により、「録画中前提」と「録画済み前提」を helper 名だけで区別できるようにする。

## spec 構成の見直し

### `error-recovery` の分割

`frontend/tests/e2e/error-recovery.spec.ts` は、前提状態が異なるケースを 1 ファイルに混在させている。これは Playwright の isolation とデバッグ容易性の観点で望ましくない。

分割後の想定:

- `frontend/tests/e2e/error-recovery-recording-live.spec.ts`
  - 録画中メタデータオプション取得失敗
  - 録画中メタデータ保存失敗
  - 録画中ネットワーク障害からの回復
- `frontend/tests/e2e/error-recovery-recorded-assets.spec.ts`
  - 録画済みメタデータ更新失敗
  - 録画済み一覧取得失敗
  - 録画済み削除失敗
  - 録画済みバリデーションエラー
- `frontend/tests/e2e/error-recovery-settings.spec.ts`
  - 設定保存失敗

### `recorded-metadata-edit-workflow` の圧縮

現状 5 本の成功系 E2E は重複がある。初回再編では次の 3 本へ圧縮する。

- `録画済みメタデータ編集ワークフロー`
  - 数値項目と選択項目を 1 回の保存で代表確認する
- `録画済みメタデータ編集 - キャンセル`
- `録画済みメタデータ編集 - ダイアログ再オープン時の初期値`

削除対象:

- `録画済みメタデータ編集 - 選択フィールドの変更`
  - 代表保存テストへ統合
- `録画済みメタデータ編集 - 複数フィールドの一括編集`
  - 代表保存テストへ統合

### `multi-video-management` の圧縮

現状の 7 本は、seed 化したうえで次の 6 本に整理する。

- `2件の一覧表示`
- `個別削除`
- `削除キャンセル`
- `動画ごとに独立したメタデータ状態`
- `空リスト時の表示`
- `全削除後の確認`

削除対象:

- `2本目のみ編集`
  - `ビデオごとに独立したメタデータ状態` と価値が重複しているため統合

### `edit-upload-workflow` の扱い

この spec は削除しないが、前提生成を replay から recorded seed へ置き換える。

理由:

- 主題は編集・アップロード開始であり、録画中遷移ではない
- ただし一覧からの導線、重複起動防止、進行表示は E2E 価値がある

### `recording-metadata-edit-workflow` の扱い

この spec は replay を維持する。録画中前提の UI 操作であり、今回の保持条件に一致するためである。

ただし、将来的に lower test で十分担保できる項目が見つかった場合は、別途圧縮余地を再評価してよい。

### `error-recovery-recording-live` の重複削減

録画中失敗系のうち、`メタデータ保存失敗` と `ネットワーク切断シミュレーション` はユーザー可視の失敗パターンが同一かどうかを実装で確認する。

- 同一のエラー表示・同一の回復操作に収束する場合
  - 代表 1 本へ統合する
- transport error と application error で UI 分岐が異なる場合
  - 両方を残す

現時点のコード読解では、暫定的には統合候補である。ただし未確認の分岐がありうるため、実装時に検証して最終判断する。

## 想定変更ファイル

### 新規または大きく変更する対象

- `frontend/tests/e2e/support/appHelpers.ts`
  - recorded seed helper 追加
  - replay helper と seed helper の責務整理
- `frontend/tests/e2e/support/e2eEnv.ts`
  - seed 用の temp path 解決補助
- `frontend/tests/e2e/edit-upload-workflow.spec.ts`
  - recorded seed 利用へ変更
- `frontend/tests/e2e/multi-video-management.spec.ts`
  - recorded seed 利用へ変更
  - 重複ケース削減
- `frontend/tests/e2e/recorded-metadata-edit-workflow.spec.ts`
  - recorded seed 利用へ変更
  - 重複ケース削減
- `frontend/tests/e2e/error-recovery-recording-live.spec.ts`
  - 新規
- `frontend/tests/e2e/error-recovery-recorded-assets.spec.ts`
  - 新規
- `frontend/tests/e2e/error-recovery-settings.spec.ts`
  - 新規
- `frontend/tests/e2e/error-recovery.spec.ts`
  - 削除
- `docs/e2e_replay_test.md`
  - replay 前提と seed 前提の責務を更新
  - 分割後 spec 名、実行入口、動画を使うケースと使わないケースの説明を更新
- `Taskfile.yml`
  - spec 分割に伴う補助 task が必要なら更新

## 期待効果

### replay 再生回数

ローカル実装の現状調査では 33 回である。

今回の設計を適用した場合の暫定見積り:

- replay 維持
  - `auto-recording-workflow`: 3 回
  - `recording-metadata-edit-workflow`: 5 回
  - `error-recovery-recording-live`: 3 回前後
- 合計: 11 回前後

さらに `error-recovery-recording-live` の重複統合が成立すれば、9 回前後まで削減できる見込みがある。

この数値は暫定であり、実装後に `ensureAutoRecordingEnabled()` 呼び出し回数で再測定する。

### 期待される副次効果

- E2E 実行時間短縮
- spec ごとの責務明確化
- 失敗時の切り分け容易化
- replay fixture の増減が全 E2E 実行時間へ与える影響の縮小

## 検証方法

実装後は次を確認する。

- `task.exe test:e2e` が通ること
- `task.exe test:frontend:e2e:auto-recording` が通ること
- replay 維持 spec だけが `ensureAutoRecordingEnabled()` を呼ぶこと
- seed 化 spec で replay input 未設定でも目的の UI が成立すること
- `error-recovery` 分割後に、各 spec が単独実行可能であること
- E2E ドキュメントの責務記述が実装と一致すること

## リスクと対策

- recorded seed が backend 一覧仕様とずれる
  - 対策: backend repository の現行列挙仕様に合わせて helper を実装し、一覧系 E2E で確認する
- seed と replay で metadata 形がずれる
  - 対策: 既存 replay fixture の sidecar を seed 元として使い、metadata 形を揃える
- `error-recovery-recording-live` の transport error と application error が実は別 UX
  - 対策: 実装時に UI 分岐を確認し、差があれば両方残す
- spec 分割で task や docs が古くなる
  - 対策: 同一変更で `Taskfile.yml` と `docs/e2e_replay_test.md` を更新する

## 結論

採用案は次のとおりである。

- replay は「自動録画制御」と「録画中操作」に限定する
- recorded asset 前提の E2E は filesystem seed 化する
- `error-recovery` は責務ごとに分割する
- 重複・不要 E2E は、事前に定めた判定基準に従って統合または削除する

この方針は、ユーザー要件・Playwright の isolation 原則・現在の recorded asset 実装仕様の 3 つと整合している。
