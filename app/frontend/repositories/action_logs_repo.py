"""action_logs テーブルへのアクセス層（I-F契約 2.9）。

- 操作履歴（search_club / view_club / apply）を記録・参照する。
- action ごとの必須項目（search_club→conditions, view_club/apply→club_id）は
  DBの action_logs_shape_check が最後の砦。事前検証は service 層（action_log_service）の担当とし、
  ここは薄く保つ（不正な組み合わせは DB の CHECK 制約がエラーとして拒否し、そのまま伝播させる）。
- 「存在しない」は例外にせず None で返す（I-F契約 0.4）。
"""

from db.client import supabase


def insert(employee_id: str, action: str, *, club_id=None, conditions=None) -> int:
    """操作履歴を1件追加し、採番された id を返す。

    None の列は送らない（DBのデフォルト/NULLに委ねる）。
    action と必須項目の整合は DB の action_logs_shape_check が担保する。
    """
    row: dict = {"employee_id": employee_id, "action": action}
    if club_id is not None:
        row["club_id"] = club_id
    if conditions is not None:
        row["conditions"] = conditions
    res = supabase.table("action_logs").insert(row).execute()
    return res.data[0]["id"]


def get_last(employee_id: str, action: str) -> dict | None:
    """(employee_id, action) の最新1件を返す。無ければ None。

    連続同一操作の二重記録防止の比較に使う（session_state ではなく DB を見る）。
    """
    res = (
        supabase.table("action_logs")
        .select("*")
        .eq("employee_id", employee_id)
        .eq("action", action)
        .order("created_at", desc=True)
        .order("id", desc=True)
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None
