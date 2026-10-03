"""messages テーブルへのアクセス層（I-F契約 2.7）。

- 「存在しない」は例外にせず空リストで返す（I-F契約 0.4）。
- DBエラーはそのまま伝播させる。
- 申込がキャンセル済みでも閲覧できるよう、status では絞り込まない（SP-39）。
"""

from db.client import supabase


def list_by_application(application_id: int) -> list[dict]:
    """その申込のやり取りを古い順（sent_at 昇順、同時刻は id 昇順）で返す。該当なしは空リスト。"""
    res = (
        supabase.table("messages")
        .select("*")
        .eq("application_id", application_id)
        .order("sent_at")
        .order("id")
        .execute()
    )
    return res.data or []


def insert(application_id: int, sender_id: str, body: str) -> int:
    """メッセージを1件追加し、採番された id を返す。sent_at はDBの既定値に委ねる。

    body の空白のみ不可は DB の CHECK 制約（messages_body_not_blank_check）に委ねる。
    """
    res = (
        supabase.table("messages")
        .insert(
            {
                "application_id": application_id,
                "sender_id": sender_id,
                "body": body,
            }
        )
        .execute()
    )
    return res.data[0]["id"]
