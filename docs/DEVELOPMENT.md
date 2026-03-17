# 開発ガイド

このドキュメントは、Splat Replay の開発を始めるための環境構築、テスト実行、品質確認の手順を説明します。

## システム要件

- **OS**: Windows 11
- **Python**: 3.13 以上（`backend/.python-version` 記載バージョンに追随）
- **uv**: Python パッケージマネージャー
- **Node.js**: フロントエンドビルド用
- **Task**: タスクランナー（ビルド・開発タスク管理）

## セットアップ

### 依存関係のインストール

```bash
# すべての依存関係をインストール
task.exe install
```

詳細は [ビルドガイド](./build_guide.md) を参照してください。

### 開発サーバーの起動

```bash
# 開発モードで起動（ホットリロード有効）
task.exe dev
```

## テスト実行

### 日常の品質確認

```bash
# フォーマット・リント・型チェック・テストを一括実行
task.exe verify
```

### テストの分類と実行コマンド

#### Backend テスト

```bash
# Backend 全テスト
task.exe test:backend

# 契約テスト（API / ドメインモデルの回帰確認）
task.exe test:contract
```

#### Frontend テスト

```bash
# Frontend 全ユニットテスト（logic + component + integration）
task.exe test:frontend:unit

# ロジックテスト（純粋な TypeScript ロジック）
task.exe test:frontend:logic

# コンポーネントテスト（UI コンポーネント単体）
task.exe test:frontend:component

# インテグレーションテスト（複数コンポーネント連携）
task.exe test:frontend:integration
```

#### E2E テスト（Playwright）

```bash
# UI / 自動録画フローの軽量回帰確認
task.exe test:workflow:smoke

# 全 E2E テスト
task.exe test:workflow:full
```

#### リリース前の総合確認

```bash
# 総合回帰確認（全テスト実行）
task.exe test:release

# 性能影響を含むリリース前回帰確認
task.exe test:release:performance
```

## カバレッジ測定

```bash
# 全体のカバレッジ測定（backend + frontend）
task.exe coverage

# Backend のみ
task.exe coverage:backend

# Frontend のみ
task.exe coverage:frontend

# カバレッジレポートをブラウザで開く
task.exe coverage:report
```

カバレッジレポートは以下の場所に生成されます：

- Backend: `backend/htmlcov/index.html`
- Frontend: `frontend/coverage/index.html`

## 品質チェック

### 個別チェック

```bash
# フォーマット適用
task.exe format

# リント実行
task.exe lint

# 型チェック実行
task.exe type-check
```

### 領域別チェック

```bash
# Backend のみ
task.exe format:backend
task.exe lint:backend
task.exe type-check:backend

# Frontend のみ
task.exe format:frontend
task.exe lint:frontend
task.exe type-check:frontend
```

## 開発ワークフロー

### 日常開発

1. **コード変更**
2. **フォーマット**: `task.exe format`
3. **リント**: `task.exe lint`
4. **型チェック**: `task.exe type-check`

### 振る舞い変更時

1. **テスト実行**: `task.exe test`
2. **失敗したテストを修正**（失敗を残したまま完了しない）

### PR 前

1. **全チェック**: `task.exe verify`
2. **全テストがパスすることを確認**

## 関連ドキュメント

- [テスト戦略](./test_strategy.md) - テストの分類と戦略の詳細
- [動画リプレイ入力による E2E 回帰テスト](./e2e_replay_test.md) - E2E テストの詳細
- [内部設計](./internal_design.md) - アーキテクチャと設計思想
- [外部仕様](./external_spec.md) - 外部システムとのインターフェース

## AI エージェント向けドキュメント

コーディングエージェントを使用する場合は、以下のドキュメントを参照してください：

- [AGENTS.md](../AGENTS.md) - プロジェクト全体の実装ルール
- [backend/src/splat_replay/domain/AGENTS.md](../backend/src/splat_replay/domain/AGENTS.md) - ドメイン層の実装ルール
- [backend/src/splat_replay/application/AGENTS.md](../backend/src/splat_replay/application/AGENTS.md) - アプリケーション層の実装ルール
- [backend/src/splat_replay/infrastructure/AGENTS.md](../backend/src/splat_replay/infrastructure/AGENTS.md) - インフラ層の実装ルール
- [backend/src/splat_replay/interface/AGENTS.md](../backend/src/splat_replay/interface/AGENTS.md) - インターフェース層の実装ルール
- [frontend/AGENTS.md](../frontend/AGENTS.md) - フロントエンドの実装ルール
