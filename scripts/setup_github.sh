#!/usr/bin/env bash
# 部活コンシェルジュ：GitHub Issue/Project運用の初期セットアップ（段階1）
#
# 作るもの:
#   - Label: area:be / area:ui / area:pdm / type:feature / type:bug / prio:high / prio:mid / prio:low
#   - Milestone: 実装計画.md R-48のスケジュール3節（due日付つき）
#   - Seed Issue: 実装計画.md 2章「実装順序（マイルストーン）」の分担をそのままIssue化（W3-1〜W3-4）
#
# 前提: gh CLI がインストール・認証済み（gh auth login 済み）で、
#       このリポジトリのディレクトリ内で実行すること。
# 再実行しても壊れないよう、作成前に既存の有無を確認する。
#
# 使い方:
#   chmod +x scripts/setup_github.sh
#   ./scripts/setup_github.sh

set -euo pipefail

if ! command -v gh >/dev/null 2>&1; then
  echo "エラー: gh CLI が見つかりません。docs/github-管理セットアップ.md の手順でインストールしてください。" >&2
  exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "エラー: gh が未認証です。'gh auth login' を先に実行してください。" >&2
  exit 1
fi

REPO="$(gh repo view --json nameWithOwner --jq .nameWithOwner)"
echo "対象リポジトリ: ${REPO}"

# ---------------------------------------------------------------------------
# 1. Label
# ---------------------------------------------------------------------------
echo ""
echo "== Label =="

create_label() {
  local name="$1" color="$2" desc="$3"
  if gh label list --limit 200 --json name --jq '.[].name' | grep -Fxq "$name"; then
    echo "  skip (既存): $name"
  else
    gh label create "$name" --color "$color" --description "$desc"
    echo "  created: $name"
  fi
}

create_label "area:be"      "1d76db" "Data/Backend（DB・API）領域"
create_label "area:ui"      "d93f0b" "App/UI（フロント）領域"
create_label "area:pdm"     "0e8a16" "PdM/共通部品・データ生成領域"
create_label "type:feature" "5319e7" "新規機能・実装タスク"
create_label "type:bug"     "b60205" "不具合修正"
create_label "prio:high"    "e11d21" "優先度：高"
create_label "prio:mid"     "fbca04" "優先度：中"
create_label "prio:low"     "c2e0c6" "優先度：低"

# ---------------------------------------------------------------------------
# 2. Milestone
# ---------------------------------------------------------------------------
echo ""
echo "== Milestone =="

create_milestone() {
  local title="$1" due="$2" desc="$3"
  if gh api "repos/${REPO}/milestones" --paginate --jq '.[].title' | grep -Fxq "$title"; then
    echo "  skip (既存): $title"
  else
    gh api "repos/${REPO}/milestones" -f title="$title" -f state="open" \
      -f description="$desc" -f due_on="$due" >/dev/null
    echo "  created: $title (due: $due)"
  fi
}

# 実装計画.md R-48 のスケジュール目安（3節）
create_milestone "〜9/29 アプリのカタチ" "2026-09-29T14:59:59Z" "R-48 第1節：アプリの形が見える状態まで"
create_milestone "〜10/2 8割"          "2026-10-02T14:59:59Z" "R-48 第2節：実装8割の目安"
create_milestone "10/7-12 最終"        "2026-10-12T14:59:59Z" "R-48 第3節：最終調整・デモ・プレゼン（10/7〜10/12）"

# ---------------------------------------------------------------------------
# 3. Seed Issue（実装計画.md 2章の分担をそのままIssue化。W3-1〜W3-4）
# ---------------------------------------------------------------------------
echo ""
echo "== Seed Issue =="
echo "  (注) milestone・assigneeは実装計画.mdに明記の対応がないため未設定。PM/担当者が後で紐付けてください。"

create_issue() {
  local title="$1" body="$2" labels="$3"
  if gh issue list --state all --search "in:title \"$title\"" --json title --jq '.[].title' | grep -Fxq "$title"; then
    echo "  skip (既存): $title"
  else
    gh issue create --title "$title" --body "$body" --label "$labels" >/dev/null
    echo "  created: $title"
  fi
}

create_issue \
  "[W3-1][BE] Supabaseスキーマ作成" \
  $'実装計画.md W3-1 より。設計.md 3章の型/制約/インデックスどおりに Supabase(PostgreSQL) のスキーマを作成する。\n\n対応: 設計.md 3章 / 一次情報コミット 9a6a20f' \
  "area:be,type:feature"

create_issue \
  "[W3-1][BE] db/client.py・Secrets接続" \
  $'実装計画.md W3-1 より。Supabase接続クライアントとStreamlit Secretsの雛形を作成する。\n\n対応: 設計.md / N-01〜N-04' \
  "area:be,type:feature"

create_issue \
  "[W3-1][PDM] ダミーデータ生成 scripts/reset_data.py" \
  $'実装計画.md W3-1 より。社員500名・部活15件、実在情報不使用、seed固定でダミーデータを再投入するスクリプト。\n\n対応: SP-78 / N-07〜N-09' \
  "area:pdm,type:feature"

create_issue \
  "[W3-2a][BE] repositories/ 実装（9本）" \
  $'実装計画.md W3-2a より。データアクセス層 repositories/ 一式（9本）を実装する。\n\n対応: 設計.md 層分離 / 実装計画.md 1.1表' \
  "area:be,type:feature"

create_issue \
  "[W3-2a][BE] services/ 実装：申込・キャンセル・初参加判定・未読・権限・操作履歴" \
  $'実装計画.md W3-2a より。サービス層 services/ 一式（申込/キャンセル/初参加判定/未読/権限/操作履歴）を実装する。\n\n対応: SP-66〜SP-71, SP-76, SP-77' \
  "area:be,type:feature"

create_issue \
  "[W3-2b][UI] app.py ルーティング・session_state" \
  $'実装計画.md W3-2b より。app.py の画面ルーティングとsession_state管理を実装する。\n\n対応: SP-01〜SP-03' \
  "area:ui,type:feature"

create_issue \
  "[W3-2b][UI] 画面：S03部活検索・S04部活詳細" \
  $'実装計画.md W3-2b より。S03部活検索・S04部活詳細（申込フォーム含む）を実装する。\n\n対応: SP-19〜SP-32' \
  "area:ui,type:feature"

create_issue \
  "[W3-2b][UI] 画面：S06メッセージ・S08社員検索・S09プロフィール・S10管理" \
  $'実装計画.md W3-2b より。S06メッセージ・S08社員検索・S09社員プロフィール・S10部活/開催の管理を実装する。\n\n対応: SP-35〜SP-62' \
  "area:ui,type:feature"

create_issue \
  "[W3-2b][UI/PDM] 画面：S05申込完了・S07通知一覧（自己完結）" \
  $'実装計画.md W3-2b／はなえ担当分（20%）より。自己完結した表示中心の画面2つ。\n\n対応: SP-33〜SP-34, SP-44〜SP-46' \
  "area:ui,area:pdm,type:feature"

create_issue \
  "[W3-2b][UI/PDM] 共通部品 rule_notice/error_banner・固定文言" \
  $'実装計画.md W3-2b／はなえ担当分より。共通部品 rule_notice / error_banner と、運営ルールの固定文言を実装する。\n\n対応: SP-04, SP-06' \
  "area:ui,area:pdm,type:feature"

create_issue \
  "[W3-3] 結合：画面×サービス×DBの通し、単体テスト添付" \
  $'実装計画.md W3-3 より。画面・サービス・DBを通しで結合し、各実装者が単体テスト(U-xx)を添付する。\n\n対応: 実装計画.md 4章 完了の定義' \
  "type:feature,prio:high"

create_issue \
  "[W3-4] テスト実行：結合(I-001〜I-120)・システム(S-01〜S-60)" \
  $'実装計画.md W3-4 より。kurosuが結合テスト・システムテストを実行し、テスト結果.mdに合否と実行ログを固定する。\n\n対応: テスト設計.md I/S節' \
  "type:feature,prio:high"

echo ""
echo "完了。GitHub Projects（board）の作成と、Issue/PRの紐付けは docs/github-管理セットアップ.md の手順に従ってください。"
