"""【仮の部活・開催管理サービス】部活・開催の管理画面（S10）用の代役。

I-F契約には、部活・開催の管理用の関数がまだ無い。画面が必要とする形をこちらから提案して仮に置く。
（本物は clubs_repo / events_repo / club_members_repo にある関数を、権限と入力の検証つきでつなぐ形になる）
  list_manageable_clubs(requester_id)                 … 管理できる部活（運営者は全部、幹事は担当だけ）
  get_club(club_id, requester_id)                     … 編集用に部活の全項目
  create_club(requester_id, data) -> club_id          … 運営者のみ
  update_club(club_id, requester_id, data)            … 幹事（担当）・運営者。幹事の変更・公開中は運営者のみ
  list_club_events(club_id, requester_id)             … 今日以降の開催（申込人数つき）
  get_last_meeting_place(club_id)                     … 前回の開催の集合場所（開催追加の初期値）
  create_event / update_event / set_event_status      … 開催の追加・変更・中止／予定に戻す
  list_club_members / add_club_member / remove_club_member … メンバー（Should）
権限と入力の検証は、すべてこのサービスがする（画面は「親切」のための先回りだけ）。
DB の代わりに、メモリ上の dict で動く。ここで変えた内容は、検索・詳細など他の仮物には反映されない。
"""

from datetime import date

from mocks import profile_service, search_service
from mocks.auth_service import ROLE_ADMIN, get_role
from services.errors import ConflictError, NotFoundError, PermissionDeniedError, ValidationError

# 仕様.md 3.2 の選択肢
LOCATIONS = ["東京", "大阪"]
SLOTS = ["平日夜", "土曜午前", "土曜午後", "日曜"]
FREQUENCIES = ["毎週", "月2回", "月1回", "不定期"]
LEVELS = ["初心者歓迎", "レベル問わず", "経験者向け"]
FACT_ADULT_STARTERS = ["多い", "少しいる", "いない"]
MOOD_TAGS = ["ゆるめ", "しっかり練習", "黙々と集中", "わいわい賑やか", "おしゃべり多め", "少人数"]
FEES = ["無料", "500円以下", "1,000円以下", "それ以上"]
RENTALS = ["あり", "なし"]
JOIN_LEAVES = ["OK", "できれば最初から", "要相談"]
AFTER_ACTIVITIES = ["なし", "ランチ・お茶", "飲み会", "日による"]
STATUS_PLANNED = "予定"
STATUS_CANCELED = "中止"
MAX_MOOD_TAGS = 3

# 保存で必須の項目（キー）。ここに無い schedule_note / fee_note / belongings_note は任意
REQUIRED_KEYS = ("name", "icon", "activity_id", "location", "slot", "frequency", "level", "fact_adult_starters",
                 "message", "fee", "rental", "join_leave", "after_activity", "organizer_id")
_ADMIN_ONLY_KEYS = ("organizer_id", "is_active")

_clubs = {}
_events = {}
_members = {}
_next_club_id = [100]
_next_event_id = [9000]


def _ensure():
    """初回だけ、検索・詳細の仮データから管理用のデータを作る。"""
    if _clubs:
        return
    for club in search_service._search_pool():
        club_id = club["club_id"]
        info = search_service._DETAIL_INFO[club_id]
        (frequency, starters, fee_note, rental, belongings, join_leave, organizer_id, *_rest) = info
        _clubs[club_id] = {
            "id": club_id, "name": club["name"], "icon": club["icon"], "activity_id": club_id,
            "location": club["location"], "slot": club["slot"], "schedule_note": None, "frequency": frequency,
            "level": club["level"], "fact_adult_starters": starters, "mood_tags": list(club["mood_tags"]),
            "message": search_service._SEARCH_INFO[club_id][2], "fee": club["fee"], "fee_note": fee_note,
            "rental": rental, "belongings_note": belongings, "join_leave": join_leave,
            "after_activity": club["after_activity"], "organizer_id": organizer_id, "is_active": True,
        }
        _events[club_id] = [dict(e, id=e["event_id"]) for e in search_service._events_of(club)]
        for event in _events[club_id]:
            event.pop("event_id", None)
            event["_base_count"] = len(search_service._participants_of(dict(event, event_id=event["id"]), None))
        _members[club_id] = [organizer_id] + [
            e for e in profile_service.employee_ids()
            if club_id in profile_service.memberships(e) and e != organizer_id
        ]


def _is_admin(requester_id):
    return get_role(requester_id) == ROLE_ADMIN


def _check_club_access(club_id, requester_id):
    """部活が無ければ NotFoundError、権限が無ければ PermissionDeniedError（SP-74）。"""
    _ensure()
    club = _clubs.get(club_id)
    if club is None:
        raise NotFoundError(f"club {club_id}")
    if not _is_admin(requester_id) and club["organizer_id"] != (requester_id or "").strip().upper():
        raise PermissionDeniedError("only the organizer or an admin can manage this club")
    return club


def _validate_club(data):
    for key in REQUIRED_KEYS:
        value = data.get(key)
        if value is None or (isinstance(value, str) and not value.strip()):
            raise ValidationError(f"required:{key}")
    if len(data.get("mood_tags") or []) > MAX_MOOD_TAGS:
        raise ValidationError("too_many_mood_tags")
    choices = {"location": LOCATIONS, "slot": SLOTS, "frequency": FREQUENCIES, "level": LEVELS,
               "fact_adult_starters": FACT_ADULT_STARTERS, "fee": FEES, "rental": RENTALS,
               "join_leave": JOIN_LEAVES, "after_activity": AFTER_ACTIVITIES}
    for key, allowed in choices.items():
        if data[key] not in allowed:
            raise ValidationError(f"invalid:{key}")
    if any(tag not in MOOD_TAGS for tag in data.get("mood_tags") or []):
        raise ValidationError("invalid:mood_tags")
    if data["activity_id"] not in dict(profile_service.ACTIVITIES):
        raise ValidationError("invalid:activity_id")


def _clean(data):
    keys = REQUIRED_KEYS + ("schedule_note", "fee_note", "belongings_note", "mood_tags", "is_active")
    return {k: data.get(k) for k in keys if k in data}


# ---- 部活 ---------------------------------------------------------------------

def list_manageable_clubs(requester_id):
    """管理できる部活。運営者は全部（公開していないものも）、幹事は担当の部活だけ（SP-58）。"""
    _ensure()
    requester = (requester_id or "").strip().upper()
    clubs = [c for c in _clubs.values() if _is_admin(requester) or c["organizer_id"] == requester]
    return [dict(c, mood_tags=list(c["mood_tags"])) for c in sorted(clubs, key=lambda c: c["id"])]


def get_club(club_id, requester_id):
    club = _check_club_access(club_id, requester_id)
    return dict(club, mood_tags=list(club["mood_tags"]))


def create_club(requester_id, data):
    """部活の新規作成（運営者のみ。SP-74）。club_id を返す。"""
    _ensure()
    if not _is_admin(requester_id):
        raise PermissionDeniedError("only an admin can create a club")
    _validate_club(data)
    _next_club_id[0] += 1
    club_id = _next_club_id[0]
    _clubs[club_id] = dict(_clean(data), id=club_id, is_active=bool(data.get("is_active", True)),
                           mood_tags=list(data.get("mood_tags") or []))
    for key in ("schedule_note", "fee_note", "belongings_note"):
        _clubs[club_id].setdefault(key, None)
    _events[club_id] = []
    _members[club_id] = [data["organizer_id"]]
    return club_id


def update_club(club_id, requester_id, data):
    """部活情報の更新（幹事・運営者）。幹事の変更と公開中の切り替えは運営者のみ（SP-74）。"""
    club = _check_club_access(club_id, requester_id)
    if not _is_admin(requester_id):
        for key in _ADMIN_ONLY_KEYS:
            if key in data and data[key] != club[key]:
                raise PermissionDeniedError(f"only an admin can change {key}")
    merged = dict(club, **_clean(data))
    _validate_club(merged)
    club.update(merged)
    club["mood_tags"] = list(merged.get("mood_tags") or [])
    if club["organizer_id"] not in _members[club_id]:  # 幹事もメンバーに入れる（SP-77）
        _members[club_id].insert(0, club["organizer_id"])


# ---- 開催 ---------------------------------------------------------------------

def _event_view(event):
    view = {k: v for k, v in event.items() if not k.startswith("_")}
    view["applicant_count"] = event.get("_base_count", 0)
    return view


def list_club_events(club_id, requester_id):
    """今日以降の開催を日付順に（SP-60）。各 dict に applicant_count（申込済みの人数）が付く。"""
    _check_club_access(club_id, requester_id)
    today = date.today()
    return [_event_view(e) for e in sorted(_events[club_id], key=lambda e: (e["event_date"], e["id"]))
            if e["event_date"] >= today]


def get_last_meeting_place(club_id, requester_id):
    """前回の開催の集合場所（開催追加の初期値。SP-60）。無ければ None。"""
    _check_club_access(club_id, requester_id)
    rows = sorted(_events[club_id], key=lambda e: (e["event_date"], e["id"]))
    return rows[-1]["meeting_place"] if rows else None


def _validate_event(data):
    for key in ("event_date", "start_time", "end_time", "meeting_place"):
        value = data.get(key)
        if value is None or (isinstance(value, str) and not value.strip()):
            raise ValidationError(f"required:{key}")
    if data["event_date"] < date.today():
        raise ValidationError("past_date")  # 画面が SP-61 の文言を出す
    if data["end_time"] <= data["start_time"]:
        raise ValidationError("end_before_start")  # 画面が SP-61 の文言を出す


def create_event(club_id, requester_id, data):
    """開催の追加（SP-60, SP-61）。event_id を返す。"""
    _check_club_access(club_id, requester_id)
    _validate_event(data)
    _next_event_id[0] += 1
    event = {"id": _next_event_id[0], "club_id": club_id, "event_date": data["event_date"],
             "start_time": data["start_time"], "end_time": data["end_time"],
             "meeting_place": data["meeting_place"].strip(), "meeting_time": data.get("meeting_time"),
             "status": STATUS_PLANNED, "_base_count": 0}
    _events[club_id].append(event)
    return event["id"]


def _find_event(event_id, requester_id):
    _ensure()
    for club_id, events in _events.items():
        for event in events:
            if event["id"] == event_id:
                _check_club_access(club_id, requester_id)
                return event
    raise NotFoundError(f"event {event_id}")


def update_event(event_id, requester_id, data):
    event = _find_event(event_id, requester_id)
    merged = dict(event, **{k: v for k, v in data.items() if k in
                            ("event_date", "start_time", "end_time", "meeting_place", "meeting_time")})
    _validate_event(merged)
    event.update({k: merged[k] for k in ("event_date", "start_time", "end_time", "meeting_place", "meeting_time")})


def set_event_status(event_id, requester_id, status):
    """「中止」にする／「予定」に戻す（SP-73）。すでにある申込の状態は変えない。"""
    if status not in (STATUS_PLANNED, STATUS_CANCELED):
        raise ValidationError("invalid:status")
    event = _find_event(event_id, requester_id)
    if event["status"] == status:
        raise ConflictError("already_" + ("planned" if status == STATUS_PLANNED else "canceled"))
    event["status"] = status


# ---- メンバー（Should）----------------------------------------------------------

def _member_row(employee_id):
    name, dept, *_rest = profile_service._basic(employee_id)
    return {"id": employee_id, "name": name, "dept": dept}


def list_club_members(club_id, requester_id):
    """メンバー一覧（幹事を含む）。"""
    _check_club_access(club_id, requester_id)
    return [_member_row(e) for e in _members[club_id]]


def add_club_member(club_id, requester_id, employee_id):
    club = _check_club_access(club_id, requester_id)
    employee_id = (employee_id or "").strip().upper()
    if not profile_service._is_valid_id(employee_id):
        raise NotFoundError(f"employee {employee_id}")
    if employee_id in _members[club["id"]]:
        raise ConflictError("already_member")
    _members[club["id"]].append(employee_id)


def remove_club_member(club_id, requester_id, employee_id):
    club = _check_club_access(club_id, requester_id)
    employee_id = (employee_id or "").strip().upper()
    if employee_id == club["organizer_id"]:
        raise ValidationError("organizer")  # 幹事は外せない（先に幹事を変更する）
    if employee_id not in _members[club["id"]]:
        raise NotFoundError(f"member {employee_id}")
    _members[club["id"]].remove(employee_id)
