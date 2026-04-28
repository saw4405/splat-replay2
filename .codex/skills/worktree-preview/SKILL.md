---
name: worktree-preview
description: 複数の機能ブランチを統合した動作確認用の worktree を作成・更新するときに使用する。preview/integration の再作成、対象ブランチの merge、競合解消、取り込み状態の確認、VS Code への追加を扱う。
---

# Worktree Preview

このスキルは、複数の機能ブランチを `preview/integration` に統合し、動作確認用 worktree を準備するために使う。

## 基本方針

- 既存の機能ブランチは変更しない。
- preview worktree は確認用の統合場所として扱う。
- デフォルトの成功条件は「取り込み完了」とする。`task.exe verify` は必須ではない。
- 競合が起きた場合は、preview 側だけで解消する。
- 解消判断に設計判断が必要な場合は、影響と選択肢を示してユーザーに確認する。

## 手順

1. 対象ブランチとベースを確認する。
   - 既定ブランチ: `preview/integration`
   - 既定ベース: `main`
   - 既定 worktree: `<repo-parent>/<repo-name>.worktrees/preview-integration`

2. 既存 preview を使うか作り直すか判断する。
   - `git worktree list` で preview worktree の有無とパスを確認する。
   - preview worktree がない、壊れている、または `main` 更新後の古い merge 履歴が残っていて現在の取り込み対象が分かりにくい場合は作り直す。
   - 前回と今回で取り込むブランチの組み合わせが変わり、古い競合解消や一時的な修正が混ざるおそれがある場合は作り直す。
   - 既存 preview を破棄する場合は、必ず `git -C <preview-worktree-path> status --short` で未コミット差分がないことを確認してから行う。
   - 未コミット差分がある場合は作り直さず、差分の扱いをユーザーに確認する。
   - 迷う場合は、作り直し寄りに判断する。ただし差分破棄を伴う操作はユーザー確認なしに行わない。

3. preview worktree を用意する。

   新規作成または作り直しの場合だけ、setup script を実行する。

```bash
bash .codex/skills/worktree-setup/scripts/setup_worktree.sh \
  --branch preview/integration \
  --base main
```

   既存 preview を再利用する場合は、次を確認してから統合へ進む。

```powershell
git -C <preview-worktree-path> branch --show-current
git -C <preview-worktree-path> status --short
```

   - 現在ブランチが `preview/integration` であること。
   - `status --short` が空であること。
   - 想定外のブランチまたは未コミット差分がある場合は、統合せずユーザーに確認する。

4. 対象ブランチを 1 本ずつ統合する。

```powershell
git -C <preview-worktree-path> merge --no-ff <branch-a>
git -C <preview-worktree-path> merge --no-ff <branch-b>
```

   - 複数ブランチを同時に指定する octopus merge は使わない。
   - 競合が起きた場合に preview 側で解消できるよう、1 本ずつ merge する。

5. 競合があれば preview 側で解消する。
   - `git status` で競合ファイルを確認する。
   - 自明な重複や import の競合は修正して `git add` する。
   - 競合解消後は `git commit` で merge を完了してから、次のブランチへ進む。
   - 意味判断が必要な競合は、採用案・影響・リスクを示してユーザーに確認する。

6. 取り込み状態を確認する。

```powershell
git -C <preview-worktree-path> status --short
git -C <preview-worktree-path> diff --check
git -C <preview-worktree-path> merge-base --is-ancestor <branch-a> HEAD
git -C <preview-worktree-path> merge-base --is-ancestor <branch-b> HEAD
```

   - `status --short` が空なら、取り込み後の worktree は clean。
   - `diff --check` は未コミット差分がある場合の空白エラー検出用。出力がなければ問題なし。
   - `merge-base --is-ancestor` は対象ブランチごとに実行し、終了コード 0 ならそのブランチの tip は preview に含まれている。
   - この段階では品質ゲートは未確認。報告では `task.exe verify` 未実行を明記する。

7. VS Code に追加する。

```powershell
code.cmd --add "<preview-worktree-path>"
```

   - 作成または更新した preview worktree を、現在の VS Code workspace / Source Control view に追加する。

## ユーザー指示がある場合の手順

通常の取り込み作業では、この節は実行しない。ユーザーが明示した場合だけ実行する。

### 追加検証

最低限の smoke を指示された場合:

```powershell
task.exe test
```

品質ゲート確認を指示された場合:

```powershell
task.exe verify
```

- ユーザー指示の範囲に対応するコマンドだけ実行する。
- 完了証明、PR 前、リリース前、または明示的な品質ゲート確認を指示された場合は `task.exe verify` を使う。

## 報告内容

- 作成または更新した preview worktree のパス。
- merge したブランチ。
- 競合の有無と解消内容。
- 実行した取り込み確認コマンドと結果。
- VS Code への追加結果。
- 追加検証の指示がなかった場合は、`task.exe verify` 未実行で品質ゲート未確認であること。
- ユーザー指示で追加実行した手順があれば、そのコマンドと結果。
- 追加で必要な確認事項。
