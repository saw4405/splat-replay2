# Splat Replay — 共通作業指示書

> **目的**: すべてのマイルストーンで共通となる _作業の注意点・作業前準備・作業後確認_ を 1 枚にまとめたチェックリストです。Pull Request の作成前後で必ず本書を参照してください。

---

## 1. 作業の注意点

| カテゴリ                    | 要点                                                                                                                                                                                                           |
| --------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **アーキテクチャ遵守**      | Clean Architecture (Domain → Application → Interface → Infrastructure) を厳守。ポート: `application.interfaces.*` / アダプタ: `infrastructure.adapters.*`。ドメイン層は外部依存を直接呼び出さない純粋 Python。 |
| **コーディング規約**        | フォーマッタ: **Ruff** (行長 79) / 型ヒント 100 % 必須。リンター: `ruff` + `mypy --strict`。ロギング: `structlog` (JSON)。一時デバッグコード・ファイルはコミット禁止。                                      |
| **依存管理**                | Python 3.13 / **uv** を使用 (`pip install` 禁止)。**uv** 実行前に仮想環境 `./.venv/Scripts/Activate.ps1` を必ず有効化し、`uv sync` で依存をインストール・同期すること。                                        |
| **設定管理**                | すべて `config/*.yaml` or `*.toml`。読み込みは Pydantic v2 `BaseSettings` + `shared/di.py` DI。                                                                                                                |
| **テスト & CI**             | `pytest` / CI Green かつ Review ≥ 2 でマージ。                                                                                                                                                                 |
| **ドキュメント**            | ADR (`docs/adr/`)、CHANGELOG、development_plan サインオフを忘れず更新。                                                                                                                                        |
| **ドキュメント参照**        | 外部設計書: `docs/external_spec.md` / 内部設計書: `docs/internal_design.md` / 開発計画書: `docs/development_plan.md`                                                                                           |
| **デバッグ & 一時ファイル** | デバッグログや一時スクリプトは最小限に留め、レビュー前に削除。                                                                                                                                                 |

### uv コマンド例

```powershell
# 仮想環境を有効化 (PowerShell)
.\.venv\Scripts\Activate.ps1

# 依存関係を pyproject.toml に合わせて同期
uv sync

# 新規パッケージを追加 (pyproject.toml と lock を自動更新)
uv add <package>

# `--dev` で開発依存
uv add <package> --dev

# パッケージを削除
uv remove <package>
```

> **禁止事項** — `pip install` / `python -m pip` 等 pip 系コマンドは使用不可。

---

## 2. 作業前準備

1. **カレントディレクトリ確認**: コマンド実行前に必ずプロジェクトルート (`SplatReplay/`) にいることを確認するか、`-C <dir>` などで明示的にディレクトリを指定する。
2. **仮想環境確認**: `./.venv/Scripts/Activate.ps1` で仮想環境を有効化し、`uv sync` で依存を同期。
3. **テスト実行**: `pytest -q` が Green であること。
4. **コードベース調査**: `src/` や `shared/` を検索し再利用可能な実装を確認。
5. **タスク妥当性確認**: 外部設計書 / 内部設計書 / 開発計画書 を読み、作業が開始可能か判断。不足があれば速やかにユーザーへ報告。

---

## 3. 作業後確認

1. **フォーマッター実行**: `ruff format .` を実行し、差分がないことを確認。
2. **静的解析**: `ruff check .` と `mypy --strict` がエラーゼロ。
3. **ドキュメント更新**:

   - 重大変更 → `docs/adr/ADR-YYYYMMDD-NNN.md`
   - `CHANGELOG.md` に追加。
   - マイルストーン完了欄を `docs/implementation_plan.md` に追記。

4. **不要ファイル削除**: 一時デバッグコード / VS Code 個人設定ファイル (`launch.json` 等) が残っていないか確認。

---
