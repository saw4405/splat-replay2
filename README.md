# Splat Replay

Splat Replay はスプラトゥーン 3 のプレイ動画を自動で録画・整理するためのツールです。

## 開発環境構築手順
1. Python 3.13 をインストールする。
2. リポジトリ直下で `uv venv` を実行して仮想環境を作成する。
3. `./.venv/bin/activate` で仮想環境を有効化する。
4. `uv sync` で依存関係をインストールする。
5. `python -m splat_replay --help` を実行して CLI が表示されれば準備完了。

## コントリビュート方法
1. 新しいブランチを作成し変更をコミットする。
2. `ruff format .` でコードを整形する。
3. `pytest -q` が緑色になることを確認する。
4. Pull Request を作成してレビューを受ける。
