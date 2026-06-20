---
name: test-ops
description: テスト実装・修正・削除・整理、既存テストのレビュー、検証入口選定、カバレッジ確認など、テストに関する判断を行うときに使用する。
---

# Test Ops

## Overview

このスキルは、テストに関する判断を必ず `docs/test_strategy.md` へ接続するための入口です。
テスト方針、分類、禁止事項、テスト実装の到達基準、検証入口の選定は
`docs/test_strategy.md` を SSoT とし、このスキルには詳細ルールを重複定義しません。

## Workflow

1. テストに関する作業なら、最初に `docs/test_strategy.md` の `0. AI エージェント実行契約` を読む。
2. 作業前に、変更分類、新規テスト判断、検証入口、完了報告項目を決める。
3. テスト実装・修正・削除・整理、既存テストのレビュー、検証入口選定、カバレッジ確認はすべて `docs/test_strategy.md` に従って判断する。
4. 汎用 TDD スキル、古い計画、既存テストの慣習、カバレッジ率目標と衝突する場合も、`docs/test_strategy.md` を優先する。
5. Taskfile の実在する入口名を確認する必要がある場合だけ `Taskfile.yml` を見る。
6. frontend 固有のテストファイル名やセレクタ方針を確認する必要がある場合だけ `frontend/AGENTS.md` を見る。
7. 完了報告では、`docs/test_strategy.md` のテンプレートに基づく判断と未確認事項を明記する。

## Primary Reference

- `docs/test_strategy.md`
  - テスト方針の SSoT
  - AI エージェント実行契約
  - 変更分類、テスト実装基準、禁止事項、意味ベース入口、完了報告
- `frontend/AGENTS.md`
  - frontend 固有ルールが必要な場合だけ参照
- `Taskfile.yml`
  - 実在する `task.exe` 入口名が必要な場合だけ参照

## Report Template

- 参照した方針: `docs/test_strategy.md`
- 変更分類:
- 新規テスト判断:
- テスト実行判断:
- 実行した入口:
- 省略した入口と理由:
- 未確認事項:
- 追加で必要な確認:

このスキル自体は追加の `scripts/` や `references/` を持たず、repo 既存文書を一次参照として使う。
