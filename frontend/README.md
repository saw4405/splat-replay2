# Splat Replay Web GUI

Web ベースの GUI フロントエンド (Svelte + FastAPI)

## 機能

- 自動録画機能の開始
- リアルタイムプレビュー映像表示 (WebSocket 経由)
- モダンな Web インターフェース

## 開発環境のセットアップ

### 前提条件

- Python 3.13+
- Node.js 18+
- uv (Python パッケージマネージャー)

### 依存関係のインストール

```bash
# Pythonの依存関係
uv sync

# フロントエンドの依存関係
cd frontend
npm install
cd ..
```

## 開発サーバーの起動

### フロントエンド + バックエンドを同時起動 (推奨)

```bash
uv run splat-replay web --dev
```

これにより以下が起動します:

- フロントエンド開発サーバー: http://localhost:5173
- バックエンド API サーバー: http://localhost:8000
- API ドキュメント: http://localhost:8000/docs

### 個別に起動

#### バックエンドのみ

```bash
uv run splat-replay web
```

#### フロントエンドのみ

```bash
cd frontend
npm run dev
```

## 使用方法

1. 開発サーバーを起動
2. ブラウザで http://localhost:5173 にアクセス
3. 「録画開始」ボタンをクリック
4. プレビュー映像が表示されます

## アーキテクチャ

### フロントエンド

- **フレームワーク**: Svelte 5
- **ビルドツール**: Vite
- **言語**: TypeScript
- **通信**: WebSocket (プレビュー映像), REST API (制御)

### バックエンド

- **フレームワーク**: FastAPI
- **サーバー**: Uvicorn
- **通信**: WebSocket (フレーム配信), REST API (エンドポイント)

### 通信フロー

```
┌─────────────┐      WebSocket      ┌──────────────┐
│             │◄────────────────────┤              │
│  Frontend   │                     │   Backend    │
│  (Svelte)   │      REST API       │  (FastAPI)   │
│             ├────────────────────►│              │
└─────────────┘                     └──────────────┘
                                           │
                                           ▼
                                    ┌──────────────┐
                                    │ AutoRecorder │
                                    │   Service    │
                                    └──────────────┘
```

## デバッグ

### VS Code デバッグ設定

`.vscode/launch.json`に以下を追加:

```json
{
  "type": "python",
  "request": "launch",
  "name": "Web GUI Dev Server",
  "module": "splat_replay.cli",
  "args": ["web", "--dev"],
  "console": "integratedTerminal"
}
```

### ブラウザ開発者ツール

- Chrome/Edge: F12
- WebSocket メッセージを確認: Network タブ → WS

## トラブルシューティング

### ポートが既に使用されている

```bash
# Windowsでポートを確認
netstat -ano | findstr :5173
netstat -ano | findstr :8000

# プロセスを終了
taskkill /PID <プロセスID> /F
```

### npm install が失敗する

```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
```

### バックエンドが起動しない

```bash
# 依存関係を再インストール
uv sync --reinstall
```

## 本番ビルド

```bash
# フロントエンドをビルド
cd frontend
npm run build
cd ..

# バックエンドのみ起動 (ビルド済みフロントエンドを配信)
uv run splat-replay web
```

## ライセンス

プロジェクトのライセンスに準じます
