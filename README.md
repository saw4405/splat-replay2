<div align="center">
  <h1 style="display: flex; align-items: center; justify-content: center;">
    <img src="assets/icon.png" alt="アプリアイコン" width="32" height="32" style="margin-right: 8px; position: relative; top: 4px;" />
    Splat Replay
  </h1>
</div>

Splat Replay は、スプラトゥーン 3 のプレイ動画を自動で録画・編集・アップロードするアプリです。一連の処理を自動化することで、プレイに集中しながら記録を残せます。

<div style="display: grid; grid-template-areas:
  'setup arrow1 play arrow2 result';
  grid-template-columns: 1fr 40px 2fr 40px 1fr;
  align-items: start;
  text-align: center;
  font-family: sans-serif;
  padding-top: 10px;
  padding-bottom: 10px;
">

  <!-- 左：準備 -->
  <div style="grid-area: setup;">
    <div style="margin-bottom: 10px; background-color: #2f2f2f; padding: 10px; border-radius: 8px;">
      <span style="font-size: 24px; color: #FFD700;">🔌</span><br>
  <strong style="color: #FFD700;">機器接続</strong><br>
  <small>必要なデバイスを繋ぐだけ</small>
    </div>
    <div style="background-color: #2f2f2f; padding: 10px; border-radius: 8px;">
      <span style="font-size: 24px; color: #FFD700;">🚀</span><br>
      <strong style="color: #FFD700;">アプリ起動</strong><br>
      <small>特別な操作は不要</small>
    </div>
  </div>

  <!-- 矢印１ -->
  <div style="grid-area: arrow1; display:flex; align-items:center; align-self: center; justify-content:center; font-size:16px; color:#FFD700;">
    ▶
  </div>

  <!-- 中央：プレイ＋自動処理 -->
  <div style="grid-area: play; align-self: center;">
    <!-- プレイするだけ！ -->
    <div style="background-color: #FFD700; color: #303030; padding: 20px; border-radius: 12px; border: 2px solid #444444; margin-bottom: 12px;">
      <span style="font-size: 36px;">🎮</span><br>
      <strong style="font-size: 22px;">プレイするだけ！</strong><br>
      <small>アプリが自動で録画・編集・アップロード</small>
    </div>
  </div>

  <!-- 矢印２ -->
  <div style="grid-area: arrow2; display:flex; align-items:center;align-self: center; justify-content:center; font-size:16px; color:#A020F0;">
    ▶
  </div>

  <!-- 右：結果 -->
  <div style="grid-area: result; align-self: center;">
    <div style="background-color: #A020F0; padding: 10px; border-radius: 8px;">
      <span style="display:inline-block; width:36px; height:24px;" aria-label="YouTube">
        <svg width="36" height="24" viewBox="0 0 24 17" xmlns="http://www.w3.org/2000/svg">
          <path fill="#FF0000" d="M23.5 3.2s-.2-2.2-.9-3.1c-.8-1-1.7-1-2.1-1.1C16.9-1.5 12-1.5 12-1.5s-4.9 0-8.5.5c-.4.1-1.3.1-2.1 1.1-.7.9-.9 3.1-.9 3.1S0 5.7 0 8.1v.8c0 2.4.6 4.9.6 4.9s.2 2.2.9 3.1c.8 1 1.6 1 2.1 1.1 3.6.5 8.5.5 8.5.5s4.9 0 8.5-.5c.4-.1 1.3-.1 2.1-1.1.7-.9.9-3.1.9-3.1s.6-2.5.6-4.9v-.8c0-2.4-.6-4.9-.6-4.9Z" transform="translate(0 1.5)"/>
          <path fill="#FFFFFF" d="M9.75 5.25v6.5l5.5-3.25-5.5-3.25Z"/>
        </svg>
      </span><br>
      <strong>振り返り</strong><br>
      <small>好きなタイミングで視聴</small>
    </div>
  </div>

</div>

## 主な機能

- **自動録画**: キャプチャーデバイスからの映像をリアルタイムで監視し、バトル開始・終了等を検出して録画を開始・停止します。録画には OBS を使用しています。
- **自動編集**: 録画した動画をタイムスケジュール毎に結合し、サムネイルを自動生成します。
- **自動アップロード**: 編集済みの動画を YouTube にアップロードし、タイトル、説明、サムネイル、字幕を設定します。

![画面](./assets/gui.png)

## 使い方

インストール方法や使用方法については [ユーザーガイド](./docs/usage.md) を参照してください。

## 開発環境構築手順

1. Python 3.13 をインストールする。
2. リポジトリ直下で `uv venv` を実行して仮想環境を作成する。
3. `./.venv/bin/activate` で仮想環境を有効化する。
4. `uv sync` で依存関係をインストールする。
5. `uv pip install -e .` でパッケージを開発モードでインストールする。
6. `splat_replay --help` を実行して CLI が表示されれば準備完了。

## コントリビュート方法

1. 新しいブランチを作成し変更をコミットする。
2. `ruff format .` でコードを整形する。
3. `pytest -q` が緑色になることを確認する。
4. Pull Request を作成してレビューを受ける。
