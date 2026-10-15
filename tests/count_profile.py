"""性能テスト用：1回の操作でのDB読取往復を数える（DB・ネットワーク不使用。仕様 SP-82、テスト設計 I-211〜I-213）。

- アプリのコード（app/）は変更しない。tests/fakes.py の偽repoを入れ、各repo関数を計数ラッパで包み、
  `streamlit.testing.v1.AppTest` でアプリを動かして、1操作ぶんの呼び出しを集計する。
- 「往復」= Supabase への HTTP 1往復。1関数が2往復のもの（EXEC）は換算する。読取を本回数とし、書込みは別に数える。
- 回数は「サイドバー込みの合計」と、その内数の「サイドバー分」を出す（SP-82②）。
- 偽DBは架空データ。規模は小（部活2・所属者2・開催1・申込2・社員4）と大（部活6・所属者4・開催2・申込6・社員12）。
  「もっと見る」だけは、表示件数（20件）を超える社員数が要るため、追加の規模（社員30）で数える。
- 社員の種類（偽repoの社員。`tests/fakes.py` の World とは別に build_world で全員の未読通知を用意）：
    一般＝E003、幹事＝E002（全部活の幹事）、運営者＝E001（is_admin）。
  本番の架空社員ID（E001＝一般、E002＝運営者）とは対応が違う。偽repoのIDで数えている。
- 検索条件を付けた `clubs_repo.search`・`employees_repo.search` の本番での +1〜2 往復は、偽repoが条件を見ないため含まれない
  （SP-82⑤。回数は「検索条件なし」の下限）。

実行（リポジトリ直下。DB・ネットワーク・secrets を使わない）:
    python3 tests/count_profile.py            # Markdown の表を出す
    python3 tests/count_profile.py --json     # JSON を出す
"""

import json
import sys
import types
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

import fakes  # noqa: E402  (db.client をダミー化し、app/frontend を sys.path へ)
from streamlit.testing.v1 import AppTest  # noqa: E402

import state  # noqa: E402

APP = str(ROOT / "app" / "frontend" / "app.py")
WRITE_PREFIX = ("insert", "update", "set_", "add_member", "remove_member", "mark_read", "create", "delete", "upsert")

# 1関数あたりの .execute() 回数（1以外のものだけ。条件なしの呼び出しでの値。SP-82）
EXEC = {
    ("applications_repo", "list_by_organizer_club"): 2,
    ("applications_repo", "has_past_non_canceled"): 2,
}

REPOS = {
    name: getattr(fakes, name)
    for name in (
        "action_logs_repo", "activities_repo", "applications_repo", "club_members_repo",
        "clubs_repo", "employees_repo", "events_repo", "messages_repo", "notifications_repo",
    )
}

ROLES = (("一般", "E003"), ("幹事", "E002"), ("運営者", "E001"))
SCALES = {
    "小": (2, 2, 1, 2, 4),
    "大": (6, 4, 2, 6, 12),
}
SCALE_MORE = ("社員30", (2, 2, 1, 2, 30))  # 「もっと見る」用（PAGE_SIZE=20 を超える）

CALLS = []  # (repo, func, is_write, origin)
RERUNS = {"n": 0}
WORLD = {}


def _is_write(name):
    return name.startswith(WRITE_PREFIX)


def _origin():
    for fr in traceback.extract_stack():
        if fr.name == "_render_sidebar":
            return "sidebar"
    return "screen"


def instrument():
    for repo_name, mod in REPOS.items():
        for fname in dir(mod):
            fn = getattr(mod, fname)
            if fname.startswith("_") or not isinstance(fn, types.FunctionType) or getattr(fn, "_counted", False):
                continue
            if fn.__module__ not in (mod.__name__, "fakes"):
                continue

            def make(fn=fn, repo_name=repo_name, fname=fname):
                def wrapper(*a, **k):
                    CALLS.append((repo_name, fname, _is_write(fname), _origin()))
                    return fn(*a, **k)
                wrapper._counted = True
                return wrapper
            setattr(mod, fname, make())


_orig_init = state.init


def _counted_init():
    RERUNS["n"] += 1
    return _orig_init()


state.init = _counted_init


def build_world(C, M, E, A, P):
    w = fakes.World()
    w.clubs.clear()
    w.members.clear()
    for i in range(3, 3 + P):
        w.add_employee(f"E{i + 10:03d}", name=f"社員{i}", dept=["開発", "営業"][i % 2])
    members = [e for e in w.employees if e not in ("E001", "E002")]
    for c in range(1, C + 1):
        w.add_club(c, organizer_id="E002", name=f"部活{c}")
        for m in members[:M]:
            w.add_member(c, m)
        for e in range(E):
            ev = w.add_event(c, day_offset=1 + (e % 2))
            for a in members[: max(A // max(C, 1), 1)]:
                w.add_application(ev, a)
    for emp in members[:P]:
        w.interests[emp] = [{"activity_id": 1, "level": "初心者"}]
    for emp in ("E003", "E002", "E001"):  # 社員の種類ごとに、未読の通知を3件（種類は「メッセージ」＝「見る」が出る）
        for _ in range(3):
            w.add_notification(emp, "メッセージ", read=False)
    return w


def fresh(scale):
    """測定ごとに世界を作り直す（既読化などの書込みが次の測定に残らないように）。"""
    w = build_world(*scale)
    WORLD["w"] = w
    fakes.install(w)
    instrument()
    return w


def new_app(employee_id, page):
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["employee_id"] = employee_id
    at.session_state["employee"] = dict(WORLD["w"].employees[employee_id])
    at.session_state["current_page"] = page
    at.session_state["page_history"] = []
    return at


def reset():
    CALLS.clear()
    RERUNS["n"] = 0


def tally(at):
    reads = [c for c in CALLS if not c[2]]
    writes = [c for c in CALLS if c[2]]
    return {
        "reruns": RERUNS["n"],
        "reads": sum(EXEC.get((c[0], c[1]), 1) for c in reads),
        "sidebar_reads": sum(EXEC.get((c[0], c[1]), 1) for c in reads if c[3] == "sidebar"),
        "repo_calls": len(reads),
        "writes": len(writes),
        "exceptions": len(at.exception),
        "page": at.session_state["current_page"],  # 操作のあとに表示されている画面（押しても動かなかった測定を見分ける）
    }


# --- 操作（at を受けて、押して、再実行まで待つ） ---------------------------------
def side(key):
    return lambda at: at.sidebar.button(key=f"sidebar_{key}").click().run()


def by_label(label, nth=0):
    def act(at):
        found = [b for b in at.button if b.label == label]
        if len(found) <= nth:
            raise LookupError(f"ボタンが無い: {label}")
        found[nth].click().run()
    return act


def by_key_prefix(prefix):
    def act(at):
        found = [b for b in at.button if (b.key or "").startswith(prefix)]
        if not found:
            raise LookupError(f"ボタンが無い: key={prefix}*")
        found[0].click().run()
    return act


def measure(rows, tid, label, role, scale_name, emp, start, prep, action, note=""):
    """起点の画面を開き、準備の操作を行ってから、測る操作を1回行って集計する。"""
    row = {"id": tid, "transition": label, "role": role, "scale": scale_name, "note": note}
    try:
        at = new_app(emp, start)
        at.run()
        for p in prep:
            p(at)
        reset()
        action(at)
        row.update(tally(at))
    except LookupError as e:
        row.update({"skipped": str(e)})
    rows.append(row)


def run_scale(scale_name, scale, rows, roles=ROLES, only_more=False):
    for role, emp in roles:
        manage = role in ("幹事", "運営者")

        def m(tid, label, start, prep, action, note=""):
            fresh(scale)
            measure(rows, tid, label, role, scale_name, emp, start, prep, action, note)

        if only_more:
            m("S5", "社員検索「もっと見る」", "employee_search", [], by_label("もっと見る"))
            continue

        # サイドバーからの遷移（①〜⑦）
        m("①", "ホーム→部活を探す", "home", [], side("club_search"))
        m("②", "ホーム→人を探す", "home", [], side("employee_search"))
        m("③", "ホーム→メッセージ", "home", [], side("messages"))
        m("④a", "ホーム→通知（未読あり）", "home", [], side("notifications"), "未読の通知3件。開くと既読化（書込み）")
        m("④b", "ホーム→通知（未読0）", "home", [side("notifications"), side("home")], side("notifications"), "既読化済み")
        m("⑤", "ホーム→自分のプロフィール", "home", [], side("employee_profile"))
        if manage:
            m("⑥", "ホーム→部活の管理", "home", [], side("club_admin"))
        for src, page in (("部活を探す", "club_search"), ("人を探す", "employee_search"), ("メッセージ", "messages"),
                          ("通知", "notifications"), ("自分のプロフィール", "employee_profile")):
            m("⑦", f"{src}→ホーム", page, [], side("home"))
        if manage:
            m("⑦", "部活の管理→ホーム", "club_admin", [], side("home"))

        # カード・ボタンからの遷移（⑧〜⑭）
        to_detail = [by_label("詳しく見る")]
        m("⑧", "部活を探す→部活詳細（詳しく見る）", "club_search", [], by_label("詳しく見る"))
        m("⑨", "部活詳細→部活を探す（← 戻る）", "club_search", to_detail, by_key_prefix("club_detail_back"))
        m("⑩", "部活詳細→主催者プロフィール", "club_search", to_detail, by_key_prefix("club_detail_organizer"))
        m("⑪", "部活詳細→メンバーのプロフィール", "club_search", to_detail, by_key_prefix("club_detail_member_"))
        m("⑫", "人を探す→プロフィール", "employee_search", [], by_key_prefix("employee_search_profile_"))
        m("⑬", "プロフィール→人を探す（← 戻る）", "employee_search", [by_key_prefix("employee_search_profile_")],
          by_key_prefix("employee_profile_back"))
        m("⑭", "通知→遷移先（見る）", "home", [side("notifications")], by_label("見る"), "遷移先はメッセージ（種類「メッセージ」）")

        # 検索の入力（表示操作）
        m("S1", "部活検索：キーワード入力", "club_search", [], lambda at: at.text_input[0].set_value("部活").run())
        m("S2", "部活検索：絞り込み1つ選択", "club_search", [], lambda at: at.multiselect[0].select(at.multiselect[0].options[0]).run())
        m("S3", "社員検索：名前入力", "employee_search", [], lambda at: at.text_input[0].set_value("社員").run())
        m("S4", "社員検索：絞り込み1つ選択", "employee_search", [], lambda at: at.multiselect[0].select(at.multiselect[0].options[0]).run())


def run_all():
    rows = []
    for name, scale in SCALES.items():
        run_scale(name, scale, rows)
    more_name, more_scale = SCALE_MORE
    run_scale(more_name, more_scale, rows, only_more=True)
    return rows


def to_markdown(rows):
    out = ["| ID | 遷移 | 社員の種類 | 規模 | 操作後の画面 | 再実行 | 読取往復（合計） | うちサイドバー | 書込み | 備考 |",
           "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in rows:
        if "skipped" in r:
            out.append(f"| {r['id']} | {r['transition']} | {r['role']} | {r['scale']} | - | - | 未取得 | - | - | {r['skipped']} |")
            continue
        note = r["note"] + (f"（例外{r['exceptions']}件）" if r["exceptions"] else "")
        out.append(f"| {r['id']} | {r['transition']} | {r['role']} | {r['scale']} | {r['page']} | {r['reruns']} | {r['reads']} | "
                   f"{r['sidebar_reads']} | {r['writes']} | {note} |")
    return "\n".join(out)


if __name__ == "__main__":
    result = run_all()
    if "--json" in sys.argv:
        print(json.dumps(result, ensure_ascii=False, indent=1))
    else:
        print(to_markdown(result))
