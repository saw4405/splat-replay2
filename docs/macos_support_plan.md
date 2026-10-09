# macOS 対応調査と着手計画

- 状態: M1〜M10 の実装と対象検証を終え、最終検証中。2026-10-02 にユーザーが実ゲームの自動録画・音声観測・XP/スペシャル回数、編集・アップロード、別端末 LAN 接続、機器切断後の再接続・復帰、DMG 起動を確認し、2026-10-03 に matching 開始表示を再確認した。2026-10-09 に既存アプリの payload を再ビルドせず固定自己署名で候補化し、親の独立検証後に起動中アプリへ反映した。health/setup/status と録画・監視・処理の安全状態、メイン画面を親が確認した。カメラ許可の毎起動再表示と本番 YouTube Keychain の再許可は未確認。LFS 素材不足のため workflow は未実行で、全体受け入れは未完了。マイクから字幕、通知の実表示、常駐メニューの実操作、初回導入の未確認経路も残る。実スリープと復帰の検査はユーザー判断で今回は実施しない。
- 作成日: 2026-09-25
- 対象: Apple Silicon 搭載 Mac。初回対応から Windows 版の全機能を同等に利用可能にする。Intel Mac は今回の対象外。
- 目的: macOS 上でも初回セットアップから自動録画、振り返り、編集、YouTube アップロードまで正常に利用できるようにする。
- 成功条件: Apple Silicon 向け macOS 配布物から起動し、必要な権限と外部ソフトを設定した後、実機映像の検出・録画・保存・再生・編集・アップロードに加え、キャプチャ機器の列挙・選択・接続判定・切断監視、処理後スリープ、通知、LAN アクセスを確認する。USB 機器の自動復旧は Windows / macOS とも対象外とする。
- 変更責務: OS 固有の取得・起動・保存・通知・電源操作は `infrastructure` と `bootstrap` / 配布設定、導線表示は `interface` / `frontend` に置く。`domain` の録画・編集判断に OS 分岐を入れず、既存の port と DI を優先して使う。

## 現状と対応が必要な機能

以下はコード調査と macOS 実機での対象検証の結果を分けて記す。既存の `replay` E2E 合格も native 実機動作の保証ではない（[既存 ADR](architecture/decisions/20260827-041653-WSL2%20replay%20E2E可搬性ゲートをComposition%20Rootの実行プロファイルで分離する.md)）。

| ID | 機能・ユーザー影響 | 確認した障害・未確認点 | 主な責務と対応方針 |
| --- | --- | --- | --- |
| M1 | 開発環境と依存導入 | macOS arm64 用の Taskfile、hook / LFS 導入、doctor の POSIX 経路、Windows 専用依存の分離を実装し、依存解決・PyAudio 初期化・pywebview の最小起動を確認した。実データ取得は許可済みだが Git LFS の3オブジェクトが404となり、replay workflow は未実行。 | 開発・doctor の OS 別経路は実装済み。LFS オブジェクトを取得できる状態にした後、replay workflow を確認する。 |
| M2 | デスクトップ起動・設定/動画の保存 | arm64 `.app` の起動、設定の保存・再読込、動画パス解決、Application Support への設定・ログ保存、Keychain API のダミー項目操作を確認した。 | `.app` 内の資産とユーザーデータは分離済み。DMG 起動は2026-10-02にユーザーが確認済み。更新後の保存データ維持は継続確認する。 |
| M3 | 初回セットアップと権限案内 | OBS / NDI Runtime / FFmpeg / Tesseract / FLAC / Homebrew の検査・案内を実装した。DistroAV と NDI Runtime の手動導入後、OBS の Main Output と NDI Runtime を確認し、NDI 映像受信まで実機確認済み。`NSCameraUsageDescription` を追加し、カメラ権限許可後に録画画面が表示されることを確認した。 | DistroAV プラグインと Main Output は画面上で利用者が設定・確認する設計。権限拒否からの復旧、セットアップ画面からの Homebrew / FFmpeg / Tesseract 導入全経路は未確認。 |
| M4 | キャプチャ機器の選択・接続判定・切断監視 | FFmpeg AVFoundation の映像デバイス列挙、選択名による接続判定、未検出・タイムアウト・明示的な権限拒否を未接続とする処理、録画中の切断検査を実装した。カメラ許可後の配布アプリで MiraBox Capture と OBS Virtual Camera の列挙、MiraBox の選択・接続判定 `true` を確認した。2026-10-02 にユーザーが機器の抜き差し後の復帰を確認した。 | 既存の表示名 API / port / DI を利用する。同名機器の区別と USB 自動復旧は対象外。 |
| M5 | OBS 起動・録画・映像入力・プレビュー | macOS の OBS 実行ファイル解決、プロセス起動・検出・終了、DistroAV / NDI Runtime / Main Output と 1920×1080 BGR frame 受信を確認した。認証付き OBS WebSocket 経由でアプリの録画開始・停止・MKV 保存と、1920×1080 JPEG プレビュー受信まで実機確認済み。利用者の OBS とアプリの同時画像で Switch 映像の表示も確認した。 | 画角は利用者確認で修正済み。カメラ許可要求は配布アプリの複数回起動で解消を確認した。低解像度取得を補正し、配布 frontend の実 WKWebView で1920×1080・60 FPSを確認した。実際の Switch 映像による自動録画と音声観測は2026-10-02のユーザー確認で合格。機器の抜き差し後の復帰も確認済み。長時間受信・OBS 異常終了後の挙動は未確認。スリープ復帰の実機検査は今回実施しない。 |
| M6 | マイク・文字起こし・字幕 | Apple Silicon 用 PyAudio / PortAudio、入力チャンネルによるマイク列挙・index 解決、FLAC の検査・導入導線を実装した。BOYA mini の列挙とキャリブレーション読み取り141サンプルを確認したが、その測定は RMS が全て0だった。 | 2026-10-02に BOYA mini を保存設定へ指定。合成音声の Google 認識と字幕保存経路は確認したが、統合認識は Groq 認証エラーとなった。ユーザーのキー更新・文字起こし ON の保存後に、統合字幕を検証する。実収音から字幕までの成功は未確認。 |
| M7 | 録画済み動画・編集・サムネイル・アップロード | macOS の MKV からの一時 MP4 生成・配信・再生・シーク、yuv420p への変換、Tesseract 日本語認識、OS 標準フォントによるサムネイル生成を確認した。検証用 SRT / metadata を使った編集生成と Keychain 経由の YouTube client 経路も確認済み。実録画のスペシャル回数 1 を 7 と読む不具合を再現し、抽出の切り出し処理を修正した。 | 2026-10-02 にユーザーが実編集と YouTube アップロード、XP・スペシャル回数の最終確認に成功した。マイク由来の字幕と実録画由来の TTS は引き続き未確認。 |
| M8 | 通知・処理後スリープ・LAN アクセス | UserNotifications adapter / API、`pmset sleepnow`、macOS のファイアウォール・ローカルネットワーク案内を実装した。通知 API は許可後に HTTP 200・`status: success` を返し、macOS への登録を確認済み。LAN 公開のチェック後に保存していなかったことを確認し、UI に未保存と再起動の案内を追加した。 | 別端末からの LAN 接続は2026-10-02のユーザー確認で合格。通知バナー / 通知センターでの表示を継続確認する。実スリープの検査はユーザー指定により今回は実施しない。 |
| M9 | macOS 配布と利用手順 | 固定自己署名の arm64 `.app` と DMG を検証した。2026-10-09 候補は既存 `.app` を複製して署名し、PyInstaller からの全再生成はしていない。親は署名・DR・DMG と payload 一致を独立確認し、起動中アプリへの反映後に safe API とメイン画面を確認した。 | 公証は行わない方針。固定署名への切替とこの Mac 上での起動は確認済み。カメラ許可の再表示抑止、YouTube Keychain の再許可、Gatekeeper のダウンロード DMG 経路は未確認。全機能受け入れとリリース前の総合確認は継続中。 |
| M10 | 常駐・OS の状態表示・安全な完全終了 | 共有状態判定・終了待機へ macOS を接続し、メニューバーのアプリアイコン左下の5状態バッジ・再表示・完全終了、Dock 再オープンを実装した。実配布アプリで閉じる操作後の監視継続と、アプリメニュー・Cmd+Q の完全終了による全プロセス・ポート解放を確認した。 | メニューバーのロゴと状態の見え方・メニュー選択と Dock クリックによる復帰は検証ツールから直接確認できず未確認。録画中・後処理中の終了保護は下位テストで確認し、実ゲームの最終確認に残す。 |

## 対応方針

1. **成立性を先に調べる。** 依存の native wheel / ビルド可否、pywebview 起動、OBS・NDI・マイクの実機可用性を確認する。依存追加・削除や代替入力方式は、その結果とユーザー判断を経て確定する。
2. **Windows の動作を守る。** OS 差は既存 port の adapter または composition root と、セットアップ UI の表示に閉じる。Windows の既定値や `live` / `replay` 契約を一括変更しない。
3. **偽の成功をなくす。** デバイス・外部ソフト・権限の検査は、観測できない場合に成功を返さない。失敗箇所を UI で説明し、録画開始前に検知できるようにする。
4. **主要導線を縦に検証する。** replay のソフトウェア回帰に加え、macOS の実機入力と native 配布物を別の受け入れゲートとする。検証入口は `docs/test_strategy.md` の分類に合わせて最小の対象から選ぶ。

レビュー反映: Astra（軽）は保存先と NDI の CPU アーキテクチャ、権限拒否・機器再接続等の失敗モードを初期調査に含めるよう助言した。`design_steward`（ADVISE）は正式対応範囲・配布・保存のユーザー判断が必要とした。ユーザーは Apple Silicon を対象に確定し、USB 機器の自動復旧は Windows / macOS とも対象外にした。両レビューは実機合格を示すものではない。

## 着手順と完了ゲート

| 順 | 作業 | 完了ゲート |
| --- | --- | --- |
| 0 | Apple Silicon・全機能同等という確定済み範囲を受け入れ条件に反映し、実機構成・配布・データ保存の具体案を調べる | 配布・保存など影響の大きい未決事項を、選択肢と影響を示して実装前に確認する。 |
| 1 | M1: macOS 上で依存導入と `replay` 実行を通し、問題の native 依存を切り分ける。OBS / NDI / pywebview の成立性を小さく調べる | import と replay の失敗箇所が特定され、macOS で反復可能な開発入口がある。native 実機連携で代替案が必要な箇所が分かる。 |
| 2 | M2: macOS デスクトップ起動と保存先の最小縦断 | GUI 起動、設定保存、再起動後の再読込、動画配置がアプリ外の書き込み可能領域で確認できる。 |
| 3 | M3: macOS セットアップと権限・外部コマンド確認 | 誤った完了表示がなく、必要な OBS / NDI / FFmpeg / Tesseract / マイクの準備状態が判別できる。 |
| 4 | M4・M5: 実機映像と OBS 録画の縦断 | キャプチャ機器の列挙・切断検知、OBS 起動確認、プレビュー、録画開始・停止・保存が実機で通る。 |
| 5 | M6・M7: 音声、編集、字幕、YouTube 共有の縦断 | マイク収音から字幕までと、録画済み動画の再生・編集・アップロードが確認できる。 |
| 6 | M8: 通知、スリープ、LAN アクセス | 各機能が Apple Silicon の macOS で動き、失敗時の表示と利用者向け手順が確認できる。 |
| 7 | M9: native 配布物、手順、回帰確認 | 新規 Apple Silicon 環境で配布物から全機能が通る。Windows の対象回帰と macOS native 実機確認を別々に報告する。 |

各段階でコード変更を始める際は `docs/test_strategy.md` に沿って `static`、`logic`、`contract`、frontend `component` / `integration`、`workflow:smoke` の必要な保証だけを選ぶ。リリース前は `test:release`、性能影響があれば `test:release:performance` と実機確認を行う。

### 進捗記録

- M1: Apple Silicon の macOS 上で調査中。Taskfile の仮想環境パス・hooks・LFS・OpenAPI 生成と doctor の POSIX 経路を修正し、hooks の実設定まで成功した。Windows 専用依存を分離し、PortAudio 導入後は macOS で `uv sync --locked` が成功。`cyndilib` の Finder / Receiver 構築と Finder open、PyAudio 初期化、pywebview の最小ウィンドウ起動・終了も成功した。ただし NDI ソースと音声入力デバイスはともに 0 件で、実機収録は未確認。Web app の生成は 73 routes、bootstrap import の logic テスト 1 件、frontend doctor テスト 11 件、TypeScript 型検査、frontend ビルドは成功。OBS 32.2.2 の CLI は存在するが、FFmpeg / Tesseract は現環境の PATH にない。doctor は LFS pointer を fail と報告し、`git lfs pull` もサーバー側 3 オブジェクトの 404 で失敗したため、replay は未実行。製品 GUI と OBS / NDI 入力も未確認。
- M1 の依存判断: ユーザー承認により `comtypes` と `pygrabber` を Windows 限定、`pyaudio` を Windows / macOS 対象にし、lockfile の条件を更新した。PortAudio 19.7.0 導入後の `uv sync --locked` は成功。PyAudio の初期化は成功したが、この実行環境で列挙された入力デバイスは 0 件で、実収音は未確認。
- M2 の設計判断: ユーザーは「動画は基本的にアプリが使えればよい」「Keychain に保存」「Windows からの取込は対象外」を選択した。Apple の指針に沿い、macOS では `~/Library/Application Support/<bundle ID>/videos` を既定にする。`.app` の読み取り専用資産と書き込みデータは分離する。`design_steward` の ADVISE は、この分離と動画・認証情報の保存先決定を推奨した。
- M2 の実装・検証: bundle ID `io.github.saw4405.splatreplay` の arm64 `.app` を `task build:macos` で生成し、`build:macos:verify` で frontend、起動画面動画、画像認識設定の同梱と、設定・動画・再配布を認められていないフォントの非同梱を確認した。可視ウィンドウに初回セットアップが表示され、隔離ホームで `/api/health` が応答し、設定・ログが `~/Library/Application Support/io.github.saw4405.splatreplay/` に作成された。設定の保存・再読込と相対動画パスの解決は contract テストで確認した。Keychain の汎用パスワード API はダミー項目の作成・更新・読込・削除まで実機確認し、YouTube OAuth token の保存経路に接続した。実アカウント認証、動画生成、実機収録、署名・公証は未確認。PyInstaller は `speech_recognition/flac-mac` の古い SDK について署名・hardened runtime 上の警告を出しており、M9 までに対処を要する。
- M3 の確定範囲: ユーザーは macOS でも FFmpeg・Tesseract のアプリ内自動導入を必須とし、Homebrew 自体もアプリのボタンから導入する方式を選択した。Homebrew 初回導入は Terminal で公式インストーラーを開き、確認・必要な管理者入力を利用者が行う。Tesseract の日本語 OCR データも導入・実行確認の対象にする。導入中・失敗時は準備完了にしない。
- M3 の実装・検証: backend に macOS の OBS / NDI / FFmpeg / Tesseract と日本語 OCR データの判定、および Homebrew による導入を接続した。frontend の初回セットアップを macOS の導入・権限案内に分岐し、導入後の再検査でのみ完了を示す。音声入力は PortAudio の入力チャンネルを持つ機器だけを列挙し、macOS では毎回再列挙する。変更当時の対象 backend 95 件と frontend 9 件が成功。arm64 `.app` の起動と `/api/health` 応答を確認した。凍結版で不足した cyndilib の実行時 import を同梱し、同じ frozen backend の隔離 probe で NDI 判定は HTTP 200・`is_installed: true`、音声入力一覧は HTTP 200・0 件を確認した。実 `.app` の GUI 再起動は Computer Use の自動承認で拒否され、修正後の GUI 経由 GET は未確認。NDI ソースは 0 件で、送受信は未確認。現ホストに FFmpeg / Tesseract はなく、アプリからの実導入は未実施。入力機器での実収音、権限拒否からの復旧も未確認。
- 最新版取り込み: `origin/main` の `57e1cd1`（USB 復旧削除）を取り込み、既存 macOS 変更を復元した。競合したセットアップ API の契約テストを新しい `RecordingPreparationService` に合わせた。関連 backend テスト 59 件、frontend テスト 9 件、Ruff、import-lint、frontend 型検査と Svelte 検査が成功。macOS での全体 `ty check src tests` は Windows 専用 import の未解決を含む 15 診断で失敗し、対象ファイルの型検査は成功。Windows 実機回帰とフル test は未実施。
- M5 の先行調査: OBS 32.2.2 arm64 はホストにあるが、当初の起動設定は Windows 既定パス、起動中判定は Win32 ウィンドウ検出を要求していた。初期の NDI セットアップ判定は backend の cyndilib Finder 初期化のみで、OBS の DistroAV plugin・必要な NDI Runtime・実映像の受信を保証しなかった。調査開始時点では DistroAV と system NDI Runtime の導入を確認できず、NDI source も 0 件だった。
- M5 のプロセス管理修正: macOS では Windows 既定の OBS 実行パスを標準 `.app` 候補に解決し、設定パスと一意に一致する既存 OBS または管理中プロセスで稼働を判定する。アプリ所有 OBS の終了は SIGTERM 後 10 秒で kill に切り替え、待機にも上限を設けた。プロセス一覧の権限拒否は OBS 不在と扱わず、`OBS_PROCESS_LOOKUP_FAILED` で重複起動を止める。対象 logic テスト 26 件、Ruff、対象 ty が成功。隔離 HOME の実 OBS 32.2.2 arm64 で `manager.launch()`、PID 検出、`is_running=True`、`teardown()` 後の終了を確認し、親エージェントも残留プロセスと一時 HOME の不在を再確認した。OBS ログでは音声・映像・入力監視の権限拒否と MiraBox 入力の初期化失敗があり、実録画・音声入力は未確認。WebSocket はユーザー設定で無効のため接続未確認。NDI 送受信も未確認。
- M5 の WebSocket 追加 smoke: 既存 OBS と TCP 4455 の listener がない状態で一時 HOME に設定を置いて OBS を起動したが、4455 は listen せず handshake 前に中止した。OBS が一時 HOME ではなく既存ユーザープロファイルを参照した可能性を排除できず、設定が不変だったとは未確認。検証用 OBS PID 4442 が残留したため、親エージェントが PGID 内に当該 PID だけがいることを確認して TERM で終了し、その後 OBS と 4455 listener がないことを再確認した。WebSocket の可用性は未確認で、同じ HOME 切替方式で追加試行しない。
- M6 の調査と実装: 現ホストの PortAudio と `system_profiler SPAudioDataType` は入力機器 0 件で、実収音と TCC 許可は未確認。SpeechRecognition 3.14.3 は Google 認識時に PATH の `flac` を優先するが、現ホストにはなく、同梱 x86_64 の `flac-mac` は Apple Silicon で `bad CPU type in executable` となる。ユーザー判断に従い、macOS の文字起こし有効化画面に FLAC の検査とアプリ内 Homebrew 導入を追加した。導入後に `flac --version` を再確認できるまで完了扱いにしない。backend 対象 57 件、frontend integration 6 件、Ruff・import-lint・対象 ty・frontend 型/Svelte/lint/format 検査は成功。arm64 `.app` を再ビルドし、親エージェントが bundle ID、`NSMicrophoneUsageDescription`、arm64 実行形式、FLAC 関連モジュールと frontend/assets/config の同梱を実物で確認した。旧 `flac-mac` の SDK 警告は残るため M9 で対処する。実 FLAC 導入、encoder 不在時の録音中の失敗表示、実マイクでの許可・拒否と字幕生成は未確認。
- M7 の先行調査と局所修正: Application Support 内の録画・編集済み `.mkv` / `.mp4` は一覧 API から WebView の `<video>` へ直接渡される。配信 API の誤った `video/mp4` 固定を改め、`.mkv` は `video/x-matroska`、`.mp4` は `video/mp4` とした。録画・編集済みの両配信について Content-Type、本文、Range、ダウンロードヘッダーの contract テストを追加し、対象 30 件成功・2 件 skip。ユーザー希望に従って直接再生を先に実測した。macOS 27.0 arm64 / pywebview 6.0 の WKWebView と localhost の Range 配信で、OpenCV 生成の 4 秒 H.264 入り MKV は `error.code=4`、metadata 未読込で再生・シーク不可だった。同じ映像形式の MP4 は metadata 読込、再生、2 秒へのシークが成功した。親エージェントも別の非表示 WKWebView で `canPlayType` が Matroska 空文字、H.264 MP4 `probably` と独立確認した。これはテスト用ファイルの結果であり、LFS 404 で取得できない現行実録画の全ファイルへ一般化しない。元録画を維持する再生方式と容量・待ち時間の判断はユーザー回答待ち。YouTube OAuth は macOS の Keychain に token を保存する経路へ接続済みだが、実アカウント認証・アップロードは未確認。loopback 認証は port 8080 固定で、競合時の失敗可能性がある。FFmpeg/Tesseract は frozen 起動時に Apple Silicon Homebrew の PATH を足す実装だが、実導入・編集・サムネイル生成は未確認。`ikamodoki1.ttf` は利用者配置の対象。
- M7 のユーザー提供実録画による検証: ユーザーは `~/Movies/2026-09-27 22-05-23.mkv` を動作テストに使用することを許可した。元ファイルは変更せず一時コピーで検査し、Matroska / H.264 / AAC、1920×1080、60 fps、約 6.1 秒と確認した。現在の `create_file_serving_router` と同じ `video/x-matroska`、`Content-Disposition: attachment`、Range 応答で Cocoa/WKWebView に配信すると、全データ取得後も `MediaError.code=4`、`readyState=0`、metadata 未読込で再生・シーク不可だった。`Content-Disposition` を外す、MIME を旧 `video/mp4` に戻す、両方を変える比較でも同じエラーだった。したがって、この実録画は HTTP ヘッダー修正だけではアプリ内再生できない。親エージェントが観測 JSON とプローブコードを確認し、元ファイルの前後 SHA-256 一致、一時物削除を確認した。再生用 MP4 を必要時に作る案と新規録画を Hybrid MP4 にする案のメリット・デメリットをユーザーへ説明した。
- M7 の確定方針: ユーザーは「MKV 録画は維持し、再生時に MP4 を一時生成する」を選択した。元 MKV は正本として保持し、録画形式は変更しない。再生用 MP4 の生成完了前は公開せず、失敗時は元ファイルを保全する。録画済みの再生・字幕編集と編集済み MKV の再生を実装した。実録画からの MP4 変換、配信経路での再生・シークは確認済み（M7 の一時 MP4 検証を参照）。長時間録画や複数動画での待ち時間・追加容量、編集・字幕・アップロードの実アプリ縦断は未確認。判断の原文と比較は ADR `20260927-224022` に記録した。
- M7 の一時 MP4 実装: macOS の録画済み・編集済み MKV は再生・字幕編集時に FFmpeg で一時 MP4 にし、既存 MP4 と Windows の MKV は直接配信する。同時要求は生成を共有し、元動画が更新されたら作り直す。H.264 でも `yuv420p` 以外は再エンコードする。完成前のファイルを公開せず、失敗時は部分ファイルを、アプリ終了時は完成済み MP4 を削除する。UI は準備中・失敗・再試行を表示する。
- M7 の一時 MP4 検証: backend logic/contract 43 件成功・2 件 skip、frontend 対象 35 件成功、型・Svelte・Lint・format・import-lint が成功した。arm64 `.app` を再ビルドし、bundle ID と同梱ファイルを確認した。Homebrew FFmpeg 9.0.2 で実録画から 1.288 秒、1,760,824 byte の H.264/AAC・yuv420p MP4 を生成し、元 MKV の SHA-256 一致を確認した。同じ配信 API と非表示 WKWebView で `readyState=4`、エラーなし、再生と約 2 秒へのシークに成功した。合成 yuv444p 入力からの yuv420p 再エンコードも成功し、検証用の一時物は削除済み。
- M7 の残る検証: 配布 `.app` の画面全体、複数の大容量動画を開いたときの一時容量、編集・字幕・アップロードの縦断確認は未完了。
- M7 の実編集調査: Luna サブエージェントがユーザー提供 MKV の一時コピーと検証用 SRT・試合 metadata を使い、`AutoEditor._edit()` の結合、字幕 sidecar、サムネイル sidecar、MKV 内 PNG stream、動画 metadata の生成を確認した。親エージェントは `_edit()` の責務、元 MKV の SHA-256 一致、検証用一時領域の削除を確認した。当時は描画時だけ Mac の CJK フォントを注入しており、指定 `ikamodoki1.ttf` は Application Support とリポジトリの両方に存在せず、標準設定のサムネイル生成は `OSError: cannot open resource` で失敗した。[作者公式ページ](https://aramugi.com/?page_id=807)は同フォントの公開終了と現在の配布物が無許可の二次配布である旨を掲示する。その後、ユーザー指定に従い OS 標準フォントへの切替を実装し、上記の M7 フォント確認で実サムネイル生成に成功した。実録画由来の字幕・試合 metadata、TTS、OCR、複数クリップ編集、実アプリの編集画面は未確認。
- M7 の YouTube 経路: Luna サブエージェントが `UploadPort` から `YouTubeClient`、macOS Keychain の認証情報ロード・保存、認証更新、動画・サムネイル・字幕の API 呼び出しを確認した。親エージェントも Keychain/YouTube の既存 logic テスト 26 件成功と差分を再確認した。実アカウント、OAuth クライアント設定、Keychain の実 ACL/許可プロンプト、YouTube への実送信は未確認であり、外部送信は行っていない。
- M3/M7 の OCR 実行確認: 合意済み Homebrew の formula `tesseract` と `tesseract-lang` を Apple Silicon ホストに導入した。Tesseract 5.5.3 で `jpn` と `jpn_vert` が列挙され、アプリの `TesseractChecker.check()` は導入済みと判定した。日本語「ガチエリア」を画像化した一時入力は `-l jpn` で同じ文字列として認識し、一時画像は削除済み。実ゲーム画面の OCR 精度とアプリ内導入ボタンの UI 操作は未確認。
- M6 の FLAC 実行確認: 合意済み Homebrew の formula `flac` 1.5.0 を Apple Silicon ホストに導入した。アプリの `FLACChecker.check()` は導入済みと判定し、`SpeechRecognition.AudioData.get_flac_data()` は合成 16 kHz 音声から FLAC データを生成した。実マイク収音、Google 音声認識への送信、アプリ内導入ボタンの UI 操作は未確認。
- M4 の再調査と実装: macOS の旧経路はデバイス列挙を空にし、接続確認を常に `True` としていた。このホストの FFmpeg AVFoundation 一覧と `system_profiler SPCameraDataType` はともに映像機器 0 件。ユーザーは同名機器があっても既存の表示名方式で継続すると決めたため、設定・API の識別子は変更しない。同名の物理機器の区別は行わず、選択名が一つでも列挙されれば接続と判定する。FFmpeg AVFoundation の映像欄を解析し、画面入力・音声欄を除外する。機器未検出・FFmpeg 不在・タイムアウト・一覧不備・明示的な権限拒否は未接続とする。録画ループはフレームが届く間も切断検査し、切断後のフレームを処理しない。画面は録画状態の切断通知を受けて再接続確認を再開する。親エージェントが backend 対象 23 件、frontend component 8 件を再実行し成功。実機で FFmpeg 9.0.2 の列挙は映像機器 0 件、checker と frozen `.app` の `/api/device/status` は `False` だった。AVFoundation の一覧だけでは TCC カメラ許可を確実に検査できない。実機の抜き差しとカメラ権限拒否は未検証。
- M7 のフォント確定方針と実装: ユーザーは `ikamodoki1.ttf` をオプションとし、見つからない場合は OS 標準フォントを使うと決めた。カスタムフォントは利用者配置のまま配布物へ同梱せず、初回セットアップでは未配置をブロック条件にしない。作者公式ページでは公開終了と無許可の二次配布が案内されているため、既存の Wayback 取得案内を撤去した。サムネイル生成とセットアップ判定は同じフォント解決器を使う。親エージェントは指定フォントがないこの Mac で `/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc` への切替と、実 `ThumbnailGenerator` による 1920×1080 PNG の生成（224,044 byte）を独立確認した。Windows の標準フォントでの実描画、従来フォントとの見た目の同一性は未確認。
- M4/M7 の配布物確認: frontend を再ビルドして arm64 `.app` を作り直し、bundle ID、資産、最新 frontend の一致、`ikamodoki1.ttf` 非同梱を確認した。隔離した設定領域で frozen `.app` の backend を起動し、`/api/health` は 200、`/setup/system/check/font` は Hiragino W3 を導入済みと返し、`/api/device/status` は未接続と返した。起動テストのプロセスと一時設定領域は削除済み。PyInstaller が同梱候補の `speech_recognition/flac-mac` に古い SDK 警告を出す問題は M9 に残る。
- M8 の着手調査: 通知 API は非 Windows で `skipped` を返していたが、frontend は HTTP 成功だけを記録していた。これを API の `status: success` まで確認するよう修正し、8 件の logic テストに成功した。既存 Windows スリープ処理は `rundll32.exe` の異常終了を見落としていたため、非ゼロ終了・起動失敗を呼び出し元へ伝えるよう修正した。LAN は既存の任意設定で全インターフェースへ bind できる一方、設定画面には Windows Firewall と PowerShell の手順が表示されていた。候補 IPv4 はこのホストで 2 件検出したが、別端末からの到達は未検証。設計助言役は利用上限で失敗し、ユーザーが通知は Splat Replay 名義、macOS スリープは `pmset` で Windows 同様に画面通知なし、LAN はシステム設定の案内と決めた。
- M8 の実装・対象検証: macOS は UserNotifications を bundle ID と表示名 `Splat Replay` の `.app` から呼び、許可拒否を 403、登録失敗・callback タイムアウトを 503 として返す。frontend は `status: success` のときだけ送信成功と扱う。処理後スリープは macOS で `pmset sleepnow` を実行し、異常終了を呼び出し元へ伝える。LAN 設定画面は macOS のファイアウォールとローカルネットワークのシステム設定を案内し、候補 URL を別端末で開いて接続を確認するよう表示する。親エージェントは通知 contract・adapter と電源 adapter の対象 20 件、LAN component 25 件、型・lint・format・依存方向を確認した。実 `pmset` によるスリープと別端末からの LAN 接続は未実施。
- M8 の frozen 実機調査: arm64 `.app` の bundle identity、資産、ad hoc 署名と `/api/health` の 200 応答を確認した。Launch Services 経由の通知 API は許可なしの状態で即時に 403 を返し、成功と誤表示しなかった。実際の通知表示は未確認。直接実行した `.app` では UserNotifications callback が返らず要求が停止したため、各 callback に上限時間を設けた。この修正を含む arm64 `.app` を再ビルドし、bundle identity、署名、`/api/health` の 200、通知 API の 403 応答を再確認した。Mac がロックされていたため通知設定の UI 確認は保留し、利用者に手動解除を依頼した。
- M9 の事前調査と確定方針: 設計助言役は Developer ID の保有・費用負担と未公証時の手動起動許可、zip / dmg の配布体験について有効な既存指針がなく、ユーザー判断が必要とした。ユーザーは「ad hoc 署名で配布し手動許可を案内する」「dmg（Finder で導入先を示しやすい）」と決めた。現在の `.app` は ad hoc 署名であり、GitHub から取得した dmg の初回起動は未検証。`speech_recognition/flac-mac` の古い SDK 警告は Apple Silicon では使わない同梱バイナリに由来する可能性があり、実物と spec の除外方法を調査中。通知・マイクの実機受け入れ、更新時の保存済みデータ維持は未確認。
- M9 の実装・検証: macOS の PyInstaller `Analysis` 後に Intel 専用 `speech_recognition/flac-mac` を配布対象から外した。完成した `.app` と dmg 内の `.app` の両方に同ファイルがないことを確認した。PyInstaller は収集時に古い SDK 警告を出すが、完成物には残らず `codesign --verify --deep --strict` は成功した。Taskfile に dmg 作成とマウント検証を追加し、Windows の zip 経路は維持した。`task` コマンドがこのホストの PATH にないため、Taskfile の YAML を解析して該当シェルコマンドを実行した。141 MB の `dist/SplatReplay.dmg` を生成し、チェックサム検査、マウント、Applications リンク、arm64、bundle ID、ad hoc 署名を確認した。完成 `.app` の Launch Services 起動と `/api/health` の 200 応答も確認した。`spctl --assess --type execute` は `rejected` を返し、手動許可を前提とする方針と整合する。macOS の初回手動許可と Application Support 内の画像差し替え先を利用者ガイドに追加した。GitHub からダウンロードした dmg の Gatekeeper での手動許可の成立、配布物からの全機能導線、実マイク・通知は未確認。
- 2026-09-29 の M8 通知実機確認: 利用者のロック解除後、システム設定の「Splat Replay」通知がオフと分かり、オンに変更した。配布 `.app` の通知 API に試験通知を 1 件送り、HTTP 200 と `status: success` を確認した。macOS に登録されたことまでの確認で、通知バナーまたは通知センターの表示は利用者確認待ち。マイク権限は試験前に OBS のみ、初回キャリブレーション後に SplatReplay がオンで追加された。ローカルネットワークにも SplatReplay がオンで追加された。
- 2026-09-29 の M4〜M6 実機調査: 利用者が MiraBox Capture と BOYA mini を接続した。OBS 32.2.2 の MiraBox ソースに Switch 映像が表示され、画面上は 60.00 FPS。親エージェントが frozen `.app` の GET API で動画機器 `MiraBox Capture` / `OBS Virtual Camera`、音声機器 `MiraBox Capture` / `BOYA mini`、NDI checker の `is_installed: true`、選択機器の status `false` を再確認した。Luna サブエージェントは USB 接続を確認し、Terminal/venv の AVFoundation・PortAudio 列挙は空と報告した。初回の BOYA mini キャリブレーションはマイク権限取得前の 15 秒上限で 504、許可後は 5 秒ウォームアップと 3 秒測定を HTTP 200 で完了し 141 サンプルを読んだ。RMS は全サンプル 0 で、利用者は今回は無音のまま進めると判断したため実音声は未確認。
- 2026-09-29 の OBS 入力方式判断: OBS には MiraBox 映像があるが、アプリの自動判定用 LIVE 入力は `AdaptiveCapture → NDICapture` 固定であり、OBS Virtual Camera の列挙は代替入力にならない。OBS のツールメニューに DistroAV/NDI はなく、プラグインマネージャーの導入済み一覧も空だった。現行 NDI checker は Finder 初期化だけで送信元や映像受信を検査しない。設計助言役が DistroAV＋NDI Runtime と OBS Virtual Camera 用 backend adapter を比較し、ユーザーは「DistroAV＋NDI Runtime を導入（現行実装に接続できる・推奨）」を選んだ。導入方法とセットアップの判定・案内を調査中で、実 NDI 映像の受信は未確認。
- 2026-09-29 の NDI 導入手順判断・実装・実機確認: ユーザーは DistroAV と NDI Runtime を公式 pkg から利用者が手動導入し、製品版 macOS も同じ方式にする方針を選んだ。DistroAV 公式は 6.2.1 に NDI Runtime 6.3 以降を要求し、NDI の macOS ランタイムライブラリ標準位置を `/usr/local/lib` と案内している。checker はこの system library の `NDIlib_version()` が 6.3 以上を返した場合だけ完了にし、アプリ同梱 cyndilib の NDI library だけでは完了にしない。セットアップ画面に DistroAV Releases、NDI Runtime for macOS の HTTPS URL、OBS 再起動、`Main Output` 有効化、Runtime 再検査を記載した。Windows の既存 Runtime 判定と exe 手順は維持した。親エージェントが公式 DistroAV 6.2.1 pkg の SHA-256 が Release checksum と一致することと公証、NDI Runtime 6.3.2 pkg の公証を確認して導入した。OBS を再起動後、「DistroAV NDI Settings」で DistroAV と NDI Runtime の両方が OK、`Main Output` の `OBS PGM` が有効なことを確認した。mDNS に `SHOUGONOMAC-MINI.LOCAL (OBS PGM)` が登録され、`NDICapture.setup()` がこの送信元へ接続し 1920×1080 BGR frame を取得した。保存した一時画像で Switch のホーム画面を目視確認した。実機入力までの成立性は確認したが、自動録画から編集・アップロードまでの通し、長時間受信・切断復帰は未確認。NDI Runtime が標準パスにない場合、バージョン API をロードできない場合、またはバージョンを解析できない場合は準備完了にしない。
- 2026-09-29 の Dock アイコン修正: macOS 27 で従来の角が透明な画像は白い台座の中に縮小表示された。既存絵柄の不透明画素を変えず、四隅の透明な 2,933 画素だけを不透明な暗背景にした。再ビルドした arm64 `.app` は Finder で角丸四角いっぱいに表示され、Launch Services からセットアップ画面まで起動した。`.app` と再生成した dmg の ad hoc 署名、dmg の整合性とマウントを確認した。Dock 自体の画面取得は環境側の操作ツールがタイムアウトしたため未確認。
- 2026-09-30 のセットアップ後クラッシュ修正: 利用者のクラッシュ報告は TCC による `NSCameraUsageDescription` 欠落の SIGABRT と明記していた。録画画面の `getUserMedia` は選択した映像入力機器のプレビューでカメラ権限を要求するため、macOS 配布 spec の `Info.plist` に用途説明を追加した。再ビルドした arm64 `.app` の plist と ad hoc 署名を検証し、利用者のカメラ許可後に録画画面が表示され、同クラッシュが再発しないことを確認した。
- 2026-09-30 の録画導線の初期状態: OBS WebSocket 5.7.4 は `server_enabled=false`、認証あり、ポート 4455。Splat Replay は `localhost:4455` に接続できず、ログ上は接続拒否と再試行が続いた。`StartVirtualCam` は接続成功後に実行されるため、当時は OBS Virtual Camera とアプリのプレビューを起動できなかった。公式実装で localhost のみへの待受設定は確認できず、有効化すると認証付きでも LAN に待ち受ける可能性があった。その後、ユーザーが OBS WebSocket の有効化を指示した。

- 2026-09-30 の OBS WebSocket・録画確認: OBS 32.2.2 の obs-websocket 5.7.4 を認証必須のまま有効化し、4455 待受と再ビルド後アプリの接続成功を確認した。設定の認証情報はログへ出さず、検証後も WebSocket を有効のままにした。OBS の DistroAV NDI Main Output 起動、macOS の OBS Virtual Camera 列挙、アプリの live-capture preview-frame 200（JPEG 1920×1080）を確認した。短い手動録画は start/stop とも 200、6.016 秒の MKV（H.264 1920×1080 / AAC）は ffprobe と全体デコードに成功した。前回の失敗試行ファイルも 4.917 秒の MKV として全体デコード後、今回の試験生成物と特定して削除した。録画一覧は試験前後とも 0 件で、今回作成した1件だけを削除した。preview の平均 RGB は約 7 でほぼ黒く、現在の Switch 映像が入った状態は未確認。停止時の原因は手動開始・OBS 外部開始で `metadata.started_at` が未設定だったこと。共通開始と外部開始の両方で既存時刻を保ちつつ不足時だけ補完し、対象 logic 13 件、Ruff、ty が成功した。修正版 arm64 `.app` の Bundle ID・カメラ利用説明・ad hoc 署名を確認し、同じ実行ファイルを含む DMG を再生成して checksum、マウント、Applications リンク、arm64、署名を検証した。
- 2026-09-30 の実録画での修正と配布候補: OBS とアプリを同時撮影した画像から、アプリのプレビューで右端・下端が切れることを確認した。録画結果画像の OCR がスペシャル回数 1 を 7 と誤読する事例を修正し、対象ケース 5 件が通った。既存の該当録画は編集・アップロード前に元 MKV・画像・メタデータ・履歴をローカルに退避して SHA-256 を照合し、アプリ API で `special` だけを 1 に訂正した。その後の自動編集と YouTube アップロード完了により元録画は削除されたが、退避と訂正済み履歴は残っている。サムネイル拡大表示、LAN 設定の未保存案内、macOS WebView のカメラ許可 delegate と仮想カメラの 16:9 希望値を実装し、対象 logic / component と静的検証が通った。arm64 `.app` と DMG を再生成して構造・署名を確認した。画角と毎起動の許可要求が実映像で解消したか、利用者が Switch を再度起動した後に確認する。

## 2026-10-01 の起動クラッシュ修正

- 原因: 前回追加したカメラ許可 delegate で、親 `BrowserDelegate` が持つ `WKUIDelegate` を子クラスで再宣言していた。実際の WebKit カメラ要求で decision handler の block 署名が欠落し、`TypeError: cannot call block without a signature` が Objective-C 境界へ漏れて SIGABRT になった。親エージェントが元コードで再現し、再宣言だけを除いたコードで終了コード 0 と映像 640×360・readyState 4 を確認した。
- 対応: Luna（xhigh）に目的・所有ファイル・完了条件を渡して修正を委譲した。プロトコル再宣言と不要になった objc import・型宣言を削除し、親の実装を継承する。自身の origin・main frame・camera のみを自動許可する条件は維持する。親エージェントが変更差分と実動作を確認した。
- 参照した方針: `docs/test_strategy.md`。
- 変更分類: backend `logic` / `static`、macOS native 起動導線の実機確認。
- 保証対象: プロトコル継承、許可範囲、実カメラ要求の完了、配布アプリの起動・終了・再起動。
- 新規テスト判断: 既存 delegate テストを更新し、親のプロトコルを継承して再宣言しないことと、実定数 Camera=0 による許可・非許可を確認した。
- テスト実行判断・実行した入口: repo 管理ラッパー `python ../scripts/run-backend-pytest.py -q tests/logic/interface/test_webview_app.py` で 17 件成功。対象 2 ファイルの Ruff check / format check、ty check と `git diff --check` が成功した。サブエージェントの結果に加え親エージェントも同じ対象を再実行した。
- 実機確認: 再生成した arm64 `.app` を 2 回起動し、どちらもカメラ許可ダイアログなしでメイン画面まで到達した。実カメラ許可完了ログ、起動後のプロセス生存、`/api/health` HTTP 200、録画 STOPPED を確認した。1 回目は macOS が以前のクラッシュに伴うウィンドウ復元確認を表示し、「復元しない」で起動した。正常終了後の 2 回目には同確認も表示されなかった。
- 配布候補: `.app` と同じ実行ファイルを含む DMG を再生成した。checksum、読み取り専用マウント、Applications リンク、bundle ID、arm64、ad hoc 署名を確認した。DMG SHA-256: `915b91765a8c016f0b1fadb8a3dc8abdd346e22966a25f6594edcc089a3d576c`。
- 省略した入口と理由: frontend component / integration / workflow runner、全体 verify・release は、今回 frontend・API・ビルド設定を変更せず、原因を GUI delegate に絞れているため追加実行しない。ネイティブ境界は上記の実機起動とカメラ取得で確認した。
- 未確認事項・追加で必要な確認: Switch は電源 OFF のため、実ゲーム映像の画角と滑らかさは未確認。Switch 起動後の表示確認と、macOS 対応全体の残る最終確認を継続する。

## 2026-10-01 のプレビュー画質・XP 欠落の原因分析

- 利用者確認: プレビューの画角は修正済み。ただし Windows 使用時に比べ不鮮明との報告を受けた。
- プレビューの確定原因: `VideoPreview.svelte` は `aspectRatio: { ideal: 16 / 9 }` と機器 ID を指定し、width / height を指定していない。親エージェントが同じ WKWebView で実測した現在の映像トラックは 640×360・30 FPS。OBS Virtual Camera に width=1920 / height=1080 の希望値を追加した診断では 1920×1080・60 FPS で取得でき、capabilities の上限も 1920×1080・60 FPS だった。低解像度の映像を大きい表示枠へ拡大することが不鮮明さにつながっている。退避した 21:44 の録画本体は ffprobe で 1920×1080・60 FPS と確認した。
- プレビューの対応候補: 16:9 と選択機器を保ち、width / height に 1920×1080 の `ideal` を指定する。現在の機器で取得可能なことまで確認したが、この分析では製品コードを変更していない。Windows の現在の実解像度は未測定。[W3C 仕様](https://www.w3.org/TR/mediacapture-streams/#constrainable-properties)では未指定の特性の設定は実装が選択する。[pywebview の公式資料](https://pywebview.flowrl.com/guide/web_engine.html)では macOS は WKWebView、Windows は Edge Chromium が優先される。
- XP 欠落の確定経路: 昨夜 23:08 にアップロードされた動画の元録画 15 件を編集ログで特定した。その 15 件の履歴はすべて `rate: null`。サムネイル生成は有効なレートを集め、0 件なら `rate=None` として XP テキストを描かない。対象時間帯の「レート候補を記録」ログも 0 件だった。動画とサムネイル双方のアップロード完了ログを確認した。
- XP 欠落の未確定箇所: XP は待機中の X マッチ選択画面から取得するが、当時の認識用 ROI と OCR 結果は残っていない。専用診断出力も見つからない。退避した結果画像・確認した録画フレーム、Movies に残る 21:43 の短い動画フレームはいずれも XP 取得対象の画面ではなかった。画面未検出・OCR 失敗・形式検証による棄却のどれかは断定できず、利用者に XP が表示される X マッチ選択画面の再現を依頼した。
- 委譲と確認: Luna（xhigh）2 名に、プレビューのコード・外部契約調査と XP の認識→メタデータ→描画経路調査を完了条件付きで分担した。親エージェントが実トラック設定、元録画仕様、対象履歴、編集・アップロードログ、描画条件と実 OCR を確認した。
- 参照した方針・変更分類・保証対象: `docs/test_strategy.md`、`logic` の診断。macOS 実 OCR の既存 XP 素材での基本動作を確認する。
- 新規テスト判断・実行した入口: 分析のみのため新規テストは追加しない。Tesseract 5.5.3 が実際に動作することを確認後、repo 管理ラッパー `python ../scripts/run-backend-pytest.py -q tests/logic/domain/test_frame_analyzer.py -k test_extract_rate` を実行し、5 件成功・103 件対象外。ダミー OCR による成功ではない。
- 省略した入口と理由: 製品コード・UI・API を変更していないため frontend component / integration / workflow、全体 verify・release は追加実行しない。既存素材での成功は、昨夜の入力で認識できた証拠にはならない。
- 追加で必要な確認: XP を表示した X マッチ選択画面の実フレームを取得し、画面判定、数字 OCR、検証結果を個別に観測する。分析用に一時領域へ書き出した動画フレームは確認後に削除した。動画・履歴・YouTube は変更していない。

## 2026-10-01 の1080pプレビュー・実画像XP認識の対応

- 目的・成功条件・責務: 共通 frontend の仮想カメラ取得で1920×1080・60 FPSを希望する。XPは既存の設定とdomain認識経路で、画面検出→モード→マッチ→数値取得が1985.1へ到達することを守る。画像認識設定の保存・更新は infrastructure の既存DI設定読込に置く。
- ユーザー判断: 当初の1920×1080・30 FPS希望に続き、「1080pがいいので、60FPSでいいです」と確定。width / height / frameRate は ideal とし、既存の機器指定・再試行・汎用制約へのフォールバックを保持した。希望値は共通コンポーネントに適用されるが、Windowsの実トラックと負荷は未確認。
- 実測: 30 FPS上限とHD希望値の組合せは一試行で取得失敗した。その後 ideal:30 と ideal:60 では両方1920×1080を取得した。各8秒の一組の観測で、30時 WebKit 12.63% / OBS 33.83%、60時13.23% /34.25%（1コア100%換算）、表示約29.96 /58.30 FPS。小さい差を観測したが、録画・解析中や別機器の負荷保証ではない。
- 配布アプリの確認: frontendをビルドし、arm64 .appを再生成した。同アプリから配信されるfrontendを実 WKWebViewで開き、トラック1920×1080・60 FPS、表示寸法1920×1080、readyState=4を確認した。health HTTP200、ad hoc署名、カメラ用途説明、同梱frontend資産も確認した。
- XP入力の保存: 解析前にAPIから明るいXマッチ選択画面のJPEGを保存した。ガチヤグラ、XP1985.1を目視確認した。後続NDI PNGは暗転後の画面で、利用者がSwitch放置による暗転と確認した。JPEGとPNGは取得時刻・状態が違い、恒常的なNDI画質差とは扱わない。診断素材はGit対象外の `backend/outputs/macos-diagnostics/20261001-xp1985/` に保持し、明るいJPEGを無変換で回帰fixture `rate_XP1985.1_mac.jpg` に追加した。
- XPの再現原因: 明るい画像は画面検出true、単独OCR1985.1・連結成分6・検証エラーなし。一方XマッチのHSV判定ROIでV=221〜230となり、既定下限230・90%一致条件では1.75%しか一致せず、mode/matchがNoneだった。既存素材は同ROI V=253でこの問題が表面化しない。H/S・ROI・一致率を維持しV下限だけ220へ補正した。同画像でBATTLE / X / XP1985.1を取得し、既存6選択・5レート素材の結果を保持、比較した非選択3画像でX誤判定0件を確認した。昨日の実行時の輝度は残っていないため、昨日も同じ失敗条件だったかは未確定。
- 設定更新の方針: macOS配布版は初回コピーの保存設定を読むため、同梱yaml修正だけでは既存環境へ反映されない。全旧版hash一覧の維持を避け、アプリ起動時に保存設定と前回導入した既定設定のbaselineを全バイト比較する。未変更なら新版へ原子的に更新し、編集済み・比較元なしの旧設定は保持する。current更新成功後baseline更新とし、baseline失敗後の同版再起動はcurrent==bundleで回復する。失敗後さらに別版へ進んだ場合は保守的に更新を止める。今回Macは旧設定が修正前Git HEADと全バイト一致することを親が再確認し、比較元 `image_matching.yaml.baseline` だけを個別保存した。恒久処理が未確認の旧設定を既定と認定することはない。
- 委譲・確認: Luna（xhigh）にfrontend、実画像XPの原因調査・補正、設定更新を目的・所有範囲・完了条件付きで委譲した。親が差分、元画像とのSHA256一致、実トラックと最小対象テストを確認した。設計助言・記録は専用役へ委譲した。
- 参照した方針・変更分類: `docs/test_strategy.md`、frontend component / backend logic / static、実WebViewのworkflow確認、観測のみの負荷比較。
- 新規テスト判断・実行した入口: frontend既存componentの取得条件を更新し、再試行後の汎用制約でもHD60希望が維持されるケースを追加。親による対象component再実行5件成功。XPの既存rateテストを通常の認識順序へ更新し、実画像ケースを追加。Luna対象25件成功、親のmode/match/rate対象19件成功（90件対象外）、実Tesseract5.5.3を使用。対象ruff/ty、frontend型・Svelte検証・対象eslint/prettierとdiff checkが成功した。
- 省略した入口と理由: frontend integration / workflow runnerは複数画面のstateやAPIを変えず、取得のnative境界を実WebViewで確認するため追加しない。全体verify・releaseはこの局所修正の保証に追加しない。ビルドには既存の混在import警告と収集途中の旧flac-mac SDK警告があるが、最終bundleには旧flac-macは同梱されていない。
- 設定更新の検証結果: Lunaの対象runtime-pathテスト18件とruff/format/tyが成功し、親も対象18件を再実行した。連続更新、コメントを含む編集済みの保持、比較元のない旧設定、明示path・Windows・開発実行、無効bundle、置換失敗、baseline保存失敗からの復旧、置換直前の編集検知を確認した。親がコード・テストの条件と失敗順序をレビューした。
- 最終配布候補・実機移行: 再ビルドしたアプリを起動し、health HTTP200とメイン画面の継続表示を確認した。保存設定・baseline・同梱yamlが全バイトで新版へ一致し、X判定下限 `[80,230,220]`、設定更新の一時ファイル0件を確認した。旧SHA256 `fa7104454b88427331dbf80fbc112116cdd0db872d9bd8ea2ed3874d16440dcd` から新版 `cfd616f1c6b71094df2784e942561d679a7775a5be44d8e9a61e8070646c0d6c` への変化は、このMacの個別確認値であり、製品が維持する旧版一覧ではない。DMGを再生成し、checksum、読み取り専用マウント、実行ファイルと設定の同一性、Applicationsリンク、arm64、ad hoc署名を確認した。DMG SHA256 `a7d430ae478070e76d62db21625147dfc5c81cdda9edc4a9ad5aa9394a849c0c`。
- 未確認事項・追加で必要な確認: 最終起動時はSwitch電源OFF。次の実ゲーム録画でのXP候補→保存メタデータ→サムネ表示は利用者による最終確認に残る。昨日の原因を今回の実画像だけで断定しない。baselineなしの未知の既存設定は保護され、今回修正が自動反映されるとは保証しない。今回作成した一時診断領域とビルドログは、必要な素材と結果をGit対象外の診断保存先へ移して撤去した。

## 2026-10-01 の OBS 音声誤判定・再起動の調査

- 目的・成功条件: OBS にキャプチャ音声があるときは正常と判定し、誤った無音判定で OBS を再起動しない。ユーザーが維持を選んだ音声復旧の自動再起動と、実録画中の再起動禁止は守る。正常な再起動後には音声・WebSocket・プレビューを復元する。現時点では全条件の達成を確認していない。
- 責務・層: 音声入力の解決と OBS 起動は infrastructure の既存 adapter、macOS Quit の変換は interface の既存 WebView が担当する。アプリ側の二回連続 `silent` 確認・復旧オーケストレーションは変更しない。設定スキーマ・依存追加は行わない。
- 最初の誤判定の実機証拠: 映像入力 `MiraBox` のメーターは約3秒間57件すべて空だった。一方、同じ機器を選ぶ別の CoreAudio 入力「音声入力キャプチャ」は2チャンネルの非ゼロ値を返していた。アプリは映像入力を先に解決し、空メーターを無音と分類していた。
- 音声入力の補正: OBS の `GetInputPropertiesListPropertyItems` による表示名と選択 UID の完全一致で、一意な CoreAudio 入力を選ぶ。UID の内部形式は推測しない。既定マイク・別機器は使わず、複数一致・取得失敗・映像入力しかない場合は `unknown` として再起動しない。対象確定後の空メーターの既存 `silent` 契約は維持する。追補 ADR: `20261001-222419`。
- 委譲・親確認: Luna（xhigh）へ所有ファイル・完了条件付きで委譲した。親が差分と対象31件を再実行し、実 OBS の読み取り専用検査で `MiraBox Capture → 音声入力キャプチャ → ok / healthy=true` を確認した。修正版を隔離ビルドし、arm64・署名・bundle identity・DMG内の同一性を検査した。
- 再検証で残った問題: 22:26 の再起動検査では、正しく選ばれた音声入力でも二回連続 `silent` となった。当時のログに数値がないため、空レベルと有効なゼロ値を区別できず、根本原因は未確認。イベント数・有効な数値を持つサンプル数・最大値だけを構造化ログに追加した。音声や生配列・認証情報は保存しない。
- 終了経路の補正: Cmd+Q による終了後に旧 backend が残り、8000番で待ち受けていた。赤い閉じるボタンでは正常終了と全プロセス解放を確認した。macOS の Quit を既存 window close と `finally` の後処理へ接続する補正を実装し、親が許可・拒否・空ウィンドウの3ケースと実 Cocoa の署名継承を確認した。実アプリの Quit メニュー・Cmd+Q の最終確認はロック解除後に残る。
- OBS 再起動の追加調査: 正常だった既存 OBS は音声アクセス `granted`、アプリが実行ファイルを直接起動した OBS は `denied` と記録した。再起動後には CoreAudio の機器応答待ちとバッファ取得失敗が発生した。TCC の起動元帰属が変わるという説明は仮説で、USB状態・権限状態との切り分けは未完了。Luna（xhigh）が、実行ファイルと一致する標準 `.app` を `NSWorkspace` で起動する補正を実装し、親が差分を確認した。callback の PID・実行パス・開始時刻を検証し、既存 PID は新規所有せず、失敗・タイムアウト後の直接実行 fallback はしない。権限を自動変更せず、起動由来・非録画条件の安全策を保持する。追補 ADR: `20261001-231244`。
- 検証方針: `docs/test_strategy.md`、変更分類 `logic / static` とネイティブ境界の実機確認。入力解決・復旧の回帰、native 起動の成功・失敗・タイムアウト・遅延 callback・別exe・既存PID拒否、Quit の許可・拒否・空ウィンドウを既存テストで追加・更新した。親が repo 管理ラッパー `scripts/run-backend-pytest.py` で OBS lifecycle・audio health・application recovery・WebView の4対象を再実行し、81件が成功した。ruff check / format・対象 ty・diff check が成功した。実 AppKit の設定 setters/getters と completion block metadata も、OBS を起動せず確認した。frontend は変更しておらず component / integration の追加は不要。全体 verify / release は公開リリースではなく局所修正の候補作成のため追加しない。
- 最新の読み取り専用確認: 直接起動した OBS は23:03に CoreAudio の初期化を完了し、23:09の WebSocket は準備完了・録画なしだった。23:10の対象「音声入力キャプチャ」は1秒間17件の有効な数値、最大 `peakMul=0.0000658021` を返し、既存閾値 `0.001` 未満のため `silent` と判定した。この時点で実際にゲーム音声があるかは未確認であり、22:26の数値未保存の判定と同じ原因とは断定しない。
- 配布候補: 入力解決・音声メーターの判定根拠ログ・正常 Quit・標準 OBS 起動を含む `dist/SplatReplay.app` と `dist/SplatReplay.dmg` を再生成した。親が arm64、bundle ID、カメラ・マイク説明キー、ad hoc 署名、DMG checksum、読み取り専用マウント、アプリ実行ファイルの同一性、Applications リンクを確認した。DMG SHA256 `bc4324df53551148c00e873a11e36afe5e567e4f66b1b2a024d7109cf8eab583`。最終候補は未起動であり、実機動作を保証する値ではない。
- 現在の実機確認待ち: Mac のロック解除と MiraBox の USB 差し直しをユーザーへ依頼した。アプリは停止済み。現在は OBS の初期化完了を確認できたが、権限画面、修正した標準起動経路での再起動後の許可・CoreAudio初期化・WebSocket準備・音声正常判定・プレビュー復元、配布アプリの Quit メニュー・Cmd+Q は未確認。最初の入力誤選択の修正だけで全問題が完了したとは扱わない。
- 一時物: 診断は Git 対象外 `backend/outputs/macos-diagnostics/20261001-obs-audio/` に保存した。今回の隔離ビルド先、ビルド work/config、旧候補の一時退避、DMG生成用領域とマウントは候補確認後に撤去した。実動画・メタデータ・設定は削除していない。

## 2026-10-02 の Switch ON 後の音声観測と無音再起動の停止

- 目的・成功条件: Switch の電源 ON を検出した時（既存の `ARMED` 遷移）に音声を確認し、`silent` の間だけマッチング開始まで継続する。音声が正常になったら観測を終了し、同じ稼働中に待機へ戻っても再開しない。直近の結果が `silent` のまま待機へ戻った場合だけ再開する。初回結果が出る前にマッチングが始まった場合は、待機復帰を新たな初回確認として扱わない。OFF / キャプチャ切断後の新しい ON 検出では初回状態をリセットする。
- 共通仕様: Windows / macOS とも、無音を理由に OBS を自動再起動しない。ユーザーの今回の明示によって、以前の「音声復旧のための自動再起動を維持する」を変更する。`unknown`、ミュート等の結果は無音と同一視せず観測を終了する。既存の入力解決・音量閾値・公開設定・音声ヘルス通知の形式は維持する。
- 責務・層: application の既存 UseCase が観測タスクと稼働期間を所有し、service / session が設定取得と既存イベントの発行を担当する。infrastructure の OBS adapter が制御接続と別のメーター接続を購読し、約1秒ごとに最大値・イベント数を集計する。集計は窓ごとにリセットし、生波形や全イベント履歴は保存しない。マッチングでは取消要求を出して処理を進め、接続終了待ちを録画開始へ持ち込まない。文字起こし準備の寿命は観測から独立させる。
- 失敗モード: 入力を一意に解決できない、イベントが届かない、OBS 接続に失敗した場合は `unknown` 等の既存結果を通知し、録画を妨げない。音量だけでは静寂と機器故障を区別できないため、実際に入力が故障していても無音録画へ進む可能性がある。
- 委譲・親確認: 設計助言は Astra、実装・最小回帰テストは Luna（xhigh）、判断記録は設計記録役へ委譲した。親エージェントが全担当コードと追加・更新テストを読み、generator の明示 close、終了 task の回収、型注釈の不足を指摘して修正を確認した。対象テストと静的検証も親が独立に再実行した。判断の原文と旧 ADR の部分変更は `20261002-075726` に記録した。
- 参照した方針・変更分類: `docs/test_strategy.md`、`logic / performance / static` と実 OBS の読み取り専用検査。ON 初回、silent 継続→正常終了、正常時の待機復帰、silent 時のマッチング→待機復帰、OFF / 切断リセット、遅い切断が録画を待たせないこと、窓の最大値リセット、入力割当変更時に古い窓を正常と判定しないこと、未着と空レベルの区別を保証対象とした。新規テストは増えた状態分岐・非同期終了の回帰に限定し、薄い委譲ごとのテストは増やさなかった。旧「silent で再起動する」期待値と専用の復旧メソッドテストは、ユーザーが廃止した契約なので削除・更新した。既存の機器解決と曖昧な候補の拒否は維持している。
- 実行した入口・結果: 親は `backend/.venv/bin/python scripts/run-backend-pytest.py -q -m 'not contract and not perf and not benchmark'` に `backend/tests/logic/application/{test_auto_recording_use_case,test_recording_audio_health_use_case}.py` と `backend/tests/logic/infrastructure/{test_recording_audio_health,test_obs_websocket_connection}.py` を指定し、46件成功・skipなし。文字起こし準備の寿命を分離したため、同じラッパーで `-m perf backend/tests/performance/test_recording_start_latency.py` を実行し、録画開始が準備を待たない既存性能テスト1件が成功した。対象コード9件・テスト5件の Ruff check / format check / ty check と `git diff --check` が成功し、import-lint の6契約も成功した。
- 省略した入口と理由: frontend・公開契約は変更しないため UI component / integration、UI workflow runner、契約全体の入口は追加しない。開始処理の待ちを下位の phase 遷移テストと上記の最小性能テストで検査した。公開リリースではなく局所修正候補の作成のため、全体 verify / release は追加しない。
- 実 OBS の親確認: 08:16:40〜43の読み取り専用検査で、`MiraBox Capture → 音声入力キャプチャ` の3窓を一つのメーター購読から取得した。判定は3窓とも `silent`。OBS ログでは制御用1接続・メーター用1接続がそれぞれ開閉し、窓ごとの再接続はなかった。close 後に残るメーター終了 task は0件。これは実際にゲーム音声が出ていることの証明ではない。検査で録画・OBS再起動は行っていない。
- 配布候補・起動終了の親確認: `dist/SplatReplay.app` を更新し、arm64、bundle ID、カメラ・マイク説明キー、ad hoc署名を確認した。更新前には OBS の録画停止とアプリの `STOPPED` を確認して Cmd+Q で終了し、親・子プロセス0件と8000番の接続不可を確認した。更新後は `/api/health` が `{"status":"ok"}`、録画 `STOPPED`、キャプチャ接続 `true`、電源監視 `waiting_for_power_on` を返し、メイン画面の POWER OFF 表示を確認した。`dist/SplatReplay.dmg` を再生成し、checksum、読み取り専用マウント、署名、アプリ実行ファイルの一致、Applicationsリンクを確認した。DMG SHA256 `9e7ae48355278021ac74b2ab9d08fd7e5a20d4c3a4433d45be0429f9c7624c93`。
- 未確認事項・追加で必要な確認: 実際の Switch ON → 無音から正常音声への変化 → マッチング開始という最終操作と、Windows 実機での同じ導線は未確認。現在のアプリは Switch ON 待機で起動中であり、ゲーム操作を伴う最終確認を利用者へ残す。長時間の接続・負荷も今回の短いプローブでは保証しない。
- 一時物: ビルド・検査ログは Git 対象外 `backend/outputs/macos-diagnostics/20261002-audio-observation/` に保存した。専用の隔離ビルド先、build work/config、旧アプリの一時退避、DMG の作成・マウント用領域、親の最終 runner の basetemp は候補確認後に撤去済み。実動画・メタデータ・設定は変更していない。

## 2026-10-02 の macOS 常駐・メニューバー状態表示

- 目的・成功条件: Windows と同等に、閉じる操作後も自動録画・後処理を継続し、OS の状態表示から画面を再表示・完全終了できるようにする。通常 close は非表示、完全終了は既存の保護対象の処理完了を待つ。ログイン自動起動や Dock への追加バッジは今回の対象ではない。
- 責務・層: interface の既存 WebView と macOS の `NSStatusItem` adapter でネイティブイベントを接続する。`DesktopSignals`、`describe_tray_status()`、制御ループ、application の `DesktopMaintenance` を再利用し、Windows IPC の有無から常駐を分離する。macOS 専用の空 IPC、公開 API・設定・依存の追加は行わない。Windows の tray module は変更していない。
- 実装: 起動・待機・録画・処理中・要確認の5状態を既存の優先順位で選び、メニューバーのアイコン・ツールチップ・日本語のメニュー説明へ反映する。「画面を開く」「完全終了（処理完了を待つ）」を追加した。Dock の再オープンは `show`、Cmd+Q・アプリメニュー終了・状態メニュー終了は共通 `quit` へ送る。AppKit の作成・更新・破棄は主スレッド、変更時だけ描画する。項目の初期化に失敗した場合は GUI 作成前の `window.hidden` を解除し、画面と終了操作を残す。
- 委譲・親確認: 設計助言は Astra、実装・最小回帰テストは Luna（xhigh）、判断記録は設計記録役へ委譲した。親が担当コード・テストを読み、macOS の `control=None`、終了時の保護待機、GUI 起動前のブロッキング `show()`、主スレッド dispatch、部分的な native item の回収を確認・修正した。設計とユーザー原文は ADR `20261002-153149` に保存した。
- 実機検証で見つけた問題と修正: 最初の候補は終了デリゲート登録時にクラッシュした。公式プロトコルの終了署名 `Q@:@` と pywebview が登録した親 selector の `I@:@` が異なっていたため、固定型をやめて親の metadata を継承するよう修正した。Dock 再オープンは `B@:@B`。Luna と親が実 PyObjC でクラス登録・署名・quit/show callbacks を確認した。クラッシュ候補が残した backend は録画停止・OBS 非録画と PID/実行パスを確認して SIGTERM で正常停止し、資源追跡プロセスも終了した。その後の修正候補は複数回の起動・終了に成功した。
- 参照した方針・変更分類・保証対象: `docs/test_strategy.md`、`logic / static / workflow` と既存の終了保護 contract の再利用。新規・更新テストは、Mac の close-hide、再表示要求、ready 前の未停止・未破棄、ready 後の正常終了、親 selector 型の継承、主スレッドでの5状態更新、初期化失敗時の可用性と native item 回収の分岐を守るために限定した。
- 実行した入口・結果: 親が `scripts/run-backend-pytest.py` で `test_webview_app.py` と `test_macos_desktop_tray.py` を再実行し25件成功。`test_tray_status.py`、`test_desktop_maintenance.py`、`test_desktop_maintenance_contract.py` は19件成功。skip なし、計44件。修正後に対象25件と変更ファイルの静的検査を再実行した。担当4ファイルの Ruff check / format check / ty check、import-lint の6契約、diff check が成功した。
- 省略した入口と理由: frontend と公開 JSON・設定スキーマは変更しないため component / integration とブラウザー workflow runner は追加しない。ネイティブの導線は配布アプリで確認する。局所修正候補であり、全体 verify / release を追加する根拠はない。Windows 専用の実機 tray テストを macOS で skip して合格とは扱っていない。
- 配布アプリでの親確認: health は `ok`、録画は `STOPPED`、監視は `running / waiting_for_power_on`。閉じる操作後も同じ3プロセスと監視状態を維持した。これは native tray の初期化成功と backend 継続の証拠だが、メニューバー上の可視表示の証明ではない。アプリメニューと Cmd+Q は「処理完了後に終了します」と表示し、それぞれ親・backend・資源追跡プロセス0件、8000番接続不可を確認した。
- 配布物: `dist/SplatReplay.app` と `dist/SplatReplay.dmg` を更新した。arm64、bundle ID、カメラ・マイク説明キー、ad hoc 署名、DMG checksum、読み取り専用マウント、実行ファイルの同一性、Applications リンクを確認した。古い `flac-mac` は収集中に SDK 警告が出るが、最終 bundle への非同梱を確認した。DMG SHA256 `30632ac94176cb6731752170c99e07251fe1c7f2687c84724cd364ced0dd9284`。最終アプリはメイン画面を表示し、上記の電源 ON 待ちで起動中。
- 未確認事項・追加で必要な確認: 検証ツールは対象ウィンドウとアプリメニューを取得できるが、状態領域・Dock を直接選択できず、メニューバーの実表示・メニューからの再表示と完全終了・Dock クリックでの復帰は未確認。録画中・編集/アップロード中の native 終了操作、5状態の実画面での変化、Windows 実機の常駐回帰も最終確認に残す。再表示・終了の native callbacks と状態の優先順位は下位テストで確認済み。Apple の [キーボード操作資料](https://support.apple.com/en-gb/102650)を参照して状態領域へのフォーカスも試したが、操作成功の証拠は得られていない。
- 一時物: ログ・検査結果だけを Git 対象外 `backend/outputs/macos-diagnostics/20261002-mac-resident/` に保存した。専用 build work/config、隔離ビルド、旧/失敗候補の退避、DMG 作成・マウント領域、親の pytest basetemp は撤去済み。実動画・メタデータ・設定は削除していない。

## 2026-10-02 の常駐アイコン識別性の修正

- ユーザー指摘: 「常駐は○アイコンのみ？アプリアイコンを表示できない？最初splat replayの常駐がないなと勘違いしてしまった。」
- 目的・成功条件・責務: interface の macOS 状態表示で、常に Splat Replay の既存アプリアイコンを表示し、その隣に起動・待機・録画・処理・要確認の記号を添える。状態説明・再表示・完全終了の既存動作を維持する。
- 実装: `NSApplication.applicationIconImage()` のコピーを18×18ポイントへ縮小し、非テンプレート画像として左側に配置する。Dock の元画像は変更しない。画像を取得できない場合も `SR` と状態記号でアプリ名を識別できる。状態更新では記号と説明だけを更新する。新しい依存・設定・公開 API は追加しない。
- 委譲と親確認: Luna（xhigh）へ対象2ファイルと完了条件を指定して委譲した。親がコードとテストを確認し、対象 `test_macos_desktop_tray.py` を独立に再実行して4件成功、skip なし。画像取得成功・欠落・例外、元画像の保持、5状態での画像維持、主スレッド更新、既存メニュー操作・初期化失敗の回収を確認した。
- 検証入口・省略理由: `logic / static` の局所変更として対象2ファイルの Ruff check / format check / ty check、diff check が成功。frontend と状態判定・終了保護の共有処理は変更しないため、frontend component / integration / browser workflow、全体 verify / release は追加しない。native の起動・終了は配布アプリで確認した。
- 配布物と親の実機確認: `dist/SplatReplay.app` と `dist/SplatReplay.dmg` を更新。arm64、bundle ID、カメラ・マイク説明キー、ad hoc 署名、DMG checksum、読み取り専用マウント、実行ファイル同一性、Applications リンクと古い `flac-mac` の非同梱を確認した。DMG SHA256 は `731c03690ed78ee649751bda34c9d954a0e173baee39aa9f6f78a0fa03e68487`。更新版の health `ok`、録画 `STOPPED`、監視 `running / waiting_for_power_on` とメイン画面を確認。Cmd+Q 後はアプリの全プロセス0件・8000番接続不可を確認し、最終アプリを再起動した。
- 未確認・失敗時: メニューバー自体を検証ツールで直接確認できないため、ロゴと記号の可視表示は利用者の最終確認に残る。画像取得失敗時は文字へフォールバックし、常駐項目の初期化失敗時は従来どおり画面を残す。
- 一時物: Git 対象外 `backend/outputs/macos-diagnostics/20261002-mac-resident-icon/` にログ・検査結果を保存。専用の隔離ビルド、build work/config、旧アプリ退避、DMG stage/mount と親の pytest basetemp は撤去済み。実動画・メタデータ・設定は変更していない。

## 2026-10-02 の常駐ロゴ・状態記号のサイズ調整

- ユーザー指摘: 「他と比べるとアイコンが小さい、かつ状態はアイコンより小さくして」。添付で従来のロゴ表示を確認した。
- 目的・成功条件・責務: interface のメニューバーロゴを18から24ポイントへ拡大し、状態記号を9ポイントのシステムフォントでロゴより小さくする。Dock の元画像、状態判定とメニュー操作は維持する。
- 委譲・親確認: Luna（xhigh）へ前回と同じ2ファイルを完了条件付きで委譲。親が変更コードと既存テスト更新を確認し、対象4件を独立再実行して成功、skip なし。担当2ファイルの Ruff check / format check / ty check と diff check が成功。実 AppKit の `setFont_` と `systemFontOfSize_` は metadata で利用可能と確認した。
- 検証選定: `docs/test_strategy.md` に従う `logic / static` の局所変更。既存の画像保持・5状態・主スレッド・メニュー・回収テストを更新し、新規テストは追加しない。frontend、共有状態と終了保護は変更しないため frontend component / integration / browser workflow、全体 verify / release は追加しない。
- 配布・実機確認: アプリ録画停止と OBS 非録画を読み取り確認し、旧アプリの完全終了・全プロセス終了・8000番解放後に `dist/SplatReplay.app` と `dist/SplatReplay.dmg` を更新した。更新アプリの health `ok`、録画 `STOPPED`、監視 `running / waiting_for_power_on` とメイン画面を親が確認した。DMG の読み取り専用マウントで arm64、署名、bundle ID、カメラ・マイク説明、実行ファイル同一性、Applications リンク、旧 `flac-mac` 非同梱を確認。DMG SHA256 `f4cf74a7533e90705f5feb5b36e28279fe3d41b537072f587f4278052014ed04`。
- 未確認・失敗時: メニューバーの可視サイズは操作ツールの取得範囲外であり、利用者の最終確認に残る。画像取得失敗時の文字フォールバックと初期化失敗時の画面維持は既存テストで確認した。
- 一時物: Git 対象外 `backend/outputs/macos-diagnostics/20261002-mac-resident-size/` に検査結果を保存。専用の隔離ビルド、build work/config、旧アプリ退避、DMG stage/mount は撤去済み。実動画・メタデータ・設定は変更していない。

## 2026-10-02 のアプリアイコン左下への状態バッジ合成

- ユーザー指示: 「アプリアイコンの左下に状態を重ねて表示して」。目的・成功条件は24ポイントのロゴの左下に小さい状態を重ね、横の記号表示を取り除くこと。責務は interface の macOS 状態画像合成に限定する。
- 実装: 各状態で元ロゴのコピーへ白丸と黒い記号を合成し、文字の描画幅に合わせて中央寄せする。元画像と Dock を変更しない。Retina 向けに48ポイントで20ポイントの丸・18ポイントの文字を描画した後、表示サイズを24ポイントへ戻すため、バッジの論理サイズは丸10・文字9ポイントとなる。描画は主スレッド、focus 解除とサイズ復帰は `finally`。同期描画用の `lockFocus` は非推奨 API であることをソースに明記した。合成成功時は横のタイトルを空にし、画像欠落・取得例外・描画例外時は `SR` と記号へ戻す。
- 委譲・親確認と検証選定: Luna（xhigh）へ担当2ファイルと完了条件を指定。親がコード・既存テスト更新を確認し、`docs/test_strategy.md` に従う `logic / static` の対象5件を独立再実行して成功、skip なし。画像の欠落・取得失敗・合成失敗、5状態、元画像不変、主スレッド描画、focus 回収、メニュー・説明の維持を確認した。Ruff check / format check / ty check と diff check が成功。frontend・公開契約・共有状態・終了保護の変更はなく、frontend component / integration / browser workflow、全体 verify / release は追加しない。
- 実画像の親確認: 実 AppKit で5状態をオフスクリーン描画し、全て24ポイント・48×48ピクセルを確認した。PNGを開いて左下の丸と全記号を確認し、合成前後の元画像 TIFF の SHA256 一致も確認した。最初の24ピクセル描画で細かい記号が不鮮明だったため、親が2倍描画を指摘して修正・再検証した。
- 配布・実機確認: アプリと OBS の非録画・Switch ON 待ちを確認し、旧アプリの完全終了・全プロセス終了・8000番解放後に `dist/SplatReplay.app` と `dist/SplatReplay.dmg` を更新。更新版の health `ok`、録画 `STOPPED`、監視 `running / waiting_for_power_on` とメイン画面を確認した。DMG を読み取り専用マウントして arm64、署名、bundle ID、カメラ・マイク説明、実行ファイル同一性、Applications リンク、旧 `flac-mac` 非同梱を確認。DMG SHA256 `21ec2856cec74b563d45411232261a38747d6266ee17125bb88eabdd8d82c97c`。
- 未確認: 合成画像の位置・解像度は確認済みだが、メニューバー自体の表示はツールの取得範囲外で、実表示の最終確認は利用者に残る。
- 一時物: Git 対象外 `backend/outputs/macos-diagnostics/20261002-mac-resident-overlay/` にログ・検査結果・確認用 PNG を保存。専用の隔離ビルド、build work/config、旧アプリ退避、DMG stage/mount は撤去済み。実動画・メタデータ・設定は変更していない。

## 2026-10-02 のユーザーによる最終確認結果

| 項目 | ユーザー原文・追加回答 | 受け入れ結果 |
| --- | --- | --- |
| 実ゲームの自動録画・音声観測・XP/スペシャル回数 | 「実ゲームの自動録画、音声観測、XP・スペシャル回数の最終確認：OK」 | 確認済み |
| 編集・YouTube アップロード | 「マイク収音→字幕→編集→YouTubeアップロード：編集とアップロードはできている」 | 編集とアップロードは確認済み。マイクから字幕は今回の申告の対象外 |
| 別端末からの LAN 接続 | 「通知表示、処理後スリープ、別端末からのLAN接続：別端末からのLAN接続はできた」 | LAN 接続は確認済み。通知と実スリープはこの申告で合格にしない |
| 機器の切断・再接続後の復帰 | 「機器切断・再接続、スリープ復帰、常駐メニューの実操作：機器切断・再接続」。抜き差し後のアプリ復帰を確認できたかへの回答「確認できた」 | 切断・再接続後の復帰は確認済み。常駐メニューとスリープ復帰はこの申告の対象外 |
| DMG 起動 | 「ダウンロードしたDMGの初回起動とリリース前総合検証：起動した」 | DMG 起動は確認済み。リリース前総合検証は別途実行する |
| 実スリープ検査 | 「今回は実際のスリープを検査しない」 | 今回は実スリープ・復帰を実行せず、実装と既存下位テストで確認する |

- 残りの作業: ユーザーの「あなたができることは対応してください」に従い、Luna（xhigh）へマイク・字幕、通知/電源/セットアップ、リリース前総合検証を完了条件付きで委譲し、親が結果を確認する。既存の実動画・設定・認証情報を保護し、スリープ実行は行わない。

### 最終検証の結果と残りの確認

- マイク: 保存中の Windows の機器名「マイク (USB Audio Device)」は、現在の入力「MiraBox Capture」「BOYA mini」に一致しなかった。BOYA mini 指定の既存キャリブレーション API は HTTP 200 を返した。親が既存設定 API でマイク名だけを BOYA mini に更新し、保存結果と文字起こし OFF を確認した。
- 字幕: 日本語の合成音声は VAD と Google 認識を通過し、その認識文を既存の字幕保存経路へ渡した SRT の本文・時刻を検査した。統合認識は Groq の認証エラーで停止したため、完全な収音→統合認識→字幕の成功とは扱わない。ユーザーはキーを更新して検証する方針を選び、アプリの入力画面で更新待ち。認証情報はログへ出力していない。合成音声と SRT の一時ファイルは撤去済み。
- 通知: 親が起動中の配布アプリへ確認通知を1件要求し、HTTP 200「Notification accepted by macOS」を確認した。これは OS への登録成功であり、バナーの実表示を直接確認した結果ではない。
- スリープ: ユーザー指定により実スリープと復帰は実行しない。既存の OS 呼び出し・失敗処理・自動スリープの予告と取消を下位テストで検査する。
- 総合検証: 最終配布前の保証として `test:release:performance` の構成と同じ静的検証・unit・performance・workflow を対象とした。現環境に `task` がないため、既存の Python ラッパーと frontend の npm スクリプトで各構成入口を実行した。親の最終 backend 全体は1009件成功・19件 skip・28件 performance 対象除外、frontend 全体は457件成功。19件の内訳は隔離保存先に動画のない契約2件と Windows 専用17件。初回の83件 skip のうち64件は武器画像の参照先不一致だったため、テストの参照先を実在する `backend/tests/fixtures` に修正した。Luna の武器認識84件がすべて成功し、親も差分を確認して backend 全体を再実行し成功した。workflow の前提不足も残るため総合合格とは扱わない。
- 性能: 他の OCR 検証と同時実行した初回では、変更していない電源 OFF 判定が32.583 msとなり25 msの予算を超過した。対象を単独で再確認して成功し、その後 performance 全体を単独実行して28件すべて成功した。閾値と期待値は緩和していない。
- テストの修正と親確認: LAN 起動テストの `npm.cmd` 固定期待を OS に合わせた。API client fixture は動画を一時保存先へ隔離し、既存の upload NoOp と Homebrew installer の結果スタブを使って実導入を防ぐ。親が全差分を読み、API smoke と起動対象60件を再実行して成功した。OBS セットアップ画面テストは platform を import 時に固定する component を同じ suite で切り替えるために module 全体を再読込していた。Mac / Windows の既存6ケースを2ファイルへ分けて通常の static import を使い、全 frontend unit 457件が成功した。親も6件を再実行して成功。画面の本番実装と期待する内容は変更していない。
- 静的検証と下位検証: Windows 実行ライブラリを Mac へ入れず、親の `ty check src tests` が成功した。親が音声・字幕保存・通知・電源・設定契約の52件も再実行して成功した。第三者ライブラリの `aifc` / `pkg_resources` 廃止警告2件は残り、プロジェクトの lint / 型エラーと区別する。テストファイルは既存 frontend ESLint の対象外であり、強制対象化の parser error を成功とは扱わない。
- workflow 素材: 必要な録画サンプル3本は Git LFS のポインターで実データがない。自動承認レビューが GitHub の LFS 取得照会を拒否したため、対象・送信する SHA-256 ID とサイズを説明して確認した。2026-10-03にユーザーが「LFS取得を許可します。あなたが確認できる範囲は全て確認してください」と明示し、取得・検証を再開した。
- 型検証の方針: ユーザーは「最小限の型定義を整備する（推奨）」を選択した。Windows の実行時依存は条件付きのまま、型定義だけを Mac の開発環境でも使用する。型検証合格を Windows の実機動作保証と同一視しない。
- 認識の修正: 既存画像でキル数05を09、11を01と読む3件を確認した。クラスタ分割と細い桁を失う前処理が原因だったため、kill の分割処理を削除し、二桁の生画像 OCR を既存の再認識経路で先に試す。生画像で読めない場合の既存フォールバックは維持した。期待値は変更せず、親がフレーム解析109件と performance 28件を再実行して成功。Windows の Tesseract 実機検証は未確認。
- 配布候補: `dist/SplatReplay-macOS-candidate.dmg` に新しい候補を保存した。SHA-256 は `3e7c41f07a9d1274d0a30edd690a9464cc9e43e8e33478aaa5efde75c28317f2`。Luna が arm64、ad hoc 署名、権限説明、readonly mount、Applications リンク、app 一式の一致を検査し、親も署名・権限・arm64・DMG checksum・frontend 5ファイル・assets 528ファイル・画像設定の一致と設定/動画/任意フォントの非同梱を確認した。Groq キー入力中のアプリは維持し、候補へ切り替えていない。親の確認後にビルド用一時領域とマウントを撤去し、DMG を安定保存先だけに保持した。初回の sandbox 内 DMG 作成は device not configured で失敗し、候補だけを対象とした権限昇格後に成功した。

### 今回の検証判断

- 参照した方針: `docs/test_strategy.md`。目的は macOS 配布候補の最終検証、成功条件は既存の認識期待値・音声/設定/API 契約・性能予算・同梱物を守ること。
- 変更分類と責務: OCR は domain の `logic / performance`、開発用型定義は `static`、テスト代役・fixture 参照・UI テストの import 修正は既存 `logic / contract / component` の検証経路。依存方向と本番公開契約は変更しない。
- 新規テスト判断: 認識不具合は既存の実画像テストで再発を検出できるため追加しない。OBS セットアップの Windows ケースは別ファイルへ移し、6ケースと期待値を維持する。
- テスト実行判断: 対象の狭い検証後、ユーザーが依頼した最終確認として既存 release 構成を検査する。backend は `scripts/run-backend-pytest.py`、frontend は `test:unit` と対象 component、性能は同ラッパーの performance 選択を使用した。親が対象テスト、backend 全体、性能全体を再実行し、差分を確認した。
- 静的検証: Ruff lint / format、全体の `ty check src tests`、import-lint 6契約、frontend format / lint / type-check / Svelte check が成功した。
- 省略した入口と理由: 2026-10-02の workflow は Git LFS の実動画取得許可待ちで実行できなかった。2026-10-03に許可を得て再開する。実スリープはユーザー指定で省略。Windows 専用実操作は Mac ホストでは実行できない。これらを成功として数えない。
- 未確認事項と次の順番: ①Groq キーと文字起こし ON の保存後の統合認識と字幕、②許可後の LFS 動画取得と workflow、③候補への切替と起動確認、④通知バナー・常駐メニューの実表示。認証情報入力が未完了の間はアプリを終了しない。今回作成した認識音声・字幕・検証用一時領域は終了後に撤去し、ユーザーの動画と設定は保持する。

## 2026-10-03 の取得許可後の確認

- ユーザーの「LFS取得を許可します。あなたが確認できる範囲は全て確認してください」を受け、Luna（xhigh）へ LFS 取得、音声・字幕・動画契約、workflow の安全な実行準備を所有範囲と完了条件付きで委譲した。親は結果とログ、原ファイル、実行結果を確認する。実スリープを実行しない既存判断は維持する。
- LFS: GitHub の batch API は HTTP 200 を返したが、指定した3オブジェクトすべてが `error.code=404` で download action を返さなかった。fixture は置換していない。親も pointer の OID / サイズと診断ログを照合し、既存 `ensure-e2e-assets.js --check` を独立実行して同じ3本の不足・終了コード1を確認した。LFS キャッシュに3 OID はなく、`~/repo`・`~/Movies`・`~/Downloads` の同名ファイル検索でも実メディアは見つからなかった。
- 復旧に必要な実体: `early-abort-from-matching.mkv`（56,577,283 bytes）、`early-abort-gray-overlay-in-game.mkv`（33,635,694 bytes）、`regular-turf-war-mincemeat-win.mkv`（159,801,780 bytes）。SHA-256 は各追跡済み pointer と診断ログに記録されている。元の3本の提供または Git LFS 側の復旧が必要。別の録画で置換したり sidecar の期待値を変更したりして総合合格にはしない。
- workflow: 前提となる実動画がないため実行できない。起動中アプリの8000番、別プロジェクトの5173番を停止・再利用しない。既存 spec の直接 fetch と Vite proxy、通知の API origin が8000番固定であることを確認した。一時 config / spec コピーで空きポートへ隔離する計画を確認したが、LFS 不足のためサーバー起動を行わない。これはアプリの故障を示すテスト失敗ではなく、未実行の前提不足である。
- 起動中アプリ: 親の読み取り検査で health=`ok`、録画=`STOPPED`、自動監視=`running / waiting_for_power_on`、後処理=`idle` を確認した。録画済み・編集済み一覧はともに0件。2026-10-03のログには検査時点で error イベントがなく、2026-10-02のキャリブレーション失敗はその後の HTTP 200 と区別して記録する。
- 音声・字幕: BOYA mini は機器列挙と一致し、キャリブレーションは HTTP 200。読み取り時点で文字起こしは OFF のため、Groq 認識を再要求せず、キー入力・ON・保存をユーザーへ依頼した。入力された認証情報の保存を代理実行しない。既知テキストを渡した字幕保存は、実 SRT の本文と0.25〜1.75秒を検査したが、統合音声認識の成功とは数えない。
- 動画 API の追加確認: 前回の backend 全体で動画未配置のため skip となった既存 mapper 契約2件に対し、テスト利用を許可された `~/Movies/2026-09-27 22-05-23.mkv` を既存 client fixture の一時保存先だけへコピーした。録画済み側の sidecar は既存 metadata 保存経路で生成し、テスト本文・期待値・skip 条件は変更しない。親が一時 plugin / runner と対象テストを読み、既存 `scripts/run-backend-pytest.py` 経由で独立再実行して2件成功・skip 0を確認した。元動画の SHA-256 は前後とも `230860d8ed20581339143e78cf3a74b05b3314d2779eab07579392d5eb65c9ef`。実編集・外部アップロードは行わず、一時動画・字幕・sidecar・runner・plugin・専用 bytecode を撤去した。
- 検証選定: `docs/test_strategy.md` を参照し、今回は既存の `contract` と音声保存の `logic`、workflow の前提確認を追加した。新規テストは作らず、Luna は音声関連36件、親は実動画を使った契約2件を実行した。既に成功した backend 全体1009件・frontend 457件・性能28件は本番コードに変更がないため再実行しない。Windows 専用17件、実スリープ、統合字幕、通知バナーと常駐メニューの実表示を今回の追加検証の成功として数えない。
- 診断記録: `backend/outputs/macos-diagnostics/20261003-final-validation/` は Git 対象外。LFS の応答 URL・認証情報は記録せず、LFS の専用一時領域は撤去した。配布候補 DMG と起動中アプリは維持した。

## 2026-10-03 の Git レビュー指摘への対応

- 全169ファイルの Astra（low）レビュー後、親が修正要否を確認した。初回音声観測の中断、macOS Git hook の Windows 専用 entry、LAN 案内の閲覧端末 OS 判定、導入ガイドの章リンク不一致は、いずれも対応が必要。
- 初回音声観測: Luna（xhigh）へ application use case と対象テストを所有範囲・完了条件付きで委譲した。初回結果が未到着の STANDBY 周期では pending を保持し、最初の結果・現行世代タスク終了・マッチング開始・電源状態解除で解除する。正常確認後の停止、直前が無音の場合だけ待機へ戻って再開する仕様、電源周期でのリセットを維持する。無音で OBS を再起動しない Windows / macOS 共通仕様は変更しない。
- Git hook と導入ガイド: 別の Luna（xhigh）が `.pre-commit-config.yaml` の ty / import-lint を既存の `uv run --no-sync` へ接続し、従来の作業ディレクトリと引数を維持した。依存・lock・Git index は変更しない。`docs/usage.md` に README のリンクと一致する明示 anchor を追加した。helper や新規テストは追加不要と判断した。
- 親の確認: 音声対象テスト17件成功、対象 Ruff lint / format 成功。修正された hook entry をそれぞれ直接実行し、ty 成功、import-lint 6契約維持を確認した。実 Git hook・commit・push は実行しない。README の fragment と唯一の anchor の一致、`git diff --check` も成功した。レビュー時の169ファイルのハッシュとの比較で、今回の担当ファイル以外が変更されていないことを確認した。
- LAN・OS別表示: ユーザーの範囲拡大と手段の委任を受け、専用助言後に Luna（xhigh）へ順番に委譲した。既存 `/setup/status` と同じ応答 DTO に `server_platform` を追加し、初期状態ストアを使う全8箇所（LAN、機器、FFmpeg、OBS、Tesseract、フォント、字幕用 FLAC、YouTube 保存先）を稼働 OS の判定へ接続した。初期状態が遅延・失敗・未知・項目欠落の場合は、セットアップを表示せず再試行を案内する。再取得前の古い OS 情報も破棄する。セットアップ完了済みのメイン画面は未知 OS でも表示し、LAN は共通案内にする。動画の再生形式は閲覧端末の互換性に関わるため、既存の判定を独立した `getClientPlatform()` に移して維持した。
- 親の追加確認: backend の対象 API 契約39件、frontend の対象12ファイル84件を独立再実行して成功。実 API 応答→実ストア→機器画面で Mac サーバーと Windows / iPhone 閲覧、Windows サーバーと Mac 閲覧を確認し、遅延・取得失敗・未知・欠落・再試行・古い OS 情報の破棄、完了済みメイン画面、LAN 共通案内、動画 URL の既存互換性も対象に含めた。Mac 表示の期待値を未知 OS の汎用文に一致しない形へ絞り、偽合格を防いだ。backend Ruff lint / format と全体 ty、frontend の対象 Prettier / ESLint、全体 TypeScript / Svelte check は成功（Svelte は errors 0 / warnings 0）。
- 検証選定: `docs/test_strategy.md` に従い `logic / contract / component / integration / static` の最小対象を選び、初回音声結果待ち、OS応答契約、実ストアと画面の導線に必要な回帰を追加した。全体 unit は対象を絞れたため再実行せず、性能は今回変更の時間予算に影響しないため追加しない。workflow smoke / full は既知の LFS3本不足で未実行。Windows hook の実機実行、実 OBS での今回の寿命修正は未確認。担当と親の今回作成した pytest / cache 一時領域は撤去した。
- 設計記録: 専用記録役の起動がエージェント上限で失敗し、ADR は保存できなかった。ユーザーへ通知し、実装・検証を継続した。
- 配布物: `dist/SplatReplay-macOS-candidate.dmg` を今回の修正入りへ更新した。SHA-256 は `4bfb6e3558b0db14a7a3e49be5ae5decdfbf945bf9474e6c72a773ccafee0236`。Luna（xhigh）が隔離領域でビルドし、親も readonly mount から PYZ を読み、音声観測 use case と setup 応答 schema の同梱コードが現ソースの compile 結果と一致することを確認した（ファイル名だけ正規化）。frontend 5ファイル、asset 528ファイル、画像認識設定も一致した。ad hoc 署名・arm64・bundle ID・カメラ/マイク/LAN 権限説明・Applications リンク・DMG checksum・秘密設定/動画/任意フォント/FLAC の非同梱を親も確認し、検証済みソース15ファイルの不変を照合した。キー入力待ちの起動中アプリと従来の `dist/SplatReplay.dmg` は保持し、新候補アプリを起動していない。
- ビルド補足: frontend build の既存 dynamic import 警告2件を診断ログへ残した。PyInstaller の FLAC SDK 警告も記録し、対象バイナリが最終候補に存在しないことを検査した。PyInstaller は初回に共有ビルドキャッシュへのアクセスが拒否され、専用の `PYINSTALLER_CONFIG_DIR` で再試行して成功した。初回失敗前に共有ビルドキャッシュが一部削除されたかは未確認。DMG 作成・attach は sandbox 内で失敗した後、候補だけを対象とする権限昇格で成功した。専用 readonly mount とビルド一時領域は親の確認後に担当が撤去し、親も撤去・候補 SHA・ソース不変・通常版の修正前コード維持を確認した。結果とハッシュは Git 対象外の `backend/outputs/macos-diagnostics/20261003-git-review-fixes/` に保持する。

## 2026-10-03 の起動中アプリ更新

- ユーザーの「起動中アプリも更新して」を受け、Luna（xhigh）へ更新先・完了条件・旧版退避・親確認後の撤去を指定して委譲した。親も更新前の録画 `STOPPED`、自動監視 `running / waiting_for_power_on`、編集・アップロード `idle` を確認した。
- `dist/SplatReplay.app` を検証済み候補 DMG（SHA-256 `4bfb6e3558b0db14a7a3e49be5ae5decdfbf945bf9474e6c72a773ccafee0236`）の内容へ置き換え、正規パスから再起動した。親も更新後の実行ファイル SHA-256 `f6e8df49f7308c1c79e677c001aec4100410a386f9463a012320a38cc82b341e`、backend 2モジュールの現ソース compile 結果との一致、frontend 5ファイル・asset 528ファイル・画像認識設定のハッシュ一致、arm64・ad hoc 署名・権限説明を独立確認した。検証済みソース15ファイルにも変更はなかった。
- 親の再起動後確認: 正規アプリの GUI PID 67641・backend PID 67643、8000番の待ち受けを確認した。health、setup status、録画状態、自動監視状態、処理状態の5 API は HTTP 200。`is_completed=true / server_platform=macos`、録画 `STOPPED`、自動監視 `running / waiting_for_power_on`、処理 `idle` だった。OBS PID 29443 は更新前後で継続した。認証値は取得・出力しない。
- 操作上の制約: 画面確認ツールが長時間応答しなかったため中断し、API で安全状態を確認した。通常の macOS Quit 要求は終了につながらず、停止中の対象 GUI と残存 Uvicorn に限定した SIGTERM で終了した。置き換え後の sandbox 内起動は失敗し、正規アプリだけを対象とする権限昇格で起動に成功した。画面の見た目や通常 Quit 不成立の原因は今回未確認であり、API と同梱内容の確認から区別する。
- 診断記録: `backend/outputs/macos-diagnostics/20261003-live-update/` に親の更新前後ハッシュ・同梱一致・再起動後 API 検査と担当の実施手順を保存した。親の成功確認後に、担当が今回専用 readonly mount・一時領域・旧版退避物を撤去し、親も一時領域と退避版の非存在、正規 app と候補 DMG のハッシュ維持を確認した。今回の更新は実機ゲーム・字幕・LFS不足の総合 workflow を再検証したことには数えない。

## 2026-10-03 の READY 後のマッチング未検出

- ユーザーから22〜23時のマッチング未検出・開始時刻通知なしを報告された。親が現在の NDI 判定画像と OBS の program / MiraBox sourceScreenshot を取得したところ、すべて1920×1080だが左右240pxの黒帯があり、中央のゲーム映像が1440px幅へ横方向に縮んでいた。OBS シーンの変換は scale 1・crop 0 で、MiraBox の元画像にも黒帯があったため、NDI より前の入力段階の異常と切り分けた。22〜23時のログは STANDBY のままでマッチング検出・解析エラーの記録がなかった。
- Luna（xhigh）が既存の判定経路を確認した。ARMED 後の STANDBY handler は、マッチ選択判定とは独立に matching_start を毎フレーム判定し、陽性時に開始時刻とイベントを設定する。音声観測はこの判定のゲートではない。ROI `(10,30,300,80)` とテンプレート・閾値0.9は従来のままで、今回の横圧縮と黒帯で文字の位置・大きさが外れる。
- 担当は既存陽性 fixture `matching_1.png` を使い、正常入力と今回相当の横圧縮・黒帯を比較した。親も独立再実行し、正常入力の一致率 `0.99999994` は検出、変形入力の `-0.03016058` は不検出と確認した。過去の6.1秒動画は陽性フレームを含まず、そこから検出回復を証明したとは数えない。
- ユーザーが「obsでソースを選択し直したら戻った」と報告した。親も黒帯のない1920×1080の全面映像とゲームモード・XPなどの認識復帰を確認した。その後の実ゲームで23:32:53に「マッチング開始を検知」・STANDBY→MATCHING、23:33:43にバトル開始・録画開始完了・MATCHING→IN_GAMEを確認した。API の開始時刻は `2026-10-03T23:32:53.096164`、録画状態は `RECORDING`。開始時刻の画面表示もユーザーが「表示された」と確認した。
- 本番コード・認識設定・テンプレート・閾値は変更しない。検証済みソース15ファイルの不変を親が確認した。今回の分類は既存判定の `logic` 診断と実入力・状態遷移の `contract / workflow` 確認であり、新規テスト・広いテスト・再ビルドは不要とした。画角異常が見逃し要因であることと復旧は確認済みだが、OBS / AVCapture / 機器内部でなぜこの画角になったか、再発条件は未確定。自動 crop・拡大などの恒久仕様は追加しない。
- 画像・比較 JSON・ログ抜粋・親の確認は Git 対象外の `backend/outputs/macos-diagnostics/20261003-matching-missed/` に保存した。録画中のアプリは停止しない。

## 2026-10-07 の Keychain 読み込みエラー

- 07:41:50 の編集・アップロード処理で `macOS Keychain の読み込みに失敗しました (OSStatus -128)` を記録した。親は Apple Security framework の `errSecUserCanceled=-128` とエラー説明「ユーザが操作をキャンセルしました」を確認した。これは未登録の `errSecItemNotFound=-25300` と異なる。実際に許可画面が表示されたか、利用者がキャンセルしたかは未確認。
- Luna（xhigh）が Keychain・YouTube client・処理再実行・通知の経路を読み取り解析し、親も照合した。読み込みは `SecItemCopyMatching` のみで、失敗を未登録扱いにせず例外として伝える。保存済み認証情報の更新・削除や新規 OAuth 開始には進まない。アップロードが失敗した編集済み動画も、成功後の削除処理には進まない。
- 既存の復旧経路は、失敗アラートを閉じ、資産が残っている状態で「処理開始」を再度押すこと。次回のアップロードで Keychain を読み直す。macOS の許可画面が出た場合は本人の許可・認証が必要。自動処理は同じ失敗対象を直ちに再試行しない。親の検査時点では health=`ok`、録画=`RECORDING`、処理=`failed / OSStatus -128` であり、アプリを停止しない。
- 現アプリの ad hoc 署名は指定要件が cdhash に依存していた。Apple の説明では Keychain はアプリの指定要件でアクセス許可を追跡するため、更新後に再許可が必要となった可能性はあるが、今回の許可画面・操作との関係は未確認。署名や Keychain のアクセス制御は変更しない。参照: [Apple errSecUserCanceled](https://developer.apple.com/documentation/security/errsecusercanceled)、[TN2206 の Trust and Code Signing](https://developer.apple.com/library/archive/technotes/tn2206/_index.html)。
- ソース変更・新規テスト・再ビルド・実機の認証情報照会・処理再実行は行わない。既存ソースと OS 定数・状態 API を用いた診断であり、復旧後の Keychain 読み込みとアップロード成功は未確認。親の証拠は Git 対象外の `backend/outputs/macos-diagnostics/20261007-keychain-read/` に保存した。

## 2026-10-08 の案内修正候補と起動中アプリ更新

- 今回の案内修正を含む macOS arm64 ad hoc 候補 DMG `dist/SplatReplay-macOS-candidate-20261008.dmg` を生成し、SHA-256 `1d9174bd630d0b647d548c6dac8ff8dd765f8fa612535d3b30465551a782ad7e` を記録した。親は read-only mount で arm64、bundle ID、ad hoc deep-strict 署名、3 permission usage keys、必須 asset と秘密設定等の非同梱を確認した。実行ファイル SHA-256 は `3c51852eef2849a32428ca68a71cb846827596316b40bf90498a59b2a7d8fb66`。
- ユーザーの明示許可を受け、録画停止・処理 idle を safe API で確認してから正規 `dist/SplatReplay.app` を候補内容へ更新・起動した。親は bundle と候補のファイルハッシュ、frontend 配信内容、同梱 backend、署名、arm64 を独立確認した。
- 起動後 API は health 200、setup completed / `server_platform=macos`、recorder `STOPPED`、auto `running / waiting_for_power_on`、process `idle`。設定・動画・Keychain、OBS、別プロジェクトは変更していない。旧版 backup と今回専用 build/mount は親確認後に撤去した。
- これは source 更新と起動中 app の反映確認であり、全利用者受け入れではない。macOS ホストの全 backend test 1,014 passed / 19 skipped / 28 deselected、frontend unit 483 passed、performance 28 passed。skip は Windows 専用17件と専用storageに実動画がない contract 2件。GitHub LFS の対象3本が404で、workflow full は未実行。Windows 実機検証は専用 snapshot の利用者実行待ち。

## 2026-10-09 の固定署名ビルド経路

- ユーザーは macOS 配布用の固定自己署名証明書を採用した。公開 SHA-256 は `2b617e1206573418df294b7cb8f256f0aa0ee5ed556df9be32064774de8d20b5`、Common Name は `Splat Replay Local Code Signing`。秘密鍵は login Keychain にあり、リポジトリへは含めない。
- Taskfile はビルド開始前に pinned fingerprint、証明書の用途と有効期間、同じ証明書に対応する Keychain identity を検証する。PyInstaller の中間署名は維持し、最終 `.app` の外側だけを固定 identity で署名する。最終 DR は bundle identifier と証明書 leaf fingerprint に固定し、ad hoc / cdhash 単独署名は受け入れない。
- `task build:macos:candidate` は日時付き専用出力先を使い、既存 `dist/SplatReplay.app`、従来 DMG、通常 build 出力をクリーンしない。同一候補出力先が存在する場合は停止する。
- 初回に codesign が login Keychain の秘密鍵を使う際、OS のアクセス確認が出る場合がある。以後のビルドは登録済み証明書を再利用し、新規証明書発行・Keychain trust 設定・ACL 変更を自動では行わない。表示された許可を本人が判断する。
- 固定自己署名証明書は公証済み Developer ID ではない。Gatekeeper の初回手動許可が必要になる場合がある。YouTube の Keychain item、TCC、WebView サイト許可は別の対象であり、一度化を保証しない。
- 候補作成では `dist/SplatReplay.app` を `dist/macos-candidates/20261009-085647/SplatReplay.app` へ複製し、PyInstaller の再実行なしで外側の署名を固定証明書へ切り替えた。親は 1,724 項目を照合し、変更が `Contents/MacOS/SplatReplay` の署名だけで、他の payload はすべて一致することを確認した。新しい実行ファイル SHA-256 は `825cc53c55384eb9657333dde9e1f5c076f66954db7d8b658954d1b59dd16586`。
- 候補 DMG `dist/macos-candidates/20261009-085647/SplatReplay.dmg` の SHA-256 は `4c9dfc5a8b1e73b3795d9e7012a5dfcb363c38b08bbe4128c02f881c0586eebd`。親が checksum、読み取り専用マウント、Applications リンク、arm64、固定証明書署名、候補 app との全内容一致を独立確認した。証拠は Git 対象外の [候補内容照合](../backend/outputs/macos-diagnostics/20261009-fixed-signing/parent-candidate-content.json) と [DMG 検証](../backend/outputs/macos-diagnostics/20261009-fixed-signing/parent-dmg-verification.json) にある。
- 起動中アプリの切替前に録画 `STOPPED`、監視 `waiting_for_power_on`、処理 `idle` を確認し、Cmd+Q で通常終了した。3 プロセスと API が停止した後に旧版を `dist/macos-candidates/20261009-085647/SplatReplay-before-fixed-signing.bundle-backup` へ退避し、候補を `dist/SplatReplay.app` に昇格して起動した。親は実行ファイル SHA-256、起動、`/api/health`、`/setup/status`（完了済み・`server_platform=macos`）、録画 STOPPED、監視 running / waiting_for_power_on、処理 idle、メインの POWER OFF 画面を確認した。[親のライブ更新記録](../backend/outputs/macos-diagnostics/20261009-fixed-signing/parent-live-update.json) を参照。カメラ許可の毎起動再表示と本番 YouTube Keychain の再許可は確認していない。
- 内容の異なる A/B probe 実行ファイル間で、probe 用 bundle ID と固定 leaf SHA を含む同一 DR が相互検証に成功した。製品候補では別途、製品 bundle ID `io.github.saw4405.splatreplay` と固定 leaf を含む DR を確認した。これは署名 identity の継続性の確認であり、カメラ TCC や本番 YouTube Keychain item の許可継続を確認したものではない。[親の A/B 記録](../backend/outputs/macos-diagnostics/20261009-fixed-signing/parent-signature-continuity.json) と [候補の DR 表示](../backend/outputs/macos-diagnostics/20261009-fixed-signing-candidate/candidate-designated-requirement.txt)（ローカル診断記録、Git対象外）を参照。通常 Taskfile 経由の再ビルド・PyInstaller 再生成は今回未実施。

## 確定した判断と残る調査事項

- ユーザー判断: 「全機能を同等に対応」「Apple Silicon のみ」。USB 機器の自動復旧機能は削除済みであり、Windows / macOS とも実装対象外。M4 は機器列挙・接続判定・切断監視を扱う。処理後スリープ、通知、LAN アクセスは初回対応の対象に含む。現在利用可能な調査環境は `Darwin arm64`。Intel Mac の動作保証は対象外。
- 保存先は Application Support、YouTube OAuth token は Keychain と確定。Windows データの取込は対象外。macOS 配布は固定した自己署名で署名した `.app` を dmg に入れ、初回の手動起動許可を案内する。Developer ID 署名・公証は採用しない。
- `ikamodoki1.ttf` は任意で、未配置なら OS 標準フォントに切り替える。同名キャプチャ機器は既存の表示名方式で継続する。
- OBS 音声は Switch ON 検出時に確認を始め、無音の場合だけマッチング開始まで継続する。正常確認後は同じ稼働中に再開しない。Windows / macOS とも無音による自動再起動を行わない。
- macOS も画面を閉じると非表示で常駐し、メニューバーから状態確認・再表示・完全終了を行う。Dock は残し、完全終了の安全条件は Windows と共通にする。
- M8 は macOS の通知を Splat Replay 名義で表示し、処理後スリープは `pmset` を使い、失敗時も Windows と同じく画面通知を出さずログに記録する。LAN のファイアウォールとローカルネットワーク権限はシステム設定を案内し、アプリから設定を変更しない。
- OBS の起動・DistroAV/NDI Runtime の手動導入・Main Output 設定・NDI frame 受信、認証付き WebSocket でのアプリの短い手動録画・保存は Apple Silicon ホストで確認済み。実際の Switch 映像による自動録画・音声観測・機器切断と再接続後の復帰は、2026-10-02 のユーザー確認で合格。長時間受信、権限拒否からの復旧、OBS 異常終了後の挙動は未確認。実スリープと復帰はユーザー判断で今回の検査を実施しない。USB 機器の自動復旧は対象外と確定した。全機能同等の達成が難しいことが判明した場合は、根拠と代替案を提示し、機能範囲を変更する前にユーザーへ判断を求める。

## 参照した主な一次情報

- `Taskfile.yml`、`scripts/dev-doctor.mjs`、`backend/pyproject.toml`、`backend/packaging/splat-replay-webview.spec`
- `backend/src/splat_replay/infrastructure/filesystem/paths.py`、`backend/src/splat_replay/infrastructure/di/adapters.py`
- `backend/src/splat_replay/infrastructure/adapters/capture/{capture_device_checker,ndi_capture,adaptive_capture}.py`
- `backend/src/splat_replay/infrastructure/adapters/obs/process_manager.py`、`backend/src/splat_replay/infrastructure/adapters/audio/microphone_enumerator.py`
- `backend/src/splat_replay/application/services/setup/{system_setup_service,system_check_service}.py`
- `backend/src/splat_replay/interface/web/routers/notifications.py`、`backend/src/splat_replay/infrastructure/adapters/system/system_power.py`
- `frontend/src/setup/components/steps/`、`frontend/src/main/components/settings/SettingsDialog.svelte`
- `docs/test_strategy.md`、`docs/external_spec.md`、上記 ADR
- [Apple: macOS Library Directory Details](https://developer.apple.com/library/archive/documentation/FileManagement/Conceptual/FileSystemProgrammingGuide/MacOSXDirectories/MacOSXDirectories.html)、[Apple: File System Basics](https://developer.apple.com/library/archive/documentation/FileManagement/Conceptual/FileSystemProgrammingGuide/FileSystemOverview/FileSystemOverview.html)（2026-09-25 参照）
- [DistroAV Releases](https://github.com/DistroAV/DistroAV/releases/latest)、[DistroAV 要件](https://github.com/DistroAV/DistroAV/blob/master/README.md#requirements)、[NDI Runtime for macOS](https://ndi.link/NDIRedistV6Apple)、[NDI 動的ライブラリ読み込み](https://docs.ndi.video/all/developing-with-ndi/sdk/dynamic-loading-of-ndi-libraries)（2026-09-29 参照）
- [PyAudio の導入手順](https://pypi.org/project/PyAudio/)、[PyInstaller の macOS bundle 仕様](https://pyinstaller.org/en/stable/spec-files.html)（2026-09-25 参照）
