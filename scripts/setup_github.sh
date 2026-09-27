#!/usr/bin/env bash
# 部活コンシェルジュ：GitHub Label/Milestone運用の初期セットアップ（段階1）
#
# 作るもの:
#   - Label: area:be / area:ui / area:pdm / type:feature / type:bug / prio:high / prio:mid / prio:low
#   - Milestone: 実装計画.md R-48のスケジュール3節（due日付つき）
#
# Issue作成は 実装ガイド/create_issues.sh で行う（本スクリプトはseed Issueを作らない。
# kurosuの横断レビュー裁定・T-016により、create_issues.sh（36件）を正としてseed Issue作成は廃止した）。
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

echo ""
echo "完了。Issueの作成は 実装ガイド/create_issues.sh を実行してください。"
echo "GitHub Projects（board）の作成と、Issue/PRの紐付けは docs/github-管理セットアップ.md の手順に従ってください。"
