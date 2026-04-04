# Splat Replay Frontend

Splat Replay の Web GUI フロントエンドです。Svelte 4 / Vite / TypeScript を使って実装しています。

この README では、frontend のローカル開発・ビルド・検証だけを扱います。リポジトリ全体のセットアップや backend を含む開発フローは [`docs/DEVELOPMENT.md`](../docs/DEVELOPMENT.md) を参照してください。

## この README の責務

- frontend の依存関係インストール
- frontend 開発サーバーの起動
- frontend のビルド・検証・テスト
- backend 連携の前提条件の共有

## フロントエンドの役割

- 録画や設定変更の UI を提供する
- SSE と backend API を通して状態更新を受け取り、制御リクエストを送る
- 仮想カメラまたは preview-frame API を使ってプレビュー映像を表示する

## 前提条件

- Node.js 24.12.0+

補足:

- Node.js の要件は [`frontend/package.json`](./package.json) の `engines.node` に合わせています。
- backend を含む統合動作確認には、別途 Python / uv を含む全体セットアップが必要です。詳細は [`docs/DEVELOPMENT.md`](../docs/DEVELOPMENT.md) を参照してください。

## セットアップ

```powershell
cd frontend
npm install
```

リポジトリ全体をまとめてセットアップする場合は、ルートで `task.exe install` を使用してください。手順全体は [`docs/DEVELOPMENT.md`](../docs/DEVELOPMENT.md) にあります。

## 開発サーバー

### frontend のみ起動する

```powershell
cd frontend
npm run dev
```

通常は `http://localhost:5173` で Vite 開発サーバーが起動します。

### backend 連携が必要な場合

この frontend は、既定で `http://localhost:8000` の backend API / SSE / preview エンドポイントを前提に動作します。録画開始、設定保存、プレビュー確認など backend 依存の機能を試す場合は、リポジトリルートから `task.exe dev` または `uv run splat-replay web --dev` を使って全体を起動してください。詳細は [`docs/DEVELOPMENT.md`](../docs/DEVELOPMENT.md) を参照してください。

## 主要コマンド

```powershell
cd frontend

npm run dev
npm run build
npm run preview
npm run verify
npm run test:logic
npm run test:component
npm run test:integration
npm run test:unit
npm run test:e2e
```

補足:

- `npm run verify` は `format:check + lint + type-check + svelte-check` をまとめて実行します。
- テスト選定の基準は [`docs/test_strategy.md`](../docs/test_strategy.md) を参照してください。

## ビルド

```powershell
cd frontend
npm run build
```

ビルド成果物の確認だけなら、続けて `npm run preview` を使えます。backend からの配信を含む確認は [`docs/DEVELOPMENT.md`](../docs/DEVELOPMENT.md) を参照してください。

## デバッグ

- ブラウザ開発者ツールは Chrome / Edge の `F12`
- Network タブで `/api/events/*` や `/api/recorder/preview-frame` を確認可能
- API 呼び出し失敗時は Console と Network を合わせて確認

## トラブルシューティング

### `5173` 番ポートが既に使用されている

```powershell
netstat -ano | findstr :5173
taskkill /PID <プロセスID> /F
```

### `npm install` が失敗する

```powershell
cd frontend
Remove-Item -Recurse -Force node_modules, package-lock.json
npm install
```

### API やプレビューに接続できない

backend が起動していない可能性があります。frontend 単体の `npm run dev` では backend は起動しません。統合起動の手順は [`docs/DEVELOPMENT.md`](../docs/DEVELOPMENT.md) を参照してください。
