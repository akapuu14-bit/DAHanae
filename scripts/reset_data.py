"""テストデータの初期化スクリプト（T-D01 / SP-78 / N-07〜N-09）。

Supabase のすべてのテーブルを空にして、ダミーデータを入れ直す開発者用の処理。
アプリの画面からは呼べない。開発者が自分のパソコンから実行する。

使い方（リポジトリ直下で実行）::

    python scripts/reset_data.py --dry-run
    python scripts/reset_data.py --dry-run --show-clubs
    python scripts/reset_data.py --dry-run --base-date 2026-10-06

注意:
    --dry-run を付けずに実行すると、接続先のデータベースの全データが消える
    （申込・メッセージ・操作履歴も含む）。実行前にチームへ声をかけること。
    いまは社員・活動・部活の生成までで、DB への書き込みはまだ実装していない。
"""

import argparse
import hashlib
import json
import os
import random
import sys
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

# 乱数の種。固定する（N-08）。変えると、作られるデータが全部変わる。
SEED = 42

REPO_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = REPO_ROOT / "app" / "frontend"

# ---- 選択肢（DB の CHECK 制約と同じ値。supabase/migrations 参照） ----
LOCATIONS = ["東京", "大阪"]
SLOTS = ["平日夜", "土曜午前", "土曜午後", "日曜"]
ENTRY_TYPES = ["新卒", "中途", "異動"]
CATEGORIES = ["スポーツ", "ゲーム", "ウェルネス", "文化・趣味"]
FREQUENCIES = ["毎週", "月2回", "月1回", "不定期"]
LEVELS = ["初心者歓迎", "レベル問わず", "経験者向け"]
FACT_ADULT_STARTERS = ["多い", "少しいる", "いない"]
MOOD_TAGS = ["ゆるめ", "しっかり練習", "黙々と集中", "わいわい賑やか", "おしゃべり多め", "少人数"]
FEES = ["無料", "500円以下", "1,000円以下", "それ以上"]
RENTALS = ["あり", "なし"]
JOIN_LEAVES = ["OK", "できれば最初から", "要相談"]
AFTER_ACTIVITIES = ["なし", "ランチ・お茶", "飲み会", "日による"]

# ---- 社員の作り方（開発仕様書 7章、PM 決定 2026-10-06） ----
EMPLOYEE_COUNT = 500
TOKYO_COUNT = 350  # 残りは大阪（150名）
RECENT_YEARS = [2024, 2025, 2026]  # 入社1〜3年目
RECENT_PER_YEAR = 50  # 1年あたり50名（3年で150名）
OLDER_YEARS = list(range(2015, 2024))
PUBLIC_COUNT = 400  # 公開（ON）にする人数（8割）
NO_SLOTS_COUNT = 50  # 参加可能時間が未入力の人数（1割）
ENTRY_TYPE_WEIGHTS = [6, 3, 1]

SURNAMES = [
    "佐藤", "鈴木", "高橋", "田中", "伊藤", "渡辺", "山本", "中村", "小林", "加藤",
    "吉田", "山田", "佐々木", "山口", "松本", "井上", "木村", "林", "斎藤", "清水",
    "山崎", "森", "池田", "橋本", "阿部", "石川", "山下", "中島", "石井", "小川",
    "前田", "岡田", "長谷川", "藤田", "後藤", "近藤", "村上", "遠藤", "青木", "坂本",
    "福田", "太田", "西村", "藤井", "金子", "岡本", "藤原", "三浦", "中野", "原田",
]
GIVEN_NAMES = [
    "翔太", "大輝", "拓海", "蓮", "颯太", "悠斗", "健太", "直樹", "達也", "和也",
    "裕介", "浩二", "隆", "誠", "学", "亮", "純", "修平", "勇気", "大地",
    "光", "駿", "慎吾", "智也", "康平",
    "美咲", "陽菜", "結衣", "彩香", "優子", "恵", "麻衣", "由美", "真理", "沙織",
    "奈々", "千尋", "愛", "菜月", "莉子", "瞳", "絵美", "香織", "理恵", "加奈",
    "夏美", "綾", "舞", "葵", "遥",
]
DEPARTMENTS = [
    "営業部", "マーケティング部", "開発部", "情報システム部", "人事部",
    "総務部", "経理部", "法務部", "カスタマーサポート部", "企画部",
]

# ---- 活動と部活（開発仕様書 7章、PM 決定 2026-10-06） ----
# 活動20件：先頭15件は部活のある活動、最後の5件は部活がない活動
ACTIVITIES = [
    ("テニス", "スポーツ"), ("フットサル", "スポーツ"), ("ランニング", "スポーツ"),
    ("ボルダリング", "スポーツ"), ("卓球", "スポーツ"), ("バドミントン", "スポーツ"),
    ("ゴルフ", "スポーツ"),
    ("ボードゲーム", "ゲーム"), ("将棋", "ゲーム"), ("麻雀", "ゲーム"),
    ("ヨガ", "ウェルネス"), ("ウォーキング", "ウェルネス"),
    ("写真", "文化・趣味"), ("料理", "文化・趣味"), ("読書", "文化・趣味"),
    ("ダンス", "スポーツ"), ("登山", "スポーツ"), ("釣り", "文化・趣味"),
    ("カラオケ", "文化・趣味"), ("サウナ", "ウェルネス"),
]

# いつもの活動時間の補足（時間帯ごとに固定。開催の時刻も、これに合わせる）
SCHEDULE_NOTES = {
    "平日夜": "平日 19:00〜21:00",
    "土曜午前": "土曜 10:00〜12:00",
    "土曜午後": "土曜 14:00〜16:00",
    "日曜": "日曜 10:00〜12:00",
}


def club(
    *, name, activity, icon, location, slot, frequency, level, fact_adult_starters,
    mood_tags, message, fee, fee_note, rental, belongings_note, join_leave,
    after_activity,
) -> dict:
    """部活1件分のデータ。幹事（organizer_id）と activity_id は、あとで決める。"""
    return {
        "name": name,
        "activity": activity,  # 活動名。DB に入れるときに activity_id に置き換える
        "icon": icon,
        "location": location,
        "slot": slot,
        "schedule_note": SCHEDULE_NOTES[slot],
        "frequency": frequency,
        "level": level,
        "fact_adult_starters": fact_adult_starters,
        "mood_tags": mood_tags,
        "message": message,
        "fee": fee,
        "fee_note": fee_note,
        "rental": rental,
        "belongings_note": belongings_note,
        "join_leave": join_leave,
        "after_activity": after_activity,
        "is_active": True,
    }


CLUB_SPECS = [
    club(
        name="テニス部", activity="テニス", icon="🎾", location="東京", slot="土曜午前",
        frequency="毎週", level="初心者歓迎", fact_adult_starters="多い",
        mood_tags=["ゆるめ", "おしゃべり多め"],
        message="初心者大歓迎です。ラケットを握るのが久しぶりでも大丈夫。ラリーを楽しみながら、少しずつ上達しましょう。",
        fee="500円以下", fee_note="コート代を人数で割ります。", rental="あり",
        belongings_note="ラケットは貸出あり。動きやすい服装とテニスシューズ（なければ運動靴）、飲み物をお持ちください。",
        join_leave="OK", after_activity="ランチ・お茶",
    ),
    club(
        name="フットサル部", activity="フットサル", icon="⚽", location="東京", slot="平日夜",
        frequency="毎週", level="レベル問わず", fact_adult_starters="少しいる",
        mood_tags=["わいわい賑やか", "ゆるめ"],
        message="仕事帰りにみんなでボールを追いかける部活です。経験の差は気にせず、楽しく汗を流しています。",
        fee="500円以下", fee_note="コート代の割り勘です。", rental="なし",
        belongings_note="運動できる服装、室内用シューズ、すね当て（あれば）、タオル、飲み物。",
        join_leave="OK", after_activity="飲み会",
    ),
    club(
        name="ランニング部", activity="ランニング", icon="🏃", location="東京", slot="日曜",
        frequency="月2回", level="レベル問わず", fact_adult_starters="多い",
        mood_tags=["黙々と集中", "少人数"],
        message="自分のペースで走る部活です。距離やタイムは問いません。走ったあとのお茶も楽しみのひとつです。",
        fee="無料", fee_note=None, rental="なし",
        belongings_note="ランニングウェアとシューズ、飲み物、タオル。",
        join_leave="OK", after_activity="ランチ・お茶",
    ),
    club(
        name="ボルダリング部", activity="ボルダリング", icon="🧗", location="東京", slot="土曜午後",
        frequency="月2回", level="初心者歓迎", fact_adult_starters="多い",
        mood_tags=["ゆるめ", "少人数"],
        message="ジムで壁を登る部活です。初めての人には、道具の使い方から教えます。",
        fee="1,000円以下", fee_note="ジムの利用料（シューズのレンタル代込み）です。", rental="あり",
        belongings_note="動きやすい服装（のびる素材がおすすめ）、タオル、飲み物。シューズは貸出あり。",
        join_leave="OK", after_activity="日による",
    ),
    club(
        name="卓球部", activity="卓球", icon="🏓", location="東京", slot="平日夜",
        frequency="毎週", level="初心者歓迎", fact_adult_starters="少しいる",
        mood_tags=["ゆるめ", "わいわい賑やか"],
        message="平日の夜に、軽く体を動かす部活です。ラリーが続くだけで盛り上がります。",
        fee="無料", fee_note=None, rental="あり",
        belongings_note="動きやすい服装と室内用シューズ。ラケットは貸出あり。",
        join_leave="OK", after_activity="なし",
    ),
    club(
        name="バドミントン部", activity="バドミントン", icon="🏸", location="大阪", slot="平日夜",
        frequency="毎週", level="レベル問わず", fact_adult_starters="少しいる",
        mood_tags=["わいわい賑やか", "しっかり練習"],
        message="ラリーから試合形式まで、レベルに合わせて楽しみます。仲間と汗を流したい人におすすめです。",
        fee="500円以下", fee_note="体育館の利用料の割り勘です。", rental="あり",
        belongings_note="運動できる服装、室内用シューズ、タオル。ラケットは貸出あり。",
        join_leave="OK", after_activity="飲み会",
    ),
    club(
        name="ゴルフ部", activity="ゴルフ", icon="⛳", location="大阪", slot="日曜",
        frequency="月1回", level="経験者向け", fact_adult_starters="いない",
        mood_tags=["しっかり練習", "少人数"],
        message="月に一度、コースをまわります。ある程度ラウンド経験のある方向けです。",
        fee="それ以上", fee_note="プレー代はコースにより異なります。参加前に目安をお伝えします。", rental="なし",
        belongings_note="ゴルフクラブ一式、ウェア、シューズ。",
        join_leave="できれば最初から", after_activity="日による",
    ),
    club(
        name="ボードゲーム部", activity="ボードゲーム", icon="🎲", location="東京", slot="平日夜",
        frequency="月2回", level="初心者歓迎", fact_adult_starters="多い",
        mood_tags=["ゆるめ", "おしゃべり多め"],
        message="いろいろなボードゲームを持ち寄って遊びます。ルールはその場で説明するので、初めてでも大丈夫です。",
        fee="無料", fee_note=None, rental="あり",
        belongings_note="手ぶらで大丈夫です。気になるゲームがあれば、持ってきてください。",
        join_leave="OK", after_activity="日による",
    ),
    club(
        name="将棋部", activity="将棋", icon="♟", location="東京", slot="土曜午後",
        frequency="月2回", level="レベル問わず", fact_adult_starters="少しいる",
        mood_tags=["黙々と集中", "少人数"],
        message="駒の動かし方から教えます。対局のあとは、ゆっくり感想戦をします。",
        fee="無料", fee_note=None, rental="あり",
        belongings_note="手ぶらで大丈夫です。盤と駒は用意します。",
        join_leave="OK", after_activity="なし",
    ),
    club(
        name="麻雀部", activity="麻雀", icon="🀄", location="大阪", slot="平日夜",
        frequency="不定期", level="レベル問わず", fact_adult_starters="少しいる",
        mood_tags=["おしゃべり多め", "わいわい賑やか"],
        message="不定期に卓を囲みます。点数計算が不安な人も、一緒に覚えながら遊べます。",
        fee="500円以下", fee_note="雀荘の場所代の割り勘です。", rental="あり",
        belongings_note="手ぶらで大丈夫です。",
        join_leave="要相談", after_activity="飲み会",
    ),
    club(
        name="ヨガ部", activity="ヨガ", icon="🧘", location="東京", slot="平日夜",
        frequency="毎週", level="初心者歓迎", fact_adult_starters="多い",
        mood_tags=["ゆるめ", "黙々と集中"],
        message="仕事のあとに、体をのばして整える部活です。呼吸を意識して、ゆったり過ごします。",
        fee="500円以下", fee_note="スタジオの利用料です。", rental="あり",
        belongings_note="動きやすい服装、タオル、飲み物。マットは貸出あり。",
        join_leave="OK", after_activity="なし",
    ),
    club(
        name="ウォーキング部", activity="ウォーキング", icon="🚶", location="大阪", slot="土曜午前",
        frequency="月2回", level="初心者歓迎", fact_adult_starters="多い",
        mood_tags=["ゆるめ", "おしゃべり多め"],
        message="街や公園を、おしゃべりしながら歩く部活です。無理なく続けられます。",
        fee="無料", fee_note=None, rental="なし",
        belongings_note="歩きやすい靴と服装、飲み物。雨の日は中止になることがあります。",
        join_leave="OK", after_activity="ランチ・お茶",
    ),
    club(
        name="写真部", activity="写真", icon="📷", location="東京", slot="日曜",
        frequency="月1回", level="レベル問わず", fact_adult_starters="少しいる",
        mood_tags=["ゆるめ", "少人数"],
        message="季節ごとの風景や街角を、みんなで撮り歩きます。スマホのカメラでも参加できます。",
        fee="無料", fee_note=None, rental="なし",
        belongings_note="スマートフォンかカメラ。歩きやすい靴。",
        join_leave="OK", after_activity="ランチ・お茶",
    ),
    club(
        name="料理部", activity="料理", icon="🍳", location="大阪", slot="土曜午後",
        frequency="月1回", level="初心者歓迎", fact_adult_starters="多い",
        mood_tags=["わいわい賑やか", "おしゃべり多め"],
        message="毎回ひとつのテーマで、みんなで作って食べます。包丁を持つのが久しぶりでも大丈夫です。",
        fee="1,000円以下", fee_note="食材代と、調理室の利用料です。", rental="あり",
        belongings_note="エプロン、タオル。調理器具は貸出あり。",
        join_leave="できれば最初から", after_activity="ランチ・お茶",
    ),
    club(
        name="読書部", activity="読書", icon="📖", location="東京", slot="土曜午前",
        frequency="月1回", level="レベル問わず", fact_adult_starters="少しいる",
        mood_tags=["ゆるめ", "黙々と集中"],
        message="それぞれが選んだ本を持ち寄って、おすすめを紹介し合います。読み終えていなくても参加できます。",
        fee="無料", fee_note=None, rental="なし",
        belongings_note="紹介したい本を1冊。",
        join_leave="OK", after_activity="ランチ・お茶",
    ),
]


# ---- 幹事・メンバー・興味の作り方（PM 決定 2026-10-07） ----
ORGANIZER_MAX_JOINED_YEAR = 2023  # 幹事は入社2023年以前の社員から選ぶ
MEMBERS_MIN = 3  # 部活メンバーの人数（幹事を含む）
MEMBERS_MAX = 20
INTEREST_MAX = 3  # 1人の興味の最大数
CLUB_ACTIVITY_INTEREST_RATE = 0.5  # 部活メンバーが、自分の部活の活動に興味を持つ確率
INTEREST_LEVELS = ["未経験", "初心者", "経験あり"]
E002_CLUB = "テニス部"  # E002（幹事のデモ用アカウント）が幹事をつとめる部活
# E001（新入社員のデモ用アカウント）：おすすめ表示を確認できるように固定する
DEMO_NEWCOMER = {
    "interests": [("テニス", "未経験"), ("ボードゲーム", "未経験"), ("ヨガ", "初心者")],
    "available_slots": ["平日夜", "土曜午前"],
}


# ---- 開催の作り方（PM 決定 2026-10-07） ----
# 開催の状態は「予定」「中止」の2種類だけ。過去の開催は、状態「予定」で日付が過去のもの。
PAST_DAYS = 30  # 基準日の何日前までの、過去の開催を作るか
FUTURE_DAYS = 56  # 基準日の何日先（8週）までの、未来の開催を作るか
PAST_EVENTS_MAX = 2  # 1部活あたりの過去の開催数（0〜2件）
FUTURE_EVENTS_MIN = 2  # 1部活あたりの未来の開催数（2〜4件）
FUTURE_EVENTS_MAX = 4
NO_EVENT_CLUB_COUNT = 2  # 未来の開催をゼロにする部活の数（「予定なし」の確認用）
THIS_WEEK_CLUB_COUNT = 4  # 基準日〜今週の日曜に開催が1件ある部活の数（「今週」の確認用）
CANCEL_RATE = 0.1  # 未来の開催のうち、中止にする割合
MEETING_TIME_NONE_RATE = 0.5  # 集合時間を空にする割合（空でも画面が落ちないかの確認用）
MEETING_BEFORE_MINUTES = 15  # 集合時間は、開始の何分前か

# 部活の slot ごとの、開催できる曜日（月曜=0 … 日曜=6）と、開始・終了の時刻
SLOT_WEEKDAYS = {
    "平日夜": [0, 1, 2, 3, 4],
    "土曜午前": [5],
    "土曜午後": [5],
    "日曜": [6],
}
SLOT_TIMES = {
    "平日夜": ("19:00", "21:00"),
    "土曜午前": ("10:00", "12:00"),
    "土曜午後": ("14:00", "16:00"),
    "日曜": ("10:00", "12:00"),
}
# 集合場所の候補（仮案。拠点ごと）
MEETING_PLACES = {
    "東京": ["本社ビル1階ロビー", "最寄り駅の改札前", "会場の入口前"],
    "大阪": ["大阪支社1階ロビー", "最寄り駅の改札前", "会場の入口前"],
}

def apply_demo_overrides(employees: list[dict]) -> None:
    """デモ用の E001（新入社員）の参加可能時間と公開設定を固定する。"""
    e001 = employees[0]
    e001["available_slots"] = list(DEMO_NEWCOMER["available_slots"])
    e001["interests_public"] = True
    e001["slots_public"] = True


def assign_organizers(
    rng: random.Random, employees: list[dict], clubs: list[dict]
) -> dict[str, str]:
    """各部活の幹事を決める。{部活名: 社員ID} を返す。"""
    organizers = {E002_CLUB: "E002"}
    used = {"E002"}
    for c in clubs:
        if c["name"] in organizers:
            continue
        candidates = [
            e["id"]
            for e in employees
            if e["location"] == c["location"]
            and e["joined_year"] <= ORGANIZER_MAX_JOINED_YEAR
            and e["id"] not in ("E001", "E003")
            and e["id"] not in used
        ]
        chosen = rng.choice(candidates)
        organizers[c["name"]] = chosen
        used.add(chosen)
    return organizers


def make_club_members(
    rng: random.Random,
    employees: list[dict],
    clubs: list[dict],
    organizers: dict[str, str],
) -> list[dict]:
    """部活メンバーを作る（幹事も、メンバーとして登録する）。"""
    members = []
    for c in clubs:
        organizer = organizers[c["name"]]
        pool = [
            e["id"]
            for e in employees
            if e["location"] == c["location"] and e["id"] not in ("E001", organizer)
        ]
        size = rng.randint(MEMBERS_MIN, MEMBERS_MAX)  # 幹事を含む人数
        chosen = [organizer] + rng.sample(pool, size - 1)
        for employee_id in chosen:
            # "club" は部活名。DB に入れるときに club_id に置き換える
            members.append({"club": c["name"], "employee_id": employee_id, "joined_at": None})
    return members


def make_interests(
    rng: random.Random,
    employees: list[dict],
    clubs: list[dict],
    members: list[dict],
) -> list[dict]:
    """社員の興味・経験を作る（各社員に0〜3個。部活メンバーは自分の部活の活動に興味を持ちやすい）。"""
    activity_of_club = {c["name"]: c["activity"] for c in clubs}
    own_activities: dict[str, list[str]] = {}
    for m in members:
        own_activities.setdefault(m["employee_id"], []).append(activity_of_club[m["club"]])

    all_activities = [name for name, _ in ACTIVITIES]
    interests = []
    for e in employees:
        if e["id"] == "E001":
            for activity, level in DEMO_NEWCOMER["interests"]:
                interests.append({"employee_id": "E001", "activity": activity, "level": level})
            continue
        count = rng.randint(0, INTEREST_MAX)
        chosen = []
        own = own_activities.get(e["id"], [])
        if count > 0 and own and rng.random() < CLUB_ACTIVITY_INTEREST_RATE:
            chosen.append(rng.choice(own))
        remaining = [a for a in all_activities if a not in chosen]
        chosen += rng.sample(remaining, count - len(chosen))
        for activity in chosen:
            interests.append(
                {"employee_id": e["id"], "activity": activity, "level": rng.choice(INTEREST_LEVELS)}
            )
    return interests


def dates_between(start: date, end: date, slot: str) -> list[date]:
    """start から end まで（両端を含む）の日付のうち、部活の slot で開催できる曜日のものを返す。"""
    days = (end - start).days + 1
    candidates = [start + timedelta(days=i) for i in range(days)]
    return [d for d in candidates if d.weekday() in SLOT_WEEKDAYS[slot]]


def minus_minutes(hhmm: str, minutes: int) -> str:
    """'19:00' のような時刻の文字列から、指定した分数を引いた時刻（'18:45'）を返す。"""
    t = datetime.strptime(hhmm, "%H:%M") - timedelta(minutes=minutes)
    return t.strftime("%H:%M")


def make_events(rng: random.Random, clubs: list[dict], base_date: date) -> list[dict]:
    """開催を作る。日付は 'YYYY-MM-DD'、時刻は 'HH:MM' の文字列で持つ。

    過去の開催は、状態「予定」で日付が基準日より前のもの（状態に「終了」は無い）。
    "club" は部活名。DB に入れるときに club_id に置き換える。
    """
    this_sunday = base_date + timedelta(days=6 - base_date.weekday())  # 今週の日曜

    # 未来の開催をゼロにする部活（「予定なし」の確認用）。E002 のテニス部は除く
    names = [c["name"] for c in clubs]
    no_event = set(rng.sample([n for n in names if n != E002_CLUB], NO_EVENT_CLUB_COUNT))

    # 基準日〜今週の日曜に、開催を1件入れる部活（「今週」の確認用）
    week_candidates = [
        c["name"]
        for c in clubs
        if c["name"] not in no_event and dates_between(base_date, this_sunday, c["slot"])
    ]
    this_week = set(
        rng.sample(week_candidates, min(THIS_WEEK_CLUB_COUNT, len(week_candidates)))
    )

    events = []
    protected = set()  # 中止にしない開催（今週の確認用）の番号
    for c in clubs:
        slot = c["slot"]
        start, end = SLOT_TIMES[slot]

        # 過去：基準日の PAST_DAYS 日前から前日まで
        past_dates = dates_between(
            base_date - timedelta(days=PAST_DAYS), base_date - timedelta(days=1), slot
        )
        past = rng.sample(past_dates, min(rng.randint(0, PAST_EVENTS_MAX), len(past_dates)))

        # 未来：基準日から FUTURE_DAYS 日先まで
        future = []
        week_date = None
        if c["name"] not in no_event:
            count = rng.randint(FUTURE_EVENTS_MIN, FUTURE_EVENTS_MAX)
            if c["name"] in this_week:
                week_date = rng.choice(dates_between(base_date, this_sunday, slot))
                future.append(week_date)
            rest = [
                d
                for d in dates_between(base_date, base_date + timedelta(days=FUTURE_DAYS), slot)
                if d != week_date
            ]
            future += rng.sample(rest, min(count - len(future), len(rest)))

        for d in sorted(past) + sorted(future):
            if d == week_date:
                protected.add(len(events))
            if rng.random() < MEETING_TIME_NONE_RATE:
                meeting_time = None
            else:
                meeting_time = minus_minutes(start, MEETING_BEFORE_MINUTES)
            events.append(
                {
                    "club": c["name"],
                    "event_date": d.isoformat(),
                    "start_time": start,
                    "end_time": end,
                    "meeting_place": rng.choice(MEETING_PLACES[c["location"]]),
                    "meeting_time": meeting_time,
                    "status": "予定",
                }
            )

    # 未来の開催の一部を中止にする（今週の確認用の開催は除く）
    cancelable = [
        i
        for i, e in enumerate(events)
        if e["event_date"] >= base_date.isoformat() and i not in protected
    ]
    cancel_count = max(1, round(len(cancelable) * CANCEL_RATE))
    for i in rng.sample(cancelable, cancel_count):
        events[i]["status"] = "中止"
    return events

def validate_membership(
    employees: list[dict],
    clubs: list[dict],
    organizers: dict[str, str],
    members: list[dict],
    interests: list[dict],
) -> None:
    """幹事・メンバー・興味のデータが、ルールどおりかを確かめる。間違いはまとめて表示して止まる。"""
    problems = []
    employee_of = {e["id"]: e for e in employees}
    club_of = {c["name"]: c for c in clubs}
    activity_names = {name for name, _ in ACTIVITIES}

    # 幹事
    if set(organizers) != set(club_of):
        problems.append("幹事が決まっていない部活があります")
    if len(set(organizers.values())) != len(organizers):
        problems.append("同じ人が複数の部活の幹事になっています")
    if organizers.get(E002_CLUB) != "E002":
        problems.append(f"E002 が {E002_CLUB} の幹事になっていません")
    for club_name, employee_id in organizers.items():
        if employee_id in ("E001", "E003") and not (employee_id == "E002"):
            problems.append(f"{club_name}: E001・E003 は幹事にできません")
        if employee_of[employee_id]["location"] != club_of[club_name]["location"]:
            problems.append(f"{club_name}: 幹事 {employee_id} の拠点が部活と違います")

    # メンバー
    keys = [(m["club"], m["employee_id"]) for m in members]
    if len(keys) != len(set(keys)):
        problems.append("同じ部活に同じ人が2回入っています")
    counts = Counter(m["club"] for m in members)
    for club_name, c in club_of.items():
        if not (MEMBERS_MIN <= counts[club_name] <= MEMBERS_MAX):
            problems.append(f"{club_name}: メンバー数 {counts[club_name]} が範囲外です")
        if (club_name, organizers[club_name]) not in keys:
            problems.append(f"{club_name}: 幹事がメンバーに入っていません")
    for m in members:
        if m["employee_id"] == "E001":
            problems.append("E001 が部活に入っています")
        if employee_of[m["employee_id"]]["location"] != club_of[m["club"]]["location"]:
            problems.append(f"{m['club']}: メンバー {m['employee_id']} の拠点が違います")

    # 興味
    pairs = [(i["employee_id"], i["activity"]) for i in interests]
    if len(pairs) != len(set(pairs)):
        problems.append("同じ人が同じ活動に2回興味を持っています")
    per_employee = Counter(i["employee_id"] for i in interests)
    for employee_id, count in per_employee.items():
        if count > INTEREST_MAX:
            problems.append(f"{employee_id}: 興味が {count} 個あります")
    for i in interests:
        if i["level"] not in INTEREST_LEVELS:
            problems.append(f"{i['employee_id']}: 経験レベル {i['level']!r} は選択肢にありません")
        if i["activity"] not in activity_names:
            problems.append(f"{i['employee_id']}: 活動 {i['activity']!r} が活動の一覧にありません")
    if len(interests) > 1000:
        problems.append(f"興味が {len(interests)} 件あり、1000件を超えています")

    if problems:
        raise ValueError("データの検査で問題が見つかりました:\n" + "\n".join(problems))


def validate_events(clubs: list[dict], events: list[dict], base_date: date) -> None:
    """開催のデータが、DB の制約や PM 決定どおりかを確かめる。間違いはまとめて表示して止まる。"""
    problems = []
    club_of = {c["name"]: c for c in clubs}
    base = base_date.isoformat()
    past_limit = (base_date - timedelta(days=PAST_DAYS)).isoformat()
    future_limit = (base_date + timedelta(days=FUTURE_DAYS)).isoformat()
    this_sunday = (base_date + timedelta(days=6 - base_date.weekday())).isoformat()

    for e in events:
        label = f"{e['club']} {e['event_date']}"
        c = club_of.get(e["club"])
        if c is None:
            problems.append(f"{label}: 部活が一覧にありません")
            continue
        d = date.fromisoformat(e["event_date"])
        if d.weekday() not in SLOT_WEEKDAYS[c["slot"]]:
            problems.append(f"{label}: 曜日が部活の slot（{c['slot']}）と合いません")
        if (e["start_time"], e["end_time"]) != SLOT_TIMES[c["slot"]]:
            problems.append(f"{label}: 開始・終了の時刻が slot と合いません")
        if not e["end_time"] > e["start_time"]:
            problems.append(f"{label}: 終了時刻が開始時刻より後ではありません")
        if e["meeting_place"] not in MEETING_PLACES[c["location"]]:
            problems.append(f"{label}: 集合場所 {e['meeting_place']!r} が候補にありません")
        meeting_time = e["meeting_time"]
        if meeting_time is not None and meeting_time != minus_minutes(
            e["start_time"], MEETING_BEFORE_MINUTES
        ):
            problems.append(f"{label}: 集合時間が開始の {MEETING_BEFORE_MINUTES} 分前ではありません")
        if e["status"] not in ("予定", "中止"):
            problems.append(f"{label}: 状態 {e['status']!r} は選択肢にありません")
        if e["event_date"] < base:
            if e["status"] != "予定":
                problems.append(f"{label}: 過去の開催の状態が「予定」ではありません")
            if e["event_date"] < past_limit:
                problems.append(f"{label}: {PAST_DAYS} 日より前の開催があります")
        elif e["event_date"] > future_limit:
            problems.append(f"{label}: {FUTURE_DAYS} 日より先の開催があります")

    keys = [(e["club"], e["event_date"]) for e in events]
    if len(keys) != len(set(keys)):
        problems.append("同じ部活に同じ日の開催が2件あります")

    past_count = Counter(e["club"] for e in events if e["event_date"] < base)
    future_count = Counter(e["club"] for e in events if e["event_date"] >= base)
    for name in club_of:
        if past_count[name] > PAST_EVENTS_MAX:
            problems.append(f"{name}: 過去の開催が {past_count[name]} 件あります")
        n = future_count[name]
        if n and not (FUTURE_EVENTS_MIN <= n <= FUTURE_EVENTS_MAX):
            problems.append(f"{name}: 未来の開催の件数 {n} が範囲外です")
    no_future = [name for name in club_of if future_count[name] == 0]
    if len(no_future) != NO_EVENT_CLUB_COUNT:
        problems.append(f"未来の開催がない部活は {NO_EVENT_CLUB_COUNT} 個のはずですが {len(no_future)} 個です")
    if E002_CLUB in no_future:
        problems.append(f"{E002_CLUB} に未来の開催がありません（E002 のデモ用）")

    this_week_clubs = {
        e["club"]
        for e in events
        if base <= e["event_date"] <= this_sunday and e["status"] == "予定"
    }
    if not this_week_clubs:
        problems.append("今週（基準日〜日曜）に開催がある部活がありません")
    canceled = [e for e in events if e["status"] == "中止"]
    if not canceled:
        problems.append("中止の開催がありません")
    if any(e["event_date"] < base for e in canceled):
        problems.append("過去の開催が中止になっています")
    none_count = sum(e["meeting_time"] is None for e in events)
    if none_count == 0 or none_count == len(events):
        problems.append("集合時間が空の開催と、入っている開催の両方が必要です")

    if problems:
        raise ValueError("データの検査で問題が見つかりました:\n" + "\n".join(problems))

def print_membership_summary(
    clubs: list[dict],
    employees: list[dict],
    organizers: dict[str, str],
    members: list[dict],
    interests: list[dict],
) -> None:
    """幹事・メンバー・興味の件数や内訳を表示する（目で確認するため）。"""
    name_of = {e["id"]: e["name"] for e in employees}
    member_count = Counter(m["club"] for m in members)
    per_employee = Counter(i["employee_id"] for i in interests)

    print()
    print("■ 幹事・メンバー・興味")
    for c in clubs:
        organizer = organizers[c["name"]]
        print(
            f"  {c['name']}: 幹事 {organizer} {name_of[organizer]}"
            f" / メンバー {member_count[c['name']]}名"
        )
    in_clubs = len({m["employee_id"] for m in members})
    print(f"  部活メンバーの総数: {len(members)}件（部活に入っている社員 {in_clubs}名）")
    print(f"  興味の総数: {len(interests)}件（1000件以下: {len(interests) <= 1000}）")
    print(
        "  興味の数ごとの人数:",
        dict(sorted(Counter(per_employee.get(e["id"], 0) for e in employees).items())),
    )
    print("  経験レベル:", dict(Counter(i["level"] for i in interests)))
    print(
        "  E001 の興味:",
        [(i["activity"], i["level"]) for i in interests if i["employee_id"] == "E001"],
    )
    print(f"  E002 が入っている部活: {[m['club'] for m in members if m['employee_id'] == 'E002']}")
    print(
        f"  指紋: 幹事 {fingerprint([organizers])}"
        f" / メンバー {fingerprint(members)} / 興味 {fingerprint(interests)}"
    )
    
    
def parse_date(text: str) -> date:
    """--base-date の文字列（YYYY-MM-DD）を日付にする。"""
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"日付は YYYY-MM-DD の形で指定してください: {text}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="テストデータの初期化（全データを消して、ダミーデータを入れ直す）"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="DB に書き込まず、作るデータの件数などだけを表示する",
    )
    parser.add_argument(
        "--base-date",
        type=parse_date,
        default=date.today(),
        help="開催日などの基準日（YYYY-MM-DD）。省略すると今日",
    )
    parser.add_argument(
        "--show-clubs",
        action="store_true",
        help="部活のひとこと・費用の補足・持ち物の文章も表示する（文章の確認用）",
    )
    return parser.parse_args()


def get_supabase():
    """Supabase のクライアントを返す。DB に書き込むときだけ呼ぶ。

    db/client.py は import した時点で接続して secrets を読むため、
    ファイルの先頭ではなく、この関数の中で import する
    （--dry-run を secrets の無い環境でも動かすため）。
    """
    sys.path.insert(0, str(FRONTEND_DIR))
    os.chdir(FRONTEND_DIR)  # .streamlit/secrets.toml を見つけてもらうため
    from db.client import supabase  # pyright: ignore[reportMissingImports]

    return supabase


def make_flags(rng: random.Random, total: int, true_count: int) -> list[bool]:
    """True が true_count 個、残りが False のリストを、並びをシャッフルして返す。"""
    flags = [True] * true_count + [False] * (total - true_count)
    rng.shuffle(flags)
    return flags


def make_employees(rng: random.Random) -> list[dict]:
    """社員500名のデータを作る（employees テーブルの列名どおりの dict）。"""
    n = EMPLOYEE_COUNT

    # 名前：姓×名の全組み合わせから、重複なしで500通りを選ぶ（スペースなし）
    pairs = [(s, g) for s in SURNAMES for g in GIVEN_NAMES]
    names = [s + g for s, g in rng.sample(pairs, n)]

    # 部署：10部署を50名ずつ（均等）
    depts = DEPARTMENTS * (n // len(DEPARTMENTS))
    rng.shuffle(depts)

    # 拠点：東京350・大阪150
    locations = ["東京"] * TOKYO_COUNT + ["大阪"] * (n - TOKYO_COUNT)
    rng.shuffle(locations)

    # 入社年：入社1〜3年目（2024〜2026）が150名、残りは2015〜2023
    years = [y for y in RECENT_YEARS for _ in range(RECENT_PER_YEAR)]
    years += [rng.choice(OLDER_YEARS) for _ in range(n - len(years))]
    rng.shuffle(years)
    # E001（新入社員）は2026年入社にする。2026年入社の誰かと入れ替えて、人数は変えない
    j = years.index(2026)
    years[0], years[j] = years[j], years[0]

    # 入社区分：新卒6・中途3・異動1くらいの割合。E001 は新卒にする
    entry_types = rng.choices(ENTRY_TYPES, weights=ENTRY_TYPE_WEIGHTS, k=n)
    entry_types[0] = "新卒"

    # 公開設定：8割が ON（興味と時間は別々に決める）
    interests_public = make_flags(rng, n, PUBLIC_COUNT)
    slots_public = make_flags(rng, n, PUBLIC_COUNT)

    # 参加可能時間：1割は未入力、それ以外は1〜3個
    no_slots = set(rng.sample(range(n), NO_SLOTS_COUNT))

    employees = []
    for i in range(n):
        if i in no_slots:
            slots = None
        else:
            picked = rng.sample(SLOTS, rng.randint(1, 3))
            slots = [s for s in SLOTS if s in picked]  # 並びをそろえる
        employees.append(
            {
                "id": f"E{i + 1:03d}",
                "name": names[i],
                "dept": depts[i],
                "location": locations[i],
                "joined_year": years[i],
                "entry_type": entry_types[i],
                "available_slots": slots,
                "interests_public": interests_public[i],
                "slots_public": slots_public[i],
                "is_admin": i == 2,  # E003 だけ運営者
            }
        )
    return employees


def make_activities() -> list[dict]:
    """活動20件のデータを作る（activities テーブルの列名どおり）。"""
    return [{"name": name, "category": category} for name, category in ACTIVITIES]


def make_clubs() -> list[dict]:
    """部活15件のデータを返す（直書きのデータで、乱数は使わない）。"""
    return [dict(spec) for spec in CLUB_SPECS]


def validate_clubs(activities: list[dict], clubs: list[dict]) -> None:
    """活動と部活のデータが、DB の選択肢や PM 決定どおりかを確かめる。

    間違いがあれば、まとめて表示して止まる（DB に入れる前に気づくため）。
    """
    problems = []

    activity_names = [a["name"] for a in activities]
    if len(activity_names) != len(set(activity_names)):
        problems.append("活動の名前が重複しています")
    for a in activities:
        if a["category"] not in CATEGORIES:
            problems.append(f"活動 {a['name']}: カテゴリ {a['category']!r} は選択肢にありません")

    category_of = {a["name"]: a["category"] for a in activities}
    checks = [
        ("location", LOCATIONS), ("slot", SLOTS), ("frequency", FREQUENCIES),
        ("level", LEVELS), ("fact_adult_starters", FACT_ADULT_STARTERS),
        ("fee", FEES), ("rental", RENTALS), ("join_leave", JOIN_LEAVES),
        ("after_activity", AFTER_ACTIVITIES),
    ]
    for c in clubs:
        for key, allowed in checks:
            if c[key] not in allowed:
                problems.append(f"{c['name']}: {key}={c[key]!r} は選択肢にありません")
        if c["activity"] not in category_of:
            problems.append(f"{c['name']}: 活動 {c['activity']!r} が活動の一覧にありません")
        if len(c["mood_tags"]) > 3 or any(t not in MOOD_TAGS for t in c["mood_tags"]):
            problems.append(f"{c['name']}: 雰囲気タグが不正です {c['mood_tags']}")
        if len(c["icon"]) != 1:
            problems.append(f"{c['name']}: アイコンが1文字ではありません {c['icon']!r}")
        for key in ("message", "belongings_note"):
            if not c[key]:
                problems.append(f"{c['name']}: {key} が空です")

    club_names = [c["name"] for c in clubs]
    if len(club_names) != len(set(club_names)):
        problems.append("部活の名前が重複しています")
    if len(clubs) != 15:
        problems.append(f"部活は15件のはずですが {len(clubs)} 件です")
    if len(activities) != 20:
        problems.append(f"活動は20件のはずですが {len(activities)} 件です")
    location_counts = Counter(c["location"] for c in clubs)
    if location_counts["東京"] != 10 or location_counts["大阪"] != 5:
        problems.append(f"東京10・大阪5のはずですが {dict(location_counts)} です")
    non_sports = sum(category_of.get(c["activity"]) != "スポーツ" for c in clubs)
    if non_sports < 7:
        problems.append(f"スポーツ以外の部活が少なすぎます（{non_sports}件）")

    if problems:
        raise ValueError("データの検査で問題が見つかりました:\n" + "\n".join(problems))


def fingerprint(rows: list[dict]) -> str:
    """データの中身から作る短い文字列。同じ seed なら、いつ作っても同じ値になる。"""
    text = json.dumps(rows, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def print_employee_summary(employees: list[dict]) -> None:
    """作った社員データの件数や割合を表示する（目で確認するため）。"""
    print()
    print(f"■ 社員（{len(employees)}名）")
    names = {e["name"] for e in employees}
    print(f"  同姓同名なし: {len(names) == len(employees)}")
    print("  拠点:", dict(Counter(e["location"] for e in employees)))
    print("  部署:", dict(Counter(e["dept"] for e in employees)))
    recent = sum(1 for e in employees if e["joined_year"] >= RECENT_YEARS[0])
    print(f"  入社1〜3年目（{RECENT_YEARS[0]}〜{RECENT_YEARS[-1]}年入社）: {recent}名")
    print("  入社年:", dict(sorted(Counter(e["joined_year"] for e in employees).items())))
    print("  入社区分:", dict(Counter(e["entry_type"] for e in employees)))
    print(
        f"  興味を公開: {sum(e['interests_public'] for e in employees)}名 / "
        f"参加可能時間を公開: {sum(e['slots_public'] for e in employees)}名"
    )
    print(f"  参加可能時間が未入力: {sum(e['available_slots'] is None for e in employees)}名")
    print(f"  運営者（is_admin）: {[e['id'] for e in employees if e['is_admin']]}")
    print("  先頭の5名:")
    for e in employees[:5]:
        print(
            f"    {e['id']} {e['name']} {e['dept']} {e['location']} "
            f"{e['joined_year']}年 {e['entry_type']}"
        )
    print(f"  指紋（同じ seed なら同じ値）: {fingerprint(employees)}")


def print_club_summary(
    activities: list[dict], clubs: list[dict], show_details: bool
) -> None:
    """作った活動・部活データの件数や内訳を表示する（目で確認するため）。"""
    category_of = {a["name"]: a["category"] for a in activities}
    used = {c["activity"] for c in clubs}

    print()
    print(f"■ 活動（{len(activities)}件）")
    print("  カテゴリ:", dict(Counter(a["category"] for a in activities)))
    print("  部活がない活動:", [a["name"] for a in activities if a["name"] not in used])
    print(f"  指紋: {fingerprint(activities)}")

    print()
    print(f"■ 部活（{len(clubs)}件）")
    print("  拠点:", dict(Counter(c["location"] for c in clubs)))
    print("  カテゴリ:", dict(Counter(category_of[c["activity"]] for c in clubs)))
    for key, label in (
        ("frequency", "頻度"), ("level", "レベル"), ("fee", "費用"),
        ("after_activity", "活動後"), ("join_leave", "途中参加"),
    ):
        print(f"  {label}:", dict(Counter(c[key] for c in clubs)))
    for c in clubs:
        tags = "、".join(c["mood_tags"])
        print(
            f"  {c['icon']} {c['name']}（{c['location']}・{c['slot']}・{c['frequency']}）"
            f" {c['level']} / {c['fee']} / {tags}"
        )
        if show_details:
            print(f"      ひとこと: {c['message']}")
            print(f"      費用の補足: {c['fee_note']}")
            print(f"      持ち物: {c['belongings_note']}")
    print(f"  指紋: {fingerprint(clubs)}")


def print_event_summary(clubs: list[dict], events: list[dict], base_date: date) -> None:
    """作った開催データの件数や内訳を表示する（目で確認するため）。"""
    base = base_date.isoformat()
    this_sunday = (base_date + timedelta(days=6 - base_date.weekday())).isoformat()
    weekday = "月火水木金土日"

    def label(e: dict) -> str:
        d = date.fromisoformat(e["event_date"])
        return (
            f"{e['club']} {e['event_date']}（{weekday[d.weekday()]}）"
            f"{e['start_time']}〜{e['end_time']} {e['status']}"
        )

    past = [e for e in events if e["event_date"] < base]
    future = [e for e in events if e["event_date"] >= base]
    this_week = [e for e in events if base <= e["event_date"] <= this_sunday]

    print()
    print(f"■ 開催（{len(events)}件）")
    print(f"  過去: {len(past)}件 / 未来: {len(future)}件")
    print("  状態:", dict(Counter(e["status"] for e in events)))
    print(f"  集合時間が空: {sum(e['meeting_time'] is None for e in events)}件")
    print("  集合場所:", dict(Counter(e["meeting_place"] for e in events)))
    print(f"  今週（{base}〜{this_sunday}）の開催: {len(this_week)}件")
    for e in this_week:
        print(f"    {label(e)}")
    print("  中止の開催:")
    for e in events:
        if e["status"] == "中止":
            print(f"    {label(e)}")
    print("  部活ごとの件数（過去 / 未来）:")
    for c in clubs:
        p = sum(1 for e in past if e["club"] == c["name"])
        f = sum(1 for e in future if e["club"] == c["name"])
        note = "  ← 未来の開催なし" if f == 0 else ""
        print(f"    {c['name']}: {p} / {f}{note}")
    print(f"  指紋: {fingerprint(events)}")


# ---- 申込の作り方（PM 決定 2026-10-07） ----
# 申込の状態は「申込済み」「キャンセル」の2種類だけ。ID は DB の自動採番に任せるので、
# 申込が指す開催は、events リストの番号（"event"）で持つ。
APP_SEED_OFFSET = 1  # 申込専用の乱数。開催までの指紋を変えないために、別の乱数にする
APP_PAST_COUNT = 25  # 過去の開催への申込の数
APP_FUTURE_COUNT = 35  # 未来の開催への申込の数（E001 の2件、中止の開催への申込を含む）
APP_CANCEL_PAST = 3  # 過去の開催への申込のうち、キャンセルの数
APP_CANCEL_FUTURE = 3  # 未来の開催への申込のうち、キャンセルの数（E001 の1件を含む）
APP_MEMBER_PAST = 2  # 部活のメンバーが、自分の部活の過去の開催に申し込む件数
APP_MEMBER_FUTURE = 3  # 同じく、未来の開催に申し込む件数
APP_REPEAT_COUNT = 5  # 同じ部活の過去と未来の両方に申し込む外部の人の数（組）
APP_CANCELED_EVENT_COUNT = 2  # 中止の開催への申込の数
APP_E002_INBOUND = 2  # E001 以外から、E002 の部活（テニス部）の未来の開催に入る申込の数
APP_CONFIRM_RATE_PAST = 0.8  # 過去の「申込済み」のうち、幹事が確認済みの割合
APP_CONFIRM_RATE_FUTURE = 0.3  # 未来の「申込済み」のうち、幹事が確認済みの割合
APP_DAYS_MAX = 14  # 申込日は、開催日（未来は基準日）の何日前までか
APPLIED_HOURS = (9, 18)  # 申込した時刻（時）。確認・キャンセルは19時台にして、必ず後になるようにする
LATER_HOUR = 19
TZ_SUFFIX = "+09:00"


def stamp(d: date, rng: random.Random, later: bool = False) -> str:
    """日付に時刻を付けて、timestamptz に入れる文字列にする。"""
    hour = LATER_HOUR if later else rng.randint(*APPLIED_HOURS)
    return f"{d.isoformat()}T{hour:02d}:{rng.randint(0, 59):02d}:00{TZ_SUFFIX}"


def make_applications(
    employees: list[dict],
    clubs: list[dict],
    organizers: dict[str, str],
    members: list[dict],
    events: list[dict],
    base_date: date,
) -> list[dict]:
    """申込を作る。"event" は events リストの番号。DB に入れるときに event_id に置き換える。"""
    rng = random.Random(SEED + APP_SEED_OFFSET)
    base = base_date.isoformat()
    club_of = {c["name"]: c for c in clubs}
    member_ids = {c["name"]: set() for c in clubs}
    for m in members:
        member_ids[m["club"]].add(m["employee_id"])
    excluded = {"E001", "E003"} | set(organizers.values())
    pool = {
        loc: sorted(e["id"] for e in employees if e["location"] == loc and e["id"] not in excluded)
        for loc in LOCATIONS
    }

    past_idx = [i for i, e in enumerate(events) if e["event_date"] < base]
    open_idx = [i for i, e in enumerate(events) if e["event_date"] >= base and e["status"] == "予定"]
    stop_idx = [i for i, e in enumerate(events) if e["event_date"] >= base and e["status"] == "中止"]
    tennis_open = [i for i in open_idx if events[i]["club"] == E002_CLUB]
    if len(tennis_open) < 2:
        raise ValueError(f"{E002_CLUB}の未来の「予定」の開催が2件ありません（E001 の申込に必要）")

    apps = []  # {"event", "applicant_id", "kind"}。kind は作り方の区別（あとで状態を決める）
    taken = set()

    def add(event: int, applicant: str, kind: str) -> None:
        taken.add((event, applicant))
        apps.append({"event": event, "applicant_id": applicant, "kind": kind})

    def outsider(event: int) -> str:
        """その部活のメンバーでも幹事でもない、同じ拠点の社員を選ぶ。"""
        club = events[event]["club"]
        candidates = pool[club_of[club]["location"]]
        for _ in range(500):
            who = rng.choice(candidates)
            if who not in member_ids[club] and (event, who) not in taken:
                return who
        raise ValueError(f"{club}の開催に申し込める社員が見つかりません")

    # 1) E001：テニス部の未来の「予定」の開催に2件（日付が早い方が「申込済み」、遅い方が「キャンセル」）
    first, second = sorted(rng.sample(tennis_open, 2), key=lambda i: events[i]["event_date"])
    add(first, "E001", "e001_active")
    add(second, "E001", "e001_canceled")

    # 2) リピーター：同じ部活の過去と未来の両方に申し込む外部の人
    repeat_clubs = sorted(
        {events[i]["club"] for i in past_idx} & {events[i]["club"] for i in open_idx}
    )
    for club in rng.sample(repeat_clubs, APP_REPEAT_COUNT):
        past_event = rng.choice([i for i in past_idx if events[i]["club"] == club])
        who = outsider(past_event)
        add(past_event, who, "repeat_past")
        future_event = rng.choice([i for i in open_idx if events[i]["club"] == club])
        add(future_event, who, "repeat_future")

    # 3) メンバー：自分の部活の開催に申し込む（幹事は除く）
    def member_app(event_list: list[int], kind: str) -> None:
        for _ in range(500):
            event = rng.choice(event_list)
            club = events[event]["club"]
            candidates = sorted(member_ids[club] - {organizers[club]})
            who = rng.choice(candidates)
            if (event, who) not in taken:
                add(event, who, kind)
                return
        raise ValueError("メンバーの申込が作れません")

    for _ in range(APP_MEMBER_PAST):
        member_app(past_idx, "member_past")
    for _ in range(APP_MEMBER_FUTURE):
        member_app(open_idx, "member_future")

    # 4) 中止の開催への申込（人気集計から除かれるかの確認用）
    for _ in range(APP_CANCELED_EVENT_COUNT):
        event = rng.choice(stop_idx)
        add(event, outsider(event), "stopped_event")

    # 5) E002（テニス部の幹事）に届く申込
    for _ in range(APP_E002_INBOUND):
        event = rng.choice(tennis_open)
        add(event, outsider(event), "e002_inbound")

    # 6) 残りを、外部の人の申込で埋める
    past_rest = APP_PAST_COUNT - sum(a["kind"].endswith("_past") for a in apps)
    future_rest = APP_FUTURE_COUNT - (len(apps) - sum(a["kind"].endswith("_past") for a in apps))
    if past_rest < 0 or future_rest < 0:
        raise ValueError("申込の件数の設定が、決まった作り方の合計より小さくなっています")
    for _ in range(past_rest):
        event = rng.choice(past_idx)
        add(event, outsider(event), "fill_past")
    for _ in range(future_rest):
        event = rng.choice(open_idx)
        add(event, outsider(event), "fill_future")

    # 7) キャンセルにする申込を決める（E001 の1件は決まっているので、その分を引く）
    cancel_ids = set()
    for kind, count in (("fill_past", APP_CANCEL_PAST), ("fill_future", APP_CANCEL_FUTURE - 1)):
        pickable = [i for i, a in enumerate(apps) if a["kind"] == kind]
        cancel_ids |= set(rng.sample(pickable, count))

    # 8) 状態と日時を決める
    result = []
    for i, a in enumerate(apps):
        event = events[a["event"]]
        event_day = date.fromisoformat(event["event_date"])
        is_past = event["event_date"] < base
        if is_past:
            applied_day = event_day - timedelta(days=rng.randint(1, APP_DAYS_MAX))
        else:
            applied_day = base_date - timedelta(days=rng.randint(1, APP_DAYS_MAX))
        # 確認・キャンセルは、申込日から「開催日の前日か基準日の早い方」までの間
        limit = min(event_day - timedelta(days=1), base_date)
        later_day = applied_day + timedelta(days=rng.randint(0, (limit - applied_day).days))

        canceled = i in cancel_ids or a["kind"] == "e001_canceled"
        confirmed = False
        if not canceled and a["kind"] != "e001_active" and event["status"] == "予定":
            confirmed = rng.random() < (APP_CONFIRM_RATE_PAST if is_past else APP_CONFIRM_RATE_FUTURE)
        result.append(
            {
                "event": a["event"],
                "applicant_id": a["applicant_id"],
                "status": "キャンセル" if canceled else "申込済み",
                "is_first_time": True,  # 次の手順で決める
                "applied_at": stamp(applied_day, rng),
                "canceled_at": stamp(later_day, rng, later=True) if canceled else None,
                "confirmed_at": stamp(later_day, rng, later=True) if confirmed else None,
            }
        )

    # 9) 初参加かどうか：application_service と同じ考え方（その部活のメンバーでなく、
    #    それより前に開かれた開催に、キャンセルしていない申込もない）
    for a in result:
        event = events[a["event"]]
        cutoff = min(event["event_date"], base)
        a["is_first_time"] = a["applicant_id"] not in member_ids[event["club"]] and not any(
            b["applicant_id"] == a["applicant_id"]
            and b["status"] != "キャンセル"
            and events[b["event"]]["club"] == event["club"]
            and events[b["event"]]["event_date"] < cutoff
            for b in result
        )

    result.sort(key=lambda a: (a["applied_at"], a["event"], a["applicant_id"]))
    return result

def validate_applications(
    employees: list[dict],
    clubs: list[dict],
    organizers: dict[str, str],
    members: list[dict],
    events: list[dict],
    apps: list[dict],
    base_date: date,
) -> None:
    """申込のデータが、DB の制約や PM 決定どおりかを確かめる。間違いはまとめて表示して止まる。"""
    problems = []
    base = base_date.isoformat()
    employee_ids = {e["id"] for e in employees}
    member_ids = {c["name"]: set() for c in clubs}
    for m in members:
        member_ids[m["club"]].add(m["employee_id"])

    seen = set()
    for a in apps:
        label = f"申込（開催{a['event']}・{a['applicant_id']}）"
        if not 0 <= a["event"] < len(events):
            problems.append(f"{label}: 開催の番号が範囲外です")
            continue
        event = events[a["event"]]
        club = event["club"]
        if a["applicant_id"] not in employee_ids:
            problems.append(f"{label}: 社員が存在しません")
        if (a["event"], a["applicant_id"]) in seen:
            problems.append(f"{label}: 同じ人が同じ開催に2回申し込んでいます")
        seen.add((a["event"], a["applicant_id"]))
        if a["applicant_id"] == "E003" or a["applicant_id"] == organizers[club]:
            problems.append(f"{label}: 運営者と、その部活の幹事は申し込みません")
        if a["status"] not in ("申込済み", "キャンセル"):
            problems.append(f"{label}: 状態が不正です")
        if (a["status"] == "キャンセル") != (a["canceled_at"] is not None):
            problems.append(f"{label}: canceled_at は「キャンセル」のときだけ入ります")
        if a["status"] == "キャンセル" and a["confirmed_at"] is not None:
            problems.append(f"{label}: キャンセルに確認日時があります")
        day = a["applied_at"][:10]
        if not day < event["event_date"]:
            problems.append(f"{label}: 申込日が開催日より前ではありません")
        if not day < base:
            problems.append(f"{label}: 申込日が基準日より前ではありません")
        for key in ("canceled_at", "confirmed_at"):
            if a[key] is not None:
                if not a[key] > a["applied_at"]:
                    problems.append(f"{label}: {key} が申込日時より後ではありません")
                if not (a[key][:10] < event["event_date"] and a[key][:10] <= base):
                    problems.append(f"{label}: {key} の日付が開催日・基準日と合いません")
        if event["status"] == "中止" and a["confirmed_at"] is not None:
            problems.append(f"{label}: 中止の開催に確認日時があります")

        # 初参加の判定を、別の書き方で検算する
        cutoff = min(event["event_date"], base)
        earlier = [
            b
            for b in apps
            if b["applicant_id"] == a["applicant_id"]
            and b["status"] != "キャンセル"
            and events[b["event"]]["club"] == club
            and events[b["event"]]["event_date"] < cutoff
        ]
        expected = a["applicant_id"] not in member_ids[club] and not earlier
        if a["is_first_time"] != expected:
            problems.append(f"{label}: is_first_time が判定ルールと合いません")

    def is_past(a: dict) -> bool:
        return events[a["event"]]["event_date"] < base

    past = [a for a in apps if is_past(a)]
    future = [a for a in apps if not is_past(a)]
    if len(past) != APP_PAST_COUNT:
        problems.append(f"過去の開催への申込が {len(past)} 件です（{APP_PAST_COUNT} 件の予定）")
    if len(future) != APP_FUTURE_COUNT:
        problems.append(f"未来の開催への申込が {len(future)} 件です（{APP_FUTURE_COUNT} 件の予定）")
    if sum(a["status"] == "キャンセル" for a in past) != APP_CANCEL_PAST:
        problems.append("過去の開催のキャンセルの数が合いません")
    if sum(a["status"] == "キャンセル" for a in future) != APP_CANCEL_FUTURE:
        problems.append("未来の開催のキャンセルの数が合いません")
    if any(a["status"] == "キャンセル" and events[a["event"]]["status"] == "中止" for a in apps):
        problems.append("中止の開催への申込は、キャンセルにしない決まりです")
    stopped = sum(events[a["event"]]["status"] == "中止" for a in apps)
    if stopped != APP_CANCELED_EVENT_COUNT:
        problems.append(f"中止の開催への申込が {stopped} 件です（{APP_CANCELED_EVENT_COUNT} 件の予定）")
    member_apps = sum(a["applicant_id"] in member_ids[events[a["event"]]["club"]] for a in apps)
    if member_apps != APP_MEMBER_PAST + APP_MEMBER_FUTURE:
        problems.append(f"メンバーの申込が {member_apps} 件です")

    e001 = [a for a in apps if a["applicant_id"] == "E001"]
    if sorted(a["status"] for a in e001) != ["キャンセル", "申込済み"]:
        problems.append("E001 の申込は、「申込済み」1件と「キャンセル」1件のはずです")
    for a in e001:
        e = events[a["event"]]
        if e["club"] != E002_CLUB or e["status"] != "予定" or e["event_date"] < base:
            problems.append(f"E001 の申込が、{E002_CLUB}の未来の「予定」の開催ではありません")
        if not a["is_first_time"]:
            problems.append("E001 の申込は、初参加のはずです")
    inbound = [
        a
        for a in apps
        if a["applicant_id"] != "E001"
        and events[a["event"]]["club"] == E002_CLUB
        and not is_past(a)
        and a["status"] == "申込済み"
    ]
    if not inbound:
        problems.append(f"{E002_CLUB}に、E001 以外からの未来の申込がありません")

    if problems:
        raise ValueError("データの検査で問題が見つかりました:\n" + "\n".join(problems))


def print_application_summary(
    clubs: list[dict],
    events: list[dict],
    members: list[dict],
    apps: list[dict],
    base_date: date,
) -> None:
    """作った申込データの件数や内訳を表示する（目で確認するため）。"""
    base = base_date.isoformat()
    member_ids = {c["name"]: set() for c in clubs}
    for m in members:
        member_ids[m["club"]].add(m["employee_id"])
    past = [a for a in apps if events[a["event"]]["event_date"] < base]
    future = [a for a in apps if events[a["event"]]["event_date"] >= base]

    print()
    print(f"■ 申込（{len(apps)}件）")
    print(f"  過去の開催: {len(past)}件 / 未来の開催: {len(future)}件")
    print("  状態:", dict(Counter(a["status"] for a in apps)))
    print(
        f"  初参加: {sum(a['is_first_time'] for a in apps)}件 / "
        f"初参加でない: {sum(not a['is_first_time'] for a in apps)}件"
    )
    print(
        "  メンバーが自分の部活の開催に申込: "
        f"{sum(a['applicant_id'] in member_ids[events[a['event']]['club']] for a in apps)}件"
    )
    print(f"  幹事が確認済み: {sum(a['confirmed_at'] is not None for a in apps)}件")
    print(f"  中止の開催への申込: {sum(events[a['event']]['status'] == '中止' for a in apps)}件")
    print("  E001 の申込:")
    for a in apps:
        if a["applicant_id"] == "E001":
            e = events[a["event"]]
            print(f"    {e['club']} {e['event_date']} {a['status']}（初参加: {a['is_first_time']}）")
    print(f"  {E002_CLUB}への申込（未来・E001 以外）:")
    for a in apps:
        e = events[a["event"]]
        if e["club"] == E002_CLUB and a["applicant_id"] != "E001" and e["event_date"] >= base:
            print(f"    {e['event_date']} {a['applicant_id']} {a['status']}")
    print("  部活ごとの件数（過去 / 未来）:")
    for c in clubs:
        p = sum(1 for a in past if events[a["event"]]["club"] == c["name"])
        f = sum(1 for a in future if events[a["event"]]["club"] == c["name"])
        print(f"    {c['name']}: {p} / {f}")
    print(f"  指紋: {fingerprint(apps)}")
    

# ---- メッセージの作り方（PM 決定 2026-10-07） ----
# 申込についてのやりとり。"application" は、申込リストの番号。DB に入れるときに application_id に置き換える。
MSG_SEED_OFFSET = 2  # メッセージ専用の乱数。申込までの指紋を変えないために、別の乱数にする
MSG_FIRST_PAST = 1  # 初参加の申込のうち、過去の開催にメッセージを付ける数
MSG_FIRST_FUTURE = 2  # 同じく、未来の開催に付ける数
MSG_OTHER_PAST = 1  # 初参加でない申込のうち、過去の開催にメッセージを付ける数
MSG_OTHER_FUTURE = 1  # 同じく、未来の開催に付ける数
MSG_UNANSWERED = 1  # E001 以外で、幹事が返信していないメッセージの数（未来の開催のもの）
MSG_FIRST_TIME = "初参加です。よろしくお願いします。"  # 初参加の申込にだけ使う
MSG_ASK = "当日は現地集合で大丈夫ですか。"
MSG_REPLY = "確認しました。お待ちしています。"  # 幹事の返信
MSG_SENT_MINUTES_MAX = 5  # 申込側のメッセージは、申込日時の何分後までか
REPLY_HOUR = 20  # 幹事が返信する時刻（時）。確認・キャンセル（19時台）より後


def make_messages(
    apps: list[dict],
    events: list[dict],
    organizers: dict[str, str],
    base_date: date,
) -> list[dict]:
    """メッセージを作る。"application" は apps リストの番号。"""
    rng = random.Random(SEED + MSG_SEED_OFFSET)
    base = base_date.isoformat()

    def eligible(is_first: bool, past: bool) -> list[int]:
        """メッセージを付けられる申込（キャンセルでなく、中止でない開催への申込）の番号。"""
        return [
            i
            for i, a in enumerate(apps)
            if a["status"] == "申込済み"
            and a["applicant_id"] != "E001"
            and a["is_first_time"] == is_first
            and events[a["event"]]["status"] == "予定"
            and (events[a["event"]]["event_date"] < base) == past
        ]

    # 申込側のメッセージを付ける申込を決める：(申込の番号, 文面)
    asked = []
    e001 = [i for i, a in enumerate(apps) if a["applicant_id"] == "E001" and a["status"] == "申込済み"]
    asked.append((e001[0], MSG_FIRST_TIME))
    for is_first, past, count, text in (
        (True, True, MSG_FIRST_PAST, MSG_FIRST_TIME),
        (True, False, MSG_FIRST_FUTURE, MSG_FIRST_TIME),
        (False, True, MSG_OTHER_PAST, MSG_ASK),
        (False, False, MSG_OTHER_FUTURE, MSG_ASK),
    ):
        for i in rng.sample(eligible(is_first, past), count):
            asked.append((i, text))

    # 返信しないもの：E001 の1件と、E001 以外の未来の開催のうち MSG_UNANSWERED 件
    other_future = [
        i for i, _ in asked[1:] if events[apps[i]["event"]]["event_date"] >= base
    ]
    unanswered = {e001[0]} | set(rng.sample(sorted(other_future), MSG_UNANSWERED))

    messages = []
    for i, text in asked:
        a = apps[i]
        event = events[a["event"]]
        sent = datetime.fromisoformat(a["applied_at"]) + timedelta(
            minutes=rng.randint(1, MSG_SENT_MINUTES_MAX)
        )
        messages.append(
            {
                "application": i,
                "sender_id": a["applicant_id"],
                "body": text,
                "sent_at": sent.isoformat(timespec="seconds"),
            }
        )
        if i in unanswered:
            continue
        # 返信は、申込日から「開催日の前日か基準日の早い方」までの間の、夜
        applied_day = date.fromisoformat(a["applied_at"][:10])
        limit = min(date.fromisoformat(event["event_date"]) - timedelta(days=1), base_date)
        reply_day = applied_day + timedelta(days=rng.randint(0, (limit - applied_day).days))
        messages.append(
            {
                "application": i,
                "sender_id": organizers[event["club"]],
                "body": MSG_REPLY,
                "sent_at": f"{reply_day.isoformat()}T{REPLY_HOUR:02d}:{rng.randint(0, 59):02d}:00{TZ_SUFFIX}",
            }
        )

    messages.sort(key=lambda m: (m["sent_at"], m["application"], m["sender_id"]))
    return messages


def validate_messages(
    apps: list[dict],
    events: list[dict],
    organizers: dict[str, str],
    messages: list[dict],
    base_date: date,
) -> None:
    """メッセージのデータが、DB の制約や PM 決定どおりかを確かめる。間違いはまとめて表示して止まる。"""
    problems = []
    base = base_date.isoformat()

    by_application: dict[int, list[dict]] = {}
    for m in messages:
        by_application.setdefault(m["application"], []).append(m)

    for m in messages:
        label = f"メッセージ（申込{m['application']}・{m['sender_id']}）"
        if not 0 <= m["application"] < len(apps):
            problems.append(f"{label}: 申込の番号が範囲外です")
            continue
        a = apps[m["application"]]
        event = events[a["event"]]
        organizer = organizers[event["club"]]
        if not m["body"].strip():
            problems.append(f"{label}: 本文が空です")
        if a["status"] != "申込済み":
            problems.append(f"{label}: キャンセルの申込にメッセージが付いています")
        if event["status"] != "予定":
            problems.append(f"{label}: 中止の開催への申込にメッセージが付いています")
        if m["sender_id"] not in (a["applicant_id"], organizer):
            problems.append(f"{label}: 送り手が、申込者でも幹事でもありません")
        if m["body"] == MSG_FIRST_TIME and not a["is_first_time"]:
            problems.append(f"{label}: 初参加でない人が「初参加です」と送っています")
        if m["sender_id"] == a["applicant_id"]:
            if not m["sent_at"] > a["applied_at"]:
                problems.append(f"{label}: 送信日時が申込日時より後ではありません")
            if m["sent_at"][:10] != a["applied_at"][:10]:
                problems.append(f"{label}: 申込側のメッセージが、申込と別の日になっています")
        else:
            asks = [x for x in by_application[m["application"]] if x["sender_id"] == a["applicant_id"]]
            if len(asks) != 1 or not m["sent_at"] > asks[0]["sent_at"]:
                problems.append(f"{label}: 返信が、申込側のメッセージの後ではありません")
            if not (m["sent_at"][:10] < event["event_date"] and m["sent_at"][:10] <= base):
                problems.append(f"{label}: 返信の日付が開催日・基準日と合いません")

    asked = [m for m in messages if m["sender_id"] == apps[m["application"]]["applicant_id"]]
    replies = [m for m in messages if m not in asked]
    if len(asked) != 1 + MSG_FIRST_PAST + MSG_FIRST_FUTURE + MSG_OTHER_PAST + MSG_OTHER_FUTURE:
        problems.append(f"申込側のメッセージが {len(asked)} 件です")
    if len(asked) - len(replies) != 1 + MSG_UNANSWERED:
        problems.append(f"返信がないメッセージが {len(asked) - len(replies)} 件です")
    if len({m["application"] for m in asked}) != len(asked):
        problems.append("同じ申込に、申込側のメッセージが2件以上あります")

    e001 = [m for m in messages if apps[m["application"]]["applicant_id"] == "E001"]
    if len(e001) != 1 or e001[0]["sender_id"] != "E001":
        problems.append("E001 の申込には、E001 のメッセージが1件だけ付くはずです")

    if problems:
        raise ValueError("データの検査で問題が見つかりました:\n" + "\n".join(problems))


def print_message_summary(
    apps: list[dict],
    events: list[dict],
    organizers: dict[str, str],
    messages: list[dict],
    base_date: date,
) -> None:
    """作ったメッセージデータの件数や内訳を表示する（目で確認するため）。"""
    base = base_date.isoformat()
    asked = [m for m in messages if m["sender_id"] == apps[m["application"]]["applicant_id"]]
    replies = [m for m in messages if m not in asked]
    replied = {m["application"] for m in replies}

    print()
    print(f"■ メッセージ（{len(messages)}件）")
    print(f"  申込側: {len(asked)}件 / 幹事の返信: {len(replies)}件")
    print("  文面:", dict(Counter(m["body"] for m in messages)))
    print(
        f"  過去の開催: {sum(events[apps[m['application']]['event']]['event_date'] < base for m in messages)}件 / "
        f"未来の開催: {sum(events[apps[m['application']]['event']]['event_date'] >= base for m in messages)}件"
    )
    print("  返信がないメッセージ:")
    for m in asked:
        if m["application"] not in replied:
            a = apps[m["application"]]
            e = events[a["event"]]
            print(f"    {a['applicant_id']} → {e['club']} {e['event_date']}（幹事 {organizers[e['club']]}）")
    print("  E001 のメッセージ:")
    for m in messages:
        if apps[m["application"]]["applicant_id"] == "E001":
            print(f"    {m['sent_at']} {m['sender_id']}: {m['body']}")
    print(f"  指紋: {fingerprint(messages)}")
    
    
def main() -> None:
    args = parse_args()
    rng = random.Random(SEED)  # 以降のデータ作りは、この乱数だけを使う

    mode = "ドライラン（DB には書き込みません）" if args.dry_run else "本番（DB に書き込みます）"
    print(f"モード: {mode}")
    print(f"基準日: {args.base_date}")
    print(f"seed: {SEED}")

    if not args.dry_run:
        raise SystemExit("DB への書き込みはまだ実装していません。--dry-run を付けて実行してください。")

    employees = make_employees(rng)
    apply_demo_overrides(employees)
    activities = make_activities()
    clubs = make_clubs()
    validate_clubs(activities, clubs)
    organizers = assign_organizers(rng, employees, clubs)
    members = make_club_members(rng, employees, clubs, organizers)
    interests = make_interests(rng, employees, clubs, members)
    validate_membership(employees, clubs, organizers, members, interests)
    events = make_events(rng, clubs, args.base_date)
    validate_events(clubs, events, args.base_date)
    applications = make_applications(employees, clubs, organizers, members, events, args.base_date)
    validate_applications(employees, clubs, organizers, members, events, applications, args.base_date)
    messages = make_messages(applications, events, organizers, args.base_date)
    validate_messages(applications, events, organizers, messages, args.base_date)

    print_employee_summary(employees)
    print_club_summary(activities, clubs, args.show_clubs)
    print_membership_summary(clubs, employees, organizers, members, interests)
    print_event_summary(clubs, events, args.base_date)
    print_application_summary(clubs, events, members, applications, args.base_date)
    print_message_summary(applications, events, organizers, messages, args.base_date)


if __name__ == "__main__":
    main()