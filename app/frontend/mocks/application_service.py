"""【仮の申込サービス】本物の services/application_service.py の代役（部活詳細・メッセージ画面用）。

本物（I-F契約 1.3）と同じ関数名・引数・戻り値・例外にそろえてある。
  apply / cancel / list_my_applications / list_received_applications / confirm_stamp
本物には無いので、こちらから提案する形で仮に置いているもの：
  send_message(application_id, sender_id, body)   … だーあさに契約への追加を依頼する
  申込の dict の "organizer"（幹事の id と名前）   … 本物の行は organizer_id しか持たない
DB の代わりに、メモリ上の dict で動く。動作確認用のデモデータ入り。
"""

from datetime import datetime, timedelta, timezone

from services.errors import ConflictError, NotFoundError, PermissionDeniedError, ValidationError

_JST = timezone(timedelta(hours=9))  # Windows には時間帯DBが無いので、固定の +9時間を使う

_STATUS_APPLIED = "申込済み"
_STATUS_CANCELED = "キャンセル"

# 申込済みの (開催ID, 社員ID)。部活詳細の重複申込チェック用。E001 は開催12に申込済みから始める
applied = {(12, "E001")}
_next_application_id = [1000]
_next_message_id = [5000]


def _now():
    return datetime.now(_JST)


def _iso(dt):
    return dt.isoformat()


# ---- 開催・部活・社員の仮データ（search_service から引く） --------------------

_PAST_EVENT_ID = 59  # 終わった開催（確認用）。将棋部（club 5）の昨日の開催


def _event_row(event_id):
    """開催の行。本物の events 行と同じキー（id など）。無ければ None。"""
    from mocks import search_service  # 循環を避けるため、使うときに読み込む

    if event_id == _PAST_EVENT_ID:
        yesterday = _now().date() - timedelta(days=1)
        return {"id": event_id, "club_id": 5, "event_date": yesterday, "start_time": "19:00",
                "end_time": "20:30", "meeting_place": "東京オフィス 1F ロビー",
                "meeting_time": "19:00", "status": "予定"}
    event = search_service.find_event(event_id)
    if event is None:
        return None
    row = {key: value for key, value in event.items() if key != "event_id"}
    row["id"] = event["event_id"]
    return row


def _club_row(club_id):
    """(部活の行, 幹事 {id, name}) を返す。"""
    from mocks import search_service

    club = next(c for c in search_service._search_pool() if c["club_id"] == club_id)
    info = search_service._DETAIL_INFO[club_id]
    return {"id": club_id, "name": club["name"], "icon": club["icon"], "organizer_id": info[6]}, {"id": info[6], "name": info[7]}


_EMPLOYEES = {
    "E001": ("デモ社員 E001", "営業部", "中途", 2015),
    "E102": ("鈴木 花子", "開発部", "新卒", 2021),
    "E103": ("田中 一郎", "人事部", "中途", 2016),
    "E104": ("伊藤 美穂", "経理部", "新卒", 2020),
    "E201": ("高橋 美咲", "営業部", "新卒", 2019),
}


def _employee_row(employee_id):
    if employee_id in _EMPLOYEES:
        name, dept, entry_type, joined = _EMPLOYEES[employee_id]
    else:
        name, dept, entry_type, joined = f"デモ社員 {employee_id}", "デモ部", "中途", 2020
    return {"id": employee_id, "name": name, "dept": dept, "entry_type": entry_type, "joined_year": joined}


def _at(event, time_key):
    hh, mm = str(event[time_key])[:5].split(":")
    return datetime(event["event_date"].year, event["event_date"].month, event["event_date"].day,
                    int(hh), int(mm), tzinfo=_JST)


# ---- 申込データ（メモリ上） ---------------------------------------------------
# 1件 = 本物の applications 行 + messages。nested（events / clubs / employees）は取り出すときに付ける。

_apps = {}


def _message(application_id, sender_id, body, minutes_ago):
    _next_message_id[0] += 1
    return {"id": _next_message_id[0], "application_id": application_id, "sender_id": sender_id,
            "body": body, "sent_at": _iso(_now() - timedelta(minutes=minutes_ago))}


def _seed():
    def add(app_id, event_id, applicant_id, status, first, confirmed, messages, applied_minutes_ago):
        _apps[app_id] = {
            "id": app_id, "event_id": event_id, "applicant_id": applicant_id, "status": status,
            "is_first_time": first, "applied_at": _iso(_now() - timedelta(minutes=applied_minutes_ago)),
            "canceled_at": _iso(_now()) if status == _STATUS_CANCELED else None,
            "confirmed_at": _iso(_now()) if confirmed else None,
            "messages": messages,
        }

    # E001 の申込（自分の申込タブ）
    add(1, 12, "E001", _STATUS_APPLIED, True, True, [
        _message(1, "E001", "初めてですが、よろしくお願いします。", 300),
        _message(1, "E201", "お待ちしています！動きやすい服装でどうぞ。", 240),
    ], 320)
    add(2, 22, "E001", _STATUS_CANCELED, False, False, [
        _message(2, "E001", "予定が入ってしまいました。", 1000),
    ], 1100)
    add(3, _PAST_EVENT_ID, "E001", _STATUS_APPLIED, False, False, [], 5000)
    # E001 が幹事のバスケ部（club 4）に届いた申込（届いた申込タブ）
    add(11, 41, "E102", _STATUS_APPLIED, True, False, [
        _message(11, "E102", "初参加です。靴はバスケ用が必要ですか？", 60),
    ], 70)
    add(12, 42, "E103", _STATUS_APPLIED, False, False, [], 50)
    add(13, 41, "E104", _STATUS_CANCELED, False, False, [], 200)


_seed()


def _with_nested(app):
    """本物の取り出し結果と同じ形（events に開催、その中の clubs に部活、employees に申込者）にする。"""
    event = _event_row(app["event_id"])
    club, organizer = _club_row(event["club_id"])
    return {
        **{k: v for k, v in app.items() if k != "messages"},
        "events": {**event, "clubs": club},
        "employees": _employee_row(app["applicant_id"]),
        "organizer": organizer,  # 【提案】本物には無い
        "messages": [dict(m) for m in app["messages"]],
    }


# ---- I-F契約 1.3 の関数 -------------------------------------------------------

def apply(event_id, applicant_id, message_text):
    """申込処理（SP-66, I-F契約 1.3）。{"application_id", "is_first_time"} を返す。

    例外：開催が無ければ NotFoundError。中止なら ConflictError("not_open")、
    同じ開催に申込済みなら ConflictError("already_applied")。
    """
    event = _event_row(event_id)
    if event is None:
        raise NotFoundError(f"event {event_id}")
    if event["status"] != "予定":
        raise ConflictError("not_open")
    if (event_id, applicant_id) in applied:
        raise ConflictError("already_applied")
    applied.add((event_id, applicant_id))
    _next_application_id[0] += 1
    app_id = _next_application_id[0]
    messages = [_message(app_id, applicant_id, message_text, 0)] if message_text else []
    _apps[app_id] = {
        "id": app_id, "event_id": event_id, "applicant_id": applicant_id, "status": _STATUS_APPLIED,
        "is_first_time": True, "applied_at": _iso(_now()), "canceled_at": None, "confirmed_at": None,
        "messages": messages,
    }
    return {"application_id": app_id, "is_first_time": True}


def cancel(application_id, requester_id):
    """キャンセル処理（SP-67）。申込者本人のみ、開催の開始時刻より前まで。"""
    app = _apps.get(application_id)
    if app is None:
        raise NotFoundError(f"application {application_id}")
    if app["applicant_id"] != requester_id:
        raise PermissionDeniedError("only the applicant can cancel")
    if app["status"] == _STATUS_CANCELED:
        raise ConflictError()
    if _at(_event_row(app["event_id"]), "start_time") <= _now():
        raise ConflictError()
    app["status"] = _STATUS_CANCELED
    app["canceled_at"] = _iso(_now())
    applied.discard((app["event_id"], app["applicant_id"]))


def list_my_applications(employee_id):
    """自分の申込一覧（SP-37）。開催日が近い順、終わった開催・キャンセルは後ろ。各 dict に "messages" 付き。"""
    now = _now()
    rows = [_with_nested(a) for a in _apps.values() if a["applicant_id"] == employee_id]

    def key(row):
        event = row["events"]
        back = _at(event, "end_time") <= now or row["status"] == _STATUS_CANCELED
        return (1 if back else 0, _at(event, "start_time"), row["id"])

    return sorted(rows, key=key)


def list_received_applications(organizer_id):
    """自分が幹事の部活への申込一覧（SP-40）。新しい順。"""
    rows = []
    for app in _apps.values():
        club, _organizer = _club_row(_event_row(app["event_id"])["club_id"])
        if club["organizer_id"] == organizer_id:
            rows.append(_with_nested(app))
    return sorted(rows, key=lambda r: (r["applied_at"], r["id"]), reverse=True)


def confirm_stamp(application_id, organizer_id):
    """「確認したよ」スタンプ（SP-72）。初参加で未確認の申込にだけ有効。"""
    app = _apps.get(application_id)
    if app is None:
        raise NotFoundError(f"application {application_id}")
    club, _organizer = _club_row(_event_row(app["event_id"])["club_id"])
    if club["organizer_id"] != organizer_id:
        raise PermissionDeniedError("only the organizer can confirm")
    if not app["is_first_time"] or app["confirmed_at"] is not None:
        raise ConflictError()
    app["confirmed_at"] = _iso(_now())


# ---- 提案中（契約に無い）-------------------------------------------------------

def send_message(application_id, sender_id, body):
    """申込に紐づくメッセージを送る（SP-38）。【提案】だーあさに契約への追加を依頼する。

    送れるのは申込者本人と、その部活の幹事だけ（PermissionDeniedError）。
    本文が空なら ValidationError、キャンセル済みの申込には ConflictError、申込が無ければ NotFoundError。
    本物では、相手への通知（「メッセージ」）も送る。
    """
    app = _apps.get(application_id)
    if app is None:
        raise NotFoundError(f"application {application_id}")
    club, _organizer = _club_row(_event_row(app["event_id"])["club_id"])
    if sender_id not in (app["applicant_id"], club["organizer_id"]):
        raise PermissionDeniedError("only the applicant or the organizer can send")
    if not (body or "").strip():
        raise ValidationError("body is empty")
    if app["status"] == _STATUS_CANCELED:
        raise ConflictError()
    app["messages"].append(_message(application_id, sender_id, body.strip(), 0))
