# external_spec.md Responsibility Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `docs/external_spec.md` を現行実装準拠で見直し、`利用者`・`本アプリ`・`外部要素` の責務境界が先に読める構成へ更新する。

**Architecture:** 既存の `docs/external_spec.md` を in-place で更新し、上部に「システム境界と責務分担」を新設する。構成図や後続章の主語が責務境界と揃うよう、見出し番号と導入文も合わせて整理する。ユーザー指示により、この作業ではコミットを行わない。

**Tech Stack:** Markdown, PowerShell, ripgrep, Git

---

## File Structure

- `docs/external_spec.md`
  - 外部設計書の本体。今回の主変更対象。
- `docs/superpowers/specs/2026-04-04-external-spec-responsibility-refresh-design.md`
  - 承認済みの設計メモ。責務境界と章立ての根拠として参照する。

### Task 1: 既存差分を保ったまま責務整理の反映対象を固定する

**Files:**
- Modify: `docs/external_spec.md`
- Reference: `docs/superpowers/specs/2026-04-04-external-spec-responsibility-refresh-design.md`

- [ ] **Step 1: 既存差分が局所的であることを確認する**

Run:

```powershell
git diff --cached -- docs/external_spec.md
git diff -- docs/external_spec.md
```

Expected:

- staged 側に既存差分がある場合でも、その内容が責務整理と競合しない範囲であることを確認できる。
- unstaged 側に不要な差分がないことを確認できる。

- [ ] **Step 2: 設計メモの責務定義を反映対象として固定する**

`docs/superpowers/specs/2026-04-04-external-spec-responsibility-refresh-design.md` を参照し、次の要素を `docs/external_spec.md` 上部へ反映する方針を採る。

```md
## 3. システム境界と責務分担

### 3.1 システム境界

### 3.2 主体別の責務

### 3.3 本アプリが担わない責務
```

- [ ] **Step 3: 反映前の見出し構成を確認する**

Run:

```powershell
rg -n "^## |^### " docs/external_spec.md
```

Expected: 現状の章番号と見出し構成が取得でき、挿入後にどこを繰り下げるか判断できる。

### Task 2: external_spec.md 上部へ責務整理を反映する

**Files:**
- Modify: `docs/external_spec.md`

- [ ] **Step 1: 目的とスコープの表現を現行実装準拠へ寄せる**

`## 1. 目的` と `## 2. スコープ & 利用シーン` を、次の要素を含む表現へ更新する。

```md
## 1. 目的

Windows 11 PC 上でスプラトゥーン 3 のプレイ映像を録画・確認し、
必要に応じて編集・アップロードまで行える環境を提供する。

## 2. スコープ

| 項目 | 内容 |
| --- | --- |
| 対象ユーザ | 個人プレイヤー |
| 主な利用目的 | 録画、振り返り、共有 |
| 対応ゲーム | スプラトゥーン 3 |
| 対応 OS | Windows 11 64bit |
| 主な外部連携 | HDMI / USB / OBS Studio / YouTube API / Groq API |
```

- [ ] **Step 2: `システム境界と責務分担` 節を新設する**

`## 2. スコープ` の後ろへ、次の内容をベースにした節を追加する。

```md
## 3. システム境界と責務分担

### 3.1 システム境界

- システム境界の内側は `本アプリ` のみとする。
- `Switch`、`キャプチャデバイス`、`マイク`、`OBS Studio`、`FFmpeg`、`Tesseract`、`Groq`、`YouTube` は外部要素として扱う。

### 3.2 主体別の責務

| 主体 | 担う責務 | 担わない責務 |
| --- | --- | --- |
| 利用者 | 機材・認証情報の準備、初期設定、必要時の確認や修正 | 録画制御や外部連携の内部処理 |
| 本アプリ | 録画準備、録画制御、メタデータ管理、編集、アップロード、状態表示 | ゲーム映像生成、外部製品の内部仕様保証 |
| 外部要素 | 入力、録画基盤、動画処理、OCR、文字起こし、公開基盤の提供 | 本アプリ内の進行制御や利用者向け管理 |

### 3.3 本アプリが担わない責務

- ゲーム映像そのものの生成
- 外部製品の内部仕様保証
- 外部サービス障害や認証ポリシー変更の恒久解消
```

- [ ] **Step 3: 既存の構成節を責務境界に合わせて繰り下げる**

次のように見出し番号を更新する。

```md
## 4. ハードウェア構成
## 5. 外部連携構成
### 5.1 使用技術・主要ミドルウェア
### 5.2 処理フロー概要
## 6. 機能要件
## 7. 非機能要件
## 8. ユースケース
## 9. 設定
## 10. UI
```

- [ ] **Step 4: 重複した小見出し番号も整える**

`自動編集` と `自動アップロード` のように連番が重複している箇所を、自然な連番へ修正する。

```md
### 6.3 自動編集
### 6.4 自動アップロード
### 6.5 スリープ
```

### Task 3: 見出しと責務の一貫性を自己レビューする

**Files:**
- Modify: `docs/external_spec.md`

- [ ] **Step 1: 見出し構成を確認する**

Run:

```powershell
rg -n "^## |^### " docs/external_spec.md
```

Expected:

- `## 3. システム境界と責務分担` が追加されている。
- 以降の章番号が連番になっている。

- [ ] **Step 2: 文書の上部を通読し、責務の主語が揃っているか確認する**

Run:

```powershell
Get-Content -Encoding UTF8 -Raw docs/external_spec.md
```

Expected:

- `利用者`、`本アプリ`、`外部要素` の責務境界が上部で読み取れる。
- 既存の `Node.js 24.12.0+` 変更が保持されている。
- 実装方式の詳細が責務主体として誤って独立していない。
