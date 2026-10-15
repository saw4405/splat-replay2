# パフォーマンステストガイド

性能に影響する変更とリリース前の検証に使います。テストの選定と合否の扱いは [テスト戦略](../../docs/test_strategy.md) に従います。

## 現在の構成

対象は `backend/tests/performance/` にあります。

| ファイル | 保証対象 |
| --- | --- |
| `test_frame_analyzer_performance.py` | 画面判定・XP・結果解析の平均処理時間 |
| `test_weapon_recognition_performance.py` | レポート出力なしのブキ認識の正確性と平均処理時間 |
| `test_weapon_display_detection_performance.py` | ブキ表示あり・なしの正確性と平均検出時間 |
| `test_handler_performance.py` | InGamePhaseHandler のフレーム処理時間 |
| `test_frame_capture_producer_performance.py` | 電源 ON 待機中の取得間隔と停止時の応答時間 |
| `test_recording_start_latency.py` | 字幕準備が録画開始を待たせないこと |

閾値の正本は各テストです。現在の主要な値は次の通りです。

- FrameAnalyzer の既定値: `(1 / 30 / 4) × 3 = 25 ms`。
- FrameAnalyzer の個別値: XP 取得 `extract_rate` は 1,000 ms、結果解析 `extract_session_result` は 3,000 ms。個別値が既定値より優先されます。
- InGamePhaseHandler: `(1 / 30) × 2 ≈ 66.67 ms`。
- FrameAnalyzer と InGamePhaseHandler の本計測は各 5 回です。プレビューの 60 FPS 要求は、これらの判定処理の実行頻度や時間予算とは別です。

## 実行する

リポジトリルートで実行します。Windows は `task.exe`、macOS は `task` を使います。

```powershell
# 閾値付き性能回帰だけを実行
task.exe test:performance

# 性能を含むリリース前の総合確認
task.exe test:release:performance

# 時間予算が未確定の観測用測定（リリース合否には使わない）
task.exe test:benchmark
```

対象を絞る場合は、`backend` を作業ディレクトリにして repo 管理ラッパーを使います。

```sh
uv run python ../scripts/run-backend-pytest.py -q -m "perf and not benchmark" tests/performance/test_frame_analyzer_performance.py
```

## 測定条件をそろえる

- 比較するコード、OS、Python・OpenCV 等のバージョン、画像・動画、電源状態、プロセス優先度、同時に動くアプリを記録します。旧版と変更版は同じ条件で比較します。
- Windows での比較は AC 電源接続と通常のプロセス優先度をそろえます。バッテリー駆動や優先度が異なる測定値を、そのまま変更による劣化・改善と扱いません。
- performance の共通 fixture は本番と同じ OpenCV 初期化を呼びます。Windows では worker 数が 4 を超える場合だけ上限 4 を適用し、macOS の値は変更しません。
- FrameAnalyzer の `PERF_THRESHOLD_SEC` は既定閾値の上書き用です。個別閾値は上書きしません。診断目的で値を変えた結果を、既存基準の合格として報告しないでください。
- 閾値超過を理由に `xfail`、skip、閾値緩和、`benchmark` 化で合格にしません。測定条件を確認して実装改善を検討します。

## 結果を保存する

`backend/tests/conftest.py` の `perf_recorder` は、利用しているテストの測定値を記録します。全テストが同じ形式の記録を出すわけではありません。
`PERF_RECORD_PATH` を指定すると、各テスト終了時に JSON Lines として追記します。相対パスは `backend/tests/` が基準です。

Windows PowerShell の例:

```powershell
$env:PERF_RECORD_PATH = "../outputs/performance/current.jsonl"
task.exe test:performance
Remove-Item Env:PERF_RECORD_PATH
```

macOS の例:

```sh
PERF_RECORD_PATH=../outputs/performance/current.jsonl task test:performance
```

この例の保存先は Git 対象外の `backend/outputs/performance/` です。測定ごとに別の出力先を使い、pytest のログ・終了コードと測定条件も残してください。生成物はコミットしません。
