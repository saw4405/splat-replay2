# E2E YouTube no-op upload 設計

作成日: 2026-03-29

## 背景

Playwright E2E は `frontend/playwright.config.ts` から backend を起動し、E2E 用の一時 `settings.toml` を渡している。一方、YouTube の認証ファイルやトークンは `backend/config/` 基準の固定経路を参照しており、E2E 用設定だけでは実アップロード防止を保証できない。

そのため、開発者環境に有効な YouTube 認証情報が残っている場合、E2E 実行時に実際の YouTube アップロードが発生する可能性がある。これはテストの安全性として許容しにくい。

## 目的

- E2E テスト実行時に、実際の YouTube へのアップロードを確実に防止する。
- 既存の編集・アップロード成功フローの E2E 検証は維持する。
- 業務フロー側ではなく、依存注入境界で安全性を担保する。

## 成功条件

- Playwright から起動した backend では、YouTube API へ実通信しない。
- E2E の編集アップロード系テストは、従来どおり成功系フローを検証できる。
- `AutoUploader` や `StartEditUploadUseCase` に E2E 専用分岐を入れない。
- 通常実行時の `YouTubeClient` 利用経路は維持される。
- ログ上で no-op upload が使われたことを判別できる。

## 非目標

- E2E 中に YouTube 認証画面や認証 API まで完全に no-op 化すること。
- 本番 UI 文言や進捗表示を E2E 用に変更すること。
- Upload 以外の外部連携をまとめてテストモード化すること。
- 既存の E2E シナリオを大きく書き換えること。

## 検討した案

### 案 A: `UploadPort` を E2E 専用 no-op 実装に差し替える

採用案。E2E 実行時だけ DI で `UploadPort` を `NoOpUploadPort` に差し替え、`upload()` を受けても外部通信せず正常終了する。

- 利点: 実アップロード防止を依存境界で保証しやすい。業務フローを汚さず、E2E 成功系を維持しやすい。
- 欠点: DI 条件分岐と E2E 用環境変数の追加が必要になる。

### 案 B: `YouTubeClient` 内で E2E 判定して即成功扱いにする

不採用。実装量は少ないが、本番アダプタにテスト都合の条件分岐が入る。責務が濁りやすく、将来の認証経路や補助メソッドへの漏れも起こり得る。

### 案 C: E2E テスト側で Google API 呼び出しをモックする

不採用。テスト側だけで閉じやすい一方、backend 内部の呼び出し詳細に依存しやすい。モック漏れ時の安全性が弱く、今回の「絶対にアップロードしない」という目的には不十分である。

## 採用方針

E2E 実行時のみ、backend の DI 登録で `UploadPort` を no-op 実装へ差し替える。

構成は以下とする。

- `application.interfaces.upload.UploadPort`
  - 既存の抽象境界をそのまま使用する。
- 新規 `infrastructure` 実装
  - `NoOpUploadPort` を追加し、`upload()` を受けても外部 API を呼ばずに正常終了する。
- `infrastructure.di.adapters`
  - 明示的な E2E 用環境変数が有効な場合だけ `UploadPort` に `NoOpUploadPort` を登録する。
  - 無効時は従来どおり `YouTubeClient` を登録する。
- `frontend/playwright.config.ts`
  - backend 起動時の環境変数に no-op upload 有効フラグを追加する。

## 環境変数方針

E2E 用 no-op upload は、既存の `SPLAT_REPLAY_E2E_MODE` に便乗せず、専用の明示フラグで有効化する。

- 追加予定: `SPLAT_REPLAY_E2E_NOOP_UPLOAD=1`

この方針にする理由は以下のとおり。

- E2E 実行モードと no-op upload の責務を分離できる。
- 将来、E2E 以外のテストや開発用起動で no-op upload だけを使いたい場合に拡張しやすい。
- 条件の意味がログやコード上で読み取りやすい。

## アーキテクチャ

### 変更対象

- `frontend/playwright.config.ts`
- `backend/src/splat_replay/infrastructure/di/adapters.py`
- `backend/src/splat_replay/infrastructure/adapters/upload/`
- backend の関連テスト

### 変更しない対象

- `AutoUploader`
- `StartEditUploadUseCase`
- `YouTubeClient`
- E2E の UI 期待値

### 依存方向

no-op 実装は `infrastructure` 層に置き、`UploadPort` を実装する。`application` 層は抽象ポートのまま利用するため、Clean Architecture の依存方向を崩さない。

## データフロー

1. Playwright が backend の `webServer` 起動時に `SPLAT_REPLAY_E2E_NOOP_UPLOAD=1` を渡す。
2. backend 起動時、DI 登録でこの環境変数を読む。
3. 環境変数が有効なら `UploadPort` に `NoOpUploadPort` を登録する。
4. 環境変数が無効なら `UploadPort` に従来どおり `YouTubeClient` を登録する。
5. `AutoUploader` は差し替えを意識せず `UploadPort.upload()` を呼ぶ。
6. E2E では no-op 実装がログを残して即時成功し、その後の削除・進捗更新・完了表示は通常どおり進む。

## `NoOpUploadPort` の振る舞い

`NoOpUploadPort.upload()` は以下を満たす。

- 引数は `UploadPort` と同じシグネチャを持つ。
- 受け取った動画パス、タイトル、公開設定、サムネイル有無、字幕有無、プレイリスト ID などをログへ記録する。
- 外部通信、認証ファイル参照、YouTube API クライアント生成を行わない。
- 正常終了する。

E2E の目的は成功系フロー検証であるため、今回の no-op は失敗ではなく成功扱いとする。

## `AuthenticatedClientPort` の扱い

今回は `UploadPort` のみ差し替え対象とする。

理由は以下のとおり。

- 現在の要件は「E2E テスト実行時に実際に YouTube にアップロードされないこと」であり、認証画面そのものの完全遮断までは求められていない。
- 現行の編集アップロード E2E は `UploadPort.upload()` の抑止だけで目的を満たす可能性が高い。
- まずは影響範囲を最小化したい。

ただし未確認事項として、将来 `AuthenticatedClientPort.authenticate()` を E2E で直接通るシナリオが増える場合は、同様の no-op 実装または差し替え方針を追加検討する。

## エラーハンドリングと安全条件

- no-op upload 有効時は、`YouTubeClient` の生成や `googleapiclient` への到達を避ける。
- 切り替え条件は Playwright から明示的に渡した環境変数のみを用いる。
- 環境変数未設定時は従来挙動を保つ。
- ログには `E2E no-op upload` の文言を含め、実アップロードではなかったことを追跡可能にする。

この設計により、認証ファイルの有無やトークン残存有無に関係なく、E2E 実行時の安全性を担保できる。

## テスト方針

最低限、以下を確認する。

- `SPLAT_REPLAY_E2E_NOOP_UPLOAD=1` のとき、DI から解決される `UploadPort` が no-op 実装になること。
- 環境変数未設定時、通常どおり `YouTubeClient` 経路が維持されること。
- no-op 実装の `upload()` が例外なく完了すること。
- E2E 起動設定に backend 向けの環境変数が追加されていること。

必要に応じて、既存の編集アップロード E2E を実行し、成功表示が維持されることも確認する。

## リスクと緩和策

- 将来 `UploadPort` 以外の YouTube 連携が E2E に入り込む可能性がある。
  - 緩和策: 今回は `UploadPort` を first guard とし、必要時に `AuthenticatedClientPort` へ拡張する。
- DI 登録の条件分岐が増え、意図しない環境で no-op 化する恐れがある。
  - 緩和策: 専用の明示環境変数だけで切り替え、名称も目的に寄せる。
- no-op により本物のアップロード失敗を E2E で検知できなくなる。
  - 緩和策: これは今回の非目標とし、実アップロード検証は別系統の統合確認で扱う。

## 実装順の提案

1. `frontend/playwright.config.ts` に backend 向け no-op upload 環境変数を追加する。
2. `infrastructure` に `NoOpUploadPort` を追加する。
3. `infrastructure.di.adapters` で環境変数に応じて `UploadPort` 登録先を切り替える。
4. 単体テストで差し替え条件と no-op 実装を検証する。
5. 必要なら既存の E2E を 1 本実行し、成功系フロー維持を確認する。

## 未確認事項

- 現行の E2E 動線で `AuthenticatedClientPort.authenticate()` がどこまで呼ばれるかは未確認である。
- DI コンテナの解決方法に応じて、登録先クラス確認テストと振る舞い確認テストのどちらが保守しやすいかは実装時に最終判断する。
