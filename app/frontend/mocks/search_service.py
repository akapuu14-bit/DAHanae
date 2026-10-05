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
        "next_event_date": date.today() + timedelta(days=days),
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
