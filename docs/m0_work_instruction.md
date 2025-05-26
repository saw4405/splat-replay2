# M0 作業指示書 (Project Bootstrap)

## 1. 作業概要

本マイルストーン **M0** では、以降の開発者が共通の基盤で作業を開始できるよう、リポジトリ構成・開発環境・最低限のスクリプト雛形・ドキュメントを整備します。仕様書類 (外部設計・内部設計・実装計画) をリポジトリの `docs/` に配置済みであることを前提とし、Python 3.12 & **uv** 仮想環境を用いた開発フローを確立することが目標です。

---

## 2. 前マイルストーン (Pre‑M0) 作業報告内容の確認

| 項目             | 内容                                                                                 | 確認方法                    |
| ---------------- | ------------------------------------------------------------------------------------ | --------------------------- |
| ドキュメント配置 | `docs/spec_external.md` `docs/spec_internal.md` `docs/implementation_plan.md` が存在 | `Get-ChildItem docs` で確認 |

> **着手前チェック**: 上記が揃っていない場合は、オーナーに確認してから作業を開始してください。

---

## 3. 作業範囲

- **含む**

  1. `uv init` によるプロジェクト初期化 (`.git/`, `.gitignore`, `pyproject.toml`, `src/` などが自動生成)
  2. Python 3.12 + uv 仮想環境セットアップ手順の整備
  3. 内部設計書で定義されたフォルダ構成の作成 (ドメイン / アプリケーション / インフラ / UI 層などサブディレクトリを含む)
  4. 最小限の CLI スケルトン (`python -m splat_replay --help` / `splat-replay --help` が動く状態)
  5. ベース依存関係のインストール確認 (OBS WebSocket, FFmpeg, OpenCV など)
  6. README & CONTRIBUTING ドキュメント雛形

- **除外** (後続マイルストーンで対応)

  - ゲーム画面検知アルゴリズムの実装
  - GUI / YouTube アップロード機能
  - 自動テスト自動化 (CI) の導入

---

## 4. マイルストーンタスク詳細

| タスク ID | 担当者       | 内容                                                                                                            | 期待成果物                                                                     |
| --------- | ------------ | --------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| M0-01     | 作業者 (LLM) | **プロジェクト初期化** `uv init`                                                                                | `src/`, `tests/`, `.git/`, `pyproject.toml` が生成                             |
| M0-02     | 作業者 (LLM) | **仮想環境セットアップ** `uv venv` → `./.venv/Scripts/Activate`                                                 | PowerShell プロンプト先頭に `(venv)` が表示                                    |
| M0-03     | 作業者 (LLM) | **仮想環境アクティベート後、依存関係インストール** `uv add opencv-python obs-websocket-py structlog typer` など | `uv pip list` にパッケージが並ぶ                                               |
| M0-04     | 作業者 (LLM) | **フォルダ構成作成** — 内部設計書で定義されたディレクトリ・プレースホルダーを作成                               | `src/splat_replay/{domain,application,infrastructure,ui_cli}` などの階層が生成 |
| M0-05     | 作業者 (LLM) | **CLI 雛形実装** `src/splat_replay/__init__.py` `cli.py` を作成し **Typer** で `--help` が出る                  | `python -m splat_replay --help` 出力確認                                       |
| M0-06     | 作業者 (LLM) | **README.md** 作成: 開発環境構築手順・コントリビュート方法を記載                                                | `README.md` が生成                                                             |
| M0-07     | 作業者 (LLM) | **作業報告書作成** — `docs/report_M0.md` を作成                                                                 | 作業報告書ドラフト                                                             |
| M0-08     | オーナー     | **承認／やり直し指示** — 作業報告書を確認し承認または修正依頼                                                   | 承認コメントまたはフィードバック                                               |
| M0-09     | 作業者 (LLM) | **承認記録反映** — 承認後、`docs/implementation_plan.md` の Milestone Log に追記し `git commit`                 | 更新済み実装計画書・コミット履歴                                               |

---

## 5. 目標 & 完了確認項目 (Definition of Done)

1. PowerShell 上で `uv sync` 完了後、`pytest -q` がエラー無しで終了 (テストは空で OK)。
2. 内部設計書どおりのフォルダ構成がリポジトリに作成されている。
3. `python -m splat_replay --help` で CLI ヘルプが表示される。
4. LLM が M0 作業報告書 (`docs/report_M0.md`) を作成し、ユーザーに提示。
5. ユーザーから作業完了の承認を取得 (もしくは修正指示が解消)。
6. 承認内容を **実装計画書** (`docs/implementation_plan.md`) の _Milestone Log_ に追記し、`git commit` で履歴に残す。

---

## 6. 開発環境

- **OS**: Windows 11 (21H2 以降)
- **シェル**: PowerShell (管理者権限不要)
- **Python**: 3.12.x 公式インストーラでシステムに追加 (`Add python.exe to PATH` オプション必須)
- **仮想環境**: uv を用いて `.venv` をプロジェクト直下に作成

### PowerShell コマンド例

```powershell
# 0. カレントディレクトリはプロジェクトフォルダ

# 1. プロジェクト初期化 (uv は既にインストールされている前提)
> uv init  # 対話式でプロジェクト名などを設定

# 2. 仮想環境作成 & 有効化
> uv venv
> .\.venv\Scripts\Activate

# 3. 依存関係同期 (仮想環境をアクティベート後に実行)
> uv sync
```

---

## 7. 使用依存関係と使い方例

| パッケージ / ツール   | 公式情報                                                                                     | インストール                      | 最小使用例                                   |
| --------------------- | -------------------------------------------------------------------------------------------- | --------------------------------- | -------------------------------------------- |
| **uv**                | [https://docs.astral.sh/uv/](https://docs.astral.sh/uv/)                                     | — (前提インストール済)            | `uv init` / `uv venv`                        |
| **OBS Studio**        | [https://obsproject.com/](https://obsproject.com/)                                           | 手動インストーラ                  | 仮想カメラ ON → WebSocket 接続               |
| **obs‑websocket‑py**  | [https://github.com/obsproject/obs-websocket](https://github.com/obsproject/obs-websocket)   | `uv add obs-websocket-py`         | `obsws('localhost', 4455, 'pass').connect()` |
| **FFmpeg**            | [https://ffmpeg.org/download.html](https://ffmpeg.org/download.html)                         | ZIP 展開して PATH 追加            | `ffmpeg -i in.mp4 -c copy out.mp4`           |
| **OpenCV‑Python**     | [https://opencv.org/](https://opencv.org/)                                                   | `uv add opencv-python`            | `import cv2; cap = cv2.VideoCapture(0)`      |
| **Typer**             | [https://typer.tiangolo.com/](https://typer.tiangolo.com/)                                   | `uv add typer`                    | `typer.run(app)`                             |
| **Tesseract OCR**     | [https://tesseract-ocr.github.io/](https://tesseract-ocr.github.io/)                         | Windows インストーラ              | `tesseract img.png out -l jpn`               |
| **Google API Client** | [https://developers.google.com/youtube/v3](https://developers.google.com/youtube/v3)         | `uv add google-api-python-client` | YouTube Data API アップロード                |
| **Groq API**          | [https://console.groq.com/docs/speech-to-text](https://console.groq.com/docs/speech-to-text) | `uv add groq`                     | 音声 → 文字 API 呼び出し                     |

#### obs‑websocket‑py 具体例

```python
from obswebsocket import obsws, requests as R

ws = obsws('localhost', 4455, 'pass')
ws.connect()
ws.call(R.StartRecord())
```

---

## 8. 作業前チェックリスト

- ***

## 9. 作業報告書テンプレート (M0 用)

`docs/report_M0.md` として以下をコピペして使用してください。

```
# M0 作業報告書

## 完了タスク
- M0‑01 プロジェクト初期化 … 完 / 未了
- M0‑02 仮想環境セットアップ … 完 / 未了
- M0‑03 依存関係インストール … 完 / 未了
- M0‑04 フォルダ構成作成 … 完 / 未了
- M0‑05 CLI 雛形実装 … 完 / 未了
- M0‑06 README 作成 … 完 / 未了

## 確認結果
- CLI ヘルプ確認 OK (`python -m splat_replay --help`)
- フォルダ構成: internal_design_structure.txt と比較し一致
- uv sync 所要時間: ___ 秒

## 残課題 / 共有事項
-
```

---

## 10. 参考リンク (公式優先)

- uv Docs [https://docs.astral.sh/uv/](https://docs.astral.sh/uv/)
- uv "Creating projects" [https://docs.astral.sh/uv/concepts/projects/init/](https://docs.astral.sh/uv/concepts/projects/init/)
- Typer Docs [https://typer.tiangolo.com/](https://typer.tiangolo.com/)
- OBS Virtual Camera Guide [https://obsproject.com/kb/virtual-camera-guide](https://obsproject.com/kb/virtual-camera-guide)
- FFmpeg Download [https://ffmpeg.org/download.html](https://ffmpeg.org/download.html)
- OpenCV Install Guide [https://docs.opencv.org/4.x/d5/de5/tutorial_py_setup_in_windows.html](https://docs.opencv.org/4.x/d5/de5/tutorial_py_setup_in_windows.html)
- Tesseract User Manual [https://tesseract-ocr.github.io/](https://tesseract-ocr.github.io/)
