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
from datetime import date
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

    print_employee_summary(employees)
    print_club_summary(activities, clubs, args.show_clubs)
    print_membership_summary(clubs, employees, organizers, members, interests)


if __name__ == "__main__":
    main()
    