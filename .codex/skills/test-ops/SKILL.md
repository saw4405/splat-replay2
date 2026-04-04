---
name: test-ops
description: 変更内容から必要な Taskfile の検証入口を選び、最小限の確認順序を決める必要があるときに使用する。特に frontend UI、API 契約、E2E、性能影響が絡み、`task.exe test` だけでは不足する可能性がある変更で使用する。
---

# Test Ops

## Overview

このスキルは、このリポジトリの変更を「何を保証するか」で分類し、
`docs/test_strategy.md` を一次情報として必要な `task.exe` 入口を選ぶ。
詳細な分類定義は文書に置き、ここでは運用手順だけを定義する。

## Workflow

1. 先に `docs/test_strategy.md` を読む。
2. 変更を `static / logic / contract / workflow / performance` のどれに当たるかで分類する。
3. frontend 変更では必要に応じて `logic / component / integration / workflow` へ細分化する。
4. `fast-to-slow` で、必要最小限の入口を選ぶ。
5. 選んだ入口ごとに、なぜ必要かと、なぜ重い入口を省いたかを説明する。
6. 実行後は、変更分類、実行した入口、未確認事項、追加で必要な確認を報告する。

## Primary Reference

- `docs/test_strategy.md`
  - 変更分類
  - 意味ベース入口
  - AI エージェントの完了報告
- `frontend/AGENTS.md`
  - frontend テスト種別
  - ファイル命名規約
- `Taskfile.yml`
  - 実在する入口名

## Selection Rules

- `task.exe verify` は完了判定の最低入口とする。
- `task.exe test` は backend + frontend unit の基本入口とする。
- unit レイヤで守れる変更は、まず `task.exe test` を起点にする。
- frontend の UI コンポーネント単体は `task.exe test:frontend:component` を優先する。
- frontend の複数コンポーネント連携や状態管理は `task.exe test:frontend:integration` を優先する。
- 主要導線、replay、録画済み一覧、preview 周辺は `task.exe test:workflow:smoke` を優先する。
- API、schema、settings の契約変更は `task.exe test:contract` を含める。
- 認識・解析・閾値変更は `task.exe test:performance` を release 前候補として明示する。
- リリース前の総合確認は `task.exe test:release`、性能影響がある場合は `task.exe test:release:performance` を使う。

## Guardrails

- `task.exe test` だけで `contract` / `workflow` / `performance` まで確認したとは扱わない。
- `workflow:full` を初手で提案しない。必要性がある場合だけ後段に置く。
- Taskfile に存在しない raw command を新しい標準入口として提案しない。
- docs の説明と Taskfile の実体がずれている場合は、ずれ自体を指摘する。
- `未確認` の項目を「パス想定」で言い換えない。

## Report Template

- 変更分類:
- 実行した入口:
- 省略した重い入口と理由:
- 未確認事項:
- 追加で必要な確認:

## Common Cases

- ドキュメントのみ:
  - リンクとコマンドの整合確認に留める。
- backend の内部ロジック:
  - `task.exe test:backend`
- frontend の純粋 TS ロジック:
  - `task.exe test:frontend:logic`
- frontend の UI コンポーネント単体:
  - `task.exe test:frontend`
  - 必要に応じて `task.exe test:frontend:component`
- frontend の複数コンポーネント連携:
  - `task.exe test:frontend`
  - 必要に応じて `task.exe test:frontend:integration`
- user-visible flow:
  - `task.exe test`
  - `task.exe test:workflow:smoke`
- release 前:
  - `task.exe test:release`

このスキル自体は追加の `scripts/` や `references/` を持たず、repo 既存文書を一次参照として使う。
