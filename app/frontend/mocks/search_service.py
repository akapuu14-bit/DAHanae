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

from mocks import application_service
from services.errors import NotFoundError


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


# ---------------------------------------------------------------------------
# 部活詳細（SP-24〜SP-28, T-F08）用の仮データ
# 本物の関数は I-F契約 にまだ無い。画面が必要とする形をこちらから提案して仮に置いている
#   get_club_detail(club_id, viewer_id) -> dict   （だーあさに契約への追加を依頼中）
# ---------------------------------------------------------------------------

# club_id -> (頻度, 社会人から始めた人, 費用の補足, 道具の貸し出し, 持ち物の補足, 途中参加, 幹事ID, 幹事名, 幹事の部署, 入社年, 入社区分)
_DETAIL_INFO = {
    1: ("毎週", "多い", "体育館代の割り勘", "あり", "動きやすい服装・室内シューズ", "OK", "E201", "高橋 美咲", "営業部", 2019, "新卒"),
    2: ("月2回", "少しいる", None, "あり", "なし", "OK", "E202", "中村 健", "開発部", 2017, "中途"),
    3: ("毎週", "多い", "マット代込み", "あり", "飲み物・タオル", "できれば最初から", "E203", "小林 彩", "人事部", 2020, "新卒"),
    4: ("毎週", "少しいる", "コート代込み", "なし", "バスケットシューズ", "要相談", "E001", "デモ社員 E001", "営業部", 2015, "中途"),  # デモ用：E001 がバスケ部の幹事
    5: ("月2回", "いない", None, "あり", "なし", "OK", "E205", "吉田 恒一", "経理部", 2012, "新卒"),
    6: ("月1回", "多い", None, "なし", "カメラ（スマホでもOK）", "OK", "E206", "山口 優", "企画部", 2018, "異動"),
    7: ("毎週", "多い", "コート代の割り勘", "あり", "運動靴・飲み物", "OK", "E207", "松本 翔", "開発部", 2021, "新卒"),
    8: ("不定期", "少しいる", None, "なし", "読みたい本1冊", "要相談", "E208", "井上 里奈", "総務部", 2016, "中途"),
}

# 参加者・メンバーの顔ぶれ（ダミー）
_PEOPLE = [
    ("E101", "佐藤 太郎", "営業部"), ("E102", "鈴木 花子", "開発部"), ("E103", "田中 一郎", "人事部"),
    ("E104", "伊藤 美穂", "経理部"), ("E105", "渡辺 大輔", "企画部"), ("E106", "山本 由美", "総務部"),
]

# 活動時間（slot）ごとの開始・終了
_TIMES = {"平日夜": ("19:00", "20:30"), "土曜午前": ("10:00", "11:30"), "土曜午後": ("14:00", "15:30"), "日曜": ("10:00", "12:00")}
_PLACES = {"東京": "東京オフィス 1F ロビー", "大阪": "大阪オフィス 受付前"}
_CANCELED_EVENT_IDS = {32}  # ヨガ部の2回目は中止（確認用）
_NO_MEETING_TIME_IDS = {82}  # 集合時刻なし（確認用）


def _events_of(club):
    """その部活の今日以降の開催3回分（日付順）。開催IDは 部活ID×10+1〜3。"""
    start, end = _TIMES[club["slot"]]
    events = []
    for n, offset in enumerate((1, 8, 15), start=1):
        event_id = club["club_id"] * 10 + n
        events.append({
            "event_id": event_id,
            "club_id": club["club_id"],
            "event_date": date.today() + timedelta(days=club["club_id"] + offset),
            "start_time": start,
            "end_time": end,
            "meeting_place": _PLACES[club["location"]],
            "meeting_time": None if event_id in _NO_MEETING_TIME_IDS else start,
            "status": "中止" if event_id in _CANCELED_EVENT_IDS else "予定",
        })
    return events


def find_event(event_id):
    """開催IDから開催を探す（仮の申込サービスが使う）。無ければ None。"""
    for club in _search_pool():
        for event in _events_of(club):
            if event["event_id"] == event_id:
                return event
    return None


def _participants_of(event, viewer_id):
    """参加者のリスト。本物と同じく、中止の開催でも返す（画面で出し分ける）。デモの申込（applied）も含める。"""
    people = [{"id": pid, "name": name, "is_first_time": index == 0}
              for index, (pid, name, _dept) in enumerate(_PEOPLE[: 2 + event["event_id"] % 3])]
    for event_id, employee_id in sorted(application_service.applied):
        if event_id == event["event_id"] and employee_id not in {p["id"] for p in people}:
            people.append({"id": employee_id, "name": f"デモ社員 {employee_id}", "is_first_time": True})
    return [dict(p, is_self=(p["id"] == viewer_id)) for p in people]


def get_club_detail(club_id, viewer_id):
    """部活詳細に必要な情報をまとめて返す（SP-24〜SP-28）。部活が無ければ NotFoundError。"""
    club = next((c for c in _search_pool() if c["club_id"] == club_id), None)
    if club is None:
        raise NotFoundError(f"club {club_id}")
    (frequency, starters, fee_note, rental, belongings, join_leave,
     organizer_id, organizer_name, organizer_dept, joined_year, entry_type) = _DETAIL_INFO[club_id]
    _category, _activity, message = _SEARCH_INFO[club_id]

    events = []
    for event in _events_of(club):
        participants = _participants_of(event, viewer_id)
        events.append(dict(
            event,
            participant_count=len(participants),
            first_timer_count=sum(1 for p in participants if p["is_first_time"]),
            participants=participants,
            is_applied=any(p["is_self"] for p in participants),  # 契約（#91）：True / False
        ))
    # 本物と同じく、members には幹事本人も含める（契約 #91）
    members = [{"id": organizer_id, "name": organizer_name, "dept": organizer_dept}]
    members += [{"id": pid, "name": name, "dept": dept} for pid, name, dept in _PEOPLE if pid != organizer_id]
    return {
        "club": {
            "club_id": club_id, "name": club["name"], "icon": club["icon"], "location": club["location"],
            "slot": club["slot"], "schedule_note": None, "frequency": frequency, "level": club["level"],
            "fact_adult_starters": starters, "mood_tags": club["mood_tags"], "message": message,
            "fee": club["fee"], "fee_note": fee_note, "rental": rental, "belongings_note": belongings,
            "join_leave": join_leave, "after_activity": club["after_activity"],
        },
        "member_count": len(members),
        "organizer": {"id": organizer_id, "name": organizer_name, "dept": organizer_dept,
                      "joined_year": joined_year, "entry_type": entry_type},
        "members": members,
        "events": events,
    }
