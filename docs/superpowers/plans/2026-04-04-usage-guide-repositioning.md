# usage.md Repositioning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `docs/usage.md` を配布版ユーザー向けの詳細ガイドへ再構成し、PyInstaller 配布とセットアップウィザード前提の導線へ揃える。

**Architecture:** 既存の `docs/usage.md` を in-place で書き換え、文書の責務を「配布版利用者の導入と利用」に限定する。開発者向け手順や詳細仕様は本文から削除し、必要な場面だけ `README.md`、`docs/DEVELOPMENT.md`、`docs/external_spec.md` へ参照を張る。

**Tech Stack:** Markdown, PowerShell, ripgrep, Git

---

## File Structure

- `docs/usage.md`
  - 配布版ユーザー向けガイドの本体。今回の主変更対象。
- `README.md`
  - 最短導線の表現確認に使う参照元。通常は変更しない。
- `docs/DEVELOPMENT.md`
  - 開発者向け文書との責務境界確認に使う参照元。通常は変更しない。
- `docs/external_spec.md`
  - 仕様詳細を逃がす参照先。通常は変更しない。

### Task 1: 文書の責務を配布版ユーザー向けへ切り替える

**Files:**
- Modify: `docs/usage.md`
- Reference: `README.md`
- Reference: `docs/DEVELOPMENT.md`

- [ ] **Step 1: 旧文書に開発者向け語彙が残っていることを確認する**

Run:

```powershell
rg -n "git clone|task\.exe build|Python 3\.13|uv|Node\.js|Task" docs/usage.md
```

Expected: 1 件以上ヒットする。旧 `usage.md` が開発者向け手順を含んでいる確認になる。

- [ ] **Step 2: 文書冒頭を新しい骨格へ置き換える**

`docs/usage.md` の冒頭を、次の骨格に合わせて書き換える。

```md
# Splat Replay ユーザーガイド

この文書は、配布版の `SplatReplay.zip` を展開して利用する方向けのガイドです。
初回起動時のセットアップウィザードと、日常利用の流れを中心にまとめています。

ソースコードからのビルドや開発環境構築は対象外です。
開発者向け手順は [開発ガイド](./DEVELOPMENT.md) を参照してください。

## この文書の対象

- GitHub Releases から配布版を取得して使いたい方
- 初回セットアップで何を準備すればよいか知りたい方
- 普段の起動方法や止め方を確認したい方

## 利用開始までの流れ

1. GitHub Releases から `SplatReplay.zip` をダウンロードします。
2. ZIP ファイルを任意のフォルダへ展開します。
3. 展開先の `SplatReplay.exe` を起動します。
4. 初回はセットアップウィザードに従って必要な準備を行います。
5. セットアップ完了後、通常利用を開始します。

## 事前に必要なもの

## セットアップウィザード

## 使い方

## カスタマイズ

## トラブルシューティング
```

- [ ] **Step 3: 新しい主要見出しが追加されていることを確認する**

Run:

```powershell
rg -n "^## " docs/usage.md
```

Expected: 少なくとも次の見出しがヒットする。

```text
## この文書の対象
## 利用開始までの流れ
## 事前に必要なもの
## セットアップウィザード
## 使い方
## カスタマイズ
## トラブルシューティング
```

- [ ] **Step 4: 骨格変更をコミットする**

Run:

```powershell
git add docs/usage.md
git commit -m "docs: refocus usage guide on packaged users"
```

Expected: `docs/usage.md` の骨格変更だけがコミットされる。

### Task 2: 事前準備とセットアップウィザード説明を実装に揃えて書き換える

**Files:**
- Modify: `docs/usage.md`
- Reference: `README.md`
- Reference: `docs/external_spec.md`

- [ ] **Step 1: 旧来の手動インストール節が残っていることを確認する**

Run:

```powershell
rg -n "必要ソフトウェアのインストール|Python 3 のインストール|uv のインストール|Task のインストール|Node\.js のインストール|アプリケーションのセットアップ" docs/usage.md
```

Expected: 1 件以上ヒットする。旧構成の節がまだ残っている確認になる。

- [ ] **Step 2: `事前に必要なもの` 節を利用者向け前提に置き換える**

`## 事前に必要なもの` の本文を次の内容へ置き換える。

```md
## 事前に必要なもの

- Windows 11 の PC
- Nintendo Switch とドック
- 1080p / 60fps に対応したキャプチャーボード
- OBS Studio
- YouTube アカウント
  - 初回セットアップ時の認証に必要です。
- 必要に応じてマイク
  - 文字起こし機能を使う場合に必要です。
- 必要に応じて Groq API キー
  - 文字起こし機能を使う場合に必要です。

補足:

- OBS Studio、FFmpeg、Tesseract OCR などの外部ソフトは、セットアップウィザードの進行中に確認します。
- 録画・編集・アップロードの詳しい仕様を確認したい場合は [外部設計書](./external_spec.md) を参照してください。
```

- [ ] **Step 3: `セットアップウィザード` 節を現行ステップ構成に合わせて書き換える**

`## セットアップウィザード` の本文を次の内容へ置き換える。

```md
## セットアップウィザード

初回起動時はセットアップウィザードが開きます。
画面の案内に従って、必要な項目を順に確認してください。

### 1. ハードウェア確認

- Switch、キャプチャーボード、PC の接続状態を確認します。
- 必要に応じてマイクの利用有無も確認します。

### 2. FFmpeg

- 動画編集に必要な FFmpeg の利用可否を確認します。
- 未導入の場合は、画面の案内に従って準備してください。

### 3. OBS Studio

- OBS Studio の導入状況や利用準備を確認します。
- キャプチャーデバイス、WebSocket、NDI など、録画に必要な設定をこの段階で見直します。

### 4. Tesseract OCR

- OCR に必要な Tesseract OCR の利用可否を確認します。
- 文字認識機能を使う場合は、この段階で準備してください。

### 5. フォント

- サムネイル生成に必要なフォントを確認します。
- 利用可能なフォントがない場合は、案内に従って準備してください。

### 6. 文字起こし

- 文字起こし機能を使う場合は、マイク名、Groq API キー、言語、辞書を設定します。
- 文字起こしを使わない場合は、このステップをスキップできます。

### 7. YouTube

- YouTube 認証を行います。
- 初回認証時や認証期限切れ時はブラウザが開きます。

すべてのステップが完了すると、通常の利用に進めます。
```

- [ ] **Step 4: セットアップ節に必要なステップ名が揃っていることを確認する**

Run:

```powershell
rg -n "ハードウェア確認|FFmpeg|OBS Studio|Tesseract OCR|フォント|文字起こし|YouTube" docs/usage.md
```

Expected: 7 つのステップ名がすべてヒットする。

- [ ] **Step 5: セットアップ説明の更新をコミットする**

Run:

```powershell
git add docs/usage.md
git commit -m "docs: align usage setup guide with wizard flow"
```

Expected: 事前準備とセットアップウィザードの説明更新だけがコミットされる。

### Task 3: 利用方法と利用者向け補足だけを残す形で後半を整理する

**Files:**
- Modify: `docs/usage.md`
- Reference: `docs/external_spec.md`

- [ ] **Step 1: 仕様書寄りの節が残っていることを確認する**

Run:

```powershell
rg -n "仕様概要|バトル録画の仕組み|編集時の動画のグルーピング|動画のタイトルと説明" docs/usage.md
```

Expected: 1 件以上ヒットする。旧 `usage.md` に仕様説明が残っている確認になる。

- [ ] **Step 2: `使い方` 節を配布版ユーザー向けの運用説明へ置き換える**

`## 使い方` の本文を次の内容へ置き換える。

```md
## 使い方

### 起動する

1. 展開したフォルダの `SplatReplay.exe` を起動します。
2. OBS Studio を利用できる状態にします。
3. Switch をキャプチャーボード経由で PC に接続します。

### 普段の流れ

- アプリ起動後は、ゲーム映像の監視、録画、編集、アップロードが自動で進みます。
- 文字起こしを有効にしている場合は、その設定に従って処理されます。
- 初回セットアップ時や認証期限切れ時はブラウザが開くので、画面表示に従って YouTube 認証を完了してください。

### 停止する

- 通常はアプリケーションウィンドウを閉じて終了します。
- 処理状況によっては、終了まで少し時間がかかる場合があります。
```

- [ ] **Step 3: `カスタマイズ` と `トラブルシューティング` を利用者向け内容へ置き換える**

`## カスタマイズ` と `## トラブルシューティング` の本文を次の内容へ置き換える。

```md
## カスタマイズ

### サムネイル画像を差し替える

1. 1920x1080 の PNG 画像を用意します。
2. 展開したフォルダの `assets/thumbnail/thumbnail_overlay.png` として保存します。

補足:

- 透過部分がある場合は、自動生成サムネイルの上に重ねて表示されます。
- 完全に不透明な画像を置いた場合は、自動生成部分が見えなくなります。

## トラブルシューティング

### セットアップウィザードが完了できない

- 途中で未完了の項目があると、通常利用へ進めません。
- 画面上で強調表示されている項目を確認し、必要な準備を完了してください。

### YouTube 認証が求められる

- 初回利用時や認証期限切れ時は、ブラウザでの再認証が必要です。
- ブラウザ画面の案内に従って認証を完了してください。

### 録画やプレビューが始まらない

- Switch、キャプチャーボード、OBS Studio の状態を確認してください。
- OBS Studio の設定を見直したい場合は、セットアップウィザードの OBS Studio ステップを再確認してください。

### Switch の電源 OFF を検知できない

- キャプチャーボードによっては電源 OFF 時の画面が異なります。
- 必要な場合は、展開したフォルダの `assets/templates/power_off.png` を差し替えて調整してください。
```

- [ ] **Step 4: 開発者向け語彙が消え、利用者向け参照が残っていることを確認する**

Run:

```powershell
rg -n "git clone|task\.exe build|Python 3\.13|uv|Node\.js|Task" docs/usage.md
rg -n "開発ガイド|external_spec\.md|thumbnail_overlay\.png|power_off\.png|セットアップウィザード" docs/usage.md
```

Expected:

- 1 本目はヒットしない。
- 2 本目は複数ヒットする。

- [ ] **Step 5: 後半整理をコミットする**

Run:

```powershell
git add docs/usage.md
git commit -m "docs: streamline packaged user usage guide"
```

Expected: 利用方法、カスタマイズ、トラブルシューティングの整理だけがコミットされる。

### Task 4: 文書全体を読み直して責務のズレを最終確認する

**Files:**
- Modify: `docs/usage.md`
- Reference: `README.md`
- Reference: `docs/DEVELOPMENT.md`
- Reference: `docs/external_spec.md`

- [ ] **Step 1: 差分を確認して、配布版利用者向け以外の内容が残っていないか確認する**

Run:

```powershell
git diff -- docs/usage.md
```

Expected: 差分が、配布版利用者向けへの再構成に収まっている。

- [ ] **Step 2: 文書責務の観点で最終チェックする**

次の観点で `docs/usage.md` を通読する。

```text
- 配布版ユーザーが最初に読む文書として自然か
- 開発手順やビルド手順が本文に残っていないか
- セットアップウィザード中心の流れになっているか
- 詳細仕様を語りすぎず、必要時だけ参照先へ逃がしているか
```

- [ ] **Step 3: 必要なら文言だけを微修正して最終確認する**

Run:

```powershell
rg -n "^## |^### " docs/usage.md
Get-Content -Raw -Encoding utf8 docs/usage.md
```

Expected: 見出し構成が設計どおりで、本文全体が自然につながっている。

- [ ] **Step 4: 最終状態をコミットする**

Run:

```powershell
git add docs/usage.md
git commit -m "docs: reposition usage guide for packaged distribution"
```

Expected: 最終レビュー後の `docs/usage.md` がコミットされる。
