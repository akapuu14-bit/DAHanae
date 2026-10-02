"""club_members テーブルへのアクセス層（I-F契約 2.4）。

- (club_id, employee_id) は一意制約。add_member は二重呼び出しでも壊れない。
- 「存在しない」は例外にせず None / 空リスト / False で返す（I-F契約 0.4）。
- DBエラーはそのまま伝播させる。
"""

from db.client import supabase


def is_member(club_id: int, employee_id: str) -> bool:
    """指定社員がその部活の所属者かどうか。初参加判定でも使う。"""
    res = (
        supabase.table("club_members")
        .select("employee_id")
        .eq("club_id", club_id)
        .eq("employee_id", employee_id)
        .limit(1)
        .execute()
    )
    return bool(res.data)


def list_members(club_id: int) -> list[dict]:
    """その部活の所属者一覧を employee_id 順で返す。該当なしは空リスト。"""
    res = (
        supabase.table("club_members")
        .select("*")
        .eq("club_id", club_id)
        .order("employee_id")
        .execute()
    )
    return res.data or []


def add_member(club_id: int, employee_id: str, joined_at=None) -> None:
    """所属を追加する。既に所属済みなら何もしない（二重呼び出し安全）。

    一意制約 (club_id, employee_id) に対し ignore_duplicates で衝突時は無視するため、
    再呼び出しで既存の joined_at を上書きしない。joined_at が None なら列を送らない。
    """
    row: dict = {"club_id": club_id, "employee_id": employee_id}
    if joined_at is not None:
        row["joined_at"] = joined_at
    (
        supabase.table("club_members")
        .upsert(row, on_conflict="club_id,employee_id", ignore_duplicates=True)
        .execute()
    )


def remove_member(club_id: int, employee_id: str) -> None:
    """所属を解除する。存在しなくてもエラーにしない。"""
    (
        supabase.table("club_members")
        .delete()
        .eq("club_id", club_id)
        .eq("employee_id", employee_id)
        .execute()
    )
