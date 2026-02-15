# Frontend AGENTS.md

このドキュメントは、コーディングエージェント（Copilot / Claude Code 等）が frontend コードを安全に変更するための **最小ルール** を定義する。

- 親ディレクトリの `AGENTS.md` の原則に従う
- ここに書くのは **frontend 固有の行動ルール（Do / Don't）** のみ

---

## 1. 目的

フロントエンド（TypeScript / Svelte）の変更を **素早く・安全に** 行い、品質（可読性・保守性・信頼性）を落とさないための共通ルールを提供する。

---

## 2. ダイアログ実装ルール

### 2.1 ブラウザ標準ダイアログの禁止

**禁止**: ブラウザ標準のダイアログ API（`alert()`, `confirm()`, `prompt()`）を使用してはいけない。

**理由**:

- UI/UX の一貫性を保つため
- スタイリングやアクセシビリティのコントロールが不可能
- モダンな Web アプリケーションとして不適切

### 2.2 カスタムダイアログの使用

**必須**: すべてのダイアログは、以下のカスタムコンポーネントを使用する。

#### 共通コンポーネント（`frontend/src/common/components/`）

- **BaseDialog**: 高度なカスタムダイアログの基底クラス
- **NotificationDialog**: メッセージ通知（info / success / warning / error）
- **ConfirmDialog**: 確認ダイアログ（OK / キャンセル）
- **ErrorDialog**: エラー詳細表示（エラーコード、復旧方法を含む）

これらのコンポーネントは、メインアプリとインストーラーの両方で使用できる。

### 2.3 NotificationDialog のバリアント

NotificationDialog は `variant` プロパティで4種類の通知を表示できる：

- `info`（デフォルト）: 情報メッセージ（青色、Info アイコン）
- `success`: 成功通知（緑色、CheckCircle2 アイコン）
- `warning`: 警告メッセージ（オレンジ色、AlertTriangle アイコン）
- `error`: エラーメッセージ（赤色、AlertCircle アイコン）

---

## 3. Svelte コンポーネントの型

### 3.1 動的コンポーネントの型指定

`svelte:component` で動的にコンポーネントを切り替える場合、`ComponentType` を使用する：

```typescript
import type { ComponentType } from 'svelte';
export let currentComponent: ComponentType | null = null;
```

**誤った例（禁止）**:

```typescript
export let currentComponent: unknown = null; // NG: unknown は型安全性を損なう
export let currentComponent: any = null; // NG: any は型チェックを無効化する
```

### 3.2 共通型の配置

- **共通型**: `frontend/src/common/types.ts` に配置
  - 例: `ApiError` インターフェース（メインアプリとインストーラーで共有）
- **公式型が無い外部ライブラリ**: `typings/` に最小限の型スタブを追加

---

## 4. 検証コマンド

**frontendディレクトリで実行**:

```bash
cd frontend
npm run verify  # format:check + lint + type-check + svelte-check
```

個別実行:

```bash
npm run format      # Prettier でフォーマット適用
npm run format:check # Prettier でフォーマット確認のみ
npm run lint        # ESLint 実行
npm run type-check  # TypeScript 型チェック
npm run check       # svelte-check 実行
```

---

## 5. テーマ化とスタイリング

### 5.1 テーマ変数の使用

**必須**: すべての色・スタイル定義はテーマ変数を使用すること。

#### テーマファイル

- **テーマ定義**: `frontend/src/themes/neon-abyss.css`
  - すべてのカラーパレット、フォント、グラデーション、影の定義
  - RGB値（`--theme-rgb-*`）とHEX値（`--theme-color-*`, `--theme-accent-color`等）の両方を提供
- **グラスモーフィズム変数**: `frontend/src/app.css`
  - `--glass-bg`, `--glass-bg-strong`, `--glass-border` 等の中間変数
  - テーマ変数から値を取得し、コンポーネントで再利用可能な形式に整形

#### 使用例

```css
/* ✅ 良い例: テーマ変数を使用 */
.my-element {
  color: var(--theme-accent-color);
  background: rgba(var(--theme-rgb-surface-card), 0.8);
  border: 1px solid rgba(var(--theme-rgb-accent), 0.2);
}

/* ❌ 悪い例: ハードコードされた色 */
.my-element {
  color: #2ff6e3;
  background: rgba(16, 23, 48, 0.8);
  border: 1px solid rgba(47, 246, 227, 0.2);
}
```

### 5.2 グラスモーフィズムユーティリティ

`app.css` で定義されたグラスモーフィズムユーティリティクラスを活用：

- `.glass-surface`: メインのグラスサーフェス
- `.glass-panel`: パネルスタイル
- `.glass-card`: カードスタイル
- `.glass-icon-button`: アイコンボタン
- `.glass-divider`: 区切り線
- `.glass-pill`: ピルバッジ

---

## 6. 禁止事項（明確に NG）

- ブラウザ標準ダイアログ（`alert()`, `confirm()`, `prompt()`）の使用
- Svelte コンポーネントの型に `unknown` や `any` を使用
- 共通型を複数箇所で重複定義する
- **色の直接指定（HEXコード、RGB値のハードコード）**: 必ずテーマ変数を使用すること

---

## 7. ディレクトリ構成

### 7.1 現在の構成（2025-12-31時点）

```text
frontend/src/
├── common/              # 共通コンポーネント・型
│   ├── components/      # 共通ダイアログ（BaseDialog, NotificationDialog等）
│   └── types.ts         # ApiError等の共通型
├── main/                # メインアプリケーション
│   ├── api/             # API通信層（機能別に分割）
│   │   ├── types.ts          # API型定義
│   │   ├── recording.ts      # 録画制御API
│   │   ├── assets.ts         # アセット管理API
│   │   ├── metadata.ts       # メタデータ・字幕API
│   │   ├── mappers.ts        # データマッパー
│   │   └── utils.ts          # 共通ユーティリティ
│   ├── components/      # コンポーネント群（17個）
│   │   └── settings/    # 設定関連コンポーネント
│   ├── api.ts           # API re-export（互換性維持）
│   ├── domainEvents.ts  # ドメインイベント購読
│   └── MainApp.svelte   # メインアプリ
└── setup/               # セットアップウィザード
    ├── stores/          # 状態管理（機能別に分割）
    │   ├── state.ts         # 基本状態管理
    │   ├── navigation.ts    # ナビゲーション
    │   ├── system.ts        # システムチェック
    │   └── config.ts        # 設定管理
    ├── components/      # コンポーネント群
    │   └── steps/       # ステップコンポーネント
    ├── store.ts         # Store re-export（互換性維持）
    └── SetupApp.svelte  # セットアップアプリ
```

### 7.2 ファイル分割の原則

- **1ファイルは100〜300行を目安**（絶対ではない）
- **責務の単一性**: 1ファイルは1つの責務のみ
- **Re-export維持**: 既存のimport文を変更しないよう、分割前のファイルをre-export用に残す

### 7.3 API層（main/api/）の責務

- `types.ts`: 全API共通の型定義
- `recording.ts`: 録画制御（start/state）
- `assets.ts`: アセット管理（録画済み・編集済みビデオの一覧・削除）
- `metadata.ts`: メタデータ更新、字幕取得・更新
- `mappers.ts`: バックエンドのsnake_caseをfrontendのcamelCaseに変換
- `utils.ts`: HTTPヘッダー、エラーハンドリング

### 7.4 セットアップ状態管理（setup/stores/）の責務

- `state.ts`: セットアップ状態の保持、ローディング・エラー管理、進行状況計算
- `navigation.ts`: ステップ間の移動、サブステップ管理、ステップのスキップ・完了
- `system.ts`: 外部ソフトウェアのチェック、FFmpeg/Tesseractセットアップ
- `config.ts`: OBS設定、ビデオデバイス、YouTube設定の取得・保存

---

## 8. ルートのAGENTS.mdとの関係

このドキュメントは、ルートの `AGENTS.md` を補完するものであり：

- ルートのAGENTS.mdの原則（原則1〜5）をすべて継承する
- このドキュメントは、frontend固有の技術的詳細（ダイアログ実装、Svelte型、検証コマンド）を定義する
- 設計の詳細や背景は `docs/` 配下のドキュメントを確認すること
