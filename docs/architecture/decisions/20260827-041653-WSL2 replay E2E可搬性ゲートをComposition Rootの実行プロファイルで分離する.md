# WSL2 replay E2E可搬性ゲートをComposition Rootの実行プロファイルで分離する

- ID: 20260827-041653
- 状態: accepted
- 日時: 2026-08-27T04:16:53+09:00
- 判断者: メインエージェント

## 目的・問題

最終的な macOS 対応を目指す一方、現時点では macOS 実機がありません。まず Linux（WSL2）で、実ハードウェアに依存せず replay 入力を使う E2E を含むテストを実行可能にし、可搬性の回帰を検出する必要があります。

従来の通常起動と Playwright の E2E 起動が同じ Composition Root で実機用アダプタを構築すると、WSL2 で NDI、OBS、PnP、マイク列挙、PC 電源操作の前提に引きずられます。単に OS 判定やテスト用の条件分岐を各アダプタへ散在させると、live のユーザー向け挙動と replay の E2E 契約の境界が不明確になります。

## 前提・制約

- ユーザーの当面の目標は、Linux（WSL2）で E2E を含むテストを合格させることです。最終目標は macOS での動作です。
- Windows の通常起動では、現行の実機接続・録画の挙動を保つ必要があります。
- replay E2E は実機の NDI、OBS、PnP、マイク列挙、電源操作を必要としない可搬性ゲートとします。
- replay 入力をテスト中に切り替え、起動済みサービスが入力を動的に再解決する既存契約を維持します。
- macOS の native 実機、キャプチャ機器、配布物、署名・notarization の保証は今回の対象外です。WSL2 の成功を macOS 製品対応の証明として扱いません。
- 現行の外部仕様は Windows 11 を対応 OS としています。macOS を正式な対応 OS に加える外部仕様・配布契約の変更は別判断とします。

## 判断

1. 実行時の構成は Composition Root で `SPLAT_REPLAY_RUNTIME_PROFILE` により明示選択します。許容値は `live` と `replay` のみとします。
2. 環境変数が未指定の場合は `live` を選び、通常の Windows 起動との後方互換性を保ちます。未知値は暗黙に `live` へ丸めず、起動時に fail-fast します。
3. Playwright が起動する backend には `SPLAT_REPLAY_RUNTIME_PROFILE=replay` を明示します。`replay` は E2E 専用の実行構成です。
4. `replay` では NDI、OBS、PnP、マイク列挙、実機の電源操作を行うアダプタを構築しません。replay 入力を動的に再解決する既存契約を維持する構成を選びます。
5. OS 判定、E2E 用環境変数、またはテスト専用の代替挙動を domain/application 層へ持ち込みません。profile 選択とアダプタ組み立ての責務は Composition Root に置きます。

## 検討した選択肢と棄却理由

### WSL2 でも live 構成をそのまま起動する

実機用の外部依存を必要とし、ユーザーが求めるハードウェア非依存の Linux E2E を実現できません。WSL2 の USB 接続も標準で直接利用できる前提ではないため、可搬性ゲートとして不適切です。

### 各アダプタ内で OS や E2E 用環境変数を判定する

テスト都合の分岐が実機アダプタへ散在し、live と replay の構成差・失敗モード・依存関係を追跡できなくなります。Composition Root が担う依存組み立ての責務も曖昧になるため採用しません。

### Composition Root で `live` と `replay` を選ぶ

実機用アダプタの未構築を構成として明示でき、domain/application のポート境界を維持できます。Playwright の backend にのみ `replay` を明示し、通常起動は未指定の `live` を保てるため採用します。

### 今回の Linux E2E を macOS の製品対応・配布保証まで拡張する

macOS 実機がなく、native GUI、キャプチャ機器、OBS、署名・notarization、OS 別 bundle の検証根拠もありません。WSL2 の可搬性ゲートと製品サポート契約を混同するため採用しません。

## 適用範囲

- Playwright が起動する backend を含む replay E2E の実行構成。
- `live` と `replay` の実行プロファイル選択、未知値の fail-fast、各プロファイルで構築する外部アダプタ。
- Linux（WSL2）でのハードウェア非依存 replay E2E 可搬性ゲート。

## 適用しない範囲

- macOS での native GUI、実キャプチャ機器、OBS、マイク、電源操作、配布物、署名・notarization の動作保証。
- macOS の CPU アーキテクチャ、最小 OS バージョン、配布方式、正式サポート範囲の決定。
- Windows の `live` 構成が提供する実機録画機能の意味変更。
- Linux をエンドユーザー向けの正式対応 OS にする判断。
- テスト分類、テスト入口、CI の具体的なコマンド選定。

## 期待する効果

- WSL2 で、実機や Windows 固有の外部アダプタに依存せず replay E2E を実行できます。
- `live` と `replay` の構成差が一か所に集約され、通常起動の実機挙動を E2E 都合で変えにくくなります。
- 未知の profile 設定を早期に検出し、誤って実機構成または replay 構成で起動することを防げます。
- 将来の macOS 対応に必要な native 実機・配布検証を、WSL2 のテスト成功と区別して計画できます。

## 受け入れる欠点・リスク

- `live` と `replay` の Composition Root が将来乖離すると、E2E がユーザー導線を十分に代表しない可能性があります。
- replay は実機アダプタを構築しないため、NDI、OBS、PnP、マイク、電源操作の統合不具合は検出しません。
- 環境変数の設定誤りは fail-fast で起動を停止します。これは誤構成を継続するより安全ですが、設定者には明示的な修正が必要です。
- profile を増やしすぎると構成の組合せが増え、保守負荷が上がります。

## 再検討条件

- macOS の native 実機・配布保証を開始し、実機統合用の構成・検証範囲を決めるとき。
- Linux をエンドユーザー向けの正式対応 OS に加えるとき。
- replay E2E が live で提供する主要導線を代表できないこと、または profile 間の構成乖離による回帰が確認されたとき。
- 実行プロファイルを `live` / `replay` 以外へ増やす必要が生じ、環境変数選択だけでは構成の責務を安全に表現できなくなったとき。

## 関連する設計指針

登録済みの accepted 設計指針はありません。Clean Architecture の依存方向とテスト戦略は本判断の制約・評価根拠ですが、テスト手順や現行構造を新しい設計指針としては扱いません。

## 関連 ADR

- `20260812-132848-変更分類と保証対象から最小の検証範囲を選ぶ`: テスト選定の SSoT と、広い検証を保証対象から選ぶ運用を定めます。本 ADR は実行構成の境界を定めるものであり、同 ADR のテスト手順を変更しません。
- `20260813-200649-Switch電源サイクルをまたぐ連続自動処理をバックエンド常駐サービスと永続未処理キューで実現する` および `20260814-095458-Switch電源ON待機時の実キャプチャを1秒間隔の単一ゲートにする`: `live` の実機録画ライフサイクルに関する判断です。本 ADR は replay 構成で当該実機アダプタを構築しないだけで、live の状態遷移・取得方針を変更しません。

## 置換・追補関係

既存 ADR の置換・追補はありません。現行の外部仕様にある Windows 11 の正式サポート範囲は変更しません。

## 調査した根拠

### リポジトリ内の一次情報

- `AGENTS.md`: Clean Architecture の依存方向、重要な設計判断では `design_steward` の助言・記録を使う常時ルール。
- `docs/architecture/decisions/README.md`: ADR の記録基準、原文保持、書き込み範囲、設計指針とテスト手順を区別する実行契約。
- `docs/test_strategy.md`: workflow E2E を主要導線として扱い、skip を合格と扱わないテスト戦略。
- `docs/external_spec.md`: 現行の正式対応 OS が Windows 11 64bit であること。
- `frontend/playwright.config.ts`、`frontend/tests/e2e/support/e2eEnv.ts`: Playwright が backend / frontend を起動し、replay 入力と一時設定を使う現行 E2E 構成。
- `backend/src/splat_replay/application/interfaces/recording.py`: replay bootstrap を解決するポートが既に存在すること。

### 外部一次情報

- Playwright, Browsers, https://playwright.dev/docs/browsers, 参照日 2026-08-27。Linux / WSL を含む browser E2E では OS 依存の browser / system dependency 導入が必要である点を、WSL2 の実行前提の評価に用いました。
- Microsoft Learn, Connect USB devices, https://learn.microsoft.com/en-us/windows/wsl/connect-usb, 参照日 2026-08-27。WSL2 の USB 利用には追加の USB/IP 設定が必要である点を、初期 E2E を実キャプチャ機器に依存させない判断の評価に用いました。
- PyInstaller, Using PyInstaller, https://pyinstaller.org/en/stable/usage.html, 参照日 2026-08-27。OS ごとに native bundle が必要である点を、WSL2 の成功を macOS の配布保証と同一視しない判断の評価に用いました。

学術的知見は、外部ツール・OS 実行環境の契約と既存アーキテクチャ境界を扱う本判断を実質的に追加選別しないため、調査対象にしませんでした。

## ユーザー発言の原文

ユーザーは次の目的と制約を示しました。

> 最終的にmacosで動作するようにしたいです。
> ただmacは今ないので、まずはlinux(wsl2)でテスト合格(e2e含む)する状態をゴールとします。
> アーキテクチャなど重要な判断(間違うと手戻りが大きい)をするときには、サブエージェント(sol)にアドバイスを求めてください。

Sol の助言後、メインエージェントは次の構成境界を確定しました。

> Sol の助言を踏まえ、E2E 専用の `replay` 実行プロファイルを Composition Root で選ぶ方針にします。これにより Linux では NDI・OBS・PnP を生成せず、Windows の通常起動は既定の `live` プロファイルで維持します。この設計判断は記録対象として扱います。

RECORD の依頼では、上記を具体化して `SPLAT_REPLAY_RUNTIME_PROFILE=live|replay`、未指定時の `live`、未知値の fail-fast、Playwright backend の `replay` 明示、replay で構築しない実機依存、replay 入力の動的再解決契約維持、および macOS native 実機・配布保証を対象外とすることが、メインエージェントにより確定されました。これらはユーザー原文には含まれない実装境界の正規化であることを明記します。

## 会話カバレッジ

| 会話の判断要素 | ADR の対応節 | 点検結果 |
| --- | --- | --- |
| 最終目標を macOS の動作とする | 目的・問題、前提・制約、適用しない範囲、再検討条件 | WSL2 の成功を macOS の製品保証と混同しない境界として保持しました。 |
| macOS 実機がないため、先に Linux（WSL2）で E2E を含むテストを合格させる | 目的・問題、前提・制約、適用範囲、期待する効果 | ハードウェア非依存の replay E2E 可搬性ゲートとして保持しました。 |
| 重要なアーキテクチャ判断は Sol に助言を求める | 調査した根拠、ユーザー発言の原文 | Sol 助言後にメインエージェントが確定した構成方針として区別して保持しました。 |
| replay 実行プロファイルを Composition Root で選ぶ | 判断 1、4、5、検討した選択肢 | profile 選択とアダプタ組み立てを domain/application から分離する判断として保持しました。 |
| Linux の replay で NDI・OBS・PnP を生成しない | 判断 4、適用範囲、適用しない範囲 | 実機統合を replay E2E の保証外にする条件を保持しました。 |
| Windows の通常起動は既定 live を維持する | 前提・制約、判断 2、期待する効果 | 未指定時の `live` を明記し、互換性を保持しました。 |
| `live|replay`、未知値 fail-fast、Playwright の replay 明示 | 判断 1〜3、受け入れる欠点・リスク | RECORD 依頼で確定した具体的な環境変数契約を欠落なく正規化しました。 |
| replay 入力の動的再解決を維持する | 前提・制約、判断 4 | E2E の既存契約を profile 導入で失わない条件として保持しました。 |
| macOS native 実機・配布保証は今回の対象外 | 前提・制約、適用しない範囲、再検討条件 | 未確認範囲を成功扱いしない条件として保持しました。 |

## 記録時セルフレビュー

- SubagentStart フックで指定された親トランスクリプトだけを読み、他セッションは探索していません。
- 保存直前にユーザー原文とメインエージェントの確定発言を再走査し、目的、制約、構成選択、対象外、Sol 助言の要請を照合しました。
- ユーザー原文と、RECORD 依頼で確定した環境変数・fail-fast・Playwright 構成の詳細を区別しました。
- 既存 ADR と設計指針を確認し、live の実機録画ライフサイクルを変更しないこと、登録済み accepted 設計指針がないことを記録しました。
- 現行コード構造、テスト基準、コマンドを設計指針として扱わず、新しい設計指針を作成していません。
- 対象原文に機密情報、認証情報、個人の機微情報は含まれていません。
- この ADR 以外の文書、コード、テスト、Git のステージ・コミットには触れていません。
