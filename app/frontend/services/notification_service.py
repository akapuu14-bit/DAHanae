"""アプリ内通知のサービス（I-F契約 1.4, 仕様.md SP-70〜72）。

- 未読件数（count_unread）は SP-70 の算出値（自分あての read_at が空の通知）を1本だけ持つ。
  サイドバー（SP-01）もこの関数を使い、別集計は作らない。
- 通知の作成（notify）は application_service などから呼ばれる共通関数。
"""

from repositories import notifications_repo
from services.errors import ValidationError

# 仕様.md 4.9 / notifications_type_check
NOTIFICATION_TYPES = ("申込", "キャンセル", "メッセージ", "スタンプ", "中止")

# SP-36 / SP-70：メッセージ画面を開いたときに既読にする種類
_MESSAGES_SCREEN_TYPES = ["申込", "キャンセル", "メッセージ", "スタンプ"]


def count_unread(employee_id: str) -> int:
    """自分あての未読通知件数（SP-70）。"""
    return notifications_repo.count_unread(employee_id)


def list_notifications(employee_id: str) -> list[dict]:
    """自分あての通知を新しい順で返す（SP-44）。各dictに未読フラグ "is_unread" を付ける。"""
    rows = notifications_repo.list_by_recipient(employee_id)
    return [{**r, "is_unread": r.get("read_at") is None} for r in rows]


def mark_read_for_messages_screen(employee_id: str) -> None:
    """メッセージ画面を開いたとき：「申込」「キャンセル」「メッセージ」「スタンプ」を既読にする（SP-36）。"""
    notifications_repo.mark_read(employee_id, list(_MESSAGES_SCREEN_TYPES))


def mark_read_all(employee_id: str) -> None:
    """通知一覧画面を開いたとき：自分あての通知をすべて既読にする（SP-46）。"""
    notifications_repo.mark_read_all(employee_id)


def notify(
    recipient_id: str,
    type_: str,
    *,
    application_id: int | None = None,
    event_id: int | None = None,
    body: str,
) -> None:
    """通知を1件作成する。type_ が5種以外、または body が空白のみなら ValidationError。"""
    if type_ not in NOTIFICATION_TYPES:
        raise ValidationError(f"unknown notification type: {type_!r}")
    if not body or not body.strip():
        raise ValidationError("body is required")
    notifications_repo.insert(
        recipient_id,
        type_,
        application_id=application_id,
        event_id=event_id,
        body=body,
    )
