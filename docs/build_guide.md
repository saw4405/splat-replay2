# Splat Replay WebView - ビルドガイド

## 概要

Task を使用して Splat Replay WebView を Windows 実行ファイル（.exe）にビルド・パッケージ化します。

> **重要**: 本プロジェクトでは **Task を標準のビルドツール** として採用しています。

## 前提条件

### 必須環境

1. **Windows 11**: PowerShell 5.1 以上
2. **Python**: `.python-version` 記載バージョン（3.13+）
3. **uv**: Python パッケージマネージャー
4. **Node.js**: 20.x 以上（フロントエンドビルド用）
5. **Task**: タスクランナー

### Task のインストール

Task は本プロジェクトの**すべてのビルド・検証タスクを管理**します。以下のいずれかの方法でインストールしてください。

```powershell
# winget（推奨）
winget install Task.Task

# または Scoop
scoop install task

# または Chocolatey
choco install go-task
```

インストール後、以下のコマンドでバージョン確認：

```powershell
task --version
# Task version: v3.x.x
```

### 依存関係のインストール

```bash
# バックエンド + フロントエンドをまとめてインストール
task install
```

これにより以下が実行されます：

- バックエンド: `uv sync`
- フロントエンド: `npm install`（frontend/ ディレクトリ）

## ビルド方法

### 完全ビルド（推奨）

```bash
task build
```

**実行内容**:

1. 既存の dist/ をクリーンアップ
2. フロントエンド（Svelte）をビルド → `frontend/dist/`
3. バックエンド（PyInstaller）でパッケージ化 → `dist/SplatReplay/SplatReplay.exe`
4. 設定ファイル・アセットをコピー
5. ビルド情報を表示

### 部分ビルド

開発時やデバッグ時は、以下のタスクで部分的にビルドできます。

```bash
# フロントエンドのみ
task build:frontend

# バックエンドのみ（PyInstaller）
task build:backend

# ポストプロセスのみ（設定コピー等）
task build:postprocess
```

### クリーンアップ

```bash
# すべてのビルド成果物を削除
task clean

# dist/ と build/ のみ削除
task clean:dist

# frontend/dist/ と node_modules を削除
task clean:frontend
```

## 出力

ビルドが成功すると、以下のディレクトリ構造が `dist/SplatReplay/` に生成されます：

```
dist/
└── SplatReplay/
    ├── SplatReplay.exe        # メイン実行ファイル
    ├── _internal/             # PyInstaller の内部リソース（変更不可）
    │   ├── frontend/
    │   │   └── dist/          # Svelte フロントエンド（ビルド済み）
    │   └── （DLL・依存ライブラリ）
    ├── assets/                # 画像マッチング・サムネ生成用アセット
    │   ├── matching/
    │   └── thumbnail/
    ├── config/                # 設定ファイル（ユーザー編集可能）
    │   ├── settings.toml          # メイン設定（example から自動生成）
    │   └── image_matching.yaml    # 画像マッチング設定
    └── videos/                # 録画/編集済みビデオ保存先
        ├── recorded/
        └── edited/
```

**注意事項**:

- `_internal/` 内のファイルは PyInstaller が管理する静的リソース（直接変更不可）
- `config/` と `videos/` はユーザーが編集・使用可能
- `assets/` には再配布禁止のフォント（ikamodoki1.ttf）は含まれません

## 実行

### ビルド成果物を実行

```bash
# Task 経由（推奨）
task run

# または直接実行
.\dist\SplatReplay\SplatReplay.exe
```

### 開発サーバーの起動

ビルド前の開発・デバッグには以下を使用します（**別々のターミナルで実行**）：

```bash
# ターミナル 1: フロントエンド開発サーバー
task dev:frontend

# ターミナル 2: バックエンド開発サーバー（uvicorn with reload）
task dev:backend
```

## トラブルシューティング

### ビルドエラーが発生した場合

1. **依存関係の再インストール**:

   ```bash
   task clean
   task install
   task build
   ```

2. **フロントエンドのキャッシュ削除**:

   ```bash
   task clean:frontend
   task install:frontend
   task build:frontend
   ```

3. **PyInstaller のキャッシュクリア**:
   ```bash
   task clean:dist
   uv sync --group build
   task build:backend
   ```

### よくある問題

- **`SplatReplay.exe` が起動しない**: `config/settings.toml` が正しく配置されているか確認
- **編集に失敗する**: `ikamodoki1.ttf` フォントが `assets/thumbnail/` に存在するか確認
- **フロントエンドが表示されない**: `_internal/frontend/dist/` にビルド済みファイルがあるか確認

## その他の有用なタスク

```bash
# すべての検証（フォーマット・Lint・型チェック・テスト）
task verify

# フォーマット実行
task format

# Lint 実行
task lint

# 型チェック
task type-check

# テスト実行
task test

# 利用可能なタスク一覧を表示
task --list
```
