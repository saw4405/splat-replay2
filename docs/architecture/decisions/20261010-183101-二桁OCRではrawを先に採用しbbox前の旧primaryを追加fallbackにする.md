# 二桁 OCR では raw を先に採用し bbox 前の旧 primary を追加 fallback にする

- ID: 20261010-183101
- 状態: accepted
- 日時: 2026-10-10T18:31:01+09:00
- 判断者: ユーザー

## 目的・問題

キル・デス・スペシャル回数の認識で、前景 bbox と白 15 px の余白を使う変更は、Windows で従来誤読していた 4 件の `7→1` を解消しました。一方、別の Windows 結果画像 `battle_result_14.png` では、death の期待値 `5` を `13` と読む回帰が残りました。修正候補の primary は `0`、既存 fallback の最後は `13` を返していました。

前景 bbox の改善と既知の `5→13` 回帰修正を両立し、Mac と Windows で同じ認識順序を使う必要がありました。

## 前提・制約

- 先行する変更は、bbox 前の画像を前景の外接矩形に切り出し、白 15 px の余白を加えた画像を primary にするものでした。先行変更の当初承認は追加 fallback の承認を含みません。
- 2 桁認識を raw から先に採用する既存順序を維持します。Mac の既知 fixture では raw から `11` を正しく読めています。
- 追加する OCR 呼び出しは既存の OCRPort を通し、OS 別・fixture 別の分岐を設けません。
- 性能閾値、期待値、skip 条件は変更しません。
- Windows の実 OCR 性能 3 項目は閾値を超えたままです。過去 baseline と今回の測定条件は同一ではなく、原因は未確認です。

## 判断

固定幅の 2 桁統計値の認識順序を次のとおりにします。

1. raw 画像を OCR し、数字が 2 桁読めた場合はその結果を採用します。
2. raw で 2 桁読めなかった場合だけ、bbox 前の旧 primary 画像を 1 回 OCR します。この画像は death / special の横方向 crop を適用した後、前景 bbox と白余白を加える前の画像です。ここで 2 桁読めた場合は採用します。
3. 旧 primary でも 2 桁読めない場合は、既存の 3 つの前処理候補へ進みます。

この順序は Windows の既知 `5→13` を直しつつ、raw が正しく 2 桁を返す場合の先行採用を維持します。追加候補は Mac と Windows で共通に使います。

## 検討した選択肢と棄却理由

- **bbox primary と既存 3 候補を維持する:** 既知画像で primary が `0`、既存 fallback が最後に `13` を返すため、回帰を解消できません。
- **余白を 20 px に増やす:** 該当画像の比較で改善しませんでした。
- **raw より先に旧 primary を試す:** 採用しません。raw の 2 桁結果を先に採用する順序を維持し、Mac の既知 `11` fixture を保護します。
- **固定幅表示に特化した認識方式や確信度を使う:** 助言役が理想案として挙げましたが、今回の変更範囲を超え、具体的な方式と評価は未確認です。
- **共通の単一前処理で既知画像を満たす:** 余白 20 px の比較では成立せず、両 OS で成立する別の共通前処理は確認できていません。

設計助言役は、OCRPort 経由の追加候補は既存構造に整合すると評価しました。一方、旧 primary を既存候補より先に置くトレードオフを既存指針から選べず、ユーザー判断が必要としました。ユーザーは、raw の優先を保ち、旧 primary を既存 3 候補より前に試す案を承認しました。

## 適用範囲

Mac と Windows のバトル結果画面にあるキル・デス・スペシャル回数の 2 桁 OCR に適用します。raw が 2 桁を返せないときだけ旧 primary を試し、その後に既存候補へ進む認識経路が対象です。

## 適用しない範囲

- 武器認識、他の画面の OCR、汎用 OCR の候補順序は変更しません。
- 性能閾値、テスト期待値、skip 条件を変更しません。
- Windows build、検証 ZIP の転送、push はこの判断で承認されていません。
- 今回の判断を一般的な設計指針へ昇格しません。

## 期待する効果

- Windows の既知 `battle_result_14.png` death を `5` として認識し、前景 bbox による既知 4 件の `7→1` 改善を保ちます。
- raw で 2 桁を読める場合は旧 primary を追加で呼び出さず、従来どおり raw の結果を優先します。
- 検証した 9 fixture では Mac・Windows とも全件正解になりました。

## 受け入れる欠点・リスク

- 旧 primary が誤った 2 桁を返す入力では、その結果が後段の既存候補より先に採用され、後段に正解があっても遮る可能性があります。2 桁という条件は形式を見ているだけで、認識の正しさを保証しません。
- raw が 2 桁を返さず旧 primary も 2 桁を返さない場合は OCR 呼び出しが 1 回増えます。未見入力全体での遅延影響は未確認です。
- 既知 fixture の認識成功は、未見画像全般の正しさを保証しません。
- Windows の性能検査は 3 項目とも失敗のままです。この判断は性能合格を意味しません。

## 再検討条件

- 未見画像または実利用画像で、旧 primary の誤った 2 桁結果が後段の正しい候補を遮ったとき。
- Mac または Windows で OCR の正解が失われる回帰が確認されたとき。
- 実 OCR 条件を揃えた性能測定で追加候補の遅延影響が確認されたとき、または性能閾値を満たすために候補順序の再選択が必要になったとき。
- 固定幅認識や確信度による採用基準を評価できる具体案が得られたとき。

## 関連する設計指針

`docs/architecture/principles/README.md` に登録済みの設計指針はありません。Domain 層の外部依存をポート経由にする既存方針は OCRPort の利用と整合しますが、OCR 候補の優先順は選別しません。今回の判断から新しい指針は作成しません。

## 関連 ADR

- `20260828-081339-replay E2Eの武器認識をfixture観測アダプタで分離する`: workflow E2E と実 OCR の精度・性能保証を分ける判断です。本 ADR の候補順序は扱わず、置換もしません。
- `20260927-153139-macOSのFFmpeg・Tesseract・日本語OCRデータをアプリ内導入しHomebrew初回導入はTerminalで利用者が確認する`: macOS の OCR 依存導入方式を扱います。本 ADR の候補順序は扱わず、置換もしません。

## 置換・追補関係

先行する前景 bbox と白 15 px の余白を使う修正は維持し、raw が 2 桁を読めない場合に限って、bbox 前の旧 primary を既存 3 候補より先に試す規則を追補します。既存 ADR を置換しません。

## 調査した根拠

### 事実

- 親会話の実 OCR 検証報告では、先行 bbox 修正の Windows 109 件中に `battle_result_14.png` death の `5→13` が残り、余白 20 px でも解消しませんでした。
- 9 fixture の候補比較では、Mac は 9/9 正解、Windows は比較元 8/9 から候補 9/9 へ改善しました。Windows の該当 fixture では bbox primary が `0`、bbox 前旧 primary が `05` を返しました。この 9 fixture 比較は pytest ではなく、既存抽出器と隔離候補へ画像を直接適用した診断です。
- 隔離した候補の既存 FrameAnalyzer 109 件は、Mac・Windows とも 109 pass、0 fail、0 error、0 skip でした。
- Mac の性能検査は `extract_session_result` の 1 件が pass しました。平均値は記録されていません。JUnit の case time `3.906` 秒を平均値として扱いません。
- Windows の性能検査は 3 件すべて失敗しました。`detect_power_off` は 51.541 ms（閾値 25 ms）、`extract_session_result` は 3827.543 ms（3000 ms）、`display_detection_visible` は 1157.163 ms（250 ms）でした。閾値は変更されていません。
- 過去の Windows `extract_session_result` baseline は DummyOCR 条件で、今回の実 Tesseract 結果と直接比較できません。性能超過の原因は未確認です。
- ユーザー承認後の候補適用は別担当が実施したと親会話に記録されています。本 ADR はそのコード変更や build の完了を主張しません。

### 未確認事項

- 未見画像全体で、旧 primary が誤った 2 桁を返す頻度は未確認です。
- 追加候補による長期的な性能影響は未確認です。
- Mac の performance case time `3.906` 秒から平均実行時間は分かりません。
- Windows 性能超過がこの候補変更によるものかは未確認です。

### 参照したプロジェクト内資料

- `backend/outputs/windows-diagnostics/20261010-performance-recheck/windows-result14-margin-diagnostic/legacy-primary-fallback.diff`
- `backend/outputs/windows-diagnostics/20261010-performance-recheck/windows-result14-margin-diagnostic/parent-nine-fixture-comparison-review.json`
- `backend/outputs/windows-diagnostics/20261010-performance-recheck/windows-result14-margin-diagnostic/windows-legacy-primary-fallback-diagnostic.json`
- `backend/outputs/windows-diagnostics/20261010-performance-recheck/windows-run-20261010-182019-b6dc6fd8/performance-recheck-legacy-primary-20261010-182019-b6dc6fd8/parent-candidate-windows-result-review.json`
- `backend/outputs/macos-diagnostics/20261010-kill-record-bbox-fix/candidate-validation/parent-candidate-result-review.json`
- `backend/outputs/macos-diagnostics/20261010-kill-record-bbox-fix/candidate-validation/candidate-validation-summary.json`
- 親会話中の設計助言役 `/root/ocr_fallback_advice` の助言結果。候補順序は既存指針で選べず、ユーザー判断が必要との結論でした。

## ユーザー発言の原文

### 先行修正の承認

> 1. 適用して

これは前景 bbox と白 15 px の余白を使う先行修正への回答です。今回の旧 primary fallback 順序を含む承認ではありません。

### 本判断の質問と回答

質問:

> Windowsで残った「5→13」の誤読を直す追加修正を適用しますか？ 生画像で2桁が読めない場合だけ従来の画像で再認識する案です。Mac・Windowsとも認識109項目に合格しましたが、Windowsの性能3項目は上限超過のままです。OCR候補の優先順を変える判断について、AGENTS.mdの設計判断契約とAstraの助言に従い確認します。

回答:

> 追加修正を適用する（推奨）

この回答は直前の質問に対する承認として記録します。性能検査の失敗を合格扱いにする承認、または Windows build・ZIP 転送・push の承認ではありません。

## 会話カバレッジ

| 会話上の判断要素 | ADR の記録先 | 点検 |
| --- | --- | --- |
| 14 行の bbox・白 15 px 修正で既知の 4 件を直したが `5→13` の回帰が残った | 目的・問題、前提・制約、調査した根拠 | 原文の経緯を維持しました |
| raw を優先し、raw が 2 桁でない場合だけ bbox 前の旧 primary を一度試し、その後に既存 3 候補へ進む | 判断、適用範囲 | 質問と承認の範囲に限定しました |
| 余白 20 px は解決せず、raw 優先は Mac の `11` を保つ | 検討した選択肢と棄却理由、判断 | 候補の理由と既知事例を併記しました |
| 9 fixture と 109 件は成功したが Windows 性能 3 件は未達。過去 baseline と直接比較できない | 調査した根拠、受け入れる欠点・リスク | 認識と性能を分け、原因を断定していません |
| 旧 primary の誤った 2 桁が後続の正解を遮る可能性 | 受け入れる欠点・リスク、再検討条件 | 未見入力のリスクとして保持しました |
| 適用承認と build・ZIP 転送・push の承認は別 | ユーザー発言の原文、適用しない範囲 | 受諾範囲を拡張していません |

## 記録時セルフレビュー

- 指定された親トランスクリプトを自分で再走査し、先行修正の承認、今回の質問、回答、経緯を照合しました。
- 質問と回答は原文で併記し、`追加修正を適用する（推奨）` の対象を明示しました。
- 事実、未確認事項、性能原因の不明点を分け、平均性能や未見画像の精度を補っていません。
- 旧 primary が誤った 2 桁を返すリスクと性能未達を隠していません。
- 書き込みは本 ADR だけです。設計指針、コード、テスト、AGENTS.md、Git の状態は変更していません。
