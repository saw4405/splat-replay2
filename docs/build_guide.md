# Splat Replay WebView - ビルドガイド

## 概要

PyInstaller を使用して Splat Replay WebView を Windows 実行ファイル（.exe）にパッケージ化します。

## 前提条件

1. **Python 環境**: Python 3.13 以上
2. **依存関係**: プロジェクトの全依存関係がインストール済み
3. **Node.js**: フロントエンドビルド用
4. **PyInstaller**: ビルドグループに含まれる

```powershell
# 依存関係のインストール
uv sync --all-groups

# フロントエンドのインストール
cd frontend
npm install
cd ..
```

## ビルド方法

```powershell
# ビルドスクリプトを実行
.\scripts\build_webview.ps1
```

このスクリプトは以下を自動実行します:

1. フロントエンドのビルド確認・実行
2. 既存ビルドのクリーンアップ
3. PyInstaller でのパッケージ化
4. 実行時ディレクトリ（config, videos）のコピー

## 出力

ビルドが成功すると、以下のディレクトリ構造が生成されます:

```
dist/
└── SplatReplay/
    ├── SplatReplay.exe        # メイン実行ファイル
    ├── _internal/             # PyInstallerの内部ファイル
    │   ├── frontend/
    │   │   └── dist/          # Svelteフロントエンド
    │   ├── assets/            # アイコン等のアセット
    │   └── （多数のDLLと依存ファイル）
    ├── config/                # 設定ファイル（ユーザー編集可能）
    │   ├── settings.example.toml
    │   └── image_matching.yaml
    └── videos/                # 録画/編集済みビデオ保存先
        ├── recorded/
        └── edited/
```

補足:

- `_internal/` 内のファイルは PyInstaller が管理する静的リソース
- `config/` と `videos/` は実行ファイルと同じ階層に配置され、ユーザーが編集・使用可能

## 実行

```powershell
.\dist\SplatReplay\SplatReplay.exe
```
