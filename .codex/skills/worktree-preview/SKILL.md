---
name: worktree-preview
description: 複数の機能ブランチを統合した動作確認用の worktree を作成・更新するときに使用する。preview/integration の再作成、対象ブランチの merge、競合解消、検証、VS Code への追加を扱う。
---

# Worktree Preview

このスキルは、複数の機能ブランチを `preview/integration` に統合し、動作確認用 worktree を準備するために使う。

## 基本方針

- 既存の機能ブランチは変更しない。
- preview worktree は確認用の統合場所として扱う。
- 競合が起きた場合は、preview 側だけで解消する。
- 解消判断に設計判断が必要な場合は、影響と選択肢を示してユーザーに確認する。

## 手順

1. 対象ブランチとベースを確認する。
   - 既定ブランチ: `preview/integration`
   - 既定ベース: `main`
   - 既定 worktree: `<repo-parent>/<repo-name>.worktrees/preview-integration`

2. 必要に応じて既存 preview を作り直す。
   - 既存 preview を破棄する場合は、未コミット差分がないことを確認してから行う。
   - `git worktree list` で worktree 状態を確認する。

3. preview worktree を作成する。

```bash
bash .codex/skills/worktree-setup/scripts/setup_worktree.sh \
  --branch preview/integration \
  --base main
```

4. 対象ブランチを統合する。

```bash
git -C <preview-worktree-path> merge --no-ff <branch-a> <branch-b>
```

5. 競合があれば preview 側で解消する。
   - `git status` で競合ファイルを確認する。
   - 自明な重複や import の競合は修正して `git add` する。
   - 意味判断が必要な競合は、採用案・影響・リスクを示してユーザーに確認する。

6. 検証する。

```bash
task.exe install
task.exe verify
```

7. 必要なら VS Code に追加する。

```powershell
code.cmd --add "<preview-worktree-path>"
```

## 報告内容

- 作成または更新した preview worktree のパス。
- merge したブランチ。
- 競合の有無と解消内容。
- 実行した検証コマンドと結果。
- 追加で必要な確認事項。
