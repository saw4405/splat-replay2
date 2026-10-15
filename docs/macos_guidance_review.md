# macOS 案内の見直しメモ

- 状態: **2026-10-08 時点の対応結果を記録した履歴**。後日の実機確認や現在の対応状況は示しません。現行の利用手順は[ユーザーガイド](usage.md)を参照してください。本文の「現状」と行番号は変更前の確認時点を指し、実機復旧など未確認事項は確認済みと扱いません。
- 目的: 確認済みの操作と未確認事項を利用者向け案内に反映し、原因が異なる問題を同じ手順にまとめない。
- 記録先: 詳細な調査履歴・診断証拠は[macOS 対応の開発・検証記録](macos_support_plan.md)を参照する。このメモは正式対応宣言や新しい設計判断ではない。

## 1. Keychain エラーの案内（最優先）

**現状と区別:** [ユーザーガイド](usage.md)（127–130行）はブラウザーで行う YouTube 認証を説明している。[YouTubeSetup](../frontend/src/setup/components/steps/YouTubeSetup.svelte)（490–513行）の `client_secret.json` 配置と15分以上の動画向け YouTube アカウント本人確認、および[YouTubePermissionDialog](../frontend/src/main/components/permission/YouTubePermissionDialog.svelte)（43–49行）の Google OAuth 同意も、それぞれ別の操作である。macOS Keychain のアクセス許可をこれらと混同しない。

[Keychain 読み込み](../backend/src/splat_replay/infrastructure/adapters/upload/macos_keychain.py)（29–57行）はアイテム未登録だけを `None` とし、他の OSStatus は例外として伝える。2026-10-07 の `-128` は `errSecUserCanceled` に対応するが、誰が何をキャンセルしたか、アプリ更新との因果、再試行で復旧するかは未確認。[処理フロー](../frontend/src/main/components/recording/useProcessFlow.svelte.ts)（149行、187行）は SSE と状態ポーリングの両方で処理エラーを表示する。

**対応結果:** エラー発生元で `-128` に限り OSStatus を残した対処を付加した。録画中は中断せず、録画後にエラーを閉じ、録画済みまたは編集済み動画が一覧に残っていれば「処理開始」で再実行し、Keychain 許可画面が実際に出た場合だけ本人が確認する案内である。既存の SSE / poll の共通エラー表示を使う。

**確認:** `-128` 専用分岐と他 OSStatus の既存例外経路、SSE / poll の文面伝達、OAuth 新規開始や動画削除へ進まない保護を対象テストとコードで確認した。Keychain 削除・ACL リセット・自動再認証は追加していない。再試行での実機復旧は未確認であり、編集成功時に元録画がすでに削除され得るため全ての元動画が残るとは保証しない。

## 2. 処理開始タイミングとデータ保全（優先度高）

**現状:** [ユーザーガイド](usage.md)（69–71行）は監視・録画・編集・アップロードがすべて起動後自動で進むように読める。一方 [AutoProcessService](../backend/src/splat_replay/application/services/process/auto_process_service.py)（93–98行）は起動時に残った未処理動画を見つけても録画を優先し、自動処理を開始しない。[外部仕様](external_spec.md)（242–248行）は手動開始と自動開始を分けている。自動処理予告は Switch 電源 OFF を検出し、「電源オフ後に編集開始する」が有効な場合に表示する。

[AutoEditor](../backend/src/splat_replay/application/services/editing/auto_editor.py)（318–329・502–510行）は編集成果物の保存確定後に元録画を削除し、[AutoUploader](../backend/src/splat_replay/application/services/upload/auto_uploader.py)（113–122行）はアップロード成功後に編集済み動画を削除する。ローカル動画が常に保存される仕様ではない。

**対応結果:** [ユーザーガイド](usage.md)で起動後の自動監視・録画と後処理を分けた。起動時の未処理動画は保持し、自動後処理は行わない。処理開始は手動、または Switch 電源 OFF 検出と「電源オフ後に編集開始する」が有効な場合の予告後に始まる。処理前の XP / スペシャル / 字幕確認・訂正と、必要な動画・メタデータの退避、編集成果物確定後の元録画削除、アップロード成功後の編集済み動画削除、処理中スリープ変更が今回だけの一時上書きであることを記した。保存仕様や確認モーダルは変更していない。

**確認:** [ユーザーガイド](usage.md)の通常利用手順に反映済み。保存動作の変更や毎回の確認 UI はない。

## 3. LAN のポートと稼働 OS（優先度高）

**現状:** [ユーザーガイド](usage.md)（92・96行）と[SettingsDialog](../frontend/src/main/components/settings/SettingsDialog.svelte)（22–33行）は Windows Firewall 用 TCP 5173 を固定表示する。[LAN status](../backend/src/splat_replay/interface/web/routers/remote_access.py)（194–199行）は `FRONTEND_PORT` がなければ backend port を使い、backend は既定8000。[WebView 起動](../backend/src/splat_replay/interface/gui/webview_app.py)（603–610行）も backend port の既定を8000としている。従って5173は開発環境向けであり、配布時の固定案内と一致しない場合がある。

**対応結果:** [SettingsDialog](../frontend/src/main/components/settings/SettingsDialog.svelte) は取得した稼働 port を整数かつ 1–65535 の場合だけ表示・コマンドへ使う。欠落・不正・取得失敗では具体的なポートや PowerShell コマンドを表示しない。Windows の Firewall 案内は URL の port に合わせ、macOS / Windows / unknown は稼働 OS で分岐する。[ユーザーガイド](usage.md)は公開を保存して再起動した後に表示 URL と port を見てから Firewall を設定する順とし、配布既定8000、開発既定5173、別 port を説明する。

**確認:** 8000 / 5173 / 任意の有効 port、欠落・文字列・範囲外・小数・取得失敗の対象テストを追加・実行した。アクセス URL と PowerShell 複数行の行継続も検証した。稼働 OS による案内を維持した。

## 4. READY と映像画角（優先度高）

**現状:** [CaptureControl](../frontend/src/main/components/recording/CaptureControl.svelte)（69–77・162–168行）の READY は次のバトルを録画する準備状態を表す。[OBSSetup](../frontend/src/setup/components/steps/OBSSetup.svelte)（741–783行）はOBS側のゲーム映像と1920×1080等を案内し、[ユーザーガイド](usage.md)（121–125行）もプレビューを確認させる。しかし外形寸法が1920×1080でも、映像全体が正しい画角とは限らない。

2026-10-03 は MiraBox 元画像、OBS program、NDI 判定画像の全てで左右240pxの黒帯と中央1440pxへの横縮みが見つかった。元画像にも同じ状態があり、NDI変換が原因とは確認されなかった。OBSでソースを選び直すと全面表示に戻り、認識と23:32:53のmatching開始検出・画面上のマッチング開始時刻表示が復帰した（[調査記録](macos_support_plan.md)285–292行）。具体的な設定操作や発生原因は未確認。

**対応結果:** [CaptureControl](../frontend/src/main/components/recording/CaptureControl.svelte) の READY 読み上げと title を「自動録画の待機中」「マッチング検出後に画面へマッチング開始時刻表示」とした。[OBSSetup](../frontend/src/setup/components/steps/OBSSetup.svelte) と [ユーザーガイド](usage.md)では OBS とアプリ両方で全体16:9、黒帯・横縮みなしを確認するよう説明し、解像度の数字だけでは判断しない。READY の画面上のマッチング開始時刻と OS 通知も区別した。10-03 のソース再選択後に復旧した事実は記し、原因と操作詳細は未確認のままにした。

**確認:** 画角案内は Mac / Windows の既存 component 対象で確認する。映像解析、crop、拡大、認識閾値は変更していない。

## 5. 2026-10-08 時点の macOS 確認状況

2026-10-02 にユーザーは実ゲームの自動録画・音声観測・XP/スペシャル・編集とYouTubeアップロード・別端末LAN接続・機器抜き差し後の復帰・DMG起動を確認し、10-03にはmatching開始から録画開始までを再確認した（[記録](macos_support_plan.md)1–3行、285–292行）。一方、マイク由来の字幕/Groq統合、通知バナー、常駐メニューの実操作、初回依存導入の全経路、Windows実機、全受け入れとリリース前 workflow は未完了。実スリープ復帰はユーザー判断で今回は検査しない。

**対応結果:** [ユーザーガイド](usage.md)、[README](../README.md)、[外部仕様](external_spec.md)、[開発ガイド](DEVELOPMENT.md)の macOS 記述を部分確認済み・全体受け入れ未完了へ更新した。10-02 の利用者確認と10-03 matching 開始表示を記し、実マイク字幕/Groq 統合、通知の実表示、常駐メニュー実操作、初回導入の全経路、今回の Windows 実機、workflow、スリープは未確認または未実施とした。正式対応への昇格はしていない。

[macos_support_plan.md](macos_support_plan.md)の現在概要 M1 を「取得許可済み、LFS の3オブジェクト404で workflow 未実行」に更新し、過去の日時付き調査履歴は変更していない。詳細な試行記録をユーザーガイドへ転載していない。

**確認:** 部分確認済みの導線と未完了範囲を分けて記載した。正式対応や全体合格を示唆しない。実スリープ未実施と LFS 不足による workflow 未実行を残した。

## 6. 音声の案内（優先度中、Windows / macOS 共通）

**現状:** [recorder_controller.py](../backend/src/splat_replay/infrastructure/adapters/obs/recorder_controller.py)（73–101行）の `silent` 短文は「音声入力なし」だが詳細は音量メーター未反応と記録継続の可能性を説明する。[VideoPreviewContainer](../frontend/src/main/components/recording/VideoPreviewContainer.svelte)（829–839行）に既存の警告pillと詳細titleがある。

**対応結果:** silent の短文を「音量メーター未反応」に改め、既存 warning pill と詳細表示を維持した。[OBSSetup](../frontend/src/setup/components/steps/OBSSetup.svelte) と [ユーザーガイド](usage.md)に OBS のミュート・入力・録音トラック・ゲーム音を確認する案内を追加した。音声入力消失や音声を保証する表現はしていない。

既存共通仕様を明記する: Switch ON 検出後、待機中の初回結果待ちも観測を継続する。メーター未反応の間はマッチング開始まで観測を続け、正常音声を確認すると停止する。マッチング開始で観測を停止し、待機に戻った場合は直前がメーター未反応のときだけ再開する。正常音声を確認した後は同じ電源周期内で再開しない。次の電源 ON で新しい周期に入る。無音を理由に OBS を再起動しない。

**確認:** Switch ON 後の初回結果待ちとメーター未反応の継続、マッチング開始時の停止、待機復帰時は直前がメーター未反応の場合のみ再開、正常音声確認後は同じ電源周期で再開しないこと、無音を理由に OBS を再起動しないことを案内に記した。録音ロジックや OS 分岐、新規ダイアログは追加していない。

## 7. 初回導入・字幕・カメラ権限の補足（優先度中）

[FFMPEGSetup](../frontend/src/setup/components/steps/FFMPEGSetup.svelte)314–315行と[TesseractSetup](../frontend/src/setup/components/steps/TesseractSetup.svelte)354–355行は、変更前から Homebrew がない場合に Terminal が開くと案内していた。[ユーザーガイド](usage.md)には、Terminal の内容・必要な認証を本人が確認し、導入後に再検査する共通案内と [Homebrew の公式手順](https://docs.brew.sh/Installation)を追加した。

[TranscriptionSetup](../frontend/src/setup/components/steps/TranscriptionSetup.svelte)533行のFLAC導入説明はTerminal操作・認証が不足するため補足候補。596–602行のマイクOS権限案内は既存で十分。デバイス名の一覧表示は実収音成功を意味せず、APIキー入力も認証・字幕成功を意味しない。ミュートや送信機のペアリングを確認し、既存の[SettingsDialog](../frontend/src/main/components/settings/SettingsDialog.svelte)と[SpeechTestDialog](../frontend/src/main/components/settings/SpeechTestDialog.svelte)の認識テストへ案内する。キーをチャットへ送るよう求めない。

**完了条件:** 必要な本人操作と導入後の再検査を短く伝える。マイク選択と実収音を混同せず、既存テスト画面を使い、新しいテストダイアログ/API検証機構を作らない。

### カメラ許可の主体を区別する

[CameraPermissionDialog](../frontend/src/main/components/permission/CameraPermissionDialog.svelte)（43–46行）はブラウザのカメラ許可を案内する。[VideoPreview](../frontend/src/main/components/recording/VideoPreview.svelte)（300–315・353–365行）は列挙/開始失敗をconsoleへ記録するだけで、拒否からの利用者向け復旧案内は不足している。[shouldUseBackendPreviewFrame](../frontend/src/main/clientEnvironment.ts)（18–23行）は loopback 以外で画像APIを選ぶ。[VideoPreviewContainer](../frontend/src/main/components/recording/VideoPreviewContainer.svelte)（674–690行）の既存案内判定は `video_file` 以外で許可案内を出し得て、LAN画像API表示を除外していない。

**対応結果:** [TranscriptionSetup](../frontend/src/setup/components/steps/TranscriptionSetup.svelte) に Homebrew 未導入時の Terminal・本人確認・FLAC 再検査と、マイク一覧/API キー保存だけでは成功確認にならない旨、既存の音声認識テストへの案内を加えた。[CameraPermissionDialog](../frontend/src/main/components/permission/CameraPermissionDialog.svelte) では macOS デスクトップと localhost ブラウザの許可主体を分け、LAN 画像 API 表示ではカメラ許可が不要と説明する。[VideoPreviewContainer](../frontend/src/main/components/recording/VideoPreviewContainer.svelte) は既存の `shouldUseBackendPreviewFrame` を使い、LAN / video_file では許可案内を表示せず、開いている案内も閉じる。

拒否時は本人が該当するシステム設定またはブラウザ設定を確認するよう案内した。拒否後の実機復旧は未確認であり、権限リセット・自動再要求・新モーダルは追加していない。

**確認:** LAN でカメラ許可 API を呼ばず、localhost では既存案内を維持する component 回帰を追加した。全端末が許可すべきとは案内せず、復旧実機を確認済みとは扱わない。

## 8. 日常利用の短文（低優先）

- [ユーザーガイド](usage.md)に Application Support の動画・設定・ログの場所、YouTube 認証情報と `client_secret.json` の保存先、MKV と再生時の一時 MP4、フォント fallback、ローカル preview と LAN 画像 API の違い、黒画面時の Switch 省電力確認を追記した。OBS WebSocket の有効化・認証・既定ポート `4455` と公式案内も追加した。YouTube 以外の API キーが Keychain にあるとは案内していない。
- macOS 更新時は「アプリケーション」内の既存アプリを置き換えて DMG を取り出すこと、ad hoc 署名後に再許可が必要な場合があるが毎回ではないことを記した。

## 今回は追加しないもの

新しいモーダル、常駐/フォント/LANの既存案内の重複、全旧版向けの画像資産ハッシュ恒久検査、USB自動復旧、OBS無音時の自動再起動、自動crop、署名方針変更、正式対応への昇格は対象外。利用者への影響が大きい新方針を採る場合だけ、実装前にユーザー確認を行う。

## 今回の検証結果

- **分類:** SettingsDialog の稼働 port 境界、LAN / localhost のカメラ許可分岐、Mac / Windows のカメラ案内、READY tooltip、OBS・字幕表示は `component`、FLAC / microphone 設定経路は `integration`、音声警告文言は既存 `logic` テスト、コード整形・lint・型検査は `static` とした。文書だけの更新にはテストを追加しない（[test_strategy.md](test_strategy.md)「0. AI エージェント実行契約」）。
- **新規テスト判断:** ポートの整数・範囲・取得失敗、PowerShell 全文の改行と行末継続文字、LAN で許可問い合わせを抑止し localhost では案内する条件、Mac/Windows の許可先表示を守る最小回帰を追加した。長い説明文の一文ごとにテストは追加していない。
- **最小入口:** frontend component 7 files / 75 tests、integration 2 files / 7 tests、backend `test_recording_audio_health.py` 13 tests が成功した。frontend `type-check`、`check`（0 errors / 0 warnings）、対象 Svelte の ESLint / Prettier、backend 対象の Ruff check / format と `ty` が成功した。Keychain / YouTube client 27 tests と YouTubePermission component 9 tests は前工程で親が別途実行し成功を確認した。
- **親の独立確認:** component 8 files / 84 tests（YouTubePermission の9件を含む）、integration 2 files / 7 tests、backend 40 tests が成功し、合計131 tests。Markdown link 85件は欠落0、対象 backend Ruff も成功した。
- **広い入口の省略:** UI 文言と既存 API / store の近接分岐を対象テストで守れるため、全 unit、`verify`、workflow、performance、release build は実行していない。実アプリ・OBS・Keychain の操作も行っていない。
- **未確認:** Keychain `-128` からの実機再試行復旧、カメラ許可拒否からの実機復旧、今回の LAN Firewall 設定を含む Windows 実機、実マイクから Groq 字幕までの統合、通知表示、常駐メニュー実操作、初回依存導入の全経路、LFS 3 オブジェクト404による workflow、実スリープ復帰。詳細は[macOS 対応調査](macos_support_plan.md)を参照する。
- **追加確認:** 親が最終差分と文書リンクを確認済み（案内修正時点でリンク85件、欠落0）。この案内修正工程の終了時点では実アプリを更新していなかった。配布前の総合検証は LFS オブジェクト復旧後に、`docs/test_strategy.md` に従って別途判断する。


## 2026-10-08 追記: 候補ビルドと起動中アプリ更新

案内修正後の source から候補 DMG `dist/SplatReplay-macOS-candidate-20261008.dmg` を作成し、ユーザーの明示許可を受けて起動中の正規 `dist/SplatReplay.app` を更新した。候補 SHA-256 は `1d9174bd630d0b647d548c6dac8ff8dd765f8fa612535d3b30465551a782ad7e`、更新後 executable SHA-256 は `3c51852eef2849a32428ca68a71cb846827596316b40bf90498a59b2a7d8fb66`。親は app/mount 内容、arm64、bundle ID、ad hoc 署名、権限説明、配信 frontend と safe API を独立確認した。更新後は health 200、setup completed / `server_platform=macos`、録画停止、自動監視待機、処理 idle だった。詳細な実施記録は Git 対象外の `backend/outputs/macos-diagnostics/20261008-release-validation/live-app-update.md` にある。

今回の総合構成では backend 1,014 passed、frontend 483 passed、performance 28 passed。19件 skip は Windows 専用17件と専用storageに実動画がない contract 2件。LFS の3オブジェクト404により workflow full は未実行であり、Windows 実機結果も未確認のため、全体受け入れや正式対応昇格は示さない。過去節の「実アプリ更新・操作はしていない」は案内修正工程の時点を記録したもの。
