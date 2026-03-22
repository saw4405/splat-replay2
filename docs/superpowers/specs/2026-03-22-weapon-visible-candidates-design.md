# ブキ判別 visible 候補バッファ設計

作成日: 2026-03-22

## 背景

現状のブキ判別は、検出窓内で処理できた単発フレームに強く依存している。`recognize_weapons()` 実行中は新規フレームを十分に拾えず、長い周期では実質的に「1 周期 1 枚だけ判別」に近づく。逆に全フレームを素直にキューすると、短い周期で不要な処理と遅延が増える。

また、判別候補として使う画像は `detect_weapon_display()` を通過した `visible` フレームに限定したい。薄いフレームや `display_ng` フレームを混ぜると誤判定の可能性が高い。

## 目的

- `visible` 判定済みフレームだけを複数保持し、finalize 時の再判別候補を増やす。
- `recognize_weapons()` が重い間も、時間方向の候補を少数だけ確保する。
- フレーム処理量を上限化し、全フレーム FIFO にしない。
- 既存のブキ判別途中反映と最終確定の流れを壊さない。

## 成功条件

- 検出窓内に複数の `visible` フレームが存在すれば、finalize が新しい候補から順に再判別できる。
- `recognize_weapons()` 実行中も、一定間隔でのみフレームを保持し、処理量が増えすぎない。
- `RecordingContext` から `weapon_last_visible_frame` を削除しても、既存の完了・リセットフローに回帰がない。

## 非目標

- `display_ng` フレームを救済候補に含めること。
- recognizer を複数並列実行すること。
- 設定ファイルから候補数やサンプリング間隔を動的変更できるようにすること。

## 検討した案

### 案 A: visible 候補をサービス内部に複数保持する

採用案。`WeaponDetectionService` に候補バッファを閉じ込め、`visible` フレームだけを finalization 用に保持する。`RecordingContext` には画像配列を持たせない。

- 利点: 責務が局所化される。`RecordingContext` が軽い。今回の要件に直接対応できる。
- 欠点: サービス内部状態のテストが増える。

### 案 B: visible 候補列を `RecordingContext` に持たせる

不採用。状態は明示的だが、画像配列を immutable context に多重保持することになり、責務とメモリの両面で重い。

### 案 C: visible の中から最良 1 枚だけ選び直す

不採用。`detect_weapon_display()` は bool しか返さないため、どの 1 枚が最良かを決める根拠が弱い。推測実装になりやすい。

## 採用方針

`WeaponDetectionService` に 2 種類の内部バッファを持たせる。

- `visible_candidates`: `detect_weapon_display(frame) == True` のフレームだけを保持する本命バッファ。最大 5 枚。
- `sampled_frames`: `recognize_weapons()` 実行中でも、一定間隔ごとにだけ保持する補助バッファ。最大 3 枚、間隔は 250ms を暫定値とする。

この 2 段構成により、判別画像は最後まで `visible` 限定を守りつつ、認識処理が重い間の取りこぼしを抑える。

## 変更対象

- `backend/src/splat_replay/application/services/recording/weapon_detection_service.py`
- `backend/src/splat_replay/application/services/recording/recording_context.py`
- `backend/src/splat_replay/application/use_cases/auto_recording_use_case.py`
- `backend/tests/test_weapon_detection_service.py`

## 詳細設計

### 1. 状態モデル

`WeaponDetectionService` に以下の内部状態を追加または整理する。

- `visible_candidates`: `deque[Frame]`。新しいものが末尾。最大 5 枚。
- `sampled_frames`: `deque[Frame]` または `deque[tuple[float, Frame]]`。最大 3 枚。
- `last_sampled_at`: 最後に `sampled_frames` に追加した時刻。サンプリング間隔制御に使う。

既存の `_last_checked_frame` は削除する。これは「最後に見たフレーム」であり、今回の要件である「visible 判定済み候補」と一致しないためである。

`RecordingContext.weapon_last_visible_frame` は削除する。現状の参照先は `weapon_detection_service.py`、`auto_recording_use_case.py`、およびテストのみであり、外部契約としては機能していない。候補画像の保持責務はすべてサービス内部へ寄せる。

### 2. フレーム処理フロー

通常フローは維持しつつ、認識中の補助サンプリングを追加する。

1. 検出窓内で recognizer が空いている場合は、従来どおり `detect_weapon_display()` を実行する。
2. `detect_weapon_display()` が `True` の場合:
   - フレームを `visible_candidates` に追加する。
   - その場で `recognize_weapons()` を実行する。
3. recognizer が忙しい場合:
   - そのフレームを無条件には積まない。
   - `last_sampled_at` から一定間隔以上経過している場合だけ `sampled_frames` に追加する。
   - `sampled_frames` は固定長で、古いものから破棄する。
4. recognizer が空いたら、`sampled_frames` を先に処理する。
   - 順序は古いものから新しいものへ進める。
   - 各フレームを `detect_weapon_display()` に通し、`True` のものだけ `visible_candidates` に昇格させる。
   - 昇格したフレームでは通常どおり `recognize_weapons()` を実行する。

この設計では、通常判別中に受けた全フレームはキューされない。一定間隔サンプリングで上限を設けることで、処理量と遅延を制御する。

### 3. finalize フロー

finalize では `visible_candidates` だけを使用する。

1. `visible_candidates` を新しい順に取り出す。
2. その時点で未確定のスロットだけを `target_slots` として `recognize_weapons()` を実行する。
3. 全スロットが確定した時点で打ち切る。
4. 候補ごとの再判別に失敗しても次候補へ進む。
5. 全候補を試しても未確定が残る場合だけ `不明` で埋める。

未一致レポート出力は finalize の最初の再判別候補で 1 回だけ試す。複数候補での連続出力は副作用が増え、デバッグ価値よりコストが大きい。

### 4. 状態遷移

以下のタイミングで `visible_candidates` と `sampled_frames` を必ず空にする。

- `request_cancel()`
- 別バトルへの切り替え
- finalize 完了

これにより、前バトルの候補が次バトルへ混入しないことを保証する。

### 5. エラー処理

- `detect_weapon_display()` が例外で失敗したフレームは `visible` 未確認のため候補にしない。
- `recognize_weapons()` が失敗しても、そのフレームが `visible` 済みなら `visible_candidates` には残す。
- finalize 中に一部候補の再判別が失敗しても、後続候補の試行を継続する。
- 未一致レポートの保存に失敗しても、最終判別そのものは継続する。

## インターフェース影響

### `RecordingContext`

以下を削除する。

- `weapon_last_visible_frame: Optional[Frame]`

これに伴い、`auto_recording_use_case.py` の `_is_reset_context()` からも `weapon_last_visible_frame is None` の条件を削除する。

### `WeaponDetectionService`

内部状態と内部ヘルパーを追加するが、外部公開メソッドのシグネチャは変えない。

## テスト方針

最低限、以下を自動テストで担保する。

- 複数の `visible` フレームがある場合、finalize が新しい候補から順に試すこと。
- `recognize_weapons()` 実行中でも、生フレーム保持は一定間隔サンプリングに制限されること。
- `sampled_frames` に入ったフレームのうち、`detect_weapon_display()` を通過したものだけが `visible_candidates` に昇格すること。
- 一部候補の再判別が失敗しても、次候補へ進み、埋められるスロットは埋まること。
- `request_cancel()`、別バトル切替、finalize 完了で内部バッファが消えること。
- `weapon_last_visible_frame` 削除後も、既存の完了・リセットフローに回帰がないこと。

## リスクと緩和策

- サンプリング間隔が短すぎると処理量が増える。
  - 緩和策: 250ms を初期値とし、定数として切り出して後から調整可能にする。
- サンプリング間隔が長すぎると候補の時間密度が下がる。
  - 緩和策: テストと実運用ログで候補数を確認し、必要なら 200ms 付近まで再調整する。
- recognizer の並行安全性は未確認である。
  - 緩和策: recognizer の並列呼び出しは導入しない。

## 実装順の提案

1. 既存の `_last_checked_frame` フォールバックを撤去する。
2. `RecordingContext` から `weapon_last_visible_frame` を削除し、関連参照とテストを更新する。
3. `WeaponDetectionService` に `visible_candidates` と `sampled_frames` を追加する。
4. 通常フローへ補助サンプリングと visible 昇格を組み込む。
5. finalize を複数候補対応に変更する。
6. 回帰テストと新規テストを追加する。

## 未確認事項

- 250ms / 3 枚 / 5 枚という上限値は暫定であり、実運用ログでの確認が必要である。
