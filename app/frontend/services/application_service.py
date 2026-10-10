"""申込まわりのサービス（I-F契約 1.3, 仕様.md SP-66〜68, SP-72、設計.md 5.1〜5.4）。

- 申込（5.1）は 開催確認→重複確認→初参加判定→申込保存→メッセージ→幹事通知→操作履歴 の順に行う。
- 初参加の判定（5.4）は _is_first_time の1箇所に集約する。
- エラーメッセージの文言はここでは組み立てない（I-F契約 0.4）。例外の種類と ConflictError.reason で画面に伝える。
- 日時は日本時間（N-05）。events の event_date / start_time / end_time は日本時間の壁時計として扱う。
"""

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from repositories import (
    applications_repo,
    club_members_repo,
    clubs_repo,
    employees_repo,
    events_repo,
    messages_repo,
)
from services import action_log_service, notification_service
from services.errors import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)

_JST = ZoneInfo("Asia/Tokyo")

_STATUS_APPLIED = "申込済み"
_STATUS_CANCELED = "キャンセル"
_EVENT_OPEN = "予定"


def _now() -> datetime:
    return datetime.now(_JST)


def _event_datetime(event: dict, time_key: str) -> datetime:
    """events 行の event_date と時刻列（start_time / end_time）から日本時間の datetime を作る。"""
    d = event["event_date"]
    t = event[time_key]
    if not isinstance(d, date):
        d = date.fromisoformat(str(d))
    if not isinstance(t, time):
        t = time.fromisoformat(str(t))
    return datetime.combine(d, t.replace(tzinfo=None), tzinfo=_JST)


def _is_first_time(club_id: int, employee_id: str) -> bool:
    """初参加の判定（SP-68, 設計.md 5.4）。メンバーでなく、その部活の過去開催への非キャンセル申込もない。"""
    if club_members_repo.is_member(club_id, employee_id):
        return False
    if applications_repo.has_past_non_canceled(club_id, employee_id):
        return False
    return True


def apply(event_id: int, applicant_id: str, message_text: str | None) -> dict:
    """申込処理（SP-66）。戻り値は {"application_id": int, "is_first_time": bool}。"""
    event = events_repo.get(event_id)
    if event is None:
        raise NotFoundError(f"event {event_id}")
    if event["status"] != _EVENT_OPEN or _event_datetime(event, "start_time") <= _now():
        raise ConflictError("not_open")
    if applications_repo.exists_active(event_id, applicant_id):
        raise ConflictError("already_applied")

    club_id = event["club_id"]
    is_first_time = _is_first_time(club_id, applicant_id)
    application_id = applications_repo.insert(event_id, applicant_id, is_first_time)

    if message_text and message_text.strip():
        messages_repo.insert(application_id, applicant_id, message_text)

    club = clubs_repo.get(club_id)
    if club is not None and club["organizer_id"] != applicant_id:
        notification_service.notify(
            club["organizer_id"],
            "申込",
            application_id=application_id,
            event_id=event_id,
            body="新しい申込があります",
        )

    action_log_service.record_apply(applicant_id, club_id)
    return {"application_id": application_id, "is_first_time": is_first_time}


def cancel(application_id: int, requester_id: str) -> None:
    """キャンセル処理（SP-67）。申込者本人のみ、開催の開始時刻より前まで。"""
    application = applications_repo.get(application_id)
    if application is None:
        raise NotFoundError(f"application {application_id}")
    if application["applicant_id"] != requester_id:
        raise PermissionDeniedError("only the applicant can cancel")
    if application["status"] == _STATUS_CANCELED:
        raise ConflictError()
    event = events_repo.get(application["event_id"])
    if event is None:
        raise NotFoundError(f"event {application['event_id']}")
    now = _now()
    if _event_datetime(event, "start_time") <= now:
        raise ConflictError()

    applications_repo.update_status(application_id, _STATUS_CANCELED, canceled_at=now.isoformat())

    club = clubs_repo.get(event["club_id"])
    if club is not None and club["organizer_id"] != requester_id:
        notification_service.notify(
            club["organizer_id"],
            "キャンセル",
            application_id=application_id,
            event_id=event["id"],
            body="申込がキャンセルされました",
        )


def _is_back_group(application: dict, now: datetime) -> bool:
    """「自分の申込」の後ろ側（終わった開催・キャンセル）か。"""
    event = application["events"]
    ended = _event_datetime(event, "end_time") <= now
    return ended or application["status"] == _STATUS_CANCELED


def _start_key(application: dict):
    return (_event_datetime(application["events"], "start_time"), application["id"])


def _organizer_of(application: dict, cache: dict) -> dict:
    """その申込の部活の幹事 {"id", "name"}（SP-37）。見つからなければ name を None にする。"""
    organizer_id = application["events"]["clubs"]["organizer_id"]
    if organizer_id not in cache:
        employee = employees_repo.get_by_id(organizer_id)
        if employee is None:
            cache[organizer_id] = {"id": organizer_id, "name": None}
        else:
            cache[organizer_id] = {"id": employee["id"], "name": employee["name"]}
    return dict(cache[organizer_id])


def list_my_applications(employee_id: str) -> list[dict]:
    """自分の申込一覧（SP-37）。前側は開催日が近い順、後ろ側（終わった開催・キャンセル）は新しい順。

    各dictに "messages" と "organizer"（幹事 {"id", "name"}）を付ける。
    """
    now = _now()
    rows = applications_repo.list_by_applicant(employee_id)
    front = sorted((a for a in rows if not _is_back_group(a, now)), key=_start_key)
    back = sorted((a for a in rows if _is_back_group(a, now)), key=_start_key, reverse=True)
    organizers: dict = {}
    return [
        {
            **a,
            "messages": messages_repo.list_by_application(a["id"]),
            "organizer": _organizer_of(a, organizers),
        }
        for a in front + back
    ]


def list_received_applications(organizer_id: str) -> list[dict]:
    """自分が幹事を務める部活への申込一覧（SP-40）。未読通知がある申込を先頭、そのあとは新しい順。"""
    unread_application_ids = {
        n["application_id"]
        for n in notification_service.list_notifications(organizer_id)
        if n["is_unread"] and n.get("application_id") is not None
    }
    rows: list[dict] = []
    for club in clubs_repo.list_by_organizer(organizer_id):
        rows.extend(applications_repo.list_by_organizer_club(club["id"]))
    rows.sort(key=lambda a: (a["applied_at"], a["id"]), reverse=True)
    rows.sort(key=lambda a: 0 if a["id"] in unread_application_ids else 1)
    return [
        {**a, "messages": messages_repo.list_by_application(a["id"])} for a in rows
    ]


def confirm_stamp(application_id: int, organizer_id: str) -> None:
    """「確認したよ」スタンプ（SP-72）。is_first_time が true で未確認の申込にのみ有効。キャンセル済みの申込には押せない（SP-67）。"""
    application = applications_repo.get(application_id)
    if application is None:
        raise NotFoundError(f"application {application_id}")
    event = events_repo.get(application["event_id"])
    if event is None:
        raise NotFoundError(f"event {application['event_id']}")
    club = clubs_repo.get(event["club_id"])
    if club is None or club["organizer_id"] != organizer_id:
        raise PermissionDeniedError("only the organizer can confirm")
    if (
        application["status"] == _STATUS_CANCELED
        or not application["is_first_time"]
        or application.get("confirmed_at") is not None
    ):
        raise ConflictError()

    applications_repo.update_status(
        application_id, application["status"], confirmed_at=_now().isoformat()
    )
    notification_service.notify(
        application["applicant_id"],
        "スタンプ",
        application_id=application_id,
        event_id=event["id"],
        body="幹事が確認しました",
    )


def send_message(application_id: int, sender_id: str, body: str) -> None:
    """申込へのメッセージ送信（SP-38, I-F契約 1.3）。送れるのは申込者本人とその部活の幹事のみ。

    例外の判定順は NotFoundError → PermissionDeniedError → ValidationError → ConflictError（キャンセル済み）。
    body は前後の空白を除いて保存し、相手に種別「メッセージ」の通知を1件送る（本文は固定文）。
    申込者が幹事本人のときは相手がいないため通知は送らない。
    """
    application = applications_repo.get(application_id)
    if application is None:
        raise NotFoundError(f"application {application_id}")
    event = events_repo.get(application["event_id"])
    if event is None:
        raise NotFoundError(f"event {application['event_id']}")
    club = clubs_repo.get(event["club_id"])
    if club is None:
        raise NotFoundError(f"club {event['club_id']}")

    applicant_id = application["applicant_id"]
    organizer_id = club["organizer_id"]
    if sender_id not in (applicant_id, organizer_id):
        raise PermissionDeniedError("only the applicant or the organizer can send")

    text = (body or "").strip()
    if not text:
        raise ValidationError("body is required")
    if application["status"] == _STATUS_CANCELED:
        raise ConflictError()

    messages_repo.insert(application_id, sender_id, text)

    recipient_id = organizer_id if sender_id == applicant_id else applicant_id
    if recipient_id != sender_id:
        notification_service.notify(
            recipient_id,
            "メッセージ",
            application_id=application_id,
            body="新しいメッセージがあります",
        )
