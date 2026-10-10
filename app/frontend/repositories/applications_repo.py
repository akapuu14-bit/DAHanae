"""applications テーブルへのアクセス層（I-F契約 2.6）。

- 「存在しない」は例外にせず None / 空リスト / False で返す（I-F契約 0.4）。
- DBエラーはそのまま伝播させる。
- 二重申込は DB の部分一意インデックス applications_one_active_per_employee_idx
  （status='申込済み' のみ対象）で防ぐ。仕様.md 8章の保留により、この層では独自の重複防止を足さない。
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from db.client import supabase


def get(application_id: int) -> dict | None:
    """application_id で1件取得する。存在しなければ None（例外にしない）。"""
    res = (
        supabase.table("applications")
        .select("*")
        .eq("id", application_id)
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None


def exists_active(event_id: int, applicant_id: str) -> bool:
    """同じ開催に「申込済み」の申込があるか。キャンセル行は対象外（キャンセル後の再申込を弾かないため）。"""
    res = (
        supabase.table("applications")
        .select("id")
        .eq("event_id", event_id)
        .eq("applicant_id", applicant_id)
        .eq("status", "申込済み")
        .limit(1)
        .execute()
    )
    return bool(res.data)


def insert(event_id: int, applicant_id: str, is_first_time: bool) -> int:
    """申込を1件追加し、採番された id を返す。status と applied_at はDBの既定値に委ねる。"""
    res = (
        supabase.table("applications")
        .insert(
            {
                "event_id": event_id,
                "applicant_id": applicant_id,
                "is_first_time": is_first_time,
            }
        )
        .execute()
    )
    return res.data[0]["id"]


def update_status(
    application_id: int,
    status: str,
    *,
    canceled_at=None,
    confirmed_at=None,
) -> None:
    """申込の状態を更新する。canceled_at / confirmed_at は None のときは列に触れない。"""
    row: dict = {"status": status}
    if canceled_at is not None:
        row["canceled_at"] = canceled_at
    if confirmed_at is not None:
        row["confirmed_at"] = confirmed_at
    (
        supabase.table("applications")
        .update(row)
        .eq("id", application_id)
        .execute()
    )


def has_past_non_canceled(club_id: int, employee_id: str) -> bool:
    """その部活の過去の開催に、キャンセル以外の申込が1件でもあるか（SP-68 ②、初参加判定に使う）。

    「過去」は仕様.md SP-26の「今日以降」の補集合として event_date < 今日 で判定する。
    """
    today = datetime.now(ZoneInfo("Asia/Tokyo")).date().isoformat()
    past_event_rows = (
        supabase.table("events")
        .select("id")
        .eq("club_id", club_id)
        .lt("event_date", today)
        .execute()
        .data
    )
    past_event_ids = [r["id"] for r in past_event_rows]
    if not past_event_ids:
        return False
    res = (
        supabase.table("applications")
        .select("id")
        .eq("applicant_id", employee_id)
        .neq("status", "キャンセル")
        .in_("event_id", past_event_ids)
        .limit(1)
        .execute()
    )
    return bool(res.data)


def list_by_applicant(applicant_id: str) -> list[dict]:
    """その社員の申込一覧を id 順で返す。各dictの "events" に開催（"events"."clubs" に部活）が入る。

    並び順（SP-37：開催日が近い順、終わった開催・キャンセルは後ろ）は service 層で行う。
    """
    res = (
        supabase.table("applications")
        .select("*, events(*, clubs(*))")
        .eq("applicant_id", applicant_id)
        .order("id")
        .execute()
    )
    return res.data or []


def list_by_organizer_club(club_id: int) -> list[dict]:
    """その部活の全開催に対する申込一覧を id 順で返す（キャンセル行も含む）。

    各dictの "events" に開催（"events"."clubs" に部活）、"employees" に申込者の社員行が入る。
    並び順（SP-40：未読を先頭、そのあとは新しい順）は service 層で行う。
    """
    event_rows = (
        supabase.table("events")
        .select("id")
        .eq("club_id", club_id)
        .execute()
        .data
    )
    event_ids = [r["id"] for r in event_rows]
    if not event_ids:
        return []
    res = (
        supabase.table("applications")
        .select("*, events(*, clubs(*)), employees(*)")
        .in_("event_id", event_ids)
        .order("id")
        .execute()
    )
    return res.data or []


def list_participants(event_id: int) -> list[dict]:
    """開催の参加者（状態「申込済み」の申込）を id 順で返す。初参加かどうかは各dictの is_first_time。

    「参加者」を申込済みに限る解釈は仕様.md SP-26（参加人数）とSP-67（キャンセル）から導いた。
    各dictの "employees" に申込者の社員行が入る（参加者の表示名に使う）。
    """
    res = (
        supabase.table("applications")
        .select("*, employees(*)")
        .eq("event_id", event_id)
        .eq("status", "申込済み")
        .order("id")
        .execute()
    )
    return res.data or []
