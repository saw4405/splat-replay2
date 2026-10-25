<details class="speech-data-notice">
  <summary>送信されるデータとログの保存場所</summary>
  <div class="notice-content">
    <p>
      文字起こしを有効/無効にする設定は次回の録画開始から反映されます。録画中に変更しても、その録画は継続します。
    </p>
    <p>
      文字起こしを有効にすると、録画中のマイク音声を Google 音声認識と Groq Whisper
      に送信します。両方の認識文とカスタム辞書は、結果を統合するため Groq に送信されます。Google
      音声認識には SpeechRecognition ライブラリ付属の共用キーを使います。
    </p>
    <p>
      「文字起こしを有効にする」と「字幕読み上げを有効化」は別設定です。字幕読み上げを有効にした場合だけ、字幕本文を
      Google Cloud Text-to-Speech に送信して音声を生成します。
    </p>
    <p>
      本アプリの認識・読み上げ処理ログには音声、認識文、辞書、モデル応答を記録せず、結果の文字数やエラー種別などを記録します。ログは
      <code>logs/splat-replay.log</code> に保存され、毎日ローテーションし、日付付きバックアップを最大30個保管します。
    </p>
    <p>
      保存場所は macOS では <code
        >~/Library/Application Support/io.github.saw4405.splatreplay/logs</code
      >、Windows ではアプリ実行ファイルと同じ場所の <code>logs</code>、開発環境では
      <code>backend/logs</code>
      です。<code>SPLAT_REPLAY_SETTINGS_FILE</code>
      を指定した場合は、その設定ファイルと同じフォルダの <code>logs</code> が使われます。
    </p>
    <p>
      ログを削除する場合はアプリを終了し、保存場所の <code>splat-replay.log</code> と日付付きバックアップを削除してください。次回起動時にログファイルが作成されます。
    </p>
    <p class="policy-links">
      公式情報:
      <a href="https://policies.google.com/terms?hl=ja" target="_blank" rel="noopener noreferrer"
        >Google 利用規約</a
      >
      <a href="https://policies.google.com/privacy?hl=ja" target="_blank" rel="noopener noreferrer"
        >Google プライバシーポリシー</a
      >
      <a href="https://console.groq.com/docs/your-data" target="_blank" rel="noopener noreferrer"
        >Groq のデータ取扱い</a
      >
      <a href="https://console.groq.com/docs/legal" target="_blank" rel="noopener noreferrer"
        >Groq の利用条件</a
      >
    </p>
  </div>
</details>

<style>
  .speech-data-notice {
    margin-top: 0.85rem;
    padding: 0.8rem 0.95rem;
    border: 1px solid rgba(var(--theme-rgb-white), 0.12);
    border-radius: 0.65rem;
    background: rgba(var(--theme-rgb-white), 0.035);
    color: var(--theme-text-secondary);
    font-size: 0.84rem;
    line-height: 1.55;
  }

  .speech-data-notice summary {
    color: var(--theme-text-primary);
    cursor: pointer;
    font-weight: 600;
  }

  .notice-content {
    display: grid;
    gap: 0.55rem;
    padding-top: 0.65rem;
  }

  p {
    margin: 0;
  }

  code {
    overflow-wrap: anywhere;
  }

  .policy-links {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem 0.75rem;
  }

  a {
    color: var(--theme-status-info);
    text-decoration: underline;
    text-underline-offset: 0.15em;
  }
</style>
