---
name: create-github-release
description: このリポジトリで、1.2.3 形式の入力から GitHub Release を作成し、前回リリース差分の確認、ユーザー承認、Windows ビルド zip 添付、draft / prerelease 判定まで行う必要があるときに使用する。
---

# Create GitHub Release

## Overview

このスキルは、このリポジトリ向けの GitHub Release 作成フローを安全に実行する。
リリースノート本文はエージェントが差分を読んで作成し、補助スクリプトはリリース境界取得、差分素材収集、タグ重複確認、dirty check、build、zip、draft release 作成だけを担当する。

## Workflow

1. `python3 .codex/skills/create-github-release/scripts/create_github_release.py prepare [version]` を実行する。
   - 入力が `v1.2.3` のように `v` 付きだった場合は、想定入力は `1.2.3` であることを明示し、微修正案として「内部入力は `1.2.3` に正規化し、実際のタグ名とリリース名は `v1.2.3` にする」と提案して、実行前にユーザー確認を取る。
   - version を省略した場合は、前回リリースを基準に patch / minor / major 候補を確認する。
2. 返却された `commits` と `changed_files` を読み、エージェントがリリースノート本文を作成する。
3. version を省略した場合は、候補バージョンのうちどれを推奨するかを決める。
   - 不具合修正のみ、またはユーザーに直接影響がない内部変更だけなら patch を推奨する。
   - ユーザーにとって仕様追加・変更があるなら minor を推奨する。
   - 互換性破壊、移行、再設定、運用変更などユーザー対応が必要なら major を推奨する。
4. ユーザーへ、候補バージョン、推奨バージョン、予定タグ名、予定リリース名、`draft` / `prerelease` 判定、本文、build / zip 添付予定を提示する。
5. ユーザーの明示的な許可が出るまで、`execute` を実行しない。
6. 許可後に `python3 .codex/skills/create-github-release/scripts/create_github_release.py execute <version> --notes-file <path>` を実行する。

## Notes Policy

- 本文はコミット一覧ではなく、ユーザー目線の要約にする。
- 区分は `仕様追加・変更`、`不具合修正`、`ユーザー対応が必要な内容` を基本とする。
- 該当しない区分は省略する。
- `仕様追加・変更` はユーザーにとっての振る舞い変化を指す。
- 入力は `1.2.3` を受け付けるが、実際のタグ名とリリース名は `v1.2.3` に補正する。
- `prepare` は version 省略を許可するが、`execute` は確定した version を必須とする。
- メジャーバージョンが `0` の場合だけ `prerelease` にする。
- Release は常に `draft` で作成する。

## Stop Conditions

- 入力が `1.2.3` / `v1.2.3` のどちらでも解釈できない場合は停止する。
- dirty worktree の場合は停止する。
- 同名タグまたは同名 release がある場合は停止する。
- `task.exe build` が失敗した場合は停止する。
- 添付 zip は一時ファイルとして扱い、release 作成後は削除する。

## Checklist

### `prepare` 前

- [ ] 入力バージョンの有無を確定した。`1.2.3`、`v1.2.3`、未指定のどれでも、その後の流れを説明できる。

### `prepare` 後、承認依頼の前

- [ ] 比較基準に使う前回リリースを確定した。GitHub Release を使ったのか、タグへフォールバックしたのかを説明できる。
- [ ] version 未指定なら、patch / minor / major の候補と、そのうちどれを推奨するかを説明できる。
- [ ] 差分の読み取り結果をユーザー影響ベースで整理した。コミット列挙や内部実装の詳細を、そのまま本文へ流していない。
- [ ] 使い勝手が変わらない内部変更を、誤って `仕様追加・変更` として扱っていない。
- [ ] リリースノート草案は `仕様追加・変更`、`不具合修正`、`ユーザー対応が必要な内容` のうち、必要な区分だけを使っている。
- [ ] 承認依頼には、候補バージョン、推奨バージョン、予定タグ名、予定リリース名、`draft` / `prerelease` 判定、本文、build / zip 添付、実行対象 `HEAD` をまとめて含めた。

### 承認待ち

- [ ] ユーザーの明示的な許可を得る前に、`execute` やタグ作成につながる書き込み操作をしていない。

### `execute` 前

- [ ] 実行前に、dirty worktree、同名タグ、同名 release で停止する前提を確認した。

### `execute` 後

- [ ] タグ作成、build 成功、zip 作成、draft release 作成、asset 添付の成否を個別に確認した。

### 失敗時

- [ ] 途中状態を隠さず報告し、再実行前にどこからやり直すべきかを整理した。
