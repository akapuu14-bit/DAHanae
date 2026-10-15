"""部活・社員の検索とホームのおすすめ（I-F契約 1.2, 仕様.md SP-16, SP-17, SP-64, SP-65, SP-75）。

- 部活カードdictのキーは I-F契約 1.2（PR #73 で確定）に従う。主キーは "club_id"。
- 件数の絞り込み（今週4件・人気3件）は画面側の責務。ここでは絞らず並びだけを保証する。
- 日付は日本時間（N-05）。「今週」は月曜〜日曜（SP-08）。
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from repositories import (
    activities_repo,
    applications_repo,
    club_members_repo,
    clubs_repo,
    employees_repo,
    events_repo,
)
from services.errors import NotFoundError

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
    "level",
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


def _next_event_dates(upcoming_events: list[dict] | None = None) -> dict[int, date]:
    """部活ごとの「予定」の開催のうち最も近い日付（今日以降）。予定の開催がない部活は含まない。

    upcoming_events を渡すと、それを使う（問い合わせを増やさない）。
    """
    result: dict[int, date] = {}
    today = _today()
    if upcoming_events is None:
        upcoming_events = events_repo.list_upcoming_all_with_club()
    for event in upcoming_events:
        if event["status"] != _EVENT_OPEN:
            continue
        d = _as_date(event["event_date"])
        club_id = event["club_id"]
        if d < today:
            continue
        if club_id not in result or d < result[club_id]:
            result[club_id] = d
    return result


def _next_event_date_of(events: list[dict]) -> date | None:
    """1つの部活の開催（event_date・status を持つdictのリスト）から、「予定」で今日以降の最も近い日付。無ければ None。

    _next_event_dates（全部活）と同じ判定を、埋め込みで取った1部活ぶんの開催に使う。
    """
    today = _today()
    dates = [
        d
        for d in (_as_date(e["event_date"]) for e in events if e["status"] == _EVENT_OPEN)
        if d >= today
    ]
    return min(dates) if dates else None


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
    """今日から今週の日曜まで（両端を含む）に「予定」の開催がある部活を開催日が近い順に返す（SP-16, SP-75, SP-08）。

    週は月曜〜日曜（SP-08）。範囲は PM 裁定で [今日, 今週の日曜]。"next_event_date" はその範囲の
    予定の開催のうち最も近い日。件数の絞り込みはしない。
    """
    return _week_clubs(events_repo.list_upcoming_all_with_club())


def _week_clubs(upcoming_events: list[dict]) -> list[dict]:
    today = _today()
    sunday = today + timedelta(days=6 - today.weekday())
    first_dates: dict[int, date] = {}
    clubs: dict[int, dict] = {}
    for event in upcoming_events:
        club = event.get("clubs")
        if event["status"] != _EVENT_OPEN or not club or not club.get("is_active"):
            continue
        d = _as_date(event["event_date"])
        if not (today <= d <= sunday):
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
    中止になった開催（events.status が「中止」）への申込は集計しない（PM 裁定）。
    同数のときは club_id の昇順（I-F契約 1.2）。件数の絞り込みはしない。
    """
    today = _today()
    next_dates = _next_event_dates()
    counted: list[tuple[int, dict]] = []
    for club in clubs_repo.search({}):
        count = 0
        for application in applications_repo.list_by_organizer_club(club["id"]):
            event = application["events"]
            if event["status"] != _EVENT_OPEN:
                continue
            event_date = _as_date(event["event_date"])
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


def get_home_page(employee_id: str) -> dict:
    """ホーム（S02）の表示に要る値を、まとめて取る（設計 D-08。部活・開催・申込を部活ごとに取らない）。

    {"week": get_this_week_clubs と同じ, "popular": get_popular_clubs と同じ,
     "recommendations": get_recommendations と同じ}。件数の絞り込み（4件・3件）や初心者向け/経験者向けの
    切り替えは、従来どおり画面側。社員の取得・興味・所属、開催（今日以降）、部活、今月の申込の集計を1回ずつ取る。
    """
    upcoming = events_repo.list_upcoming_all_with_club()
    clubs = clubs_repo.search({})
    next_dates = _next_event_dates(upcoming)

    today = _today()
    month_start = today.replace(day=1)
    next_month_start = (month_start + timedelta(days=32)).replace(day=1)
    counts = applications_repo.count_first_time_by_club_in_month(
        month_start.isoformat(), next_month_start.isoformat()
    )
    counted = [(counts[c["id"]], c) for c in clubs if counts.get(c["id"])]
    counted.sort(key=lambda t: (-t[0], t[1]["id"]))
    popular = [
        {**_card(club, next_dates.get(club["id"])), "rank": rank}
        for rank, (_, club) in enumerate(counted, start=1)
    ]

    recommendations: list[dict] = []
    employee = employees_repo.get_by_id(employee_id)
    if employee is not None:
        interests = {
            i["activity_id"]: i.get("activity_name")
            for i in employees_repo.get_interests(employee["id"])
        }
        joined = set(club_members_repo.list_clubs_by_member(employee["id"]))
        recommendations = _recommend(employee, interests, joined, clubs, next_dates)
    return {"week": _week_clubs(upcoming), "popular": popular, "recommendations": recommendations}


def get_recommendations(employee_id: str) -> list[dict]:
    """おすすめ部活（SP-18, SP-75）。

    本人の興味・拠点・参加可能時間（非公開設定に関わらず本人分を使う。裁定#19）と、
    各部活の活動・拠点・時間帯の一致数を "score" とし、1以上の部活を score 降順で返す。
    同点は次回開催日が近い順、さらに club_id 昇順。"reason" は一致した項目を並べた説明文。
    所属済みの部活（club_members に登録がある部活）は対象から除く。
    """
    employee = employees_repo.get_by_id(employee_id)
    if employee is None:
        return []
    interests = {
        i["activity_id"]: i.get("activity_name")
        for i in employees_repo.get_interests(employee["id"])
    }
    joined = set(club_members_repo.list_clubs_by_member(employee["id"]))
    return _recommend(employee, interests, joined, clubs_repo.search({}), _next_event_dates())


def _recommend(employee: dict, interests: dict, joined: set, clubs: list[dict], next_dates: dict) -> list[dict]:
    slots = set(employee.get("available_slots") or [])
    results = []
    for club in clubs:
        if club["id"] in joined:
            continue
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


def list_departments() -> list[str]:
    """社員検索（S08）の部署の選択肢（SP-48）。employees.dept の重複を除いた文字列昇順のリスト。"""
    return employees_repo.list_departments()


def list_activities() -> list[dict]:
    """活動マスタ（SP-48, SP-57）。[{"id", "name"}] を id 昇順で返す。0件なら空リスト。"""
    rows = sorted(activities_repo.list_all(), key=lambda r: r["id"])
    return [{"id": r["id"], "name": r["name"]} for r in rows]


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

    # 表示する社員ぶんの所属部活・興味を、社員の人数に関係なく1回ずつ取る（設計 D-08）
    row_ids = [row["id"] for row in rows]
    clubs_by_employee: dict[str, list[dict]] = {}
    for member in club_members_repo.list_active_clubs_for_employees(row_ids):
        clubs_by_employee.setdefault(member["employee_id"], []).append(
            {"club_id": member["club_id"], "name": member["name"]}
        )
    visible_ids = [
        row["id"]
        for row in rows
        if _visibility(row["interests_public"], row["id"].upper() == requester) != "hidden"
    ]
    interests_by_employee = employees_repo.get_interests_for(visible_ids)

    results = []
    for row in rows:
        is_self = row["id"].upper() == requester
        interests_vis = _visibility(row["interests_public"], is_self)
        slots_vis = _visibility(row["slots_public"], is_self)
        results.append(
            {
                **row,
                "interests": (
                    None if interests_vis == "hidden" else interests_by_employee.get(row["id"], [])
                ),
                "interests_visibility": interests_vis,
                "available_slots": None if slots_vis == "hidden" else row.get("available_slots"),
                "slots_visibility": slots_vis,
                "clubs": clubs_by_employee.get(row["id"], []),
            }
        )
    return results, total


_ORGANIZER_KEYS = ("id", "name", "dept", "joined_year", "entry_type")
_EVENT_KEYS = (
    "event_date",
    "start_time",
    "end_time",
    "meeting_place",
    "meeting_time",
    "status",
)


def get_club_detail(club_id: int, viewer_id: str) -> dict:
    """部活詳細（S04）の表示に必要な情報をまとめて返す読み取り専用の関数（SP-26, SP-27, SP-28, I-F契約 1.2）。

    書き込みや操作履歴の記録はしない（view_club は画面が record_view_club を別に呼ぶ）。
    is_active=false の部活も返す（PM 裁定）。参加者・人数は状態「申込済み」のみ、中止開催も
    participants に含める。viewer_id は "is_self" と "is_applied" の判定だけに使う。
    employees の行は I-F契約に列挙した列だけを返す。
    例外: NotFoundError（club_id の部活が存在しない）。
    """
    club = clubs_repo.get(club_id)
    if club is None:
        raise NotFoundError(f"club_id={club_id}")
    viewer = (viewer_id or "").strip().upper()

    organizer_row = employees_repo.get_by_id(club["organizer_id"])
    organizer = (
        {key: organizer_row.get(key) for key in _ORGANIZER_KEYS} if organizer_row else None
    )

    # メンバーの氏名・部署は所属の取得と一緒に、参加者は開催の取得と一緒に取る（人数・開催数に関係なく1回ずつ。D-08）
    members = []
    for member in club_members_repo.list_members_with_employees(club_id):
        row = member.get("employees")
        if row:
            members.append({"id": row["id"], "name": row["name"], "dept": row["dept"]})

    events = []
    for event in events_repo.list_upcoming_by_club_with_participants(club_id):
        participants = [
            {
                "id": a["applicant_id"],
                "name": a["employees"]["name"],
                "is_first_time": bool(a["is_first_time"]),
                "is_self": a["applicant_id"].upper() == viewer,
            }
            for a in event["participants"]
        ]
        events.append(
            {
                "event_id": event["id"],
                **{key: event[key] for key in _EVENT_KEYS},
                "participant_count": len(participants),
                "first_timer_count": sum(1 for p in participants if p["is_first_time"]),
                "participants": participants,
                "is_applied": any(p["is_self"] for p in participants),
            }
        )

    club_dict = {("club_id" if key == "id" else key): value for key, value in club.items()}
    return {
        "club": club_dict,
        "organizer": organizer,
        "members": members,
        "member_count": len(members),
        "events": events,
    }
