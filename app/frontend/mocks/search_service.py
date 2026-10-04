"""【仮の検索サービス】本物の services/search_service.py ができるまでの代役（ホーム画面用）。

本物の約束（I-F契約.md 1.2）にあるのは get_recommendations だけ。
get_this_week_clubs / get_popular_clubs は、ホーム（SP-16, SP-17）に必要なのに契約書に
関数が無いため、こちらから提案する名前で仮に置いている（だーあさに確認中）。

返す部活の dict は club_card.py が読むキーに合わせている:
    club_id, icon, name, location, slot, mood_tags, fee, after_activity, next_event_date
おすすめだけ、さらに score（一致度）と reason（理由）を持つ。level は初心者向け/経験者向けの
切り替え用。値はすべてダミー。選択肢は仕様.md 3.2 にあるものだけを使っている。
"""

from datetime import date, timedelta


def _club(club_id, icon, name, location, slot, mood_tags, fee, after_activity, level, days):
    return {
        "club_id": club_id,
        "icon": icon,
        "name": name,
        "location": location,
        "slot": slot,
        "mood_tags": mood_tags,
        "fee": fee,
        "after_activity": after_activity,
        "level": level,
        # days が None のときは「予定の開催なし」（SP-21 で「予定なし」と出る）
        "next_event_date": None if days is None else date.today() + timedelta(days=days),
    }


def _all_clubs():
    return [
        _club(1, "🏐", "バレー部", "東京", "土曜午前", ["ゆるめ", "わいわい賑やか"], "無料", "ランチ・お茶", "初心者歓迎", 1),
        _club(2, "🎲", "ボードゲーム部", "大阪", "平日夜", ["おしゃべり多め"], "500円以下", "飲み会", "レベル問わず", 2),
        _club(3, "🧘", "ヨガ部", "東京", "土曜午前", ["ゆるめ", "黙々と集中"], "1,000円以下", "なし", "初心者歓迎", 3),
        _club(4, "🏀", "バスケ部", "東京", "日曜", ["しっかり練習"], "500円以下", "日による", "経験者向け", 4),
        _club(5, "♟️", "将棋部", "大阪", "平日夜", ["黙々と集中", "少人数"], "無料", "なし", "レベル問わず", 5),
    ]


def get_this_week_clubs():
    """今週開催の部活（SP-16）。5件返す（画面側が最大4件に絞る確認のため）。"""
    return _all_clubs()


def get_popular_clubs():
    """今月の人気部活（SP-17）。人気順に並べて返す。"""
    clubs = _all_clubs()
    return [clubs[2], clubs[0], clubs[3]]


def get_recommendations(employee_id):
    """おすすめの部活（SP-18, I-F契約 1.2）。score（一致度）と reason（理由）つき、点数の高い順。"""
    clubs = _all_clubs()
    picks = [
        (clubs[0], 3, "興味（スポーツ）と拠点（東京）と時間帯（土曜午前）が一致"),
        (clubs[2], 2, "拠点（東京）と時間帯（土曜午前）が一致"),
        (clubs[1], 1, "興味（ゲーム）が一致"),
        (clubs[3], 1, "拠点（東京）が一致"),
    ]
    return [dict(club, score=score, reason=reason) for club, score, reason in picks]


# ---------------------------------------------------------------------------
# 部活検索（SP-19〜SP-22, I-F契約 1.2 search_clubs）用の仮データと仮の検索
# ---------------------------------------------------------------------------

# カードに載せるキー（I-F契約 1.2「部活カードdict」）。これ以外は画面に渡さない。
_CARD_KEYS = (
    "club_id", "icon", "name", "location", "slot", "mood_tags",
    "fee", "after_activity", "next_event_date",
)

# 検索に使うが、カードdictには入らない情報：club_id -> (活動カテゴリ, 活動名, ひとこと)
_SEARCH_INFO = {
    1: ("スポーツ", "バレーボール", "初心者大歓迎。みんなでゆるく楽しんでます"),
    2: ("ゲーム", "ボードゲーム", "毎回違うゲームで遊びます"),
    3: ("ウェルネス", "ヨガ", "朝のヨガで一週間をリセット"),
    4: ("スポーツ", "バスケットボール", "本気で上達したい人向け"),
    5: ("ゲーム", "将棋", "静かに一手を考える時間"),
    6: ("文化・趣味", "写真", "週末に街を撮り歩きます"),
    7: ("スポーツ", "フットサル", "仕事終わりに体を動かそう"),
    8: ("文化・趣味", "読書会", "好きな本を持ち寄って語ります"),
}


def _search_pool():
    """検索対象の部活（ホーム用の5件に、検索の確認用を3件足したもの）。"""
    return _all_clubs() + [
        _club(6, "📷", "写真部", "大阪", "土曜午後", ["ゆるめ", "おしゃべり多め"], "無料", "ランチ・お茶", "レベル問わず", 6),
        _club(7, "⚽", "フットサル部", "東京", "平日夜", ["わいわい賑やか"], "500円以下", "飲み会", "初心者歓迎", 9),
        _club(8, "📚", "読書会", "東京", "日曜", ["少人数", "おしゃべり多め"], "無料", "ランチ・お茶", "レベル問わず", None),
    ]


def _matches(club, conditions):
    """項目間は AND、同じ項目の複数選択は OR。選んでいない項目は条件にしない（SP-20）。"""
    category, activity, message = _SEARCH_INFO[club["club_id"]]
    if conditions.get("categories") and category not in conditions["categories"]:
        return False
    if conditions.get("locations") and club["location"] not in conditions["locations"]:
        return False
    if conditions.get("slots") and club["slot"] not in conditions["slots"]:
        return False
    if conditions.get("levels") and club["level"] not in conditions["levels"]:
        return False
    keyword = (conditions.get("keyword") or "").strip()
    if keyword and not any(keyword in text for text in (club["name"], activity, message)):
        return False
    return True


def search_clubs(conditions):
    """部活検索（SP-19〜SP-22, I-F契約 1.2）。次回開催日が近い順（予定なしは最後）。"""
    hits = [club for club in _search_pool() if _matches(club, conditions)]
    hits.sort(key=lambda c: (c["next_event_date"] is None, c["next_event_date"] or date.max, c["club_id"]))
    return [{key: club[key] for key in _CARD_KEYS} for club in hits]
