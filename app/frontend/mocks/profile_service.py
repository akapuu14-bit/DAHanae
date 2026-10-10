"""【仮のプロフィールサービス】社員プロフィール画面（S09）用の代役。

I-F契約には、プロフィールを返す関数がまだ無い。そこで、画面が必要とする形をこちらから提案して仮に置く。
  get_profile(employee_id, viewer_id) -> dict            … 表示に必要な情報をまとめて返す（読み取りのみ）
  update_public_settings(employee_id, requester_id, *, interests_public=None, slots_public=None)
                                                          … 公開・非公開の切り替え（SP-56）
  save_profile(employee_id, requester_id, interests, available_slots)
                                                          … 興味・経験と参加可能時間の編集保存（SP-57）
「非公開なら他の人には値を渡さない」判断は、画面ではなくこのサービスがする（SP-54, SP-65）。
DB の代わりに、メモリ上の dict で動く。
"""

from mocks import search_service
from services.errors import NotFoundError, PermissionDeniedError, ValidationError

# 仕様.md 3.2 の選択肢
EXPERIENCE_LEVELS = ["未経験", "初心者", "経験あり"]
SLOTS = ["平日夜", "土曜午前", "土曜午後", "日曜"]

# 活動マスタ（id, 名前）。部活検索の仮データの活動名に合わせる
ACTIVITIES = [(club_id, info[1]) for club_id, info in sorted(search_service._SEARCH_INFO.items())]
_ACTIVITY_NAMES = dict(ACTIVITIES)

# 社員ID -> (名前, 部署, 拠点, 入社年, 入社区分)。ここに無い E001〜E500 は汎用のダミーにする
_EMPLOYEES = {
    "E001": ("デモ社員 E001", "営業部", "東京", 2015, "中途"),
    "E101": ("佐藤 太郎", "営業部", "東京", 2018, "新卒"),
    "E102": ("鈴木 花子", "開発部", "東京", 2021, "新卒"),
    "E103": ("田中 一郎", "人事部", "大阪", 2016, "中途"),
    "E104": ("伊藤 美穂", "経理部", "東京", 2020, "新卒"),
    "E105": ("渡辺 大輔", "企画部", "大阪", 2019, "新卒"),
    "E106": ("山本 由美", "総務部", "東京", 2022, "新卒"),
    "E201": ("高橋 美咲", "営業部", "東京", 2019, "新卒"),
    "E202": ("中村 健", "開発部", "東京", 2017, "中途"),
    "E203": ("小林 彩", "人事部", "大阪", 2020, "新卒"),
    "E205": ("吉田 恒一", "経理部", "東京", 2012, "新卒"),
    "E206": ("山口 優", "企画部", "大阪", 2018, "異動"),
    "E207": ("松本 翔", "開発部", "東京", 2021, "新卒"),
    "E208": ("井上 里奈", "総務部", "東京", 2016, "中途"),
}

# 社員ID -> 所属している部活ID（デモ用）
_MEMBERSHIPS = {
    "E001": [1, 4], "E101": [1, 3], "E102": [2], "E103": [4], "E104": [5, 6],
    "E105": [7], "E106": [3], "E201": [1], "E202": [2], "E203": [3],
    "E205": [5], "E206": [6], "E207": [7], "E208": [8],
}

# 変更できる状態：社員ID -> {interests: [{activity_id, level}], slots: [...], interests_public, slots_public}
_state = {
    "E001": {"interests": [{"activity_id": 1, "level": "初心者"}, {"activity_id": 4, "level": "経験あり"}],
             "slots": ["平日夜", "土曜午前"], "interests_public": True, "slots_public": False},
    "E102": {"interests": [{"activity_id": 2, "level": "初心者"}],
             "slots": ["土曜午後"], "interests_public": False, "slots_public": True},
}


def _is_valid_id(employee_id):
    return (len(employee_id) == 4 and employee_id[0] == "E" and employee_id[1:].isdigit()
            and 1 <= int(employee_id[1:]) <= 500)


def _own_state(employee_id):
    return _state.setdefault(employee_id, {"interests": [], "slots": [], "interests_public": True, "slots_public": True})


def get_profile(employee_id, viewer_id):
    """プロフィール画面に必要な情報をまとめて返す（SP-53〜SP-55）。社員が無ければ NotFoundError。

    戻り値のキー：
      employee {id, name, dept, location, joined_year, entry_type}, is_self,
      interests（[{activity_id, activity_name, level}]。他人に非公開なら None）, interests_public,
      available_slots（[str]。他人に非公開なら None）, slots_public,
      clubs（所属部活の部活カード dict のリスト）
    """
    employee_id = (employee_id or "").strip().upper()
    if not _is_valid_id(employee_id):
        raise NotFoundError(f"employee {employee_id}")
    name, dept, location, joined_year, entry_type = _EMPLOYEES.get(
        employee_id, (f"デモ社員 {employee_id}", "デモ部", "東京", 2020, "中途"))
    own = _own_state(employee_id)
    is_self = employee_id == (viewer_id or "").strip().upper()

    interests = [{"activity_id": i["activity_id"], "activity_name": _ACTIVITY_NAMES[i["activity_id"]], "level": i["level"]}
                 for i in own["interests"]]
    cards = {c["club_id"]: c for c in search_service.search_clubs({})}
    return {
        "employee": {"id": employee_id, "name": name, "dept": dept, "location": location,
                     "joined_year": joined_year, "entry_type": entry_type},
        "is_self": is_self,
        "interests": interests if (is_self or own["interests_public"]) else None,
        "interests_public": own["interests_public"],
        "available_slots": list(own["slots"]) if (is_self or own["slots_public"]) else None,
        "slots_public": own["slots_public"],
        "clubs": [cards[club_id] for club_id in _MEMBERSHIPS.get(employee_id, []) if club_id in cards],
    }


def update_public_settings(employee_id, requester_id, *, interests_public=None, slots_public=None):
    """公開・非公開の切り替え（SP-56）。本人だけができる（PermissionDeniedError）。"""
    if (employee_id or "").strip().upper() != (requester_id or "").strip().upper():
        raise PermissionDeniedError("only the owner can change public settings")
    own = _own_state(employee_id.strip().upper())
    if interests_public is not None:
        own["interests_public"] = bool(interests_public)
    if slots_public is not None:
        own["slots_public"] = bool(slots_public)


def save_profile(employee_id, requester_id, interests, available_slots):
    """興味・経験と参加可能時間の編集保存（SP-57）。本人だけ。選択肢にない値は ValidationError。

    interests: [{"activity_id": int, "level": str}]
    """
    if (employee_id or "").strip().upper() != (requester_id or "").strip().upper():
        raise PermissionDeniedError("only the owner can edit")
    seen = set()
    for item in interests:
        if item["activity_id"] not in _ACTIVITY_NAMES or item["level"] not in EXPERIENCE_LEVELS:
            raise ValidationError("invalid interest")
        if item["activity_id"] in seen:  # employee_id × activity_id は重複不可
            raise ValidationError("duplicate activity")
        seen.add(item["activity_id"])
    if any(slot not in SLOTS for slot in available_slots):
        raise ValidationError("invalid slot")
    own = _own_state(employee_id.strip().upper())
    own["interests"] = [{"activity_id": i["activity_id"], "level": i["level"]} for i in interests]
    own["slots"] = list(available_slots)
