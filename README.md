# Splat Replay

Splat Replay はスプラトゥーン 3 のプレイ動画を自動で録画・整理するためのツールです。

## 開発環境構築手順
1. Python 3.13 をインストールする。
2. リポジトリ直下で `uv venv` を実行して仮想環境を作成する。
3. `./.venv/bin/activate` で仮想環境を有効化する。
4. `uv sync` で依存関係をインストールする。
5. `uv pip install -e .` でパッケージを開発モードでインストールする。
5. `splat_replay --help` を実行して CLI が表示されれば準備完了。

設定を変更したい場合は `config/settings.example.toml` を `config/settings.toml` として
コピーし、必要に応じて編集してください。アプリ起動時に自動で読み込まれます。

`splat-replay auto` コマンドを実行すると、録画からアップロードまでの一連の処理が自動で行われます。

## コントリビュート方法
1. 新しいブランチを作成し変更をコミットする。
2. `ruff format .` でコードを整形する。
3. `pytest -q` が緑色になることを確認する。
4. Pull Request を作成してレビューを受ける。