# macOS の OBS は対応する app を NSWorkspace で起動し実行パスを再確認する

- ID: 20261001-231244
- 状態: accepted
- 日時: 2026-10-01T23:12:44+09:00
- 判断者: メインエージェント

## 目的・問題

ユーザーは、OBS から音声が入っているのにアプリが無音と誤判定し、OBS を再起動していると報告しました。別 ADR 20261001-222419 では、macOS で検査対象の CoreAudio 入力を一意に解決してから既存の音声 readiness と復旧を行う判断を記録しています。本 ADR はその音声源の解決とは別に、macOS 上で OBS を起動する経路を定めます。

親トランスクリプト内のログでは、OBS の音声アクセス許可が 21:39:38.704 と 21:41:37.614 に granted、アプリから実行ファイルを直接起動した後の 22:28:40.878 に denied と記録されています。22:35:11.231 には MiraBox Capture の buffer frame size 取得失敗もあります。同じトランスクリプトに含まれるサンプル call graph は mac-capture、AudioUnitSetProperty、CoreAudio の AudioDeviceGetProperty を経て mach_msg で待つ状態を示します。これらは起動時の権限拒否と CoreAudio/HAL の応答待ちが観測された事実ですが、起動方式だけが差を生んだことは証明しません。

TCC が起動元の責任アプリをどう特定したか、USB 接続、OS の権限状態、HAL または機器側の状態のどれが原因かは未確定です。観測は同じ bundle・署名・ユーザー・USB・権限状態で行った統制比較ではありません。

## 前提・制約

- ユーザーは音声復旧のための既存の OBS 自動再起動を維持すると回答しています。自動復旧の条件は、既存 ADR と 20261001-222419 の対象音声入力解決に従います。
- 20260903-065610 の OBS 実行パス照合、起動済みプロセスの一意性、録画中に操作しない条件、およびアプリ起動前から存在した OBS の由来を再起動後も維持して終了時に残す扱いを変えません。
- macOS の標準 app bundle として解決できる場合だけ Launch Services を使います。ユーザーが明示した実行ファイルが app bundle に属さない場合は、既存の直接実行経路を保持します。
- macOS の TCC 許可状態を自動変更・リセットしません。新しい依存、設定、永続スキーマ、ビルド仕様は追加しません。
- Windows 等の別プラットフォームでの取得や起動設定は本判断の対象外です。

## 判断

1. macOS で設定された OBS 実行ファイルが .app bundle 内にある場合、Info.plist の CFBundleExecutable から解決した executable の実パスと設定パスが完全一致することを確認してから、その app bundle を NSWorkspace の非同期 openApplication API で起動します。
2. 起動完了 callback の NSRunningApplication から PID を取得し、psutil.Process を作成して実行ファイルのパスが設定値と完全一致することを再確認します。PID の取得、プロセス照会、またはパス照合に失敗した場合は起動失敗として扱います。
3. 起動前に設定実行パスが一意に一致する既存 OBS を確認します。既存プロセスは新規にアプリ所有として登録しません。さらに、native 起動要求の直前に記録した時刻と callback PID の psutil.Process.create_time() を比較します。macOS のプロセス開始時刻を秒・マイクロ秒の分解能で照合し、起動要求より前から存在する PID は DeviceError として拒否します。時刻取得に失敗した場合も未所有の起動失敗とし、検証できない PID をアプリの所有プロセスに登録せず、自動終了もしません。既存の録画中ガード、復旧条件、起動由来の継承、および終了時の保持を維持します。
4. NSWorkspace 呼び出しのエラーまたは callback のタイムアウト後に実行ファイルを直接起動する自動 fallback は行いません。NSWorkspace の起動が遅れて完了する可能性があり、その後の直接起動と重複するためです。曖昧な結果は起動失敗として返します。
5. 起動完了 callback は app launch の完了を示すだけです。OBS WebSocket の ready、CoreAudio の初期化、音声入力の健全性を証明するものとして扱いません。
6. 本記録時点で process_manager.py には .app bundle と executable の照合、NSWorkspace 起動、callback PID の psutil と実行パスによる検査が実装されています。メインエージェントの報告では実装と最終確認は進行中で、現在の Mac のロック解除・USB 再接続後の検証はユーザーの回答待ちです。このため、権限問題や HAL の解消、最終的な実機成功、配布完了とは判断しません。

## 検討した選択肢と棄却理由

### macOS でも app bundle 内の executable を直接起動し続ける

既存経路を保てますが、今回は標準の app bundle 起動経路を使った際の挙動を検証できません。TCC や HAL の原因が特定されていないため、直接起動を続けるだけでは今回の起動経路に関する仮説を試せません。一方、明示された standalone executable には app bundle がない場合があるため、その場合の既存経路は残します。

### executable の実パスを検証した app bundle だけ NSWorkspace で起動する

macOS が提供する標準の非同期アプリ起動 API を使い、既存の実行パス・PID 照合と併用できます。起動方式の変更は戻しやすく、アプリを選ぶ曖昧さを防げるため、原因を解消する保証がない候補として採用します。

### NSWorkspace の失敗後に Popen で直接起動する

callback の遅延後に app が起動する可能性を排除できず、fallback で二つ目の OBS を起動し得ます。重複起動を避けるため棄却します。

### OBS の音声状態や TCC をリセットしてから起動する

ユーザーが許可した音声復旧の範囲を越えて OS のプライバシー許可を変更し、観測した原因も切り分けられません。本判断では行いません。

### WebSocket 接続・起動完了だけで音声準備完了と扱う

ユーザーは OBS WebSocket の有効化を提案していますが、WebSocket 応答だけでは音声アクセス許可、CoreAudio の初期化、対象入力の音声状態を示しません。WebSocket の設定や readiness 契約は本 ADR で変更しません。

## 適用範囲

- macOS で設定された OBS executable が、検査済みの .app bundle 内にあるときのプロセス起動。
- Launch Services callback の PID から作成した psutil.Process と設定 executable の完全パス確認。
- app bundle 起動前の一意な既存 OBS 照合、および既存の OBS 所有権・終了由来の扱い。
- 起動失敗・タイムアウトを明示して重複起動を避ける処理。

## 適用しない範囲

- Windows またはその他のプラットフォームの起動方式。
- 検証済みの .app bundle を持たない明示 executable の起動。そこでは既存の直接実行経路を維持します。
- TCC の権限リセットや変更、OBS の音声デバイス設定変更。
- TCC の responsible identity が変わる保証、権限拒否や HAL 応答待ちが解消する保証。
- NSWorkspace callback を OBS の WebSocket・CoreAudio・音声 readiness とみなすこと。
- 20261001-222419 に定める CoreAudio 入力解決や、既存の誤判定修正・自動復旧条件の置換。
- OBS の終了操作や macOS の Cmd-Q 後処理の変更。

## 期待する効果

- macOS app bundle の起動に標準 Launch Services を用い、アプリ本体の実行パスを保った形で OBS を起動できます。
- callback が示す PID と実 executable を再検査するため、別の executable を起動済み OBS と誤認する範囲を抑えます。
- 非同期起動の結果が曖昧な場合に直接実行を重ねず、重複起動を避けます。
- 既存の音声復旧ポリシーとプロセス由来の扱いを維持しながら、起動方式の仮説を個別に検証できます。

## 受け入れる欠点・リスク

- NSWorkspace への切替だけで TCC の帰属や許可状態が変わるとは限らず、OBS の音声拒否や HAL 応答待ちが残る場合があります。Apple DTS の事例では embedded app の TCC 対象が Finder 上の責任アプリに結び付けられ、NSWorkspace・open・Finder で起動しても同じ結果と報告されています。これは今回の OBS 構成と同一であることを示すものではなく、起動方式による解決を一般化できない根拠です。
- NSWorkspace callback が timeout した後にアプリが遅れて起動する場合があります。自動 fallback を行わないため、呼び出し元は起動失敗を扱う必要があります。
- PyObjC の AppKit API が配布済み macOS app で使用できること、各 OBS bundle・署名・OS の組合せでの起動結果は最終確認中です。
- psutil の開始時刻が取得できない、または信頼できない環境では安全側に起動失敗となり、OBS が既に起動していてもアプリ所有にはなりません。検証失敗時にその PID を停止しないため、OBS が動作を続けている状態で SplatReplay 側だけが起動失敗と報告する場合があります。psutil の create_time はシステム時刻を基にするため、時刻補正やプラットフォーム固有の精度・取得制約も比較結果へ影響し得ます。
- Mac のロック解除および USB 再接続後に、同じ OBS bundle での起動・権限・音声の実機確認を完了していません。

## 再検討条件

- 同一 OBS bundle、署名状態、ユーザー、USB 機器、macOS 権限状態を揃え、直接起動と NSWorkspace 起動で TCC の対象・許可ログ、OBS の CoreAudio 初期化、実際の音声 readiness を比較できたとき。
- 同一条件の比較で起動方式と結果の関係が確認できない、NSWorkspace 起動で callback の PID や実行パスの整合が取れない、または配布 app で AppKit が利用できないことが判明したとき。
- OBS の録画中ガード、起動済みプロセスの由来、終了時保持を維持できない事例が見つかったとき。
- macOS または OBS の起動・プライバシー仕様が変わったときは Apple と OBS の一次情報を再確認します。

## 関連する設計指針

現在、登録済みの設計指針はありません。docs/architecture/principles/README.md を確認しました。本判断は一回限りの macOS 起動方式であり、新しい一般原則は追加しません。

## 関連 ADR

- [20260903-065610 起動済み OBS も一意な設定パス一致時だけ音声復旧し終了時は残す](20260903-065610-起動済みOBSも一意な設定パス一致時だけ音声復旧し終了時は残す.md)：一意な executable 照合、録画中の非操作、アプリ起動前からある OBS の由来と終了時保持。
- [20260901-213726 OBS 音声の silent を実機準備完了時だけアプリ所有プロセスの再起動で復旧する](20260901-213726-OBS音声のsilentを実機準備完了時だけアプリ所有プロセスの再起動で復旧する.md)：既存の音声 readiness と復旧ゲート。
- [20261001-222419 macOS の OBS 音声検査は指定 CoreAudio 入力を一意に解決してから行う](20261001-222419-macOSのOBS音声検査は指定CoreAudio入力を一意に解決してから行う.md)：音声源誤判定の対象を解決する別の補正。本 ADR はその検査ロジックを置換しません。
- [20260920-094217 完全終了を更新の Switch 停止待ちから分離し OBS のトレイ起動と正常終了を接続する](20260920-094217-完全終了を更新のSwitch停止待ちから分離しOBSのトレイ起動と正常終了を接続する.md)：Windows のトレイ起動・終了の判断を維持し、本 ADR はその Windows 範囲を変更しません。

## 置換・追補関係

既存 ADR は置換しません。20260903-065610 のプロセス特定、復旧安全条件、起動由来の保持を適用したまま、macOS の検証済み .app bundle 起動経路を補います。20261001-222419 が対象音声入力の誤解決を防ぐ判断を担い、本 ADR は起動方式を別の不確実な要因として扱います。両方を適用しても、TCC または HAL の問題解消を保証しません。

## 調査した根拠

### リポジトリ内の判断と実装

- docs/architecture/decisions/README.md：RECORD の原文取得、記録・追補形式、書き込み境界。
- docs/architecture/decisions/20260903-065610-起動済みOBSも一意な設定パス一致時だけ音声復旧し終了時は残す.md：プロセス一意性、録画中ガード、起動由来と終了時保持。
- docs/architecture/decisions/20260901-213726、20261001-222419：既存の音声復旧条件と対象 CoreAudio 入力解決。
- backend/src/splat_replay/infrastructure/adapters/obs/process_manager.py の _launch_locked、_resolve_macos_app_bundle、_launch_macos_application：設定 executable が bundle 内にある場合の bundle 検証、NSWorkspace 起動、callback PID と実パス確認を実装します。NSWorkspace 呼び出し直前に記録した launch_requested_at と psutil.Process.create_time() を比較し、要求時刻より前の PID は DeviceError にします。create_time 取得エラーも DeviceError へ変換され、検証に失敗した PID は self._process に代入される前に拒否され、自動終了処理へ渡されません。最終的な macOS 配布・機器検証は未完了とメインエージェントから報告されています。
- psutil Documentation, stable, Process.create_time(), 2026-10-01 参照: https://psutil.readthedocs.io/stable/index.html#psutil.Process.create_time 。プロセス作成時刻は epoch からの秒を表す浮動小数点値で、システム時刻の手動変更や同期（NTP など）の影響を受ける場合があります。取得失敗を新規起動の証明として扱わず、未所有の起動失敗として拒否します。
- 親トランスクリプトに含まれる OBS ログとサンプル call graph：権限 granted/denied、MiraBox Capture の buffer frame size 取得失敗、CoreAudio/HAL 呼び出しの待ちを記録しています。同一条件の A/B ではありません。obs-startup-hang.txt というサンプル名は親報告にありますが、本 ADR 作成時にその独立ファイルを直接読んだという意味ではありません。

### 外部一次情報

- Apple Developer Documentation, NSWorkspace openApplication(at:configuration:completionHandler:), 2026-10-01 参照: https://developer.apple.com/documentation/appkit/nsworkspace/openapplication(at:configuration:completionhandler:) 。アプリを指定 URL から非同期で起動し、callback で NSRunningApplication またはエラーを受け取る API です。API の利用は TCC 対象変更を保証しません。
- Apple Developer Technical Support, “TCC AUTHREQ_SUBJECT is wrong for embedded apps”, 2022-10, 2026-10-01 参照: https://developer.apple.com/forums/thread/718728 。DTS は TCC が要求プロセスからユーザーに見える責任コードを特定すると説明しています。同投稿者の embedded app 事例では NSWorkspace・open・Finder 起動の違いで TCC 対象が変わりませんでした。今回の OBS bundle に直接適用できるとの根拠ではなく、因果を未確定に保つために参照します。
- Apple Developer Technical Note TN3127, “Inside Code Signing: Requirements”, 2024-04-02 更新, 2026-10-01 参照: https://developer.apple.com/documentation/technotes/tn3127-inside-code-signing-requirements 。macOS は code signing の designated requirement をコード識別に使い、マイク許可の記憶にも関連付けると説明しています。起動 API の変更がコード identity を変えるという証拠ではありません。
- 外部資料は macOS の仕様変更で変わる可能性があるため、再検討時に現行の Apple 文書と実機動作を再確認します。

## ユーザー発言の原文

今回の誤判定報告:

> OBSから音声入力されているのに、されいないと誤判定してOBSを再起動してしまっている

自動再起動についての質問と回答:

> OBS の音声が無音のとき、アプリによる OBS の自動再起動を止めますか？ 今回のログでは、起動後の無音検出が終了・再起動を繰り返した原因です。以前は音声復旧のための再起動を許可いただいていました。

> 音声復旧のための自動再起動を維持する

作業範囲とユーザー確認の境界:

> OBS WebSocketを有効にしたらいいんじゃない？
> 私じゃないとできない一連の動作確認(最終チェックの意味も含めて)以外にあなたが対応できることは対応してください。

NSWorkspace への切替はユーザーが API 名を指定した判断ではなく、上記の範囲内でメインエージェントが選定した低リスクで戻せる起動方式です。

## 会話カバレッジ

| 会話・観測 | 記録した節 | 反映 |
| --- | --- | --- |
| 音声入力中なのに silent と誤判定し OBS を再起動しているという報告 | 目的・問題、ユーザー発言の原文 | 起動方式と入力源解決を区別し、誤判定の解消を本 ADR 単独の効果としません。 |
| 自動再起動停止を尋ねた質問と「維持する」という回答 | 前提・制約、判断、原文 | 質問と回答の双方を保存し、対象が正しいときの既存復旧を維持します。 |
| OBS WebSocket 有効化の提案と、ユーザーが必要な確認以外を依頼した発言 | 判断、選択肢、適用しない範囲、原文 | WebSocket の準備完了と音声準備完了を同一視せず、具体的な起動 API の選択をメインエージェント判断として記録します。 |
| granted と denied のログ、MiraBox buffer frame size エラー | 目的・問題、調査した根拠 | 時刻付き観測として保存し、TCC または HAL の根本原因とは断定しません。 |
| mac-capture から CoreAudio を経て mach_msg へ至るサンプル call graph | 目的・問題、受け入れる欠点・リスク | HAL 応答待ちの観測に限定し、起動方式との因果を断定しません。 |
| 既存の一意な実行パス・録画中ガード・起動由来保持 | 前提・制約、判断、関連 ADR | 既存契約を変更せず今回の macOS app launch に適用します。 |
| ロック解除・USB 再接続後の検証がユーザー回答待ちというメインエージェント報告 | 判断、リスク、再検討条件 | 最終実機確認、TCC/HAL 解消、配布完了を主張しません。 |
| Apple の NSWorkspace、TCC、designated requirement の一次情報 | 検討案、リスク、調査した根拠 | NSWorkspace は非同期標準 API だが TCC 対象を変える保証がない点を明記します。 |

## 記録時セルフレビュー

- 保存直前に SubagentStart から渡された親トランスクリプトを再走査し、誤判定報告、質問への回答、WebSocket 提案と作業範囲の原文、およびログ・call graph の文字列を再確認しました。他のセッションは探索していません。
- 自動再起動に関する回答には、受諾対象の質問原文を併記しました。
- NSWorkspace をユーザーが直接選んだとは書かず、メインエージェントの低リスク・可逆な判断としました。
- 起動方式、音声源 resolver、WebSocket、TCC、CoreAudio/HAL の役割を分け、観測事実と未確認の因果を区別しました。
- Apple DTS の embedded app 事例を今回の OBS 構成の直接証明とは扱っていません。
- 実装コードが存在する事実と、最終的な配布・実機確認が未完了であることを分け、成功・修正済み・配布済みとは記録していません。
- 新規 ADR 一件だけを追加し、principles、既存 ADR、コード、テスト、その他のディレクトリ、Git の状態は変更していません。
