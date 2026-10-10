"""S03 部活検索画面（仕様 SP-19〜SP-23）。

やること:
  1. 条件の入力欄を出す（活動カテゴリ・拠点・曜日/時間帯・レベル・キーワード）
  2. 入力どおりに検索サービスへ聞く（検索ボタンは置かない。入力が変わるたびに画面が
     再実行されるので、その場で結果が変わる）
  3. 件数と、部活カードを3列で並べる。0件なら案内文を出す
  4. 操作履歴を記録する（記録するかどうかの判断は、サービスに任せる）

検索条件は st.session_state["club_search_conditions"] に覚えておく。
詳細画面から戻っても条件が消えないようにするため（SP-03）。
"""

import streamlit as st

from components import club_card

# 本物ができたら、次の 2 行を
#     from services import action_log_service, search_service
# に書き換える。ほかは変えなくてよい。
from mocks import action_log_service, search_service

# 選択肢は仕様.md 3.2 のとおり
CATEGORIES = ["スポーツ", "ゲーム", "ウェルネス", "文化・趣味"]
LOCATIONS = ["東京", "大阪"]
SLOTS = ["平日夜", "土曜午前", "土曜午後", "日曜"]
LEVELS = ["初心者歓迎", "レベル問わず", "経験者向け"]

COLUMNS = 3  # SP-21: カードは3列
EMPTY_MESSAGE = "条件に合う部活がありません。条件を減らして探してみてください"  # SP-22

# (入力欄の名前, 検索条件のキー, 表示ラベル, 選択肢)  ※検索条件のキーは I-F契約 1.2 のとおり
_MULTI_INPUTS = (
    ("club_search_categories", "categories", "活動カテゴリ", CATEGORIES),
    ("club_search_locations", "locations", "拠点", LOCATIONS),
    ("club_search_slots", "slots", "曜日・時間帯", SLOTS),
    ("club_search_levels", "levels", "レベル", LEVELS),
)
_KEYWORD_INPUT = "club_search_keyword"


def _restore_inputs(saved):
    """入力欄の初期値を、覚えておいた検索条件から戻す。

    Streamlit は、画面を離れた入力欄の値を忘れる。だから戻ってきたときに、
    覚えておいた条件を入力欄に入れ直す（すでに値があるときは何もしない）。
    """
    for key, condition_key, _label, _options in _MULTI_INPUTS:
        st.session_state.setdefault(key, saved.get(condition_key, []))
    st.session_state.setdefault(_KEYWORD_INPUT, saved.get("keyword", ""))


def _render_inputs():
    """入力欄を出し、入力された内容を検索条件の dict にして返す。選んでいない項目は入れない（SP-20）。"""
    conditions = {}
    for column, (key, condition_key, label, options) in zip(
        st.columns(len(_MULTI_INPUTS)), _MULTI_INPUTS
    ):
        selected = column.multiselect(label, options, key=key)
        if selected:
            conditions[condition_key] = selected
    keyword = st.text_input(
        "キーワード", key=_KEYWORD_INPUT, placeholder="部活名・活動名・ひとことで探す"
    ).strip()
    if keyword:
        conditions["keyword"] = keyword
    return conditions


def _render_results(clubs):
    if not clubs:
        st.info(EMPTY_MESSAGE)  # SP-22
        return
    st.write(f"{len(clubs)}件の部活が見つかりました")  # SP-21
    for start in range(0, len(clubs), COLUMNS):
        for column, club in zip(st.columns(COLUMNS), clubs[start : start + COLUMNS]):
            with column:
                club_card.render(club, key_prefix="club_search")


def render():
    st.title("部活を探す")

    _restore_inputs(st.session_state["club_search_conditions"])
    conditions = _render_inputs()
    st.session_state["club_search_conditions"] = conditions  # SP-03: 戻ってきても残す

    clubs = search_service.search_clubs(conditions)
    _render_results(clubs)

    # SP-23: 検索した、を数えるため、条件が空のとき（開いただけ）は記録しない。
    # 「前回と同じ条件か」の判断は、サービスがする（画面では判断しない）
    if conditions:
        action_log_service.record_search(st.session_state["employee_id"], conditions)
