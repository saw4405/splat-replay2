# macOS の許可・パスワード要求調査

調査日: 2026-10-09

> 2026-10-09 時点のコードと実機状態を記録した調査履歴です。以後の状態は[ユーザーガイド](usage.md)と後続の確認記録を参照してください。

この資料は当時のコードと親エージェントの読み取り記録から、macOS で許可や認証入力が関係する経路を整理したものです。設定変更、権限要求、Keychain の読取要求、認証値の閲覧は行っていません。コード上の呼び出し、OS の公式仕様、実機で観測された事実を分け、未確認の原因や頻度は断定しません。

## 概要

| 項目 | 通常の要求契機・頻度 | 再表示の条件 | 限定した一回化・操作 | 状況 |
| --- | --- | --- | --- | --- |
| カメラ | 録画画面がWebViewの `getUserMedia` で仮想カメラを開く時 | 利用者は毎起動の再表示を報告。旧 ad hoc 署名から固定 leaf へ切替済みだが、再表示がmacOSアプリ許可とWebView origin許可のどちらか、切替後に再現するかは未確認 | システム設定で本アプリのカメラを許可し、WebViewは対象originだけを許可する。毎起動表示を一度化できる条件は未確認 | 親ログはdelegate登録が2起動、対象originへのGrantが1回。固定署名へ切替後のカメラ再表示は未確認 |
| マイク | 字幕用マイクを実際に開く時。デバイス一覧取得だけでは収音しない | macOS TCCの拒否・設定変更・署名identity変化後に再確認となる可能性 | システム設定のマイクで本アプリだけを許可する。更新を越えた一回化は署名identityに左右され得る | 実機の許可状態・今回の再表示原因は未確認 |
| 通知 | 通知API送信時、OS状態が未決定なら macOS UserNotifications が要求 | OS設定変更・再設定後。アプリは送信ごとに状態を確認 | OSの通知設定で本アプリだけを許可する。バナー表示は許可とは別設定 | 許可後のAPI成功は過去に確認。バナー継続表示は未確認 |
| LAN | macOS 15以降、ローカル宛て接続/NDI探索でLocal Network要求の可能性。受信Firewallは別 | Local Network privacy とアプリ別Firewallの設定・署名状態で異なる | 本アプリのLocal Network許可と受信Firewall規則を別々に確認する。アプリは規則を変更しない | 別端末接続は確認済み。要求元と現在状態は未確認 |
| Google OAuth | 保存認証がない/refresh失敗時にブラウザ同意 | token失効・refresh失敗・設定変更等 | Googleのアカウント/アクセス同意。macOS Keychain許可とは別 | 通常の全アップロードごととはコードから言えない |
| Keychain | macOS Keychain item を読む/更新する時 | 項目ごとの許可選択、アプリ署名identity、Keychainロック等。当時の起因は未確認 | 許可画面に選択肢がある場合も、対象のYouTube項目だけを許可する。項目削除や全アプリ許可は行わない | 利用者は毎回のパスワード画面を報告。ACL・ロック状態は未確認 |
| ビルド署名Keychain | macOS candidateのpreflightと最終署名で固定証明書の秘密鍵を使う時 | login Keychainがロック中、鍵ACL、初回アクセスなど | 初回の確認時は `/usr/bin/codesign` と対象鍵だけを本人が確認。通常buildは同じ証明書を再利用し、再発行やtrust/ACL変更をしない | 親の署名probeはOSアクセス確認待ち。許可後の頻度は未確認。アプリのYouTube token項目とは別 |
| Gatekeeper / 外部導入 | ダウンロードアプリ初回起動、Homebrew/NDI/OBS導入時 | OS版、隔離属性、署名、更新内容、パッケージ状態による | Gatekeeperの個別Open Anyway例外や、対象拡張/installerのOS承認。アプリ全体の許可ではない | 固定自己署名版はこのMacで置換起動済み。ダウンロードしたDMGからのGatekeeper画面は未確認 |
| USBアクセサリ / OBS拡張 | 新しいアクセサリ接続、OBS Virtual Camera拡張の初回ロード時 | アクセサリ設定は初回または毎回、OBS拡張はOS/拡張状態による | 対象USB機器またはOBS拡張だけをOS設定で許可 | Mac機種・設定・OBS画面は未確認 |
| Apple Events / 保護ファイル / 画面収録 / Accessibility / 自動起動 | 現行製品コードに要求APIなし | 現在の通常導線でOS promptを出すコードは見つからない | 一回化の対象となる製品要求はなし | 外部ライブラリ内部は未確認 |
| Homebrew / sleep | 導入操作時 / 処理完了後のsleep設定有効時 | Homebrewの初回導入やinstaller条件次第。sleepは処理ごとのユーザー設定 | Homebrewは一度環境へ導入し、対象formulaを確認。sleepにOS許可・password prompt APIなし | 個別installer入力と実sleepは未確認 |

## 各経路

### マイクと音声字幕

- マイク一覧取得は PortAudio デバイスの列挙です。名前が表示されても、実際の音声取得に成功したことにはなりません。[列挙処理](../backend/src/splat_replay/infrastructure/adapters/audio/microphone_enumerator.py#L26) は macOS でデバイス情報を読み、[文字起こし開始](../backend/src/splat_replay/infrastructure/adapters/audio/speech_transcriber.py#L105) で初めて `sr.Microphone` を開きます。
- 録画時に文字起こしが有効なら録画開始後にマイクを開きます。許可拒否や開始失敗時も映像録画は継続します。[録画と文字起こしの接続](../backend/src/splat_replay/infrastructure/adapters/video/recorder_with_transcription.py#L72) と [Info.plist のマイク用途説明](../backend/packaging/splat-replay-webview.spec#L240) が根拠です。
- 音声校正と「音声認識テスト」は、画面から利用者が実行した時にマイクを開く別の経路です。[校正API](../backend/src/splat_replay/interface/web/routers/settings.py#L184) は入力を測定し、[音声テストAPI](../backend/src/splat_replay/interface/web/routers/settings.py#L272) は認識結果をストリームします。
- Apple の[カメラ利用許可仕様](https://developer.apple.com/documentation/bundleresources/requesting-authorization-for-media-capture-on-macos)では、通常は初回キャプチャ要求時にOSが許可を求め、判断を記憶します。これはアプリ単位のmacOS TCC許可で、後述のWebView localhost origin 許可とは別です。アプリの通常コードが毎録画ごとにOS許可を要求する実装は見つかりませんでした。拒否後の再要求と現在のTCC状態は未確認です。
- 2026-10-08に起動中だった `.app` は ad hoc 署名でした。2026-10-09にSHA-256 `2b617e1206573418df294b7cb8f256f0aa0ee5ed556df9be32064774de8d20b5` の固定自己署名証明書で候補を署名し、親が異なる2つの A/B probe 実行ファイル間でprobe用 bundle ID と固定 leaf を含む DR の相互検証に成功した後、起動中アプリへ反映しました。製品候補では別途、製品 bundle ID と固定 leaf の DR を検証しました。候補の差分は `Contents/MacOS/SplatReplay` の署名だけで、他のpayloadは一致しました。Apple の [TN3127](https://developer.apple.com/documentation/technotes/tn3127-inside-code-signing-requirements) は ad hoc の designated requirement が個別ビルドに結び付くことと、macOS が署名要件を使ってマイク許可を更新版へ関連付けることを説明しています。今回確認したのはコード署名 identity の継続性であり、カメラ許可の再表示や本番YouTube Keychain項目の許可継続は未確認です。[候補内容照合](../backend/outputs/macos-diagnostics/20261009-fixed-signing/parent-candidate-content.json) と [署名連続性記録](../backend/outputs/macos-diagnostics/20261009-fixed-signing/parent-signature-continuity.json) はローカル診断記録（Git対象外）です。

### カメラ、WebView、OBS 仮想カメラ

- 録画画面のプレビューは `getUserMedia` で選択中の仮想カメラを取得します。[プレビュー取得](../frontend/src/main/components/recording/VideoPreview.svelte#L291) と [カメラストリーム開始](../frontend/src/main/components/recording/VideoPreview.svelte#L319) がブラウザ層の経路です。macOS 配布 Info.plist にもカメラ用途説明があります。
- macOS WebView delegate は、配布アプリのメインフレーム・バックエンドと同じ scheme/host/port・カメラ要求だけを許可し、それ以外は WebKit に判断を委ねます。[delegate の判定](../backend/src/splat_replay/interface/gui/webview_app.py#L82) と [許可処理](../backend/src/splat_replay/interface/gui/webview_app.py#L125) を参照してください。`private_mode=False` だけでは許可が永続する保証になりません。
- OSのカメラ許可は通常初回の利用時に尋ね、判断を記憶するため、同一アプリへの後続利用では再表示しない仕様です（[Appleの説明](https://developer.apple.com/documentation/bundleresources/requesting-authorization-for-media-capture-on-macos)）。WebViewのサイト許可はこれとは別です。
- 親の読み取り記録には、2026-10-08 21:43:08 の `http://127.0.0.1:8000` delegate 登録、21:43:10 の対象originへのGrant、23:29:51 の別起動時のdelegate登録が残っています。その後のGrant記録はありません。利用者は毎起動の許可画面を報告していますが、それがmacOSのアプリ許可かWebViewのサイト許可かは未確認です。記録された designated requirement は cdhash のみで、ビルドごとにidentityが変わり得ることは分かりますが、許可再表示の直接原因とは確定できません。[親の読み取り観測](../backend/outputs/macos-diagnostics/20261009-permissions-audit/parent-readonly-observation.json) はローカル診断記録（Git対象外）です。
- OBS Virtual Camera の system extension 承認は OBS 側の導入・初回ロードに関係する別の許可です。OBS の[公式トラブルシューティング](https://obsproject.com/kb/virtual-camera-troubleshooting) は macOS の「System Extension Blocked」等が出た場合にシステム設定から許可し、OBSを再起動する手順を案内しています。Splat Replay のカメラ許可と同じものではありません。対象MacのOS版と実際のOBS画面は未確認です。
- Apple Silicon Mac ノートでは、未知の USB / Thunderbolt / SD アクセサリを接続した時に OS が接続許可を尋ねる設定があります。[Apple のアクセサリ許可説明](https://support.apple.com/en-us/102282) によれば「Ask for New Accessories」等の設定により初回・毎回・再接続時に変わります。キャプチャ機器が該当するか、使用Macの機種・設定は未確認です。これはアプリの権限要求ではありません。

### 通知

- 通常の `showNotification` はウィンドウ表示中なら通知を送らず、隠れている時だけバックエンド通知APIを呼びます。[通常経路](../frontend/src/main/notification.ts#L102) と [LANクライアントの除外](../frontend/src/main/clientEnvironment.ts#L25) を参照してください。録画開始・終了通知はこの通常経路です。一方 `showNotificationAlways` は表示状態チェックを省略する例外APIです。[例外経路](../frontend/src/main/notification.ts#L74)。現時点でこの例外関数の呼出しはテストだけです。
- macOS adapter は送信時に通知設定を読み、状態が `NotDetermined` の場合だけ `requestAuthorization...` を呼びます。その後は許可状態を再読して通知を登録します。[UserNotifications adapter](../backend/src/splat_replay/infrastructure/adapters/system/macos_notification.py#L45)。Apple の[通知許可仕様](https://developer.apple.com/documentation/usernotifications/asking-permission-to-use-notifications) も初回の許可判断を保存する仕様です。
- したがって設計上は「通知を送る都度許可画面」ではなく、最初の該当送信時に未決定なら要求します。拒否済みの場合はアプリがシステム設定での許可を案内します。過去に許可後のAPI成功は確認されていますが、バナーや通知センターへの表示継続は未確認です。

### LAN、ローカルネットワーク、ファイアウォール

- LAN公開は設定と再起動後にバックエンドを `0.0.0.0` へ bind する設計です。接続候補URLを作る際に、アプリは LAN IP の対象ポートへ接続確認を行います。[ポートとURL確認](../backend/src/splat_replay/interface/web/routers/remote_access.py#L183)。アプリがファイアウォール規則を書き換えるコードはありません。macOS UI は利用者が受信接続とローカルネットワーク項目を確認する案内です。[設定画面](../frontend/src/main/components/settings/SettingsDialog.svelte#L660)。
- macOS 15 以降の Local Network privacy は、ローカルネットワーク上の相手への接続やマルチキャスト送受信に関係します。Apple の [TN3179](https://developer.apple.com/documentation/technotes/tn3179-understanding-local-network-privacy) によると、受信 TCP 接続を listen/accept するだけではこの許可の対象になりません。従って「LANサーバーを起動したから必ずこの許可が出る」とは言えません。
- このコードは LAN URL の到達確認でローカルIPへ TCP 接続し、NDIキャプチャは NDI Finder を起動してソース探索します。[URL接続確認](../backend/src/splat_replay/interface/web/routers/remote_access.py#L202) と [NDI Finder](../backend/src/splat_replay/infrastructure/adapters/capture/ndi_capture.py#L14) が候補経路です。macOS が許可を求める時点・NDI SDK内部の通信方式・実機でどの経路が警告を出すかは未確認です。
- ローカルネットワークのプライバシー許可とアプリ別Firewallは別の管理です。Firewall は受信接続を制御し、設定に応じて初回通信時に許可確認を出す場合があります。[Apple のFirewall説明](https://support.apple.com/guide/security/firewall-security-in-macos-seca0e83763f/1/web/1) と[接続警告の説明](https://support.apple.com/guide/mac-help/mh34041/mac)。許可の要否はFirewall設定・署名状態等に依存し、今回の状態は調べていません。

### Apple Events、ファイル、ユーザーデータ

- 本リポジトリで `osascript`、`NSAppleScript`、Apple Events automation の要求APIは見つかりませんでした。OBSやTerminalを開く処理は通常のアプリ起動経路であり、それだけでAutomation許可を求める根拠にはなりません。macOS はアプリが別アプリを Apple Events で操作する時に許可を求められます。[Apple Automation説明](https://support.apple.com/en-nz/guide/mac-help/mchl108e1718/mac)。依存ライブラリ内部の未知の要求までは確認していません。
- macOS frozen版の設定・出力・動画は `~/Library/Application Support/io.github.saw4405.splatreplay/` 以下です。[ランタイム保存先](../backend/src/splat_replay/infrastructure/filesystem/paths.py#L41)。保護された Desktop/Documents/Downloads 等を選ぶファイルダイアログ、Full Disk Access を要求するAPIは見つかりませんでした。Apple の[ファイルアクセス制御](https://support.apple.com/guide/security/controlling-app-access-to-files-secddd1d86a6/web)は保護場所への直接アクセスを別途制御しますが、現行の通常保存先はそこではありません。
- `NSOpenPanel` / `NSSavePanel` 等の導線は見つかりませんでした。ユーザーが保存先設定を変更した場合や外部アプリがファイルを開く場合の追加許可は、この調査では確認していません。`private_mode=False` のコメントを、TCCやファイル許可が永続する証拠としては扱っていません。
- 画面収録、Accessibility API、ログイン時自動起動を登録する呼び出しも製品コード・配布plistには見つかりませんでした。配布plistにある用途説明は Camera / Microphone / Local Network の3項目です。[macOS bundle plist](../backend/packaging/splat-replay-webview.spec#L237)。したがって、これらの許可を現在の通常利用で必須とは案内しません。外部ライブラリ内部の動作は未確認です。

### Gatekeeper、DMG、OBS・NDI導入

- 2026-10-09以降の macOS ビルドは固定自己署名証明書で署名し、公証はありません。[開発ガイド](./DEVELOPMENT.md#L338) と対応計画を参照してください。helper の `preflight` / `verify` はビルド元 Mac の login Keychain に同じ証明書と秘密鍵があることを要求します。配布先では公開署名の `codesign --verify` を別途使います。ユーザーは今回の `codesign` 初回アクセスで対象鍵に「常に許可」を選択したと報告し、親のA/B検証も成功しました。これはこのMac上のcodesign鍵アクセスとコード識別の確認であり、YouTube token項目の許可ではありません。DMGは `.app` を Applications へ置く配布形態で、アプリ内インストーラーではありません。
- Apple の[Gatekeeper説明](https://support.apple.com/en-us/102445)によると、インターネットから取得したアプリの初回起動時に署名・公証を検査し、確認できない場合に警告や「Open Anyway」を表示することがあります。表示文言や更新後の再確認はOS版・隔離属性・署名に左右され、一律に毎回/一度限りとは断定できません。Splat Replayが警告を迂回・隔離属性を消す実装は見つかりませんでした。
- NDI Runtime は公式pkgを開いて利用者がインストールし、管理者確認が表示された場合にOSの指示へ従う手順です。[OBSセットアップ](../frontend/src/setup/components/steps/OBSSetup.svelte#L708)。これはアプリの権限ダイアログではなく、外部パッケージとmacOS Installer側の確認です。実際にパスワードを求めるかは環境依存で未確認です。
- OBS Virtual Camera の system extension 承認は上記カメラ節のとおり OBS 側です。システム設定での許可・認証やOBS再起動の必要性は、macOS版と拡張の状態によります。

### Homebrew、FFmpeg・Tesseract・FLAC

- Homebrew が既にある場合、アプリは `brew install` を実行します。ない場合は公式インストールスクリプトと対象formulaを含む一時 `.command` を作り、Terminalを開きます。[installer](../backend/src/splat_replay/infrastructure/adapters/system/homebrew_software_installer.py#L39) と [Terminal起動](../backend/src/splat_replay/infrastructure/adapters/system/homebrew_software_installer.py#L81)。Terminal の内容・確認事項を利用者が見て進め、完了後にアプリの「再確認」を押します。
- Homebrew の[公式導入手順](https://docs.brew.sh/Installation)は実行内容の確認と利用者の応答を求めます。初回導入では環境によって管理者認証が必要になる場合があります。Homebrew導入済みの formula 更新でも毎回パスワードが必要とは限りません。実機で各formula導入を行っていないため、個別の入力要求は未確認です。
- FFmpeg / Tesseract / FLAC のアプリ内確認はセットアップ中の利用者操作です。macOS向けのHomebrew adapter は macOS 専用です。

### スリープ

- 設定が有効な場合、編集・アップロード処理後に15秒の予告とキャンセル機会を表示し、その後macOSでは `pmset sleepnow` を実行します。[処理後の予告](../backend/src/splat_replay/application/services/process/auto_process_service.py#L346) と [OSコマンド](../backend/src/splat_replay/infrastructure/adapters/system/system_power.py#L13)。アプリが管理者権限やパスワードを要求するコードはありません。
- OS側の電源ポリシー、アプリ実行環境、スリープの実成否は今回検証していません。処理中の設定切替と保存済み設定の挙動を混同しないでください。

### Google OAuth と Keychain

- YouTubeのOAuthはGoogleのログイン・アクセス同意です。コードは保存認証を使えない時にローカルブラウザフローを開始します。[資格情報ロード・更新](../backend/src/splat_replay/infrastructure/adapters/upload/youtube_client.py#L114) と [OAuth開始](../backend/src/splat_replay/infrastructure/adapters/upload/youtube_client.py#L138)。Googleの[OAuth説明](https://developers.google.com/youtube/v3/guides/authentication)にある同意と、macOS Keychainの許可は別です。
- macOSはYouTube OAuth tokenをKeychainの `SecItemCopyMatching` で読み、更新時は `SecItemUpdate` / `SecItemAdd` を使います。[Keychain adapter](../backend/src/splat_replay/infrastructure/adapters/upload/macos_keychain.py#L29)。Windowsは `config/token.pickle` を使います。[OS別保存](../backend/src/splat_replay/infrastructure/adapters/upload/youtube_client.py#L62)。`client_secret.json` は `config` に置く別ファイルです。
- YouTube client はプロセス内の資格情報をキャッシュし、欠落・期限切れ・APIクライアント未作成時にロードします。成功した期限切れrefresh後は更新資格情報を保存します。[キャッシュ判定](../backend/src/splat_replay/infrastructure/adapters/upload/youtube_client.py#L147)。従って、コード上「アップロードごとに必ずKeychainパスワードが必要」とは確認できません。
- 利用者からアップロードのたびにパスワード画面が出るとの報告があります。親の読み取りではKeychain値・ACL・ロック状態を調べておらず、連続起動/連続アップロードでの再現も未確認です。[Keychain read-only記録](../backend/outputs/macos-diagnostics/20261009-permissions-audit/parent-readonly-observation.json) はローカル診断記録（Git対象外）です。`-128` はコード上で許可操作未完了として伝達されますが、誰が閉じたか・更新署名が原因かは特定されていません。
- Apple の [Keychain access dialog](https://support.apple.com/en-gb/guide/mac-help/kychn002/26/mac/26) は、項目アクセス時の「Allow Once」と「Always Allow」を区別します。「Allow Once」は次回の同じ項目アクセスで再確認され、「Always Allow」は同じアプリidentityから当該項目への継続アクセスを許可します。対象はKeychainコードの[service/account定数](../backend/src/splat_replay/infrastructure/adapters/upload/macos_keychain.py#L7)（`io.github.saw4405.splatreplay` / `youtube-oauth`）のYouTube token項目だけです。全アプリへの許可、他項目への許可、Keychain項目の削除は採用しません。Keychain自体の[ロック/解除](https://support.apple.com/en-gb/guide/keychain-access/kyca1242/mac)は別状態です。
- **今回の保存方式適合性確認:** GoogleはmacOSのユーザートークン保存先の例としてKeychain Servicesを挙げています。[Google OAuth Best Practices](https://developers.google.com/identity/protocols/oauth2/resources/best-practices)にも合うため、現時点でKeychainを続ける方針を覆すコード上の根拠は見つかっていません。
- `YouTubeClient` は資格情報とAPI resourceをインスタンス内に保持し、未設定・期限切れ・API resource未作成時だけ再取得します。Web処理ではsingletonの `StartEditUploadUseCase` が `AutoUploader` と同じYouTube clientを保持するため、キャッシュが有効なら動画ごとのKeychain読込ではありません。バックエンド再起動、期限切れ、別client生成では再読込され得ます。[判定とキャッシュ](../backend/src/splat_replay/infrastructure/adapters/upload/youtube_client.py#L147)、[Web singleton登録](../backend/src/splat_replay/infrastructure/di/use_cases.py#L112)、[client保持](../backend/src/splat_replay/application/services/upload/auto_uploader.py#L25)。
- Keychain queryはservice/accountを指定した通常の `SecItemCopyMatching` で、毎回のパスワード認証やuser-presenceを要求する設定はありません。[読込query](../backend/src/splat_replay/infrastructure/adapters/upload/macos_keychain.py#L21)。読み取りqueryでlogin KeychainやData Protection backendを明示指定していないため、実項目のACL・検索対象Keychain・OS確認頻度はコードだけでは確定できません。Keychain読取失敗はそのままエラーとなり、未登録扱いのOAuth開始には進みません。
- Appleの[TN3137](https://developer.apple.com/documentation/technotes/tn3137-on-mac-keychains)はSecItem APIの使用を推奨し、新たにbackendを選ぶ場合はData Protection Keychainを推奨しています。現行コードはSecItem APIを使いますがbackendを指定しておらずfile-basedです（正式deprecatedではありませんが、廃止方向です）。移行にはentitlementを含む署名・配布設計が必要で、現行の固定自己署名証明書からの単純な置換候補ではありません。独自暗号化ファイルも暗号鍵の保管先を別途要します。どちらも今回採用していません。
- 固定署名で異なる実行ファイルのDRが継続したことは親のprobeで確認済みですが、YouTube token項目を使う連続アップロードや、その許可が更新後も続くことは未確認です。毎回のパスワード表示原因は実項目・Keychain状態を読んでいないため未確定です。
- 署名方針（ユーザー採用済み）:
  - **固定self-signed証明書**をmacOSビルドで使い、現行の限定WebKit delegateとYouTube用の対象Keychain項目だけを維持します。Appleの[コード署名技術ノート](https://developer.apple.com/library/archive/technotes/tn2206/_index.html)に沿う証明書ベースidentityで、公開SHA-256をpinします。秘密鍵はKeychainに保持し、通常ビルドは再発行しません。ユーザーは今回のcodesign初回アクセス確認で対象鍵を「常に許可」にしたと報告し、異なる実行ファイルのDR相互検証も成功しました。この結果は他のMacやOS許可全般へは一般化しません。カメラ許可の再表示とYouTube Keychain項目のアクセスは未確認です。初回Gatekeeperの警告は残ります。
  - **Developer ID署名と公証**は配布物のGatekeeper体験を改善する候補です。Appleの[Mac向け配布署名手順](https://developer.apple.com/documentation/xcode/creating-distribution-signed-code-for-the-mac)のような運用への移行は費用・運用変更を伴います。署名移行や更新で再許可が必要になる場合があり、OS privacy、Keychain lock、項目ACLを解消するものではありません。
  - どの署名案でもカメラTCC、WebView origin、マイクTCC、通知、Local Network、Firewall、OBS拡張、installer承認は別主体です。一つの包括的なOS同意にはまとめられません。DMG配布・初回手動許可の案内とWebKitカメラdelegateのorigin/frame/type限定、滑らかなプレビュー導線は維持します。新しい [固定自己署名の判断記録](./architecture/decisions/20261009-174403-macOS配布の署名を固定の自己署名証明書に切り替える.md) は旧判断の署名方式だけを置き換えます。

## Windowsとの差分

- WindowsにはmacOS Keychain adapterはなく、現行コードは YouTube token を `config/token.pickle` に保存します。[Windows側の経路](../backend/src/splat_replay/infrastructure/adapters/upload/youtube_client.py#L75)。このファイルへの読み書きにアプリ独自のOS許可APIは見つかりません。
- Windows字幕もデバイス一覧と実収音を別に行います。実機でマイクを開く時にWindowsのプライバシー設定が拒否していないことが必要ですが、OS/WebView2のプロンプト頻度は今回のWindows実機で確認していません。プレビュー `getUserMedia` のWebView2サイト許可とWindowsのカメラプライバシー設定も別層です。
- Windows通知は `winotify` からOS通知を送ります。macOS adapterのようにアプリコードが明示的に初回許可APIを呼ぶ経路はありません。[通知API](../backend/src/splat_replay/interface/web/routers/notifications.py#L83)。Windows設定による通知抑止・表示頻度は実機未確認です。
- Windows LAN画面は接続プロファイルを読み取るためにPowerShellを呼び、ファイアウォール規則のコマンドを画面に表示するだけです。[読み取り](../backend/src/splat_replay/interface/web/routers/remote_access.py#L114) と [コマンド表示](../frontend/src/main/components/settings/SettingsDialog.svelte#L82)。アプリが昇格・規則作成するコードは見つかりません。利用者が規則を適用する場合は管理者権限のPowerShellが必要です。NDI等の外部インストーラーがUACを出す条件と頻度は未確認です。

## OS許可ではないアプリ内案内・認証入力

- OBS WebSocket パスワードと Groq API キーはアプリ設定として保存される値で、macOSログインパスワードやOS許可ではありません。OBSパスワードは設定をTOMLへ保存します。[保存処理](../backend/src/splat_replay/infrastructure/adapters/system/cross_cutting.py#L95)。Groq APIキーは設定フォームから保存APIへ送られます。[字幕設定payload](../frontend/src/setup/stores/config.ts#L278) と [設定更新API](../backend/src/splat_replay/interface/web/routers/settings.py#L47)。保存済みで未変更なら通常は再入力不要で、変更・未設定時に入力します。実際に保存済みかはアプリ設定に依存します。
- `CameraPermissionDialog` と `YouTubePermissionDialog` はアプリ内の説明ダイアログで、OSのカメラ許可・Keychain認証そのものではありません。カメラ説明の表示とOS/WebViewの許可は別です。[カメラ案内](../frontend/src/main/components/permission/CameraPermissionDialog.svelte)。YouTubeの案内はGoogle同意とmacOS Keychain要求を区別し、「再度表示しない」はアプリ内案内の表示設定です。[YouTube案内](../frontend/src/main/components/permission/YouTubePermissionDialog.svelte#L40) と [表示済み状態の保存](../frontend/src/main/components/permission/YouTubePermissionDialog.svelte#L15)。Macログインパスワードを尋ねるUIでもありません。

## 未確認事項と境界

- 今回はmacOS/Windowsの権限状態、Keychain値やACL、ロック状態、TCCデータベース、Firewall設定、USBアクセサリ設定を照会していません。
- カメラの毎起動許可、Keychainの毎アップロードパスワード、今回の `-128` の起因、アプリ更新と再表示の因果は未確定です。画面の選択やOS設定変更を依頼する前に、利用者から許可画面の主体・表示文言・頻度の追加情報を得る必要があります。
- macOSで実確認済みなのは親記録にある特定時点のdelegateログ、通知API成功、過去のLAN接続等です。通知バナー、マイク実収音、Keychain再許可後の復旧、OBS extension承認、Gatekeeper更新後の再表示、実スリープは確認済みとしません。
- Windowsの権限プロンプト、WebView2の保存期間、UAC、OS通知頻度は実機未確認で、macOSと同じ頻度・永続性を保証しません。
- 調査はコード読取と公式資料照合のみです。OS許可を要求/変更せず、Keychainや認証情報を読み出さず、アプリを再起動していません。
