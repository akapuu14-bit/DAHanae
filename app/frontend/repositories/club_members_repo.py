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


def list_members_with_employees(club_id: int) -> list[dict]:
    """list_members に、各所属者の社員行（"employees": id・name・dept）を付けて1回で返す。employee_id 順。"""
    res = (
        supabase.table("club_members")
        .select("*, employees(id, name, dept)")
        .eq("club_id", club_id)
        .order("employee_id")
        .execute()
    )
    return res.data or []


def list_active_clubs_for_employees(employee_ids: list[str]) -> list[dict]:
    """複数の社員の所属部活（is_active の部活のみ）をまとめて1回で取る。

    [{"employee_id", "club_id", "name"}] を club_id 順で返す。employee_ids が空なら問い合わせず空リスト。
    """
    ids = list(dict.fromkeys(employee_ids))
    if not ids:
        return []
    res = (
        supabase.table("club_members")
        .select("employee_id, club_id, clubs(name, is_active)")
        .in_("employee_id", ids)
        .execute()
    )
    rows = [
        {"employee_id": r["employee_id"], "club_id": r["club_id"], "name": r["clubs"]["name"]}
        for r in (res.data or [])
        if r.get("clubs") and r["clubs"].get("is_active")
    ]
    return sorted(rows, key=lambda r: (r["club_id"], r["employee_id"]))


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


def list_clubs_by_member(employee_id: str) -> list[int]:
    """その社員が所属する部活の club_id を昇順で返す。所属なしは空リスト。"""
    res = (
        supabase.table("club_members")
        .select("club_id")
        .eq("employee_id", employee_id)
        .order("club_id")
        .execute()
    )
    return [r["club_id"] for r in (res.data or [])]
