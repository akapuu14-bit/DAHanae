"""events テーブルへのアクセス層（I-F契約 2.5）。

- 「存在しない」は例外にせず None / 空リストで返す（I-F契約 0.4）。
- DBエラーはそのまま伝播させる。
- 「過去を除く」境界は仕様.md SP-26「今日以降の開催を日付順に表示（過去の開催は出さない）」、
  I-F契約.md 2.5のコメント「今日以降、日付順」に基づき、今日を含める（event_date >= 今日）。
  開催日と時刻は混ぜず、event_date（date型）だけで比較する。
"""

from datetime import date

from db.client import supabase


def get(event_id: int) -> dict | None:
    """event_id で1件取得する。存在しなければ None（例外にしない）。"""
    res = (
        supabase.table("events")
        .select("*")
        .eq("id", event_id)
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None


def list_upcoming_by_club(club_id: int) -> list[dict]:
    """その部活の今日以降の開催を日付順（同日はid順）で返す。過去の開催は除く。"""
    today = date.today().isoformat()
    res = (
        supabase.table("events")
        .select("*")
        .eq("club_id", club_id)
        .gte("event_date", today)
        .order("event_date")
        .order("id")
        .execute()
    )
    return res.data or []


def list_upcoming_all_with_club() -> list[dict]:
    """全部活の今日以降の開催を日付順で、clubsをjoinして返す（ホーム「今週開催の部活」集計用）。

    各dictの "clubs" キーに該当するclubs行（1件）が入る。
    """
    today = date.today().isoformat()
    res = (
        supabase.table("events")
        .select("*, clubs(*)")
        .gte("event_date", today)
        .order("event_date")
        .order("id")
        .execute()
    )
    return res.data or []


def get_last_meeting_place(club_id: int) -> str | None:
    """その部活の直近の開催（event_date降順で最新）のmeeting_placeを返す。開催が無ければNone。"""
    res = (
        supabase.table("events")
        .select("meeting_place")
        .eq("club_id", club_id)
        .order("event_date", desc=True)
        .order("id", desc=True)
        .limit(1)
        .execute()
    )
    return res.data[0]["meeting_place"] if res.data else None


def create(data: dict) -> int:
    """開催を1件追加し、採番された id を返す。列の検証はDBのCHECK制約に委ねる。"""
    res = supabase.table("events").insert(dict(data)).execute()
    return res.data[0]["id"]


def update(event_id: int, data: dict) -> None:
    """開催の列を更新する。列の検証はDBのCHECK制約に委ねる。"""
    supabase.table("events").update(dict(data)).eq("id", event_id).execute()


def set_status(event_id: int, status: str) -> None:
    """開催の状態（"予定" / "中止"）を更新する。値の検証はDBのCHECK制約に委ねる。"""
    supabase.table("events").update({"status": status}).eq("id", event_id).execute()
