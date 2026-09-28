#!/usr/bin/env python3
"""GitHub Issue/PR/Milestoneを集計し、site/index.html にダッシュボードを生成する。

外部ライブラリ非依存（標準ライブラリのみ）。GitHub Actions の GITHUB_TOKEN で動く。

環境変数:
  GITHUB_TOKEN       - GitHub API 呼び出し用トークン（必須）
  GITHUB_REPOSITORY  - "owner/repo" 形式（GitHub Actions では自動設定）

実行:
  GITHUB_TOKEN=xxx GITHUB_REPOSITORY=owner/repo python scripts/gen_dashboard.py
"""

from __future__ import annotations

import html
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone

API_ROOT = "https://api.github.com"
PER_PAGE = 100

AREA_LABELS = {
    "area:be": {"name": "BE/DB", "color": "#2563eb"},
    "area:ui": {"name": "UI/フロント", "color": "#db2777"},
    "area:pdm": {"name": "PdM", "color": "#16a34a"},
}
UNASSIGNED = "(未アサイン)"


def api_get(path: str, token: str, params: dict | None = None) -> list | dict:
    """GitHub REST APIをGETし、ページネーションがあれば全件つなげて返す。"""
    items: list = []
    page = 1
    while True:
        query = dict(params or {})
        query["per_page"] = PER_PAGE
        query["page"] = page
        qs = "&".join(f"{k}={v}" for k, v in query.items())
        url = f"{API_ROOT}{path}?{qs}"
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "bukatsu-concierge-dashboard",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="ignore")
            print(f"[gen_dashboard] API error {e.code} for {url}: {body}", file=sys.stderr)
            raise

        if isinstance(data, dict):
            # 単一オブジェクト応答（ページネーション不要）はそのまま返す
            return data

        items.extend(data)
        if len(data) < PER_PAGE:
            break
        page += 1
    return items


def fetch_issues_and_prs(owner: str, repo: str, token: str) -> list[dict]:
    """/issues は Issue と PR の両方を含む（PRはpull_requestキーを持つ）。"""
    return api_get(f"/repos/{owner}/{repo}/issues", token, {"state": "all"})


def fetch_milestones(owner: str, repo: str, token: str) -> list[dict]:
    return api_get(f"/repos/{owner}/{repo}/milestones", token, {"state": "all"})


def is_pull_request(item: dict) -> bool:
    return "pull_request" in item


def is_merged(item: dict) -> bool:
    pr = item.get("pull_request") or {}
    return bool(pr.get("merged_at"))


def is_done(item: dict) -> bool:
    """集計上の「完了」判定。

    Issueはstate=='closed'で完了。PRはマージされて初めて完了（is_merged）とする。
    クローズされただけで未マージのPR（取り下げ等）は「完了」に含めない
    （kurosuの横断レビュー指摘・T-016で修正）。
    """
    if is_pull_request(item):
        return is_merged(item)
    return item.get("state") == "closed"


def is_counted(item: dict) -> bool:
    """集計対象かどうか。

    マージされずクローズされたPRは、完了でも未完了（作業中）でもないため、
    担当者別・Milestone別の集計そのものから除外する。
    """
    if is_pull_request(item) and item.get("state") == "closed" and not is_merged(item):
        return False
    return True


def area_labels_of(item: dict) -> list[str]:
    names = [lbl.get("name", "") for lbl in item.get("labels", []) if isinstance(lbl, dict)]
    return [n for n in names if n in AREA_LABELS]


def assignees_of(item: dict) -> list[str]:
    logins = [a.get("login") for a in item.get("assignees", []) if a.get("login")]
    return logins or [UNASSIGNED]


def aggregate_by_assignee(items: list[dict]) -> dict:
    board: dict[str, dict] = {}
    for it in items:
        if not is_counted(it):
            continue
        for login in assignees_of(it):
            entry = board.setdefault(
                login,
                {"open": 0, "closed": 0, "areas": {k: 0 for k in AREA_LABELS}, "tasks": []},
            )
            entry["tasks"].append(task_of(it, login))
            if is_done(it):
                entry["closed"] += 1
            else:
                entry["open"] += 1
            for area in area_labels_of(it):
                entry["areas"][area] += 1
    return board


def aggregate_by_milestone(items: list[dict], milestones: list[dict]) -> list[dict]:
    counts: dict[str, dict] = {}
    for it in items:
        if not is_counted(it):
            continue
        ms = it.get("milestone")
        if not ms:
            continue
        title = ms.get("title", "")
        entry = counts.setdefault(title, {"open": 0, "closed": 0, "tasks": []})
        entry["tasks"].append(task_of(it, ", ".join(assignees_of(it))))
        if is_done(it):
            entry["closed"] += 1
        else:
            entry["open"] += 1

    result = []
    for ms in milestones:
        title = ms.get("title", "")
        c = counts.get(title, {"open": 0, "closed": 0, "tasks": []})
        total = c["open"] + c["closed"]
        pct = round(c["closed"] / total * 100) if total else 0
        result.append(
            {
                "title": title,
                "due_on": ms.get("due_on"),
                "open": c["open"],
                "closed": c["closed"],
                "total": total,
                "pct": pct,
                "state": ms.get("state"),
                "tasks": c["tasks"],
            }
        )
    # 予定日順（未設定は末尾）
    result.sort(key=lambda m: (m["due_on"] is None, m["due_on"] or ""))
    return result


def recent_merged_prs(items: list[dict], limit: int = 10) -> list[dict]:
    merged = [it for it in items if is_pull_request(it) and is_merged(it)]
    merged.sort(key=lambda it: it["pull_request"]["merged_at"], reverse=True)
    out = []
    for it in merged[:limit]:
        out.append(
            {
                "number": it["number"],
                "title": it["title"],
                "html_url": it["html_url"],
                "merged_at": it["pull_request"]["merged_at"],
                "areas": area_labels_of(it),
                "user": (it.get("user") or {}).get("login", ""),
            }
        )
    return out


def fmt_dt(iso: str | None) -> str:
    if not iso:
        return "-"
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return iso
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def area_chips(entry_areas: dict) -> str:
    chips = []
    for key, count in entry_areas.items():
        if count <= 0:
            continue
        meta = AREA_LABELS[key]
        chips.append(
            f'<span class="chip" style="--chip-color:{meta["color"]}">'
            f'{html.escape(meta["name"])} {count}</span>'
        )
    return "".join(chips) if chips else '<span class="chip chip-empty">-</span>'


JST = timezone(timedelta(hours=9))


def task_of(item: dict, login: str) -> dict:
    """担当者カードの内訳（タスク行）用に、Issue/PR 1件分の表示データを作る。"""
    ms = item.get("milestone") or {}
    return {
        "number": item.get("number"),
        "title": item.get("title", ""),
        "assignee": login,
        "done": is_done(item),
        "is_pr": is_pull_request(item),
        "milestone_title": ms.get("title", ""),
        "due_on": ms.get("due_on"),
        "areas": area_labels_of(item),
        "html_url": item.get("html_url", ""),
    }


def due_date_of(due_on: str | None) -> date | None:
    """Milestoneのdue_on(ISO8601)を日本時間の日付にする。不正・未設定はNone。"""
    if not due_on:
        return None
    try:
        dt = datetime.fromisoformat(due_on.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(JST).date()


def deadline_badge(done: bool, due_on: str | None, today: date) -> tuple[str, str]:
    """状態バッジ (ラベル, CSSクラス)。期限=Milestoneのdue_on、todayは実行日(JST)。"""
    if done:
        return "完了", "badge-done"
    due = due_date_of(due_on)
    if due is None:
        return "期限未設定", "badge-none"
    diff = (due - today).days
    if diff < 0:
        return f"遅延 {-diff}日", "badge-late"
    if diff == 0:
        return "本日締切", "badge-today"
    return f"期限内(残{diff}日)", "badge-ok"


def render_task_rows(tasks: list[dict], today: date, show_milestone: bool = True) -> str:
    def sort_key(t):
        due = due_date_of(t["due_on"])
        return (t["done"], due is None, due or date.max, t["number"] or 0)

    rows = []
    for t in sorted(tasks, key=sort_key):
        label, cls = deadline_badge(t["done"], t["due_on"], today)
        due = due_date_of(t["due_on"])
        due_str = due.isoformat() if due else "-"
        state = "完了" if t["done"] else "未完了"
        kind = "PR " if t["is_pr"] else ""
        areas = "".join(
            f'<span class="chip" style="--chip-color:{AREA_LABELS[a]["color"]}">{html.escape(AREA_LABELS[a]["name"])}</span>'
            for a in t["areas"]
        )
        ms_part = f" ・ {html.escape(t['milestone_title'] or 'Milestone未設定')}" if show_milestone else ""
        rows.append(
            f"""
            <li class="task {'task-done' if t['done'] else 'task-open'}">
              <div class="task-main">
                <a href="{html.escape(t['html_url'])}" target="_blank" rel="noopener">{kind}#{t['number']} {html.escape(t['title'])}</a>
                <span class="badge {cls}">{html.escape(label)}</span>
              </div>
              <div class="task-meta">担当: {html.escape(t['assignee'])} ・ 状態: {state}{ms_part} ・ 期限: {due_str} {areas}</div>
            </li>
            """
        )
    return f'<ul class="task-list">{"".join(rows)}</ul>' if rows else ""


def render_assignee_cards(board: dict, today: date | None = None) -> str:
    today = today or datetime.now(JST).date()
    cards = []
    # 未完了が多い順→名前順
    ordered = sorted(board.items(), key=lambda kv: (-kv[1]["open"], kv[0]))
    for login, e in ordered:
        total = e["open"] + e["closed"]
        pct = round(e["closed"] / total * 100) if total else 0
        cards.append(
            f"""
            <div class="card">
              <div class="card-head">
                <span class="avatar">{html.escape(login[:1].upper() if login != UNASSIGNED else "?")}</span>
                <span class="login">{html.escape(login)}</span>
              </div>
              <div class="stats">
                <div class="stat"><span class="num">{e['closed']}</span><span class="label">完了</span></div>
                <div class="stat"><span class="num">{e['open']}</span><span class="label">未完了</span></div>
                <div class="stat"><span class="num">{pct}%</span><span class="label">進捗</span></div>
              </div>
              <div class="progress"><div class="progress-bar" style="width:{pct}%"></div></div>
              <div class="chips">{area_chips(e['areas'])}</div>
              <details class="breakdown">
                <summary>内訳を開く</summary>
                {render_task_rows(e['tasks'], today)}
              </details>
            </div>
            """
        )
    if not cards:
        return '<p class="empty">Issue/PRがまだありません。</p>'
    return "".join(cards)


def render_milestone_bars(milestones: list[dict], today: date | None = None) -> str:
    today = today or datetime.now(JST).date()
    rows = []
    for m in milestones:
        rows.append(
            f"""
            <div class="milestone">
              <div class="milestone-head">
                <span class="ms-title">{html.escape(m['title'])}</span>
                <span class="ms-due">期限: {html.escape((m['due_on'] or '-')[:10])}</span>
              </div>
              <div class="progress progress-lg">
                <div class="progress-bar" style="width:{m['pct']}%"></div>
              </div>
              <div class="ms-counts">完了 {m['closed']} / 全体 {m['total']}（{m['pct']}%）</div>
              <details class="breakdown">
                <summary>内訳を開く</summary>
                {render_task_rows(m.get('tasks', []), today, show_milestone=False)
                 or '<p class="empty">このMilestoneのタスクはまだありません</p>'}
              </details>
            </div>
            """
        )
    if not rows:
        return '<p class="empty">Milestoneが未作成です。</p>'
    return "".join(rows)


def render_recent_prs(prs: list[dict]) -> str:
    if not prs:
        return '<p class="empty">マージ済みPRはまだありません。</p>'
    items = []
    for pr in prs:
        chips = "".join(
            f'<span class="chip" style="--chip-color:{AREA_LABELS[a]["color"]}">{html.escape(AREA_LABELS[a]["name"])}</span>'
            for a in pr["areas"]
        )
        items.append(
            f"""
            <li>
              <a href="{html.escape(pr['html_url'])}" target="_blank" rel="noopener">
                #{pr['number']} {html.escape(pr['title'])}
              </a>
              <div class="pr-meta">{html.escape(pr['user'])} ・ {fmt_dt(pr['merged_at'])} {chips}</div>
            </li>
            """
        )
    return f'<ul class="pr-list">{"".join(items)}</ul>'


PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>部活コンシェルジュ 開発ダッシュボード</title>
<style>
  :root {{
    --bg: #f7f7f9;
    --card-bg: #ffffff;
    --text: #1a1a1a;
    --muted: #6b7280;
    --border: #e5e7eb;
    --accent: #2563eb;
    --progress-bg: #e5e7eb;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg: #14161a;
      --card-bg: #1e2126;
      --text: #f1f1f1;
      --muted: #9aa0aa;
      --border: #2c2f36;
      --accent: #60a5fa;
      --progress-bg: #2c2f36;
    }}
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    padding: 16px;
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Hiragino Sans", "Noto Sans JP", sans-serif;
  }}
  h1 {{ font-size: 1.4rem; margin: 0 0 4px; }}
  .updated {{ color: var(--muted); font-size: 0.85rem; margin: 0 0 24px; }}
  h2 {{ font-size: 1.1rem; margin: 32px 0 12px; }}
  .grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 12px;
  }}
  .card {{
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 14px;
  }}
  .card-head {{ display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }}
  .avatar {{
    width: 28px; height: 28px; border-radius: 50%;
    background: var(--accent); color: #fff;
    display: flex; align-items: center; justify-content: center;
    font-size: 0.8rem; font-weight: 600; flex-shrink: 0;
  }}
  .login {{ font-weight: 600; overflow-wrap: anywhere; }}
  .stats {{ display: flex; gap: 12px; margin-bottom: 8px; }}
  .stat {{ display: flex; flex-direction: column; align-items: center; flex: 1; }}
  .stat .num {{ font-size: 1.1rem; font-weight: 700; }}
  .stat .label {{ font-size: 0.7rem; color: var(--muted); }}
  .progress {{
    height: 6px; background: var(--progress-bg); border-radius: 4px; overflow: hidden; margin-bottom: 8px;
  }}
  .progress-lg {{ height: 10px; }}
  .progress-bar {{ height: 100%; background: var(--accent); }}
  .chips {{ display: flex; flex-wrap: wrap; gap: 6px; }}
  .chip {{
    font-size: 0.7rem; padding: 2px 8px; border-radius: 999px;
    background: color-mix(in srgb, var(--chip-color) 18%, transparent);
    color: var(--chip-color);
    border: 1px solid var(--chip-color);
  }}
  .chip-empty {{ color: var(--muted); border-color: var(--border); background: none; }}
  .breakdown {{ margin-top: 10px; border-top: 1px dashed var(--border); padding-top: 8px; }}
  .breakdown summary {{ cursor: pointer; color: var(--accent); font-size: 0.85rem; }}
  .task-list {{ list-style: none; padding: 0; margin: 8px 0 0; }}
  .task {{ padding: 6px 0; border-bottom: 1px solid var(--border); font-size: 0.8rem; }}
  .task-main {{ display: flex; justify-content: space-between; gap: 6px; align-items: flex-start; }}
  .task-main a {{ color: var(--accent); text-decoration: none; overflow-wrap: anywhere; }}
  .task-done .task-main a {{ color: var(--muted); text-decoration: line-through; }}
  .task-meta {{ color: var(--muted); font-size: 0.72rem; margin-top: 2px; overflow-wrap: anywhere; }}
  .badge {{ font-size: 0.7rem; padding: 1px 8px; border-radius: 999px; white-space: nowrap; flex-shrink: 0; border: 1px solid; }}
  .badge-done {{ color: #6b7280; border-color: #9ca3af; background: color-mix(in srgb, #9ca3af 18%, transparent); }}
  .badge-late {{ color: #dc2626; border-color: #dc2626; background: color-mix(in srgb, #dc2626 15%, transparent); }}
  .badge-today {{ color: #ea580c; border-color: #ea580c; background: color-mix(in srgb, #ea580c 15%, transparent); }}
  .badge-ok {{ color: #16a34a; border-color: #16a34a; background: color-mix(in srgb, #16a34a 15%, transparent); }}
  .badge-none {{ color: var(--muted); border-color: var(--border); }}
  .milestone {{
    background: var(--card-bg); border: 1px solid var(--border); border-radius: 10px;
    padding: 14px; margin-bottom: 12px;
  }}
  .milestone-head {{ display: flex; justify-content: space-between; gap: 8px; margin-bottom: 8px; flex-wrap: wrap; }}
  .ms-title {{ font-weight: 600; }}
  .ms-due {{ color: var(--muted); font-size: 0.85rem; }}
  .ms-counts {{ color: var(--muted); font-size: 0.85rem; margin-top: 6px; }}
  .pr-list {{ list-style: none; padding: 0; margin: 0; }}
  .pr-list li {{
    background: var(--card-bg); border: 1px solid var(--border); border-radius: 8px;
    padding: 10px 14px; margin-bottom: 8px;
  }}
  .pr-list a {{ color: var(--accent); text-decoration: none; font-weight: 600; }}
  .pr-list a:hover {{ text-decoration: underline; }}
  .pr-meta {{ color: var(--muted); font-size: 0.8rem; margin-top: 4px; }}
  .empty {{ color: var(--muted); }}
  footer {{ margin-top: 40px; color: var(--muted); font-size: 0.75rem; }}
</style>
</head>
<body>
  <h1>部活コンシェルジュ 開発ダッシュボード</h1>
  <p class="updated">最終更新: {generated_at} / リポジトリ: {repo} / <a href="./hub.html">開発ハブへ</a></p>

  <h2>担当者別 進捗</h2>
  <div class="grid">{assignee_cards}</div>

  <h2>Milestone 進捗</h2>
  {milestone_bars}

  <h2>直近マージ済み PR</h2>
  {recent_prs}

  <footer>Generated by scripts/gen_dashboard.py (GitHub Actions)</footer>
</body>
</html>
"""


def main() -> int:
    token = os.environ.get("GITHUB_TOKEN")
    repo_full = os.environ.get("GITHUB_REPOSITORY")
    if not token or not repo_full:
        print("[gen_dashboard] GITHUB_TOKEN / GITHUB_REPOSITORY が未設定です", file=sys.stderr)
        return 1
    owner, repo = repo_full.split("/", 1)

    items = fetch_issues_and_prs(owner, repo, token)
    milestones = fetch_milestones(owner, repo, token)

    board = aggregate_by_assignee(items)
    ms_progress = aggregate_by_milestone(items, milestones)
    prs = recent_merged_prs(items)

    html_out = PAGE_TEMPLATE.format(
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        repo=html.escape(repo_full),
        assignee_cards=render_assignee_cards(board, datetime.now(JST).date()),
        milestone_bars=render_milestone_bars(ms_progress, datetime.now(JST).date()),
        recent_prs=render_recent_prs(prs),
    )

    os.makedirs("site", exist_ok=True)
    with open("site/index.html", "w", encoding="utf-8") as f:
        f.write(html_out)
    print(f"[gen_dashboard] site/index.html を生成しました（Issue/PR件数: {len(items)}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
