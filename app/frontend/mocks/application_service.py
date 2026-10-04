"""【仮の申込サービス】本物の services/application_service.py の代役（部活詳細の申込用）。

本物（I-F契約 1.3）の apply と同じ引数・同じ戻り値・同じ例外にそろえてある。
DB の代わりに、メモリ上の applied（申込済みの組）で重複申込などをまねる。
"""

from services.errors import ConflictError, NotFoundError

# 申込済みの (開催ID, 社員ID)。動作確認用に、E001 が開催12に申込済みの状態から始める
applied = {(12, "E001")}
_next_application_id = [1000]


def apply(event_id, applicant_id, message_text):
    """申込処理（SP-66, I-F契約 1.3）。{"application_id", "is_first_time"} を返す。

    例外：開催が無ければ NotFoundError。中止なら ConflictError("not_open")、
    同じ開催に申込済みなら ConflictError("already_applied")。
    """
    from mocks import search_service  # 循環を避けるため、使うときに読み込む

    event = search_service.find_event(event_id)
    if event is None:
        raise NotFoundError(f"event {event_id}")
    if event["status"] != "予定":
        raise ConflictError("not_open")
    if (event_id, applicant_id) in applied:
        raise ConflictError("already_applied")
    applied.add((event_id, applicant_id))
    _next_application_id[0] += 1
    return {"application_id": _next_application_id[0], "is_first_time": True}
