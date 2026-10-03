"""clubs テーブルへのアクセス層（I-F契約 2.3）。

- 「存在しない」は例外にせず None / 空リストで返す（I-F契約 0.4）。
- DBエラーはそのまま伝播させる。
- search の条件組み立て（AND/OR、SP-20）はこの層に閉じる（上位層に漏らさない）。
"""

from db.client import supabase


def _escape_like(value: str) -> str:
    """LIKE/ILIKE のワイルドカードを文字として扱うためのエスケープ。"""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _strip_or_filter_reserved_chars(value: str) -> str:
    """or() フィルタのDSL区切り文字（, ( ) "）を除去する。

    _escape_like とは別レイヤの対策。_escape_like はLIKE/ILIKEのワイルドカード
    （% _ \\）を「文字として扱う」ためのエスケープで、PostgRESTのフィルタ構文
    （or=(...) のカンマ区切り・括弧のネスト）には関与しない。
    PostgRESTは値にカンマ/括弧があるとダブルクォートで囲む回避策を案内しているが、
    クォート内のダブルクォート自体やバックスラッシュのエスケープ方法が公式ドキュメント
    に明記されておらず確証が持てない（2026-10-03 docs.postgrest.org 確認時点）。
    そのため、構文を壊しうる区切り文字そのものをここで除去する、より確実な方針にする
    （検索結果が多少広がる/狭まることより、構文破壊で例外になることの方が重大）。
    """
    for ch in (",", "(", ")", '"'):
        value = value.replace(ch, "")
    return value


def get(club_id: int) -> dict | None:
    """club_id で1件取得する。存在しなければ None（例外にしない）。"""
    res = (
        supabase.table("clubs")
        .select("*")
        .eq("id", club_id)
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None


def search(conditions: dict) -> list[dict]:
    """部活検索（仕様.md SP-19・SP-20）。

    conditions のキー: "categories"（list[str], activities.category）,
    "locations"（list[str]）, "slots"（list[str]）, "levels"（list[str]）,
    "keyword"（str, 部活名・活動名・ひとことの部分一致）。
    未指定（None・空）のキーは条件にしない。項目間はAND、同一項目内はOR。
    対象は is_active が true の部活のみ。

    次回開催日順（SP-20）は events テーブルとのjoinが必要なため、この層の
    スコープ外（呼び出し側の search_service が events_repo と組み合わせて並べる）。
    """
    query = supabase.table("clubs").select("*").eq("is_active", True)

    categories = conditions.get("categories")
    if categories:
        activity_rows = (
            supabase.table("activities")
            .select("id")
            .in_("category", list(categories))
            .execute()
            .data
        )
        activity_ids = [r["id"] for r in activity_rows]
        if not activity_ids:
            return []
        query = query.in_("activity_id", activity_ids)

    if conditions.get("locations"):
        query = query.in_("location", list(conditions["locations"]))
    if conditions.get("slots"):
        query = query.in_("slot", list(conditions["slots"]))
    if conditions.get("levels"):
        query = query.in_("level", list(conditions["levels"]))

    keyword = conditions.get("keyword")
    if keyword:
        compact = keyword.strip()
        # 2段階の無害化: ①LIKEワイルドカード対策（_escape_like）
        # ②or()フィルタのDSL区切り文字対策（_strip_or_filter_reserved_chars）。
        # カンマ・括弧・ダブルクォートを含まない入力はそのまま変化しない。
        safe_compact = _strip_or_filter_reserved_chars(compact)
        if safe_compact:
            pattern = _escape_like(safe_compact)
            keyword_activity_rows = (
                supabase.table("activities")
                .select("id")
                .ilike("name", f"%{pattern}%")
                .execute()
                .data
            )
            keyword_activity_ids = [r["id"] for r in keyword_activity_rows]
            or_parts = [f"name.ilike.%{pattern}%", f"message.ilike.%{pattern}%"]
            if keyword_activity_ids:
                ids_csv = ",".join(str(i) for i in keyword_activity_ids)
                or_parts.append(f"activity_id.in.({ids_csv})")
            query = query.or_(",".join(or_parts))

    res = query.execute()
    return res.data or []


def list_by_organizer(organizer_id: str) -> list[dict]:
    """その幹事が担当する部活一覧を id 順で返す。該当なしは空リスト。"""
    res = (
        supabase.table("clubs")
        .select("*")
        .eq("organizer_id", organizer_id)
        .order("id")
        .execute()
    )
    return res.data or []


def list_all_for_admin() -> list[dict]:
    """運営者向け：is_active を問わず全部活を id 順で返す。"""
    res = supabase.table("clubs").select("*").order("id").execute()
    return res.data or []


def create(data: dict) -> int:
    """部活を1件追加し、採番された id を返す。列の検証はDBのCHECK制約に委ねる。"""
    res = supabase.table("clubs").insert(dict(data)).execute()
    return res.data[0]["id"]


def update(club_id: int, data: dict) -> None:
    """部活の列を更新する。列の検証はDBのCHECK制約に委ねる。"""
    supabase.table("clubs").update(dict(data)).eq("id", club_id).execute()
