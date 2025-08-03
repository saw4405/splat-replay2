# Splat Replay ユーザーガイド

このガイドでは、Splat Replay を使ってスプラトゥーンのゲームプレイを自動録画し、YouTube にアップロードする方法について説明します。録画からアップロード、サムネイル作成まで一連の流れを自動化することで、プレイに集中しながら記録を残せます。

## 目次

1. [システム要件](#1-システム要件)
2. [インストール手順](#2-インストール手順)
3. [初期設定](#3-初期設定)
4. [使用方法](#4-使用方法)
5. [動画のアップロード仕様](#5-動画のアップロード仕様)
6. [カスタマイズ設定](#6-カスタマイズ設定)
7. [トラブルシューティング](#7-トラブルシューティング)
8. [よくある質問](#8-よくある質問)
9. [メンテナンス情報](#9-メンテナンス情報)

## 1. システム要件

### 1.1. ハードウェア要件

- **PC**: OBS Studio が動作するスペック、USB 3.0 ポートを持つ
- **キャプチャーボード**: 1080p/60fps 対応推奨
- **マイク**: 音声認識機能を使用する場合
- **Nintendo Switch**: ドックに接続された状態

### 1.2. ソフトウェア要件

- **OS**: Windows 11
- **Python**: 3.13 以上
- **uv**: パッケージ管理用
- **OBS Studio**: 28.0 以上（WebSocket 機能を使用するため）
- **FFmpeg**: 動画処理用
- **Tesseract**: OCR（文字認識）用

## 2. インストール手順

### 2.1. 前提ソフトウェアのインストール

#### 2.1.1. Python 3 のインストール

1. [Python 公式サイト](https://www.python.org/downloads/)から Python 3.13 以上をダウンロード
2. インストーラを実行し、**「Add Python to PATH」オプションを必ずチェック**してインストール
3. インストール完了後、コマンドプロンプトで`python --version`を実行して確認

#### 2.1.2. uv のインストール

1. コマンドプロンプトを管理者権限で開き、以下のコマンドを実行:
   ```
   pip install uv
   ```
2. インストール後、`uv --version`で確認

#### 2.1.3. OBS Studio のインストール

1. [OBS Studio 公式サイト](https://obsproject.com/)から最新版をダウンロード
2. インストーラを実行し、デフォルト設定でインストール
3. 初回起動時の最適化ウィザードは「録画向け設定」を選択

#### 2.1.4. FFmpeg のインストール

1. [FFmpeg 公式サイト](https://ffmpeg.org/download.html)から最新の Windows 用ビルドをダウンロード
2. ダウンロードした zip ファイルを解凍し、例えば`C:\ffmpeg`などの場所に配置
3. システム環境変数 PATH に`C:\ffmpeg\bin`を追加
4. コマンドプロンプトで`ffmpeg -version`を実行して確認

#### 2.1.5. Tesseract のインストール

1. [UB-Mannheim のリポジトリ](https://github.com/UB-Mannheim/tesseract/wiki)から最新の Tesseract-OCR をダウンロード
2. インストーラを実行し、「Additional language data」で「English」を選択
3. インストール後、以下の追加データをダウンロード:
   - [best 版 eng データ](https://github.com/tesseract-ocr/tessdata_best/raw/master/eng.traineddata)
   - ダウンロードしたファイルを`C:\Program Files\Tesseract-OCR\tessdata`に上書き保存
4. 環境変数 PATH に Tesseract のインストールパス（例: `C:\Program Files\Tesseract-OCR`）を追加
   ```
   # 管理者権限のコマンドプロンプトで実行
   setx PATH "%PATH%;C:\Program Files\Tesseract-OCR" /M
   ```

### 2.2 必要ファイル・データの取得

#### 2.2.1. イカモドキフォントのダウンロード

1. [イカモドキフォント配布ページ](https://web.archive.org/web/20150906013956/http://aramugi.com/?page_id=807)からフォントをダウンロード
2. ダウンロードしたフォントファイルをインストールせずに保存（後で配置します）

#### 2.2.2. Groq API キーの取得（音声認識機能を使用する場合のみ）

1. [Groq 公式サイト](https://console.groq.com/)でアカウント作成
2. API キーを生成して安全な場所に保存（後で設定します）

#### 2.2.3. YouTube API 認証設定

1. [Google Cloud Console](https://console.cloud.google.com/)で新しいプロジェクトを作成
2. YouTube Data API v3 を有効化
3. 認証情報ページで「OAuth 2.0 クライアント ID」を作成:
   - アプリケーションの種類: デスクトップアプリケーション
   - リダイレクト URI: `http://localhost:8080/`
4. 作成した認証情報の「JSON をダウンロード」をクリックし、`client_secrets.json`として保存（後で配置します）
5. YouTube チャンネルの確認と登録を完了する

### 2.3. アプリケーションのインストール

#### 2.3.1. リポジトリのクローン

```powershell
git clone https://github.com/saw4405/splat-replay2.git
cd splat-replay2
```

#### 2.3.2. 依存パッケージのインストール

```powershell
uv venv
.venv\Scripts\activate
uv sync
uv pip install -e .
```

#### 2.3.3. イカモドキフォントの配置

1. ダウンロードしたイカモドキフォントを`assets\thumbnail`フォルダに配置

#### 2.3.4. YouTube API 認証情報の配置

1. ダウンロードした`client_secrets.json`を`config`フォルダに配置

## 3. 初期設定

### 3.1. 環境変数の設定

1. `config`フォルダ内の`settings.example.toml`ファイルをコピーし、`settings.toml`にリネーム
2. テキストエディタで`settings.toml`ファイルを開き、以下の重要設定を行う:
   - capture_index: キャプチャーデバイスのインデックス
   - name: キャプチャーデバイス名
   - websocket_host: OBS WebSocket のホスト名
   - websocket_port: OBS WebSocket のポート番号
   - websocket_password: OBS WebSocket のパスワード

表示された一覧から、使用するキャプチャーデバイスのインデックスを確認し、`settings.toml`の`device_index`に設定。

### 3.2. OBS Studio の設定

1. OBS Studio を起動
2. ソースを追加:
   - 「ソース」パネルの「+」ボタン →「映像キャプチャデバイス」
   - キャプチャーデバイスを選択し、解像度を 1080p、フレームレートを 60fps に設定
3. WebSocket 設定:
   - 「ツール」メニュー →「WebSocket Server Settings」
   - 「WebSocket server 有効」にチェック
   - サーバーポート: `4455`（デフォルト）
   - パスワードを設定し、`settings.toml`ファイルの`websocket_password`に同じ値を設定
4. 出力設定

### 3.3. YouTube 初回認証

1. アプリケーションを初めて起動すると、YouTube 認証のためにブラウザが開きます
2. Google アカウントでログインし、必要な権限を許可
3. 「アクセスを許可しました。このタブを閉じて先に進んでください。」と表示されたらブラウザタブを閉じる
4. 認証情報が`token.pickle`ファイルに自動保存される

## 4. 使用方法

### 4.1. システムの起動

1. Nintendo Switch からキャプチャーボードを通して PC に接続

   接続例：

   ```mermaid
   graph LR
      Switch[Switch] -- HDMI --> CaptureBoard[キャプチャボード]
      CaptureBoard -- USB --> PC[PC]
      Microphone[マイク] -- USB --> PC
      CaptureBoard -- HDMI --> Monitor[外部モニター]
   ```

2. 仮想環境を有効化し、アプリケーションを起動:

   ```
   .venv\Scripts\activate
   splat-replay auto
   ```

### 4.2. バトル録画の仕組み

通常通りバトルをするだけで、以下のようにシステムが自動で録画・編集・アップロード処理を実行します。

- システムはバックグラウンドで動作し、画面を常時監視
- スプラトゥーンのバトル開始を自動検出すると録画を開始
- バトル終了時に自動的に録画を停止し、メタデータ（ルール、ステージ、勝敗など）を抽出
- バトル情報を含む動画ファイルが自動的に作成される
- 連続したバトルはそれぞれ個別のファイルとして記録される

### 4.3. システムの停止

- 通常の停止: アプリケーションウィンドウを閉じる（× ボタンをクリック）
- 強制停止が必要な場合: Ctrl+C キーを押す

## 5. 動画のアップロード仕様

### 5.1. 動画のグルーピング

録画されたバトルは以下のルールでグループ化され YouTube にアップロードされます:

- 同じタイムスケジュールのバトル（例: 21-23 時）
- 同じマッチタイプ（ナワバリバトル、バンカラマッチなど）
- 同じルール（ガチエリア、ガチヤグラなど）

### 5.2. 動画のタイトルと説明

- **タイトル例 (デフォルト設定の場合)**:

  ```
  Xマッチ(XP19-20) ガチヤグラ 5勝3敗 '25.05.17 21時～
  ```

- **説明文例 (デフォルト設定の場合)**:
  ```
  XP: 2000.0
  00:00:00 WIN  5k 3d 2s デカライン高架下
  00:10:25 LOSE 3k 5d 1s ゴンズイ地区
  ...
  ```

### 5.3. サムネイル

- 自動生成されるサムネイルには以下の情報が含まれます:
  - 勝敗数（○ 勝 × 敗の表示）
  - バトル種別（X マッチ、ナワバリなど）
  - ルール（ガチアサリ、ガチエリアなど）
  - レート情報（XP、ウデマエ）
  - プレイしたステージ情報

## 6. カスタマイズ設定

### 6.1. 動作設定

`settings.toml`ファイルで以下の追加設定をカスタマイズできます:

- キャプチャーデバイスの設定
- OBS の接続設定
- アップロードモードと時刻
- タイトルと説明文のテンプレート
- 音量調整の設定

### 6.2. サムネイル画像のカスタマイズ

サムネイルをカスタマイズする方法:

1. 1920x1080 サイズの PNG 画像を作成
2. `assets\thumbnail`フォルダに`thumbnail_overlay.png`として保存

- **透過あり**の場合: 透過部分に自動生成サムネイルが表示され、非透過部分に独自の装飾が表示される
- **透過なし**の場合: 完全にカスタムサムネイルで置き換えられる（自動生成は無効化）

**ヒント**: 自分のロゴやチャンネルアイコンを透過付きで配置するのがおすすめです。

## 7. トラブルシューティング

### 7.1. Switch の電源 OFF を検知できない

**解決策**:

1. Switch 電源を OFF にした状態の画面をキャプチャ
2. OBS でスクリーンショットを取得
3. 画像を`assets\templates`フォルダに`power_off.png`として保存
