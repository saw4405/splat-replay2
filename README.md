<!-- markdownlint-disable MD033 MD041 -->
<!-- 理由: アイコン付きタイトルの中央揃えには HTML が必要（MD033）、視覚的な表現を優先（MD041） -->
<!-- 将来の解消方針: GitHub の Markdown レンダリングが画像+テキストの flexbox 配置をサポートするか、別の表現方法を検討 -->
<div align="center">
  <h1 style="display: flex; align-items: center; justify-content: center;">
    <img src="backend/assets/icon.png" alt="アプリアイコン" width="32" height="32" style="margin-right: 8px; position: relative; top: 4px;" />
    Splat Replay
  </h1>
</div>
<!-- markdownlint-enable MD033 MD041 -->

Splat Replay は、スプラトゥーン 3 のプレイ動画を自動で録画・編集・アップロードするアプリです。一連の処理を自動化することで、プレイに集中しながら記録を残せます。

![コンセプト](./backend/assets/concept.svg)

## 主な機能

- **自動録画**:  
  映像をリアルタイムで監視し、バトル開始・終了に応じて録画を開始・停止します。録画には OBS を使用しています。

- **自動編集**:  
  録画した動画をタイムスケジュール毎に結合し、サムネイルを自動生成します。

- **自動アップロード**:  
  編集した動画を YouTube にアップロードします。タイトル・説明・サムネイル・字幕を合わせて設定します。

![画面](./backend/assets/gui.png)

## 使い方

### インストール

Windows:

1. [GitHub リリースページ](https://github.com/saw4405/splat-replay2/releases)にある最新のリリースから、`SplatReplay.zip` をダウンロードする
2. ダウンロードした ZIP ファイルを展開する

### 起動

Windows:

1. 展開したフォルダ内の `SplatReplay.exe` を実行してアプリを起動する
2. （初回のみ）セットアップウィザードに従い、必要なアプリのインストールや設定を行う
3. Switch の映像を監視し、設定に応じてバトルを自動録画する。編集・アップロードは「処理開始」から手動で行うか、対応設定を有効にして電源 OFF 検出後の予告から開始する

Apple Silicon macOS 版は開発・検証用で、正式対応ではありません。実ゲームの録画からアップロードなど一部の利用者確認は済んでいますが、全機能の受け入れは未完了です。確認範囲と未確認事項は[macOS 対応調査](./docs/macos_support_plan.md)を、DMG の導入手順は[ユーザーガイド](./docs/usage.md#macos-apple-silicon)を参照してください。

## 開発者向け情報

このプロジェクトの開発に参加する場合は、以下のドキュメントを参照してください：

- **[開発ガイド](./docs/DEVELOPMENT.md)** - 環境構築、テスト実行、品質確認の手順
- [テスト戦略](./docs/test_strategy.md) - テストの分類と戦略の詳細
- [動画リプレイ入力による E2E 回帰テスト](./docs/e2e_replay_test.md) - E2E テストの詳細
