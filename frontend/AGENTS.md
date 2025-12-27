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

## 5. 禁止事項（明確に NG）

- ブラウザ標準ダイアログ（`alert()`, `confirm()`, `prompt()`）の使用
- Svelte コンポーネントの型に `unknown` や `any` を使用
- 共通型を複数箇所で重複定義する

---

## 6. ルートのAGENTS.mdとの関係

このドキュメントは、ルートの `AGENTS.md` を補完するものであり：

- ルートのAGENTS.mdの原則（原則1〜5）をすべて継承する
- このドキュメントは、frontend固有の技術的詳細（ダイアログ実装、Svelte型、検証コマンド）を定義する
- 設計の詳細や背景は `docs/` 配下のドキュメントを確認すること
