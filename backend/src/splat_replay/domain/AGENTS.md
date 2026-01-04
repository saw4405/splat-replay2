# Domain 層 - 実装ガイドライン

このドキュメントは、ドメイン層を変更する際の **最小ルール** を定義する。

---

## 1. ドメイン層の責務

ドメイン層は **ビジネスルール** を表現する。外部システム（DB・UI・FW）から完全に独立する。

**含むもの**：

- エンティティ（Entity）
- 値オブジェクト（Value Object）
- ドメインサービス
- ドメインイベント
- リポジトリインターフェース（ポート定義）
- ドメイン例外

**含まないもの**：

- I/O 処理（ファイル・DB・API）
- UI ロジック
- フレームワーク依存コード
- インフラ実装

---

## 2. 依存関係のルール

### 禁止事項（絶対 NG）

- 他の層（application / infrastructure / interface / shared）のインポート
- 外部ライブラリへの直接依存（標準ライブラリ以外: numpy, cv2, structlog など）

### 許可事項

- 標準ライブラリのみ（dataclasses, typing, enum, abc, datetime, uuid など）
- ドメイン層内の相互参照

### 例外（許可）

- **Pydantic の利用**（`domain/config/**`）
  - 理由: 設定モデルのバリデーション/シリアライズを安定させるため
  - 範囲: `domain/config/**` のみに限定（他の domain では禁止）

- **NumPy の利用（Frame 型）**（`models/aliases.py`, `services/analyzers/battle_analyzer.py`）
  - 理由: 画像フレーム表現として `NDArray[np.uint8]` を使用するため
  - 範囲: Frame 型/解析周辺に限定（拡大時は設計意図を明記）

---

## 3. 実装パターン

### 3.1 エンティティ（Entity）

- `@dataclass(frozen=True)` で不変にする
- ビジネスルールはメソッドとして実装
- バリデーションは `__post_init__` で実行

### 3.2 値オブジェクト（Value Object）

- 必ず `frozen=True` で不変にする
- バリデーションで不正な状態を作らせない
- `__eq__`, `__hash__` は dataclass が自動生成

### 3.3 ドメインサービス

- 外部依存は **ポート（Protocol）** 経由
- ビジネスロジックの判断を担当
- I/O 処理は行わない（ポートに委譲）

### 3.4 ドメインイベント

- `@dataclass(frozen=True)` で不変
- すべてのフィールドにデフォルト値（基底クラスがデフォルト値を持つため）
- `EVENT_TYPE` で識別

### 3.5 リポジトリインターフェース

- `Protocol` で定義（duck typing）
- メソッドは `...` で実装しない
- 実装は `infrastructure` 層

### 3.6 ドメイン例外

- ビジネスルール違反を明確に表現
- `error_code` で識別可能にする
- `Exception` を継承してスタックトレースを含む

---

## 4. アンチパターン（やってはいけない）

### ❌ I/O 処理を直接実行

- ファイル読み込み・書き込みを直接実行しない
- ポート経由で外部依存を抽象化する

### ❌ インフラ層への直接依存

- 具象クラス（TemplateMatcher など）に依存しない
- ポート（Protocol）に依存する

### ❌ 可変エンティティ

- 状態を直接変更しない
- `dataclasses.replace()` で新しいインスタンスを返す

---

## 5. チェックリスト

変更前に以下を確認：

- [ ] 他の層（application / infrastructure / interface / shared）をインポートしていないか
- [ ] 外部ライブラリ（numpy / cv2 / structlog など）に直接依存していないか
- [ ] エンティティ・値オブジェクトは `frozen=True` か
- [ ] バリデーションは `__post_init__` で実行しているか
- [ ] ドメインイベントはすべてのフィールドにデフォルト値を持つか
- [ ] ビジネスルールが明確にメソッドとして表現されているか

---

## 6. 参考資料

- ルート `AGENTS.md` - 全体方針とレイヤ間ルール
- `docs/internal_design.md` - 設計思想の詳細
