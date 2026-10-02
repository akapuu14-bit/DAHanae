"""activities テーブルへのアクセス層（I-F契約 2.2）。

マスタ参照だけの軽い層。
- 「存在しない」は例外にせず None / 空リストで返す（I-F契約 0.4）。
- DBエラーはそのまま伝播させる。
"""

from db.client import supabase


def list_all() -> list[dict]:
    """全活動マスタを id 順で返す。該当なしは空リスト。"""
    res = (
        supabase.table("activities")
        .select("*")
        .order("id")
        .execute()
    )
    return res.data or []


def get(activity_id: int) -> dict | None:
    """activity_id で1件取得する。存在しなければ None（例外にしない）。"""
    res = (
        supabase.table("activities")
        .select("*")
        .eq("id", activity_id)
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None
