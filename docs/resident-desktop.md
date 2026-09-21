# 常駐版と Android アプリ

## 動作

Windows 版は通知領域へ常駐します。ウィンドウの × は画面を隠し、Switch の監視・録画・編集・アップロードを継続します。
通知領域のメニューから画面を開き直せます。「完全終了」は録画・編集・アップロードと実行中操作の完了を待ちます。Switch のスリープを待つのは更新予約の場合です。
二重起動した場合は既存の画面を表示します。

Android アプリは PC の既存 Web 画面へ接続します。初回に SplatReplay の LAN アクセス設定に表示される URL を入力してください。
PC が起動・ログイン済みで同じ自宅 LAN に接続している必要があります。
接続不能時は再試行し、再接続後は画面を読み直します。Android アプリを閉じても PC の録画は続きます。
認証は既存の LAN 公開方式（認証なし）に従います。接続先を自宅用 IPv4 に限定する検証は、認証の代わりではありません。
PC のスリープ復帰・電源投入は行いません。

## ログイン起動の登録

配布先の EXE を指定します。登録スクリプトは現在のユーザーのスタートアップにショートカットを作成します。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/register-desktop-startup.ps1 -Executable "$env:USERPROFILE\Desktop\SplatReplay\SplatReplay.exe"
```

解除は同じ引数に `-Remove` を追加します。通常の直接起動は画面を表示し、`--background` は画面を隠して起動します。
この登録やデスクトップへの配布は実装時のテストでは実行していません。

## 更新

既存の `task.exe deploy` は、常駐版の `assets/desktop-control.json` を検出すると常駐用更新処理を使います。
初回の旧版からの移行では既存の配布処理を使います。稼働中アプリを閉じる承認が必要な入口は従来どおりです。
更新準備のビルドはアプリを停止する前に実行します。

ビルド済みパッケージから直接更新する場合:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/update-resident-desktop.ps1 -SourceDir "C:\path\to\new\SplatReplay" -DestinationDir "$env:USERPROFILE\Desktop\SplatReplay"
```

- 更新予約中も新しいプレイを録画します。Switch がスリープし、後処理の猶予と実行が終わるまで待ちます。
- 通知領域から更新予約を取り消せます。既定の待機期限は 12 時間で、`-WaitSeconds` で指定できます。
- 正常終了に失敗した場合は強制停止して更新せず、中止します。利用者が先に起動した OBS はアプリの既存の所有権ルールに従います。
- 差し替え対象は EXE・`_internal`・`assets` です。設定・動画・ログ等と個別導入フォントを保持します。
- 新版は仕事を開始しない保留状態で起動し、API の応答と画面読み込みを確認してから常駐監視を開始します。起動確認の期限は既定 120 秒です。
- 起動確認前の失敗は、新版の終了を確認してから旧版を復元します。新版が既に仕事を始めた後は自動復元しません。
- 旧版は配置先の `.splat-update-<識別子>/previous` に保持します。自動削除しないため、不要になった版は正常動作を確認してから利用者が削除してください。
- 同じ配置先・ユーザーセッションでの重複更新を排除し、差し替え中の通常の新規起動を抑止します。

更新時に必要な通信は Windows のローカルオブジェクトと親子プロセス間の信号です。LAN に更新・終了 API は追加していません。
CLI の `--desktop-command` は `show / update / cancel / quit / resume / status` を受け付けます。
`status` の終了コードは `0=稼働、3=起動中、4=不在、5=更新待ち、6=保留起動、7=予約取消` です。
`--hold` と `resume` は更新スクリプト用です。

## Android のビルド

アプリ識別子とJavaパッケージ名は `app.splatreplay.android` です。
ソースは `android/src/app/splatreplay/android` に配置します。

Android SDK Platform 35・Build Tools 35.0.0 と JDK 17 を用意し、パスを指定します。
Gradle や追加の Android ライブラリは使用しません。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build-android.ps1 -SdkRoot "C:\path\to\sdk" -JavaHome "C:\path\to\jdk-17"
```

出力は `dist/android/SplatReplay.apk` です。ローカル導入用 debug 署名で、鍵は `.task/android/debug.keystore` に保持します。
同じアプリの更新には同じ鍵を使います。生成物・鍵はコミットしません。
対応下限は Android 8（API 26）、target SDK は 35 です。

## 検証の範囲

録画優先の判定、後処理待ち、制御先分離、保留起動の API 契約、更新・復元時のデータ保持を自動テストで確認します。
通知領域と WebView の ×・再表示・完全終了は、録画しない検証用 API を使った対話デスクトップのテストでも確認します。
このテストは実 OBS の録画・終了や Android 実機の接続を代替しません。
実際の配布版での録画から更新までの通し確認、Android 実機での表示・再接続は未確認です。

### 2026-09-14 の実装時確認

- 参照方針: `docs/test_strategy.md`。
- 変更分類: `static / logic / contract / workflow`。
- 保証対象: 録画優先の更新待ち、後処理の猶予、保留起動時の受付、配置先の分離、データ保持・復元、通知領域と画面の生存期間。
- 新規テスト判断: 上記の追加分岐と境界を守るテストを追加。従来の「起動タイムアウトで強制終了する」テストは、処理を破棄しない契約へ変更した。
- 実行入口: repo の `run-backend-pytest.py` で関連 9 ファイル 44 件成功。対話デスクトップでは通知領域・実 WebView の 2 件も成功。
- 静的検証: 変更した Python の Ruff・型検査、PowerShell 4 スクリプトの構文確認、`task.exe import-lint` の依存契約 6 件を確認。
- ビルド: `task.exe build:backend` とアセット・設定例のパッケージ処理を実行。配布物の `--desktop-command status` は不在を示す終了コード 4 を返した。
- Android: SDK 35/JDK 17 でコンパイル、URL 境界のテスト、APK の v2/v3 署名検証が成功。
- 省略した入口と理由: Svelte の変更はないため component/integration は実行しない。Web の変更は保留時の受付契約に限定され、contract と専用の Windows 導線テストで確認した。全体 `verify`・release・性能テストは今回の保証範囲を超えるため実行しない。
- 未確認事項: Android 実機と実 OBS を含む通し動作、配布版自身の画面・終了の通し動作、ログイン起動の実登録。
- 追加で必要な確認: デスクトップへ反映後、Android 接続、スマホ未接続での録画、Switch スリープ後の更新、仮想カメラ停止・OBS の次回通常起動。

この実装時の生成物は `backend/dist/SplatReplay/` と `dist/android/SplatReplay.apk`。
稼働中のデスクトップ配置先は変更していない。

### 2026-09-15 のデスクトップ反映確認

- 2026-09-14 に SplatReplay の正常終了と仮想カメラ停止をログで確認し、既存 OBS も正常終了した。
- `backend/dist/SplatReplay` をデスクトップへ反映し、配布ファイルの SHA-256 を照合した。設定・動画・ログ・outputs・個別フォントの計 4,809 ファイルは更新前後でパスと SHA-256 が一致した。
- 旧版本体は配置先の `.splat-update-48abee561f044bc2abb2e013ccf3c62e/previous` に保持した。
- 現ユーザーのスタートアップに `SplatReplay.lnk` を登録し、配布先 EXE・`--background`・作業ディレクトリを読み返して確認した。実ログインによる起動は未確認。
- 保留起動の status 6 を確認後、2026-09-15 に resume して status 0 を確認した。OBS の通常起動・WebSocket 接続・仮想カメラ開始・監視開始をログで確認した。
- LAN アクセスは既存設定で有効。API が `http://192.168.1.24:8000/` を返した。
- APK は 2026-09-14 に Tailscale の XQ-CT44 へ送信成功。Android 上のインストール・表示と実録画から更新までの通し確認は未確認。

### 2026-09-15 の Android アイコン調整

- ユーザーから Android 実機での接続成功を確認した。
- 通常画像にランチャーが余白を付ける構成から、標準 adaptive-icon に変更。既存画像を中央 72dp に配置し、丸い枠で大きく表示する。versionCode 2 / versionName 1.1。
- 参照方針: `docs/test_strategy.md`。変更分類: static。保証対象: アイコンリソースの参照・コンパイル・更新APKの署名。
- 新規テストは不要（宣言的なリソース変更）。`scripts/build-android.ps1` でビルド、既存 URL チェック、v2/v3 署名検証が成功。aapt2 で APK 内の adaptive-icon と versionCode 2 を確認した。
- Svelte やバックエンドの動作変更がないため、そのテスト入口は省略した。
- 更新 APK を Tailscale で XQ-CT44 へ送信済み。アイコンの実機表示サイズは未確認で、上書きインストール後に確認が必要。

### 2026-09-15 の Android 接続操作UI

- Android側の操作を中立色の「PCへの接続」バーに集約。本体のネオン表現と区別し、タップで下から接続パネルを表示する。接続先変更・再接続・閉じるを配置し、接続失敗時はバーにも再接続と確認案内を表示する。
- 参照方針: `docs/test_strategy.md`。変更分類: static / workflow。保証対象: Android のコンパイル・署名と既存 URL 境界。UIは48dp以上の操作領域、スクロール可能なパネル、戻る・外側タップ・閉じるボタンでの終了を実装した。
- 新規自動テストは追加せず、既存 `scripts/build-android.ps1` の URL チェック・APK ビルド・v2/v3署名検証を実行し成功した。versionCode 3 / versionName 1.2。
- Webフロントエンド・PC側の変更はないため component/integration/workflow smoke の既存Web入口は省略。Androidエミュレーターは未導入で、ADB接続端末もないため、Android UI導線の実行検証は未完了。
- 実機確認項目: 上書きインストール後、バーからパネルを開く、接続先変更・再接続、戻る/外側タップ/閉じる、通信切断時の案内と復帰、横向き・大きい文字での操作。

### 2026-09-15 の接続状態・文言調整（Android 1.3）

- 状態表示に色付きの●を追加（接続済み=緑、確認中=黄、未接続/未設定=灰）。状態名と読み上げ用の操作説明も維持した。
- パネル名を「接続設定」に変更し、設計意図の説明文は削除した。
- 参照方針: `docs/test_strategy.md`。変更分類: static。表示装飾・文言の変更のため新規テストは追加しない。既存Androidビルド入口のURLチェックとv2/v3署名検証が成功。Web/バックエンドのテストは対象外。実機の色・読み上げは未確認で、更新後の確認が必要。

### Android 1.4 の表示調整

- 状態表記を「●PC未接続」「●PC接続確認中」「●PC接続済」に統一。接続先未設定もPC未接続と表示する。
- ヘッダー再接続ボタンに左8dp・右12dp・上下6dpの余白を追加。
- パネル名を「PC接続設定」に変更。下部の閉じるボタンを削除し、右上の×（48dp、読み上げラベル付き）に移動した。
- 検証方針: `docs/test_strategy.md`。分類static。表示文言・配置変更のため新規テストは追加せず、既存Androidビルド入口でコンパイル・URL境界・署名を検証する。Web/PCのテストは対象外。実機表示・タップは更新後の確認が必要。

### Android 1.5 の未接続時案内（2026-09-19 確認）

- ヘッダーの再接続ボタンを削除し、接続状態によって高さを変えない構成にした。
- 未接続画面で、PCでSplatReplayを起動・同じ自宅ネットワークへ接続・LANアクセスURL照合の順に案内する。表示URLの直下から接続先を変更でき、未設定時も案内から設定できる。
- 対処案内と別段落で、画面を開いて待つこと、失敗から5秒後に再確認すること、成功時に自動表示されることを説明。未接続からの各確認開始時は確認中を表示し、案内は維持する。
- 方針: `docs/test_strategy.md`。分類static/workflow。新規自動テストは追加せず、既存Androidビルド入口でコンパイル・URL境界チェック・v2/v3署名検証が成功。既存Web入口はAndroid画面を対象としないため省略。
- 送信再試行前にAPKのSHA-256がビルド時と同一であることを確認した。
- Android実機のUI検証は未完了。未設定/誤った接続先/自動再確認/変更後の復帰/ヘッダー高さ/大きな文字でのスクロールが残る確認項目。

### 2026-09-20 完全終了・OBSトレイ起動の修正（配布前）

- 完全終了ではSwitchの電源状態を待たず、録画停止・後処理完了・未消化OFFイベント・実行中APIの完了を確認する。更新予約は従来のSwitch停止待ちを維持する。
- 判定はフレーム境界、初期化失敗後の後片付け済み再試行境界、UC停止済み状態に限定し、録画開始と競合させない。
- OBS起動に `--minimize-to-tray` を追加。非表示の本体ウィンドウも起動確認とWM_CLOSE正常終了の対象にする。既存OBSの所有権は維持する。
- 参照方針: `docs/test_strategy.md`。分類logic/contract/workflow/static。新規分岐と再発防止（切断時終了、処理保護、停止済み/初期化失敗時終了、非表示OBS検出と終了）を既存テストへ追加。
- 関連6ファイル50件成功後、追加した2件を含む対象2ファイル14件成功。実Windows通知領域・WebViewテスト2件成功。Ruff・ty・import-lintの6契約も成功。
- 配布EXEビルド・アセット等のパッケージ作成済み。デスクトップへの反映、実OBSを含む終了・次回トレイ起動は未確認。
- Webフロントエンドは変更していないためWeb component/integrationの入口と全体release検証は省略した。

### 2026-09-20 21:08 配布版の終了・再起動確認

- 追加原因は、Uvicornが既存SSE接続の終了を待ち、lifespanの後片付けに進めない循環待ちだった。親子間の既存終了イベントをASGIへ渡し、progress/domain-eventsの両配信を終了させた。実TCPで両接続を保持した回帰を含む関連11件が成功した。
- 再開時点でデスクトップには新しいビルドが配置されていたため、再配布は行わなかった。backend/buildのEXEと配布EXEのSHA-256は `2EA42BEA973A5E8F83D5BD4E11AEDB950E3F1AD49AD03BB9BF5F7BE1B2E4B987` で一致した。
- 録画STOPPED・後処理idleで両SSEをHTTP 200のまま保持し、通知領域と同じquitコマンドを送信。受理コード0、12.98秒でSplatReplay全プロセスとOBSの終了を確認した。実際のトレイメニュークリックは今回の配布版では未確認。
- 21:07:39〜40のログで仮想カメラ停止完了、WebSocket切断、OBSウィンドウの正常終了、自動録画と後処理サービス停止を確認。強制終了は発生しなかった。
- 常駐再起動後、OBSの `--minimize-to-tray` と本体ウィンドウ非表示、WebSocket接続・仮想カメラ開始・監視runningを確認した。常駐稼働状態で残した。
- 上の「配布前」の未確認項目は、この実機検証の範囲で解消した。Android端末操作とログイン起動は今回の検証対象外。

### 通知領域の状態表示（2026-09-21）

- 既存ロゴの右下へ状態マークを表示する。緑丸=待機、赤丸=録画（ツールチップで一時停止も区別）、青の処理マーク=編集・アップロード、灰時計=起動・機器確認・終了処理、黄!=機器未接続・自動録画停止・後処理失敗。
- 録画中を最優先し、同時に進む処理と要確認事項はツールチップへ併記する。更新予約・終了待ちも併記する。録画や更新の制御条件は変更しない。
- バックエンドの既存状態をinterface層で読み取り、既存DesktopSignalsの共有メモリで親へ渡す。親からWindowsメッセージでトレイスレッドへ更新を依頼し、状態が変わった時だけアイコンを更新する。公開APIや依存ライブラリは増やさない。
- 状態アイコンは `scripts/generate-tray-icons.py` で既存ロゴから決定論的に生成する。
- 検証方針は `docs/test_strategy.md`。分類はlogic/contract/workflow/static。優先順位・spawnでの状態通知を追加し、既存Windowsトレイテストへ全状態切替とExplorer再起動後の復元を追加した。関連14件が成功（初回のExplorer再起動模擬でアイコン削除が不足し失敗、実際の再起動条件に修正後に対象3件成功）。Ruffとtyも成功。
- Web UIは変更しないためfrontend component/integration/workflow入口と全体release入口は省略。実録画・実アップロード中の目視確認は自動テストとは別の確認項目。
- 配布確認: 2026-09-21 11:01に更新完了。配布EXEとビルド元のSHA-256は `FBE82AAF5A8006683ADAC2FD5A4A9B2B8E7D274421695767504679AE5544D480` で一致。設定・動画・outputs・個別フォント計5,427ファイルの更新前後ハッシュが一致した。
- 初回更新は旧版の終了コード判定で差し替え前に停止。原因は未確定。ログで仮想カメラ・OBS・録画・後処理の終了と全プロセス消失を確認し、停止済み状態から再実行して成功した。
- 配布後APIは `running / waiting_for_power_on`。実Windowsテストで5種のアイコン更新を確認したが、配布版のツールチップはUI Automationで取得できなかったため、実プレイ中の画面目視を確認済みとは扱わない。
