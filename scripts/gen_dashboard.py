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
    return dt.astimezone(JST).strftime("%Y-%m-%d %H:%M JST")


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


def render_task_rows(
    tasks: list[dict],
    today: date,
    show_milestone: bool = True,
    show_assignee: bool = True,
) -> str:
    """タスク行。担当者内訳は担当(show_assignee=False)、Milestone内訳はMilestone名を省く。"""

    def sort_key(t):
        due = due_date_of(t["due_on"])
        return (t["done"], due is None, due or date.max, t["number"] or 0)

    rows = []
    for t in sorted(tasks, key=sort_key):
        label, cls = deadline_badge(t["done"], t["due_on"], today)
        due = due_date_of(t["due_on"])
        due_str = due.isoformat() if due else "-"
        kind = "PR " if t["is_pr"] else ""
        meta = []
        if show_assignee:
            meta.append(f"担当: {html.escape(t['assignee'])}")
        if show_milestone:
            meta.append(html.escape(t["milestone_title"] or "Milestone未設定"))
        meta.append(f"期限: {due_str}")
        areas = "".join(
            f'<span class="chip chip-sm" style="--chip-color:{AREA_LABELS[a]["color"]}">{html.escape(AREA_LABELS[a]["name"])}</span>'
            for a in t["areas"]
        )
        rows.append(
            f"""
            <li class="task {'task-done' if t['done'] else 'task-open'}">
              <div class="task-line">
                <span class="task-no">{kind}#{t['number']}</span>
                <a class="task-title" href="{html.escape(t['html_url'])}" target="_blank" rel="noopener">{html.escape(t['title'])}</a>
                <span class="badge {cls}">{html.escape(label)}</span>
              </div>
              <div class="task-meta">{" ・ ".join(meta)}{areas}</div>
            </li>
            """
        )
    return f'<ul class="task-list">{"".join(rows)}</ul>' if rows else ""


def _render_card(login: str, e: dict, today: date, muted: bool = False) -> str:
    total = e["open"] + e["closed"]
    pct = round(e["closed"] / total * 100) if total else 0
    return f"""
            <div class="card{' card-muted' if muted else ''}">
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
                {render_task_rows(e['tasks'], today, show_assignee=False)}
              </details>
            </div>
            """


def render_assignee_cards(board: dict, today: date | None = None) -> str:
    """担当者(assigneeあり)のカードのみ。未アサインは render_unassigned_block で別ブロックに出す。"""
    today = today or datetime.now(JST).date()
    # 未完了が多い順→名前順
    people = sorted(
        ((k, v) for k, v in board.items() if k != UNASSIGNED),
        key=lambda kv: (-kv[1]["open"], kv[0]),
    )
    cards = [_render_card(login, e, today) for login, e in people]
    if not cards:
        return ""
    return "".join(cards)


def render_unassigned_block(board: dict, today: date | None = None) -> str:
    """(未アサイン)を人のグリッドと分けた控えめな別ブロックにする。0件なら空文字。"""
    today = today or datetime.now(JST).date()
    e = board.get(UNASSIGNED)
    if not e or (e["open"] + e["closed"]) == 0:
        return ""
    return f"""
  <section class="unassigned">
    <h3>未アサイン</h3>
    <p class="unassigned-note">担当者が設定されていない完了Issue・マージ済みPRなど</p>
    <div class="grid">{_render_card(UNASSIGNED, e, today, muted=True)}</div>
  </section>
"""


def render_milestone_bars(milestones: list[dict], today: date | None = None) -> str:
    today = today or datetime.now(JST).date()
    rows = []
    for m in milestones:
        task_rows = render_task_rows(m.get('tasks', []), today, show_milestone=False, show_assignee=True)
        breakdown = (
            f'<details class="breakdown"><summary>内訳を開く</summary>{task_rows}</details>'
            if task_rows else ""
        )
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
              {breakdown}
            </div>
            """
        )
    return "".join(rows)


def render_section(title: str, body: str) -> str:
    """中身が空のセクションは見出しごと出さない。"""
    if not body.strip():
        return ""
    return f"<h2>{html.escape(title)}</h2>\n  {body}"


def render_recent_prs(prs: list[dict]) -> str:
    if not prs:
        return ""
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
<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Ccircle cx='8' cy='8' r='8' fill='%23fffdf2'/%3E%3Ccircle cx='8' cy='8' r='7' fill='%231f2a44'/%3E%3Cpath d='M12.5 3.5 9.5 9.5 6.5 6.5Z' fill='%23f4cb4d'/%3E%3Cpath d='M3.5 12.5 6.5 6.5 9.5 9.5Z' fill='%23c9c5aa'/%3E%3Ccircle cx='8' cy='8' r='1' fill='%23fffdf2'/%3E%3C/svg%3E">
<link rel="icon" type="image/png" sizes="32x32" href="hub-assets/favicon-32.png">
<link rel="icon" type="image/png" sizes="16x16" href="hub-assets/favicon-16.png">
<link rel="apple-touch-icon" sizes="180x180" href="hub-assets/apple-touch-icon.png">
<meta name="theme-color" content="#1f2a44">
<meta name="description" content="部活コンシェルジュの開発状況（Issue・PR・Milestone）を担当者別・Milestone別にまとめた進捗ダッシュボード。">
<meta property="og:type" content="website">
<meta property="og:title" content="部活コンシェルジュ 開発ダッシュボード">
<meta property="og:description" content="部活コンシェルジュの開発状況（Issue・PR・Milestone）を担当者別・Milestone別にまとめた進捗ダッシュボード。">
<meta property="og:url" content="https://akapuu14-bit.github.io/DAHanae/index.html">
<meta property="og:image" content="https://akapuu14-bit.github.io/DAHanae/hub-assets/og-image.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="部活コンシェルジュ 開発ダッシュボード">
<meta name="twitter:description" content="部活コンシェルジュの開発状況（Issue・PR・Milestone）を担当者別・Milestone別にまとめた進捗ダッシュボード。">
<meta name="twitter:image" content="https://akapuu14-bit.github.io/DAHanae/hub-assets/og-image.png">
<style>
  @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700&family=Zen+Kaku+Gothic+New:wght@500;700;900&display=swap');
  :root {{
    --board: #e8ebf2;
    --card-bg: #fff;
    --text: #1f2a44;
    --muted: #5b6475;
    --border: #d9dfd8;
    --accent: #243b67;
    --accent-soft: #e7ebf4;
    --tape: rgba(242, 194, 48, .86);
    --progress-bg: #dfe5df;
    --shadow: 0 8px 20px rgba(31, 42, 68, .09), 0 2px 5px rgba(31, 42, 68, .07);
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    background-color: var(--board);
    background-image: radial-gradient(rgba(31, 42, 68, .055) .7px, transparent .7px);
    background-size: 7px 7px;
    color: var(--text);
    font-family: "Noto Sans JP", sans-serif;
    line-height: 1.6;
  }}
  .wrap {{ max-width: 1100px; margin: 0 auto; padding: 42px 20px 72px; }}
  .hero {{
    position: relative; background: var(--card-bg); padding: 28px 32px 24px;
    box-shadow: var(--shadow); transform: rotate(-.2deg); margin-bottom: 34px;
  }}
  .hero::before, .card::before, .milestone::before {{
    content: ""; position: absolute; top: -9px; left: 50%; width: 76px; height: 19px;
    background: var(--tape); transform: translateX(-50%) rotate(-1.5deg);
    clip-path: polygon(3% 4%, 98% 0, 96% 96%, 0 100%);
  }}
  h1 {{ font-family: "Zen Kaku Gothic New", sans-serif; font-size: clamp(1.55rem, 4vw, 2.2rem); font-weight: 900; margin: 0 0 4px; }}
  .updated {{ color: var(--muted); font-size: 0.85rem; margin: 0; }}
  .updated a {{ color: var(--accent); font-weight: 700; }}
  h2 {{
    display: inline-block; font-family: "Zen Kaku Gothic New", sans-serif;
    font-size: 1.15rem; font-weight: 900; margin: 34px 0 17px 5px;
    padding: 3px 10px 5px; background: var(--card-bg); box-shadow: 3px 3px 0 rgba(36, 59, 103, .22);
  }}
  .grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(min(100%, 220px), 1fr));
    gap: 18px;
  }}
  .card {{
    position: relative;
    background: var(--card-bg);
    border: 0;
    border-top: 5px solid var(--accent);
    padding: 20px 16px 15px;
    box-shadow: var(--shadow);
  }}
  .card::before {{ width: 58px; height: 17px; top: -10px; }}
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
  .breakdown summary {{ cursor: pointer; color: var(--accent); font-size: 0.85rem; font-weight: 700; }}
  .breakdown summary:focus-visible, a:focus-visible {{ outline: 3px solid var(--tape); outline-offset: 3px; }}
  .task-list {{ list-style: none; padding: 0; margin: 8px 0 0; }}
  .task {{ padding: 9px 0; border-bottom: 1px solid var(--border); font-size: 0.82rem; line-height: 1.5; }}
  .task:last-child {{ border-bottom: none; }}
  .task-line {{ display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: 4px 8px; align-items: baseline; }}
  .task-no {{ font-weight: 700; font-variant-numeric: tabular-nums; white-space: nowrap; }}
  .task-title {{ color: var(--accent); text-decoration: none; overflow-wrap: anywhere; }}
  .task-title:hover {{ text-decoration: underline; }}
  .task-done .task-title {{ color: var(--muted); text-decoration: line-through; }}
  .task-meta {{ color: var(--muted); font-size: 0.72rem; margin-top: 3px; padding-left: 0; overflow-wrap: anywhere; }}
  .chip-sm {{ font-size: 0.62rem; padding: 0 6px; margin-left: 6px; vertical-align: 1px; }}
  .unassigned {{ margin-top: 20px; }}
  .unassigned h3 {{ font-size: 0.9rem; margin: 0 0 2px; color: var(--muted); }}
  .unassigned-note {{ font-size: 0.75rem; color: var(--muted); margin: 0 0 8px; }}
  .card-muted {{ background: rgba(255,255,255,.55); border: 2px dashed #aeb8ad; box-shadow: none; opacity: 0.85; }}
  .card-muted::before {{ display: none; }}
  .card-muted .avatar {{ background: var(--muted); }}
  @media (max-width: 420px) {{
    .task-line {{ grid-template-columns: auto minmax(0, 1fr); }}
    .task-line .badge {{ grid-column: 2; justify-self: start; }}
  }}
  .badge {{ font-size: 0.7rem; padding: 1px 8px; border-radius: 999px; white-space: nowrap; flex-shrink: 0; border: 1px solid; }}
  .badge-done {{ color: #6b7280; border-color: #9ca3af; background: color-mix(in srgb, #9ca3af 18%, transparent); }}
  .badge-late {{ color: #dc2626; border-color: #dc2626; background: color-mix(in srgb, #dc2626 15%, transparent); }}
  .badge-today {{ color: #ea580c; border-color: #ea580c; background: color-mix(in srgb, #ea580c 15%, transparent); }}
  .badge-ok {{ color: #16a34a; border-color: #16a34a; background: color-mix(in srgb, #16a34a 15%, transparent); }}
  .badge-none {{ color: var(--muted); border-color: var(--border); }}
  .milestone {{
    position: relative; background: var(--card-bg); border: 0; border-left: 6px solid var(--accent);
    padding: 21px 18px 16px; margin-bottom: 18px; box-shadow: var(--shadow);
  }}
  .milestone::before {{ left: auto; right: 26px; width: 62px; height: 17px; transform: rotate(2deg); }}
  .milestone-head {{ display: flex; justify-content: space-between; gap: 8px; margin-bottom: 8px; flex-wrap: wrap; }}
  .ms-title {{ font-weight: 600; }}
  .ms-due {{ color: var(--muted); font-size: 0.85rem; }}
  .ms-counts {{ color: var(--muted); font-size: 0.85rem; margin-top: 6px; }}
  .pr-list {{ list-style: none; padding: 0; margin: 0; }}
  .pr-list li {{
    background: var(--card-bg); border: 0; border-left: 4px solid var(--accent);
    padding: 12px 15px; margin-bottom: 10px; box-shadow: 0 3px 9px rgba(31, 42, 68, .07);
  }}
  .pr-list a {{ color: var(--accent); text-decoration: none; font-weight: 600; }}
  .pr-list a:hover {{ text-decoration: underline; }}
  .pr-meta {{ color: var(--muted); font-size: 0.8rem; margin-top: 4px; }}
  .empty {{ color: var(--muted); }}
  footer {{ margin-top: 44px; color: var(--muted); font-size: 0.75rem; text-align: center; }}
  @media (max-width: 600px) {{
    .wrap {{ padding: 30px 14px 52px; }}
    .hero {{ padding: 26px 21px 21px; }}
  }}
</style>
</head>
<body>
<main class="wrap">
  <header class="hero">
    <h1>部活コンシェルジュ 開発ダッシュボード</h1>
    <p class="updated">最終更新: {generated_at} / リポジトリ: {repo} / <a href="./hub.html">開発ハブへ</a></p>
  </header>

  {assignee_cards}
  {unassigned_block}

  {milestone_bars}

  {recent_prs}

  <footer>Generated by scripts/gen_dashboard.py (GitHub Actions)</footer>
</main>
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
        generated_at=datetime.now(JST).strftime("%Y-%m-%d %H:%M JST"),
        repo=html.escape(repo_full),
        assignee_cards=render_section(
            "担当者別 進捗",
            (lambda c: f'<div class="grid">{c}</div>' if c else "")(
                render_assignee_cards(board, datetime.now(JST).date())
            ),
        ),
        unassigned_block=render_unassigned_block(board, datetime.now(JST).date()),
        milestone_bars=render_section(
            "Milestone 進捗", render_milestone_bars(ms_progress, datetime.now(JST).date())
        ),
        recent_prs=render_section("直近マージ済み PR", render_recent_prs(prs)),
    )

    os.makedirs("site", exist_ok=True)
    with open("site/index.html", "w", encoding="utf-8") as f:
        f.write(html_out)
    print(f"[gen_dashboard] site/index.html を生成しました（Issue/PR件数: {len(items)}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
