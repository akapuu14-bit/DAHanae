"""L-A（service ＋ 偽repo）用の偽repoと時刻固定。

実DB・ネットワークは使わない。偽repoは I-F契約 section 2 のシグネチャ・戻り値の形に合わせた
メモリ上の実装で、各 repositories.<x>_repo モジュールの関数を直接差し替える。
このファイルの合格は「偽repoに対する合格」であり、実DBの合格ではない。
"""

import os
import sys
import types
import unittest
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")

# --- import 前提（db.client と streamlit をダミーに差し替える） --------------------
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "app", "frontend"))

_db_client = types.ModuleType("db.client")
_db_client.supabase = None
sys.modules["db.client"] = _db_client

_st = types.ModuleType("streamlit")
_st.secrets = {"common_password": "test-common-password"}
sys.modules["streamlit"] = _st

from repositories import (  # noqa: E402
    action_logs_repo,
    activities_repo,
    applications_repo,
    club_members_repo,
    clubs_repo,
    employees_repo,
    events_repo,
    messages_repo,
    notifications_repo,
)
from services import (  # noqa: E402
    action_log_service,
    application_service,
    auth_service,
    club_admin_service,
    notification_service,
    profile_service,
    search_service,
)

COMMON_PASSWORD = "test-common-password"

CLUB_FIELDS = {
    "name": "テスト部",
    "icon": "⚽",
    "activity_id": 1,
    "location": "東京",
    "slot": "平日夜",
    "frequency": "毎週",
    "level": "初心者歓迎",
    "fact_adult_starters": "多い",
    "message": "気軽に来てね",
    "fee": "無料",
    "rental": "あり",
    "join_leave": "OK",
    "after_activity": "なし",
    "organizer_id": "E002",
}


def _frozen_datetime(w):
    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return w.now.astimezone(tz) if tz else w.now.replace(tzinfo=None)

    return FrozenDatetime


class World:
    """メモリ上のDB。setUp ごとに作り直す。"""

    def __init__(self):
        # 2026-10-14（水）12:00 JST に固定
        self.now = datetime(2026, 10, 14, 12, 0, tzinfo=JST)
        self.activities = [{"id": 1, "name": "スポーツ"}, {"id": 2, "name": "音楽"}]
        self.employees = {}
        self.interests = {}
        self.clubs = {}
        self.members = []  # {"club_id","employee_id","joined_at"}
        self.events = {}
        self.applications = {}
        self.messages = []
        self.notifications = []
        self.action_logs = []
        self._seq = {}
        self.add_employee("E001", name="運営者", is_admin=True)
        self.add_employee("E002", name="幹事一郎", dept="開発", location="東京")
        self.add_employee("E003", name="一般三郎", dept="営業", location="大阪")
        self.add_employee("E004", name="幹事二郎", dept="営業", location="東京")
        self.add_employee("E005", name="一般五郎", dept="開発", location="東京")
        self.add_club(1, organizer_id="E002", name="部活A")
        self.add_club(2, organizer_id="E004", name="部活B")

    # --- 準備用 ---
    def next_id(self, key):
        self._seq[key] = self._seq.get(key, 0) + 1
        return self._seq[key]

    def today(self) -> date:
        return self.now.date()

    def add_employee(self, eid, **over):
        row = {
            "id": eid, "name": eid, "dept": "開発", "location": "東京",
            "joined_year": 2020, "entry_type": "新卒", "is_admin": False,
            "interests_public": True, "slots_public": True, "available_slots": [],
        }
        row.update(over)
        self.employees[eid] = row
        self.interests.setdefault(eid, [])
        return row

    def add_club(self, club_id, **over):
        row = {"id": club_id, "is_active": True, "mood_tags": [], "schedule_note": None,
               "fee_note": None, "belongings_note": None}
        row.update({k: v for k, v in CLUB_FIELDS.items()})
        row.update(over)
        self.clubs[club_id] = row
        self.members.append({"club_id": club_id, "employee_id": row["organizer_id"], "joined_at": None})
        return row

    def add_event(self, club_id, day_offset=1, status="予定", start="19:00:00", end="21:00:00",
                  meeting_place="会議室", event_date=None):
        eid = self.next_id("event")
        d = event_date or (self.today() + timedelta(days=day_offset))
        self.events[eid] = {
            "id": eid, "club_id": club_id, "event_date": d.isoformat(), "start_time": start,
            "end_time": end, "meeting_place": meeting_place, "meeting_time": None, "status": status,
        }
        return eid

    def add_application(self, event_id, applicant_id, status="申込済み", is_first_time=False,
                        confirmed_at=None):
        aid = self.next_id("application")
        self.applications[aid] = {
            "id": aid, "event_id": event_id, "applicant_id": applicant_id, "status": status,
            "is_first_time": is_first_time, "applied_at": f"2026-10-{aid:02d}T00:00:00+09:00",
            "canceled_at": None, "confirmed_at": confirmed_at,
        }
        return aid

    def add_member(self, club_id, employee_id):
        self.members.append({"club_id": club_id, "employee_id": employee_id, "joined_at": None})

    def add_notification(self, recipient, type_, read=False, application_id=None, event_id=None):
        nid = self.next_id("notification")
        self.notifications.append({
            "id": nid, "recipient_id": recipient, "type": type_, "application_id": application_id,
            "event_id": event_id, "body": "x", "read_at": "t" if read else None,
            "created_at": f"2026-10-01T00:00:{nid:02d}",
        })
        return nid

    def club_events(self, club_id):
        return [e for e in self.events.values() if e["club_id"] == club_id]

    def notes_for(self, recipient, type_=None):
        return [n for n in self.notifications
                if n["recipient_id"] == recipient and (type_ is None or n["type"] == type_)]


def _norm(v):
    return (v or "").strip().upper()


def install(w: World):
    """偽repoを各repoモジュールの関数として直接代入し、時刻を固定する。"""
    # employees
    def e_get_by_id(eid):
        if not eid or not eid.strip():
            return None
        for k, row in w.employees.items():
            if _norm(k) == _norm(eid):
                return dict(row)
        return None
    employees_repo.get_by_id = e_get_by_id
    employees_repo.get_interests = lambda eid: [
        {"activity_id": i["activity_id"],
         "activity_name": next(a["name"] for a in w.activities if a["id"] == i["activity_id"]),
         "level": i["level"]}
        for i in sorted(w.interests.get(eid, []), key=lambda i: i["activity_id"])]
    employees_repo.set_interests = lambda eid, items: w.interests.__setitem__(eid, [dict(i) for i in items])
    employees_repo.set_available_slots = lambda eid, slots: w.employees[eid].__setitem__("available_slots", list(slots))

    def e_update_public(eid, *, interests_public=None, slots_public=None):
        if interests_public is not None:
            w.employees[eid]["interests_public"] = interests_public
        if slots_public is not None:
            w.employees[eid]["slots_public"] = slots_public
    employees_repo.update_public_settings = e_update_public
    employees_repo.list_all = lambda: [dict(r) for r in sorted(w.employees.values(), key=lambda r: r["id"])]
    employees_repo.list_departments = lambda: sorted({r["dept"] for r in w.employees.values()})
    # 条件絞り込みは repo の責務（L-A 対象外）。偽repoは全員を返す。
    employees_repo.search = lambda conditions, limit, offset: [
        dict(r) for r in sorted(w.employees.values(), key=lambda r: r["id"])][offset:offset + limit]
    employees_repo.count = lambda conditions: len(w.employees)

    # activities
    activities_repo.list_all = lambda: [dict(a) for a in w.activities]
    activities_repo.get = lambda aid: next((dict(a) for a in w.activities if a["id"] == aid), None)

    # clubs
    clubs_repo.get = lambda cid: dict(w.clubs[cid]) if cid in w.clubs else None
    # 条件絞り込み（キーワード・拠点等）は repo の責務（L-A 対象外）。is_active=true のみ返す。
    clubs_repo.search = lambda conditions: [dict(c) for c in sorted(w.clubs.values(), key=lambda c: c["id"]) if c["is_active"]]
    clubs_repo.list_by_organizer = lambda oid: [dict(c) for c in sorted(w.clubs.values(), key=lambda c: c["id"]) if _norm(c["organizer_id"]) == _norm(oid)]
    clubs_repo.list_all_for_admin = lambda: [dict(c) for c in sorted(w.clubs.values(), key=lambda c: c["id"])]

    def c_create(data):
        cid = max(w.clubs, default=0) + 1
        row = {"id": cid, "mood_tags": [], "schedule_note": None, "fee_note": None, "belongings_note": None}
        row.update(data)
        w.clubs[cid] = row
        return cid
    clubs_repo.create = c_create
    clubs_repo.update = lambda cid, data: w.clubs[cid].update(data)

    # club_members
    club_members_repo.is_member = lambda cid, eid: any(m["club_id"] == cid and _norm(m["employee_id"]) == _norm(eid) for m in w.members)
    club_members_repo.list_members = lambda cid: [dict(m) for m in sorted((m for m in w.members if m["club_id"] == cid), key=lambda m: m["employee_id"])]
    club_members_repo.add_member = lambda cid, eid, joined_at=None: w.members.append({"club_id": cid, "employee_id": eid, "joined_at": joined_at})
    club_members_repo.remove_member = lambda cid, eid: w.members.__setitem__(slice(None), [m for m in w.members if not (m["club_id"] == cid and m["employee_id"] == eid)])
    club_members_repo.list_clubs_by_member = lambda eid: sorted(m["club_id"] for m in w.members if _norm(m["employee_id"]) == _norm(eid))

    # events
    events_repo.get = lambda eid: dict(w.events[eid]) if eid in w.events else None
    events_repo.list_upcoming_by_club = lambda cid: [dict(e) for e in sorted(w.club_events(cid), key=lambda e: (e["event_date"], e["id"])) if e["event_date"] >= w.today().isoformat()]
    events_repo.list_upcoming_all_with_club = lambda: [
        {**e, "clubs": dict(w.clubs[e["club_id"]])}
        for e in sorted(w.events.values(), key=lambda e: (e["event_date"], e["id"]))
        if e["event_date"] >= w.today().isoformat()]

    def e_last_place(cid):
        evs = sorted(w.club_events(cid), key=lambda e: (e["event_date"], e["id"]), reverse=True)
        return evs[0]["meeting_place"] if evs else None
    events_repo.get_last_meeting_place = e_last_place

    def ev_create(data):
        eid = w.next_id("event")
        w.events[eid] = {"id": eid, "meeting_time": None, **data}
        return eid
    events_repo.create = ev_create
    events_repo.update = lambda eid, data: w.events[eid].update(data)
    events_repo.set_status = lambda eid, st: w.events[eid].__setitem__("status", st)

    # applications
    applications_repo.get = lambda aid: dict(w.applications[aid]) if aid in w.applications else None
    applications_repo.exists_active = lambda eid, uid: any(a["event_id"] == eid and a["applicant_id"] == uid and a["status"] == "申込済み" for a in w.applications.values())

    def a_insert(event_id, applicant_id, is_first_time):
        return w.add_application(event_id, applicant_id, "申込済み", is_first_time)
    applications_repo.insert = a_insert

    def a_update(aid, status, *, canceled_at=None, confirmed_at=None):
        row = w.applications[aid]
        row["status"] = status
        if canceled_at is not None:
            row["canceled_at"] = canceled_at
        if confirmed_at is not None:
            row["confirmed_at"] = confirmed_at
    applications_repo.update_status = a_update

    # 「過去」= event_date < 今日（JST）。実repoのJST判定そのものは L-A では確認できない。
    def a_has_past(club_id, eid):
        past = {e["id"] for e in w.club_events(club_id) if e["event_date"] < w.today().isoformat()}
        return any(a["event_id"] in past and a["applicant_id"] == eid and a["status"] != "キャンセル" for a in w.applications.values())
    applications_repo.has_past_non_canceled = a_has_past

    def _with_event(a):
        e = dict(w.events[a["event_id"]])
        e["clubs"] = dict(w.clubs[e["club_id"]])
        return {**a, "events": e}
    applications_repo.list_by_applicant = lambda uid: [_with_event(a) for a in sorted(w.applications.values(), key=lambda a: a["id"]) if a["applicant_id"] == uid]

    def a_by_club(cid):
        ev_ids = {e["id"] for e in w.club_events(cid)}
        return [{**_with_event(a), "employees": dict(w.employees[a["applicant_id"]])}
                for a in sorted(w.applications.values(), key=lambda a: a["id"]) if a["event_id"] in ev_ids]
    applications_repo.list_by_organizer_club = a_by_club
    applications_repo.list_participants = lambda eid: [
        {**a, "employees": dict(w.employees[a["applicant_id"]])}
        for a in sorted(w.applications.values(), key=lambda a: a["id"]) if a["event_id"] == eid and a["status"] == "申込済み"]

    # messages
    messages_repo.list_by_application = lambda aid: [dict(m) for m in w.messages if m["application_id"] == aid]

    def m_insert(aid, sender, body):
        mid = w.next_id("message")
        w.messages.append({"id": mid, "application_id": aid, "sender_id": sender, "body": body})
        return mid
    messages_repo.insert = m_insert

    # notifications
    notifications_repo.count_unread = lambda eid: sum(1 for n in w.notifications if n["recipient_id"] == eid and n["read_at"] is None)
    notifications_repo.list_by_recipient = lambda eid: [dict(n) for n in sorted((n for n in w.notifications if n["recipient_id"] == eid), key=lambda n: n["id"], reverse=True)]

    def n_insert(recipient_id, type_, *, application_id=None, event_id=None, body):
        nid = w.add_notification(recipient_id, type_, False, application_id, event_id)
        w.notifications[-1]["body"] = body
        return nid
    notifications_repo.insert = n_insert

    def n_mark(eid, types):
        for n in w.notifications:
            if n["recipient_id"] == eid and n["type"] in types and n["read_at"] is None:
                n["read_at"] = "t"
    notifications_repo.mark_read = n_mark
    notifications_repo.mark_read_all = lambda eid: n_mark(eid, {n["type"] for n in w.notifications})

    # action_logs
    def l_insert(eid, action, *, club_id=None, conditions=None):
        lid = w.next_id("log")
        w.action_logs.append({"id": lid, "employee_id": eid, "action": action, "club_id": club_id, "conditions": conditions})
        return lid
    action_logs_repo.insert = l_insert
    action_logs_repo.get_last = lambda eid, action: next(
        (dict(r) for r in reversed(w.action_logs) if r["employee_id"] == eid and r["action"] == action), None)

    # 時刻固定：各 service が使う datetime を固定時刻版に差し替える。
    # service 自身の「JST に変換して今日を決める」処理はそのまま実行される（日付判定を偽にしない）。
    frozen = _frozen_datetime(w)
    application_service.datetime = frozen
    search_service.datetime = frozen
    club_admin_service.datetime = frozen


class LaTestCase(unittest.TestCase):
    """setUp で偽repoを入れ直す。self.w が偽DB。"""

    def setUp(self):
        self.w = World()
        install(self.w)
