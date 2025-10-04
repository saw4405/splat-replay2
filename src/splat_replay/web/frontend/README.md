# Web フロントエンド (Svelte)

Splat Replay の自動録画をブラウザから制御し、プレビュー映像を表示するための Svelte + Vite プロジェクトです。

## 主な機能

- FastAPI バックエンドの `/api/recorder/auto/start` へリクエストを送り、自動録画をバックグラウンドで起動します。
- `/api/preview/stream` が配信する MJPEG 映像を `<img>` 要素で表示し、ライブプレビューとして利用します。
- キャプチャデバイス接続待機中やエラー発生時には日本語メッセージでユーザーへ状態を通知します。

## 開発手順

```bash
cd src/splat_replay/web/frontend
npm install
npm run dev
```

- デフォルトでは `http://localhost:5173` でフロントエンドが起動し、`vite.config.ts` のプロキシ設定により `/api` へのアクセスは FastAPI (例: `http://localhost:8000`) に転送されます。
- 本番用ビルドは `npm run build` で `dist/` ディレクトリに生成されます。

## 注意事項

- このディレクトリには `node_modules/` を含めず、必要なパッケージは利用者が `npm install` 等で取得してください。
- すべての文言は日本語で記述しています。
