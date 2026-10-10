"""部活管理（S10）の部活・開催・メンバーの参照と更新（I-F契約 1.7, 仕様.md SP-58〜SP-62, SP-73, SP-74）。

- 権限は新しい関数を作らず auth_service.get_role / is_organizer で判定する（運営者=admin、幹事=organizer）。
- 例外の判定順は各関数の docstring のとおり（NotFound → Permission → Validation → Conflict）。
- ValidationError の理由コードは引数文字列で持たせる（required:<key> / past_date / end_before_start /
  invalid:<key> / unknown:<key>）。ConflictError の理由コードは reason に持たせる。
- 「今日」は Asia/Tokyo の日付で判定する。
"""

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from repositories import (
    activities_repo,
    applications_repo,
    club_members_repo,
    clubs_repo,
    employees_repo,
    events_repo,
)
from services import auth_service, notification_service
from services.errors import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)

_JST = ZoneInfo("Asia/Tokyo")

# 部活のフィールド定義（A-1裁定）
_CLUB_REQUIRED = (
    "name",
    "icon",
    "activity_id",
    "location",
    "slot",
    "frequency",
    "level",
    "fact_adult_starters",
    "message",
    "fee",
    "rental",
    "join_leave",
    "after_activity",
    "organizer_id",
)
_CLUB_OPTIONAL = ("schedule_note", "fee_note", "belongings_note", "mood_tags")
_CLUB_KEYS = _CLUB_REQUIRED + _CLUB_OPTIONAL

# 仕様.md 3.2 の選択肢（DBのCHECK制約と同じ）
_CHOICES = {
    "location": ("東京", "大阪"),
    "slot": ("平日夜", "土曜午前", "土曜午後", "日曜"),
    "frequency": ("毎週", "月2回", "月1回", "不定期"),
    "level": ("初心者歓迎", "レベル問わず", "経験者向け"),
    "fact_adult_starters": ("多い", "少しいる", "いない"),
    "fee": ("無料", "500円以下", "1,000円以下", "それ以上"),
    "rental": ("あり", "なし"),
    "join_leave": ("OK", "できれば最初から", "要相談"),
    "after_activity": ("なし", "ランチ・お茶", "飲み会", "日による"),
}
_MOOD_TAGS = (
    "ゆるめ",
    "しっかり練習",
    "黙々と集中",
    "わいわい賑やか",
    "おしゃべり多め",
    "少人数",
)
_MOOD_TAGS_MAX = 3

_EVENT_REQUIRED = ("event_date", "start_time", "end_time", "meeting_place")
_EVENT_KEYS = _EVENT_REQUIRED + ("meeting_time",)

_STATUSES = ("予定", "中止")
_CANCEL_BODY = "開催が中止になりました"


def _today() -> date:
    return datetime.now(_JST).date()


def _is_blank(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _same_id(a: str | None, b: str | None) -> bool:
    return (a or "").strip().upper() == (b or "").strip().upper()


# --- 権限 -------------------------------------------------------------------


def _is_admin(requester_id: str) -> bool:
    return auth_service.get_role(requester_id) == auth_service.ROLE_ADMIN


def _role_for_club(club_id: int, requester_id: str) -> str:
    """club_id の部活が無ければ NotFoundError（get_role が送出）。"""
    return auth_service.get_role(requester_id, club_id)


def _require_manager(club_id: int, requester_id: str) -> str:
    role = _role_for_club(club_id, requester_id)
    if role not in (auth_service.ROLE_ADMIN, auth_service.ROLE_ORGANIZER):
        raise PermissionDeniedError()
    return role


def _event_and_club_id(event_id: int) -> tuple[dict, int]:
    event = events_repo.get(event_id)
    if event is None:
        raise NotFoundError(f"event {event_id}")
    return event, event["club_id"]


# --- 型の読み替え -------------------------------------------------------------


def _to_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _to_time(value) -> time:
    if isinstance(value, datetime):
        return value.time()
    if isinstance(value, time):
        return value
    return time.fromisoformat(str(value))


def _to_time_or_none(value) -> time | None:
    return None if value is None else _to_time(value)


# --- 部活の検証 ---------------------------------------------------------------


def _validate_club_fields(fields: dict, *, allow_is_active: bool) -> None:
    """unknown → required → invalid の順に判定する。fields に含まれるキーだけを対象にする。"""
    allowed = _CLUB_KEYS + (("is_active",) if allow_is_active else ())
    for key in fields:
        if key not in allowed:
            raise ValidationError(f"unknown:{key}")
    for key in _CLUB_REQUIRED:
        if key in fields and _is_blank(fields[key]):
            raise ValidationError(f"required:{key}")
    for key, choices in _CHOICES.items():
        if key in fields and fields[key] not in choices:
            raise ValidationError(f"invalid:{key}")
    if "activity_id" in fields:
        activity_id = fields["activity_id"]
        if (
            isinstance(activity_id, bool)
            or not isinstance(activity_id, int)
            or activities_repo.get(activity_id) is None
        ):
            raise ValidationError("invalid:activity_id")
    if "organizer_id" in fields and employees_repo.get_by_id(fields["organizer_id"]) is None:
        raise ValidationError("invalid:organizer_id")
    if "mood_tags" in fields and fields["mood_tags"] is not None:
        tags = fields["mood_tags"]
        if (
            not isinstance(tags, (list, tuple))
            or len(tags) > _MOOD_TAGS_MAX
            or any(tag not in _MOOD_TAGS for tag in tags)
        ):
            raise ValidationError("invalid:mood_tags")
    if "is_active" in fields and not isinstance(fields["is_active"], bool):
        raise ValidationError("invalid:is_active")


def _club_data(fields: dict) -> dict:
    """repository に渡す dict。organizer_id は employees の正規の社員IDに揃える。"""
    data = dict(fields)
    if "organizer_id" in data:
        data["organizer_id"] = employees_repo.get_by_id(data["organizer_id"])["id"]
    if data.get("mood_tags") is not None:
        data["mood_tags"] = list(data["mood_tags"])
    return data


# --- 開催の検証 ---------------------------------------------------------------


def _parse_event_fields(fields: dict) -> dict:
    """unknown → required の順に判定し、日付・時刻を date / time に読み替えて返す。"""
    for key in fields:
        if key not in _EVENT_KEYS:
            raise ValidationError(f"unknown:{key}")
    for key in _EVENT_REQUIRED:
        if key in fields and _is_blank(fields[key]):
            raise ValidationError(f"required:{key}")
    parsed = dict(fields)
    try:
        if "event_date" in parsed:
            parsed["event_date"] = _to_date(parsed["event_date"])
    except (TypeError, ValueError):
        raise ValidationError("invalid:event_date") from None
    for key in ("start_time", "end_time", "meeting_time"):
        if key in parsed:
            try:
                parsed[key] = _to_time_or_none(parsed[key])
            except (TypeError, ValueError):
                raise ValidationError(f"invalid:{key}") from None
    return parsed


def _event_row(parsed: dict) -> dict:
    """repository（JSON）に渡せるよう date / time を ISO 文字列にする。"""
    return {
        key: value.isoformat() if isinstance(value, (date, time)) else value
        for key, value in parsed.items()
    }


# --- 部活 -------------------------------------------------------------------


def list_manageable_clubs(requester_id: str) -> list[dict]:
    """管理画面（S10）の部活選択の一覧（SP-58）。運営者は全部活、幹事は自分の部活（非公開も含む）を id 昇順で返す。

    運営者でも幹事でもない社員には空リスト（例外にしない）。
    """
    if _is_admin(requester_id):
        clubs = clubs_repo.list_all_for_admin()
    else:
        clubs = clubs_repo.list_by_organizer(requester_id.strip().upper())
    return [
        {
            "club_id": c["id"],
            "name": c["name"],
            "icon": c.get("icon"),
            "location": c["location"],
            "slot": c["slot"],
            "organizer_id": c["organizer_id"],
            "is_active": c["is_active"],
        }
        for c in sorted(clubs, key=lambda c: c["id"])
    ]


def get_club(club_id: int, requester_id: str) -> dict:
    """部活情報タブ（SP-59）の編集用に部活の全項目を返す。主キーは "id" ではなく "club_id"。

    例外の順: NotFoundError → PermissionDeniedError。
    """
    _require_manager(club_id, requester_id)
    club = clubs_repo.get(club_id)
    if club is None:
        raise NotFoundError(f"club {club_id}")
    result = {("club_id" if k == "id" else k): v for k, v in club.items()}
    return result


def create_club(requester_id: str, fields: dict) -> int:
    """部活の新規作成（SP-58, SP-59, SP-74）。運営者のみ。採番された club_id を返す。

    例外の順: PermissionDeniedError → ValidationError。is_active は受け取らず true で作る。
    """
    if not _is_admin(requester_id):
        raise PermissionDeniedError()
    _validate_club_fields(fields, allow_is_active=False)
    for key in _CLUB_REQUIRED:
        if key not in fields:
            raise ValidationError(f"required:{key}")
    data = _club_data(fields)
    data["is_active"] = True
    club_id = clubs_repo.create(data)
    club_members_repo.add_member(club_id, data["organizer_id"])
    return club_id


def update_club(club_id: int, requester_id: str, fields: dict) -> None:
    """部活情報の保存（SP-59）。fields に含めたキーだけを更新する。

    organizer_id と is_active の「変更」は運営者のみ（現在と同じ値なら無視する）。
    例外の順: NotFoundError → PermissionDeniedError → ValidationError。
    """
    role = _role_for_club(club_id, requester_id)
    if role not in (auth_service.ROLE_ADMIN, auth_service.ROLE_ORGANIZER):
        raise PermissionDeniedError()
    club = clubs_repo.get(club_id)
    if club is None:
        raise NotFoundError(f"club {club_id}")

    fields = dict(fields)
    if role != auth_service.ROLE_ADMIN:
        for key in ("organizer_id", "is_active"):
            if key not in fields:
                continue
            same = (
                _same_id(fields[key], club["organizer_id"])
                if key == "organizer_id"
                else fields[key] == club["is_active"]
            )
            if not same:
                raise PermissionDeniedError()
            del fields[key]

    _validate_club_fields(fields, allow_is_active=True)
    data = _club_data(fields)
    if not data:
        return
    clubs_repo.update(club_id, data)
    new_organizer = data.get("organizer_id")
    if new_organizer is not None and new_organizer != club["organizer_id"]:
        if not club_members_repo.is_member(club_id, new_organizer):
            club_members_repo.add_member(club_id, new_organizer)


# --- 開催 -------------------------------------------------------------------


def list_club_events(club_id: int, requester_id: str) -> list[dict]:
    """開催タブ（SP-60）の一覧。今日（Asia/Tokyo）以降の開催を日付順で返す。中止も含む。

    例外の順: NotFoundError → PermissionDeniedError。
    """
    _require_manager(club_id, requester_id)
    today = _today()
    result = []
    for event in events_repo.list_upcoming_by_club(club_id):
        event_date = _to_date(event["event_date"])
        if event_date < today:
            continue
        result.append(
            {
                "event_id": event["id"],
                "event_date": event_date,
                "start_time": _to_time(event["start_time"]),
                "end_time": _to_time(event["end_time"]),
                "meeting_place": event["meeting_place"],
                "meeting_time": _to_time_or_none(event.get("meeting_time")),
                "status": event["status"],
                "applicant_count": len(applications_repo.list_participants(event["id"])),
            }
        )
    return result


def create_event(club_id: int, requester_id: str, fields: dict) -> int:
    """開催の追加（SP-60, SP-61）。状態「予定」で作り、event_id を返す。

    検証の順: unknown → required → past_date → end_before_start。
    例外の順: NotFoundError（club_id）→ PermissionDeniedError → ValidationError。
    """
    _require_manager(club_id, requester_id)
    parsed = _parse_event_fields(fields)
    for key in _EVENT_REQUIRED:
        if key not in parsed:
            raise ValidationError(f"required:{key}")
    if parsed["event_date"] < _today():
        raise ValidationError("past_date")
    if parsed["end_time"] <= parsed["start_time"]:
        raise ValidationError("end_before_start")
    row = _event_row(parsed)
    row["club_id"] = club_id
    row["status"] = "予定"
    return events_repo.create(row)


def update_event(event_id: int, requester_id: str, fields: dict) -> None:
    """開催の編集（SP-60, SP-61）。fields に含めたキーだけを更新する。status は受け取らない。

    end_before_start は更新後の開始・終了時刻（fields に無いキーは現在の値）で判定する。
    past_date は fields に event_date を含む場合のみ判定する。
    例外の順: NotFoundError（event_id）→ PermissionDeniedError → ValidationError。
    """
    event, club_id = _event_and_club_id(event_id)
    _require_manager(club_id, requester_id)
    parsed = _parse_event_fields(fields)
    if "event_date" in parsed and parsed["event_date"] < _today():
        raise ValidationError("past_date")
    start = parsed.get("start_time") or _to_time(event["start_time"])
    end = parsed.get("end_time") or _to_time(event["end_time"])
    if ("start_time" in parsed or "end_time" in parsed) and end <= start:
        raise ValidationError("end_before_start")
    if not parsed:
        return
    events_repo.update(event_id, _event_row(parsed))


def set_event_status(event_id: int, requester_id: str, status: str) -> None:
    """開催の「中止にする」「予定に戻す」（SP-60, SP-73）。

    中止にしたときは、申込済みの申込者全員へ通知を自動送信する（B-1裁定。本文は固定文）。
    「予定に戻す」ときは通知しない。通知済みかどうかは記憶せず、再中止のたびに通知する。
    例外の順: NotFoundError → PermissionDeniedError → ValidationError → ConflictError("same_status")。
    """
    event, club_id = _event_and_club_id(event_id)
    _require_manager(club_id, requester_id)
    if status not in _STATUSES:
        raise ValidationError("invalid:status")
    if event["status"] == status:
        raise ConflictError("same_status")
    events_repo.set_status(event_id, status)
    if status == "中止":
        for application in applications_repo.list_participants(event_id):
            notification_service.notify(
                application["applicant_id"],
                "中止",
                application_id=application["id"],
                event_id=event_id,
                body=_CANCEL_BODY,
            )


def get_last_meeting_place(club_id: int) -> str | None:
    """開催追加フォームの集合場所の初期値。開催が無い・部活が無いときは None。権限は判定しない。"""
    return events_repo.get_last_meeting_place(club_id)


# --- メンバー -----------------------------------------------------------------


def list_club_members(club_id: int, requester_id: str) -> list[dict]:
    """メンバータブ（SP-62）の一覧。club_members の並び順のまま。

    例外の順: NotFoundError → PermissionDeniedError。
    """
    _require_manager(club_id, requester_id)
    club = clubs_repo.get(club_id)
    if club is None:
        raise NotFoundError(f"club {club_id}")
    result = []
    for member in club_members_repo.list_members(club_id):
        employee = employees_repo.get_by_id(member["employee_id"])
        if employee is None:
            continue
        result.append(
            {
                "id": employee["id"],
                "name": employee["name"],
                "dept": employee["dept"],
                "joined_at": member.get("joined_at"),
                "is_organizer": _same_id(employee["id"], club["organizer_id"]),
            }
        )
    return result


def add_club_member(club_id: int, requester_id: str, employee_id: str) -> None:
    """メンバーの追加（SP-62, 裁定#13）。

    例外の順: NotFoundError（club_id / employee_id）→ PermissionDeniedError → ConflictError("already_member")。
    """
    role = _role_for_club(club_id, requester_id)
    employee = employees_repo.get_by_id(employee_id)
    if employee is None:
        raise NotFoundError(f"employee {employee_id}")
    if role not in (auth_service.ROLE_ADMIN, auth_service.ROLE_ORGANIZER):
        raise PermissionDeniedError()
    if club_members_repo.is_member(club_id, employee["id"]):
        raise ConflictError("already_member")
    club_members_repo.add_member(club_id, employee["id"])


def remove_club_member(club_id: int, requester_id: str, employee_id: str) -> None:
    """メンバーの削除（SP-62）。

    例外の順: NotFoundError（club_id / 所属メンバーでない）→ PermissionDeniedError → ConflictError("organizer")。
    """
    role = _role_for_club(club_id, requester_id)
    employee = employees_repo.get_by_id(employee_id)
    if employee is None or not club_members_repo.is_member(club_id, employee["id"]):
        raise NotFoundError(f"member {employee_id}")
    if role not in (auth_service.ROLE_ADMIN, auth_service.ROLE_ORGANIZER):
        raise PermissionDeniedError()
    club = clubs_repo.get(club_id)
    if club is None:
        raise NotFoundError(f"club {club_id}")
    if _same_id(employee["id"], club["organizer_id"]):
        raise ConflictError("organizer")
    club_members_repo.remove_member(club_id, employee["id"])


def list_selectable_employees(requester_id: str) -> list[dict]:
    """幹事選択（SP-59）・メンバー追加（SP-62）の社員の選択肢。全社員の id と name を返す。

    権限: 運営者、またはいずれかの部活の幹事。それ以外は PermissionDeniedError。
    """
    if not (_is_admin(requester_id) or auth_service.is_organizer(requester_id)):
        raise PermissionDeniedError()
    return [{"id": e["id"], "name": e["name"]} for e in employees_repo.list_all()]
