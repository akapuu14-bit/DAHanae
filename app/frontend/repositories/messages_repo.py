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


def list_by_applications(application_ids: list[int]) -> dict[int, list[dict]]:
    """複数の申込のやり取りをまとめて1回で取る（list_by_application の一括版）。

    {application_id: [古い順のメッセージ]}。やり取りのない申込もキーを持ち、値は空リスト。
    application_ids が空なら問い合わせず空dictを返す。
    """
    ids = list(dict.fromkeys(application_ids))
    if not ids:
        return {}
    res = (
        supabase.table("messages")
        .select("*")
        .in_("application_id", ids)
        .order("sent_at")
        .order("id")
        .execute()
    )
    result: dict[int, list[dict]] = {i: [] for i in ids}
    for row in res.data or []:
        result[row["application_id"]].append(row)
    return result


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
