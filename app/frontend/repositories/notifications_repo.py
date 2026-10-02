"""notifications テーブルへのアクセス層（I-F契約 2.8）。

- 未読は read_at IS NULL で数える（= NULL との比較ではなく IS NULL）。
- 「存在しない」は例外にせず None / 空リスト / 0 で返す（I-F契約 0.4）。
- DBエラーはそのまま伝播させる。
"""

from datetime import datetime, timezone

from db.client import supabase


def _now_iso() -> str:
    """タイムゾーンaware（UTC）の現在時刻をISO文字列で返す（N-05）。"""
    return datetime.now(timezone.utc).isoformat()


def count_unread(employee_id: str) -> int:
    """未読通知の件数。read_at IS NULL を数える。"""
    res = (
        supabase.table("notifications")
        .select("id", count="exact")
        .eq("recipient_id", employee_id)
        .is_("read_at", "null")
        .limit(1)
        .execute()
    )
    return res.count or 0


def list_by_recipient(employee_id: str) -> list[dict]:
    """宛先社員の通知を新しい順（created_at 降順）で返す。該当なしは空リスト。"""
    res = (
        supabase.table("notifications")
        .select("*")
        .eq("recipient_id", employee_id)
        .order("created_at", desc=True)
        .order("id", desc=True)
        .execute()
    )
    return res.data or []


def insert(
    recipient_id: str,
    type_: str,
    *,
    application_id=None,
    event_id=None,
    body: str,
) -> int:
    """通知を1件追加し、採番された id を返す。"""
    row = {
        "recipient_id": recipient_id,
        "type": type_,
        "application_id": application_id,
        "event_id": event_id,
        "body": body,
    }
    res = supabase.table("notifications").insert(row).execute()
    return res.data[0]["id"]


def mark_read(employee_id: str, types: list[str]) -> None:
    """指定した種類の未読通知だけを既読にする。types が空なら何もしない。"""
    if not types:
        return
    (
        supabase.table("notifications")
        .update({"read_at": _now_iso()})
        .eq("recipient_id", employee_id)
        .in_("type", list(types))
        .is_("read_at", "null")
        .execute()
    )


def mark_read_all(employee_id: str) -> None:
    """宛先社員の未読通知をすべて既読にする（通知一覧を開いたとき用）。"""
    (
        supabase.table("notifications")
        .update({"read_at": _now_iso()})
        .eq("recipient_id", employee_id)
        .is_("read_at", "null")
        .execute()
    )
