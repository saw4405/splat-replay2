# パフォーマンステスト拡充ガイド

## 概要

このドキュメントは、Splat Replay のパフォーマンステストの現状と拡充方針を記述します。

## 現在のパフォーマンステスト構成

### テストファイル

1. **test_weapon_recognition_performance.py** - ブキ判定処理時間測定
   - レポート出力なし/ありでの処理時間比較
   - 統計情報: 平均・中央値・最小・最大・標準偏差
   - アサート: 処理完了のみ（閾値判定なし）

2. **test_weapon_display_detection_performance.py** - ブキ表示検出時間測定
   - 表示あり/なしフレームでの処理時間比較
   - 統計情報: 平均・最小・最大
   - アサート: 正確性のみ（閾値判定なし）

3. **test_frame_analyzer_performance.py** - FrameAnalyzer メソッド閾値判定
   - デフォルト閾値: 1/30秒/4 = 約8.33ms（30fpsで1フレーム当たり4解析を想定）
   - 個別閾値: OCR含む処理は緩和（例: extract_rate=100ms, extract_session_result=500ms）
   - 判定: 閾値超過時は pytest.fail() / xfail 設定可能
   - 測定回数: 5回（ITER=5）
   - 対象メソッド数: 20以上（SpeedCase配列）

4. **test_handler_performance.py** - InGamePhaseHandler 処理時間測定
   - 目標閾値: 1/30秒 = 約33.33ms
   - 測定回数: 5回（ITER=5）
   - アサート: なし（測定結果の出力のみ）

### 実行方法

```powershell
# パフォーマンステストのみ実行
task.exe test:performance

# または直接pytest
cd backend
uv run pytest -m perf -v -s
```

### perf_recorder フィクスチャ

`tests/conftest.py` で定義されており、各テストがパフォーマンスデータを記録できます。

```python
@pytest.fixture()
def perf_recorder() -> Iterator[Callable[[PerfRecord], None]]:
    # パフォーマンス記録を保存
    ...
```

## 拡充方針

### 1. 閾値の適正化

**現状**:

- `test_frame_analyzer_performance.py` のみ閾値判定あり
- 他のテストは測定のみ（Pass/Fail判定なし）

**拡充案**:

- `test_weapon_recognition_performance.py` に妥当な閾値を設定
  - 例: レポート出力なし < 100ms、レポート出力あり < 200ms
- `test_weapon_display_detection_performance.py` に閾値を設定
  - 例: 表示検出 < 20ms
- `test_handler_performance.py` に閾値判定を追加
  - 目標: < 33.33ms（30fps対応）

### 2. カバレッジ拡大

**不足している測定対象**:

- 動画編集処理（ffmpeg呼び出し）
- YouTube アップロード処理
- 画像マッチング（テンプレートマッチング）
- 対戦履歴の読み書き（JSON シリアライズ）
- メタデータ変換処理

**追加候補**:

- `test_video_processing_performance.py` - 動画編集・エンコード時間
- `test_upload_performance.py` - YouTube API呼び出し時間（モック化必要）
- `test_image_matching_performance.py` - テンプレートマッチング時間
- `test_persistence_performance.py` - ファイルI/O・JSON処理時間

### 3. xfail 設定の明確化

**現状**:

- `SpeedCase.xfail` フィールドはあるが、実際には使われていない

**対応案**:

- 現状で閾値を超えているメソッドを特定
- 将来的に改善予定のものに `xfail=True` を設定
- xfail理由をコメントで記載

### 4. 環境変数による閾値調整

**現状**:

- `test_frame_analyzer_performance.py` は `PERF_THRESHOLD_SEC` 環境変数で閾値上書き可能

**拡充案**:

- 他のテストにも環境変数オーバーライドを追加
- CI環境とローカル環境で異なる閾値を使用可能にする

### 5. 測定結果の可視化

**現状**:

- コンソール出力のみ
- `perf_recorder` がデータを記録するが、活用されていない

**拡充案**:

- JSON/CSV形式で測定結果を出力
- 時系列グラフ化（回帰検出）
- CI/CDでの自動比較

## 実装計画

### Phase 1: 既存テストの強化

1. ✅ `test_weapon_recognition_performance.py` に閾値追加
2. ✅ `test_weapon_display_detection_performance.py` に閾値追加
3. ✅ `test_handler_performance.py` にアサート追加
4. ✅ `test_frame_analyzer_performance.py` の xfail 設定見直し

### Phase 2: 新規パフォーマンステスト

1. ⏸️ `test_video_processing_performance.py` 作成（編集・エンコード）
2. ⏸️ `test_image_matching_performance.py` 作成（テンプレートマッチング）
3. ⏸️ `test_persistence_performance.py` 作成（ファイルI/O・JSON）

### Phase 3: 測定基盤の改善

1. ⏸️ 測定結果のJSON出力
2. ⏸️ 環境変数による閾値オーバーライド統一
3. ⏸️ CI/CDでの自動回帰検出

## 閾値設定の指針

### 30fps録画対応の閾値

- **1フレーム処理時間**: 1/30秒 = 33.33ms
  - 複数解析を行う場合は分割（例: 4解析なら 8.33ms/解析）

### 画像認識の閾値

- **軽量検出** (テンプレートマッチング単純): < 10ms
- **中量検出** (複数テンプレート): < 20ms
- **重量検出** (OCR含む): < 100ms

### I/O処理の閾値

- **ファイル読み** (JSON < 100KB): < 10ms
- **ファイル書き** (JSON < 100KB): < 20ms
- **動画エンコード** (1分動画): < 30秒

## 参考: test_strategy.md との関係

`docs/test_strategy.md` では、パフォーマンステストは以下のように位置づけられています:

- 分類: `performance`
- 実行タイミング: 影響変更時とリリース前
- 入口: `task.exe test:performance` または `task.exe test:release:performance`
- 目的: 閾値付き性能回帰の検出

## 変更履歴

- 2026-03-14: 初版作成（既存テスト棚卸し・拡充方針策定）
