"""部活・社員の検索とホームのおすすめ（I-F契約 1.2, 仕様.md SP-16, SP-17, SP-64, SP-65, SP-75）。

- 部活カードdictのキーは I-F契約 1.2（PR #73 で確定）に従う。主キーは "club_id"。
- 件数の絞り込み（今週4件・人気3件）は画面側の責務。ここでは絞らず並びだけを保証する。
- 日付は日本時間（N-05）。「今週」は月曜〜日曜（SP-08）。
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from repositories import (
    applications_repo,
    club_members_repo,
    clubs_repo,
    employees_repo,
    events_repo,
)

_JST = ZoneInfo("Asia/Tokyo")
_EVENT_OPEN = "予定"
_STATUS_CANCELED = "キャンセル"

_CARD_KEYS = (
    "name",
    "icon",
    "location",
    "slot",
    "schedule_note",
    "mood_tags",
    "fee",
    "fee_note",
    "after_activity",
)


def _today() -> date:
    return datetime.now(_JST).date()


def _as_date(value) -> date:
    return value if isinstance(value, date) else date.fromisoformat(str(value))


def _card(club: dict, next_event_date: date | None) -> dict:
    """部活カードdict（I-F契約 1.2）。"""
    card = {"club_id": club["id"]}
    for key in _CARD_KEYS:
        card[key] = club.get(key)
    card["next_event_date"] = next_event_date
    return card


def _next_event_dates() -> dict[int, date]:
    """部活ごとの「予定」の開催のうち最も近い日付（今日以降）。予定の開催がない部活は含まない。"""
    result: dict[int, date] = {}
    for event in events_repo.list_upcoming_all_with_club():
        if event["status"] != _EVENT_OPEN:
            continue
        d = _as_date(event["event_date"])
        club_id = event["club_id"]
        if club_id not in result or d < result[club_id]:
            result[club_id] = d
    return result


def _sorted_by_next_event(cards: list[dict]) -> list[dict]:
    return sorted(
        cards,
        key=lambda c: (c["next_event_date"] is None, c["next_event_date"] or date.max, c["club_id"]),
    )


def search_clubs(conditions: dict) -> list[dict]:
    """部活検索（SP-64）。is_active の部活を次回開催日が近い順（予定なしは最後）で返す。"""
    next_dates = _next_event_dates()
    cards = [_card(c, next_dates.get(c["id"])) for c in clubs_repo.search(conditions or {})]
    return _sorted_by_next_event(cards)


def get_this_week_clubs() -> list[dict]:
    """今週（月〜日）に「予定」の開催がある部活を開催日が近い順に返す（SP-16, SP-75, SP-08）。

    "next_event_date" は今週の予定の開催のうち最も近い日。件数の絞り込みはしない。
    events_repo は今日以降の開催だけを返すため、今週のうち今日より前の開催は含まれない。
    """
    today = _today()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    first_dates: dict[int, date] = {}
    clubs: dict[int, dict] = {}
    for event in events_repo.list_upcoming_all_with_club():
        club = event.get("clubs")
        if event["status"] != _EVENT_OPEN or not club or not club.get("is_active"):
            continue
        d = _as_date(event["event_date"])
        if not (monday <= d <= sunday):
            continue
        club_id = club["id"]
        clubs[club_id] = club
        if club_id not in first_dates or d < first_dates[club_id]:
            first_dates[club_id] = d
    cards = [_card(clubs[i], first_dates[i]) for i in clubs]
    return _sorted_by_next_event(cards)


def get_popular_clubs() -> list[dict]:
    """今月の人気部活（SP-17, SP-75）。

    今月の開催への申込のうち is_first_time かつキャンセル以外を部活ごとに数え、多い順に
    "rank"（1始まりの通し番号）つきで返す。集計が0件の部活は含めない。
    同数のときは club_id の昇順（I-F契約 1.2）。件数の絞り込みはしない。
    """
    today = _today()
    next_dates = _next_event_dates()
    counted: list[tuple[int, dict]] = []
    for club in clubs_repo.search({}):
        count = 0
        for application in applications_repo.list_by_organizer_club(club["id"]):
            event_date = _as_date(application["events"]["event_date"])
            in_this_month = (event_date.year, event_date.month) == (today.year, today.month)
            if (
                in_this_month
                and application["is_first_time"]
                and application["status"] != _STATUS_CANCELED
            ):
                count += 1
        if count:
            counted.append((count, club))
    counted.sort(key=lambda t: (-t[0], t[1]["id"]))
    return [
        {**_card(club, next_dates.get(club["id"])), "rank": rank}
        for rank, (_, club) in enumerate(counted, start=1)
    ]


def get_recommendations(employee_id: str) -> list[dict]:
    """おすすめ部活（SP-18, SP-75）。

    本人の興味・拠点・参加可能時間（非公開設定に関わらず本人分を使う。裁定#19）と、
    各部活の活動・拠点・時間帯の一致数を "score" とし、1以上の部活を score 降順で返す。
    同点は次回開催日が近い順、さらに club_id 昇順。"reason" は一致した項目を並べた説明文。
    """
    employee = employees_repo.get_by_id(employee_id)
    if employee is None:
        return []
    interests = {
        i["activity_id"]: i.get("activity_name")
        for i in employees_repo.get_interests(employee["id"])
    }
    slots = set(employee.get("available_slots") or [])
    next_dates = _next_event_dates()

    results = []
    for club in clubs_repo.search({}):
        matched = []
        if club["activity_id"] in interests:
            matched.append(f"興味（{interests[club['activity_id']]}）")
        if club["location"] == employee["location"]:
            matched.append(f"拠点（{club['location']}）")
        if club["slot"] in slots:
            matched.append(f"時間帯（{club['slot']}）")
        if not matched:
            continue
        card = _card(club, next_dates.get(club["id"]))
        card["score"] = len(matched)
        card["reason"] = "・".join(matched) + "が一致"
        results.append(card)
    results.sort(
        key=lambda c: (
            -c["score"],
            c["next_event_date"] is None,
            c["next_event_date"] or date.max,
            c["club_id"],
        )
    )
    return results


def _visibility(is_public: bool, is_self: bool) -> str:
    """"public"（誰にでも表示）/ "self_private"（本人にだけ値を表示）/ "hidden"（他人には非表示）。"""
    if is_public:
        return "public"
    return "self_private" if is_self else "hidden"


def search_employees(
    conditions: dict, requester_id: str, limit: int = 20, offset: int = 0
) -> tuple[list[dict], int]:
    """社員検索（SP-65）。(ページ分の社員dictリスト, 全該当件数) を返す。

    非公開の興味・参加可能時間を条件にしたときの除外は employees_repo が行う（SP-49）。
    結果の各dictには次を加える。
      "interests": [{"activity_id","activity_name","level"}]（他人に非公開なら None）
      "interests_visibility" / "slots_visibility": "public" | "self_private" | "hidden"
      "available_slots": 他人に非公開なら None
      "clubs": 所属部活 [{"club_id","name"}]（常に全員に表示）
    「非公開」「（他の人には非公開）」の文言は画面側が visibility から出す。
    """
    conditions = conditions or {}
    rows = employees_repo.search(conditions, limit, offset)
    total = employees_repo.count(conditions)
    requester = (requester_id or "").strip().upper()

    club_names = {c["id"]: c["name"] for c in clubs_repo.search({})} if rows else {}
    clubs_by_employee: dict[str, list[dict]] = {}
    for club_id in sorted(club_names):
        for member in club_members_repo.list_members(club_id):
            clubs_by_employee.setdefault(member["employee_id"], []).append(
                {"club_id": club_id, "name": club_names[club_id]}
            )

    results = []
    for row in rows:
        is_self = row["id"].upper() == requester
        interests_vis = _visibility(row["interests_public"], is_self)
        slots_vis = _visibility(row["slots_public"], is_self)
        results.append(
            {
                **row,
                "interests": (
                    None if interests_vis == "hidden" else employees_repo.get_interests(row["id"])
                ),
                "interests_visibility": interests_vis,
                "available_slots": None if slots_vis == "hidden" else row.get("available_slots"),
                "slots_visibility": slots_vis,
                "clubs": clubs_by_employee.get(row["id"], []),
            }
        )
    return results, total
