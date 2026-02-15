---
name: worktree-setup
description: 対応内容からブランチ名を提案し、別ワークツリーの作成と初期セットアップを実行する。機能開発・不具合修正・調査を既存作業と分離して進めるときに使用する。
---

# Worktree Setup

このスキルは、作業内容のヒアリングからワークツリー初期化までを一気通貫で実行する。
実処理は `scripts/setup_worktree.sh` に集約し、再現可能に実行する。

## 対話方針

- ユーザーへの質問は `ask_questions` ツールを使って対話的に行う。
- 実行前に最低限以下を確認する:
  1. 対応内容（1-2 文）
  2. ブランチ名候補（2-3 個）と採用案（選択肢として提示）
  3. ベース参照（未指定時は `main`、無ければ `HEAD`）
  4. 初期セットアップ実行有無（既定: 実行）

## ワークフロー

1. 対応内容、成功条件、制約を確認する。
2. ブランチ名を 2-3 個提案し、ユーザーに 1 つ選んでもらう。
3. ベース参照を決める。指定がなければ `main` を確認し、存在しない場合は `HEAD` を使う。
4. `scripts/setup_worktree.sh` を実行する。Git が `--no-relative-paths` をサポートしている場合、Windows 絶対パスで worktree を作成する。
5. スクリプトが自動的に新規ウィンドウで VS Code を開く。
6. 作成結果（パス、コピー件数、セットアップ結果）を報告する。

前提:

- Git が `--no-relative-paths` をサポートしている場合、Windows 絶対パス（`C:\Users\...` 形式）で worktree を作成する。これにより `.git/worktrees/<name>/gitdir` に Windows ネイティブなパスが記録され、Git Bash/WSL/PowerShell のどこからでも worktree が認識される。

パス命名:

- 既定の worktree ルートは `<repo親>/<repo名>.worktrees`。
- worktree ディレクトリ名はブランチ名の `/` を `-` に置換する（例: `feature/foo` -> `feature-foo`）。

## ブランチ名の提案ルール

- 作業種別をプレフィックスで表現する:
  - 機能追加: `feature/`
  - 不具合修正: `fix/`
  - 雑務・保守: `chore/`
  - 調査: `investigate/`
- 本文は短い kebab-case にする（例: `feature/thumbnail-retry`）。
- 英語化が難しい場合は、意味が伝わる短い英単語を優先し、必要なら日付サフィックスを付与する。

## 実行

```bash
bash .codex/skills/worktree-setup/scripts/setup_worktree.sh \
  --branch <branch-name> \
  --base <base-ref>
```

よく使うオプション:

```bash
# ヘルプを表示
bash .codex/skills/worktree-setup/scripts/setup_worktree.sh --help

# セットアップをスキップ
bash .codex/skills/worktree-setup/scripts/setup_worktree.sh --branch <branch> --skip-install

# インストールコマンドを明示
bash .codex/skills/worktree-setup/scripts/setup_worktree.sh --branch <branch> --install-cmd "task.exe install"

# 追加コピーリストを指定
bash .codex/skills/worktree-setup/scripts/setup_worktree.sh --branch <branch> --copy-list .worktree-copy-paths
```

## コピー対象ファイル

- 優先リスト: リポジトリルートの `.worktree-copy-paths`
- 追加リスト: `--copy-list <path>`（複数指定可）
- 各リストのルール:
  - 空行、`#` コメントは無視する。
  - リポジトリルート基準のパスまたは glob を書く。
  - 存在しないパターンは無視する。
  - Git 追跡済みファイルはコピーしない。

## 完了確認

```bash
git -C <worktree-path> status -sb
```

WSL を使う場合は以下も確認する:

```bash
git -C <repo-root> worktree list
```

`prunable` が出ていないことを確認する。

必要なら以下を実行する:

```bash
cd <worktree-path>
task.exe verify
```

既存のウィンドウにワークツリーを追加する（任意）:

```powershell
code.cmd --add "C:\Users\...\splat-replay2.worktrees\<worktree-name>"
```

## Worktree の削除

作業完了後、worktree が不要になった場合は以下の手順で削除する:

```bash
# 1. 変更をコミット・マージしたことを確認する
git -C <worktree-path> status

# 2. worktree を削除する（ファイルも削除される）
git worktree remove <worktree-path>

# または、すでにディレクトリを削除済みの場合
git worktree prune
```

注意事項:

- `git worktree remove` はコミットされていない変更があると失敗する（`--force` で強制削除可能）。
- worktree を削除してもブランチは残る。ブランチも削除する場合は `git branch -d <branch-name>` を実行する。
