# task dev 2画面起動 設計
作成日: 2026-04-04

## 背景

現状の `task.exe dev` は案内文を表示するだけで、実際には開発サーバーを起動しない。  
一方で日常開発では frontend / backend を同時に立ち上げたいが、backend 側は `uvicorn --reload` を維持したい。

既存実装には `uv run splat-replay web --dev` があるものの、同一ターミナル内で 2 プロセスを束ねる実装になっており、Windows 向けコメントでも `--reload` を避けている。

## 目的

- `task.exe dev` 1 回で frontend / backend の両方を起動できるようにする
- frontend の HMR と backend の `uvicorn --reload` を維持する
- Windows ではログを混在させず、別ウィンドウで扱えるようにする
- `uv run splat-replay web --dev` でも同じ挙動になるよう整合させる

## 非目的

- Linux / macOS 向けの新しいターミナル統合 UX を追加すること
- 既存の `task.exe dev:frontend` / `task.exe dev:backend` を廃止すること
- 開発サーバー停止コマンドを追加すること

## 制約

- ユーザー環境は Windows / PowerShell 前提
- Taskfile だけにロジックを閉じ込めず、既存の CLI 入口とも整合させる
- backend 側の依存方向は崩さない
- 既存ワークツリーに未関連変更があるため、差分は最小限にする

## 採用方針

### 方針 A: `task dev` は CLI の `web --dev` に委譲する

`task.exe dev` 自体は薄い入口にし、実際の 2 画面起動は既存の `splat-replay web --dev` 側に寄せる。  
これにより、Taskfile 利用者と CLI 利用者で挙動を揃えられる。

### 方針 B: Windows では PowerShell を 2 ウィンドウ起動する

Windows では Python 側から PowerShell を 2 つ起動し、frontend / backend をそれぞれ別コンソールで立ち上げる。  
backend 側は既存の `uvicorn --reload` 付きコマンドをそのまま使う。

### 不採用案

- Taskfile にだけ `Start-Process` を直書きする
  - `uv run splat-replay web --dev` と挙動が分岐し、保守点が増えるため不採用。
- 同一ターミナルで 2 プロセスを束ねる
  - 既存実装でも `--reload` を外しており、今回の成功条件と衝突するため不採用。

## 想定変更

- `backend/src/splat_replay/bootstrap/dev_server.py`
  - Windows 向けの 2 ウィンドウ起動ロジックを追加する
  - backend は `--reload` 付きで起動する
- `backend/tests/test_dev_server.py`
  - Windows 向け起動コマンドの回帰テストを追加する
- `Taskfile.yml`
  - `task.exe dev` を案内用から実起動へ変更する
- `docs/DEVELOPMENT.md`
  - `task.exe dev` の説明を実挙動へ更新する
- `frontend/README.md`
  - `web --dev` / `task.exe dev` の挙動を説明に反映する

## 検証方法

- backend unit で Windows 向け起動コマンドを検証する
- `task.exe dev` を実行し、frontend / backend の 2 ウィンドウが開くことを確認する
- backend 側コマンド文字列に `--reload` が含まれることを確認する
- `task.exe verify` を実行し、既存品質ゲートを通す

## リスク

- PowerShell コマンドの quoting を誤ると起動失敗する
  - 対策: 文字列組み立てを helper 化し、unit test で固定する
- Windows 以外では同じ UX にならない
  - 対策: 非 Windows は従来の同一ターミナル起動を維持する

## 結論

`task.exe dev` は backend CLI の `web --dev` に委譲し、Windows では PowerShell の別ウィンドウを 2 つ開いて frontend / backend を個別起動する。  
これにより、`task.exe dev:frontend` / `task.exe dev:backend` が持っていたホットリロード特性を維持したまま、1 コマンド起動を実現する。
