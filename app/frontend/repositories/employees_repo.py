"""employees / employee_interests テーブルへのアクセス層（I-F契約 2.1）。

- 「存在しない」は例外にせず None / 空リストで返す（I-F契約 0.4）。
- DBエラーはそのまま伝播させる。
"""

import re

from db.client import supabase


def _escape_like(value: str) -> str:
    """LIKE/ILIKE のワイルドカードを文字として扱うためのエスケープ。"""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def get_by_id(employee_id: str) -> dict | None:
    """社員IDで1件取得する。大文字小文字は区別しない。"""
    if not employee_id or not employee_id.strip():
        return None
    res = (
        supabase.table("employees")
        .select("*")
        .ilike("id", _escape_like(employee_id.strip()))
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None


def _resolve_id_filter(conditions: dict) -> list[str] | None:
    """interests / club_id 条件を社員IDの集合に解決する。

    None: ID絞り込みなし。空リスト: 該当者なし。
    interests は同一項目内OR、club_id は所属者（項目間はAND）。
    """
    id_sets: list[set[str]] = []

    interests = conditions.get("interests")
    if interests:
        rows = (
            supabase.table("employee_interests")
            .select("employee_id")
            .in_("activity_id", list(interests))
            .execute()
            .data
        )
        id_sets.append({r["employee_id"] for r in rows})

    club_id = conditions.get("club_id")
    if club_id is not None:
        rows = (
            supabase.table("club_members")
            .select("employee_id")
            .eq("club_id", club_id)
            .execute()
            .data
        )
        id_sets.append({r["employee_id"] for r in rows})

    if not id_sets:
        return None
    return sorted(set.intersection(*id_sets))


def _build_query(query, conditions: dict, ids: list[str] | None):
    """未指定キー（None・空）は条件にしない。項目間AND、同一項目内OR。"""
    if ids is not None:
        query = query.in_("id", ids)

    name = conditions.get("name")
    if name:
        compact = re.sub(r"\s+", "", name)  # SP-48: 入力側のスペースを無視
        if compact:
            query = query.ilike("name", f"%{_escape_like(compact)}%")

    if conditions.get("depts"):
        query = query.in_("dept", list(conditions["depts"]))
    if conditions.get("locations"):
        query = query.in_("location", list(conditions["locations"]))

    if conditions.get("slots"):
        # SP-49: 参加可能時間を条件にするときは slots_public=false を除外
        query = query.overlaps("available_slots", list(conditions["slots"]))
        query = query.eq("slots_public", True)
    if conditions.get("interests"):
        # SP-49: 興味を条件にするときは interests_public=false を除外
        query = query.eq("interests_public", True)
    return query


def search(conditions: dict, limit: int, offset: int) -> list[dict]:
    """条件に合う社員をID順で limit/offset ページングして返す。"""
    ids = _resolve_id_filter(conditions)
    if ids is not None and not ids:
        return []
    query = _build_query(supabase.table("employees").select("*"), conditions, ids)
    res = query.order("id").range(offset, offset + limit - 1).execute()
    return res.data or []


def count(conditions: dict) -> int:
    """条件に合う社員の全件数を返す。"""
    ids = _resolve_id_filter(conditions)
    if ids is not None and not ids:
        return 0
    query = _build_query(
        supabase.table("employees").select("id", count="exact"), conditions, ids
    )
    res = query.limit(1).execute()
    return res.count or 0


def update_public_settings(
    employee_id: str,
    *,
    interests_public: bool | None = None,
    slots_public: bool | None = None,
) -> None:
    """公開設定を更新する。None の項目は変更しない。"""
    values: dict = {}
    if interests_public is not None:
        values["interests_public"] = interests_public
    if slots_public is not None:
        values["slots_public"] = slots_public
    if not values:
        return
    supabase.table("employees").update(values).eq("id", employee_id).execute()


def get_interests(employee_id: str) -> list[dict]:
    """[{"activity_id", "activity_name", "level"}, ...] を activity_id 順で返す。"""
    res = (
        supabase.table("employee_interests")
        .select("activity_id, level, activities(name)")
        .eq("employee_id", employee_id)
        .order("activity_id")
        .execute()
    )
    return [
        {
            "activity_id": r["activity_id"],
            "activity_name": (r.get("activities") or {}).get("name"),
            "level": r["level"],
        }
        for r in (res.data or [])
    ]


def set_interests(employee_id: str, interests: list[dict]) -> None:
    """興味・経験を置き換え保存する。interests: [{"activity_id", "level"}, ...]。

    先に upsert（unique(employee_id, activity_id)）してから残りを削除するため、
    二重登録にならず、途中失敗で全消えにもならない。同一 activity_id は後勝ち。
    """
    by_activity = {i["activity_id"]: i["level"] for i in interests}
    if by_activity:
        rows = [
            {"employee_id": employee_id, "activity_id": a, "level": lv}
            for a, lv in by_activity.items()
        ]
        supabase.table("employee_interests").upsert(
            rows, on_conflict="employee_id,activity_id"
        ).execute()
        supabase.table("employee_interests").delete().eq(
            "employee_id", employee_id
        ).not_.in_("activity_id", list(by_activity)).execute()
    else:
        supabase.table("employee_interests").delete().eq(
            "employee_id", employee_id
        ).execute()
