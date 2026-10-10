"""S08 社員検索画面（仕様 SP-47〜SP-52）。

やること:
  1. 上部に「公開にしたものだけが検索・表示されます」の注意を出す（SP-47）
  2. 条件の入力欄を出す（名前・部署・拠点・興味・所属部活・参加可能時間）（SP-48）
     検索ボタンは置かない。入力が変わるたびに画面が再実行されるので、その場で結果が変わる
  3. 「n名見つかりました」と、社員カードを3列で並べる。0人なら案内文（SP-50, SP-52）
  4. 20件ずつ表示し、「もっと見る」で20件ずつ増やす（SP-51）
  5. 「プロフィールを見る」で、その人のプロフィール画面へ（SP-50）
「非公開の人を結果に出さない」「非公開の項目の値を渡さない」判断はサービスがしている。
この画面は、渡された値と「公開の状態」を見て、文言を出すだけ。
検索条件は st.session_state["employee_search_conditions"] に覚えておく（プロフィールから戻っても残すため）。
"""

import streamlit as st

import state

# 本物ができたら、次の 2 行を
#     from services import search_service
# に書き換える。search_employees は本物があるのでそのまま使える。
# list_departments / list_activities は I-F契約への追加待ち（依頼中）。
from mocks import search_service

NOTICE = "興味・経験と参加可能時間は、本人が公開にしたものだけが検索・表示されます"  # SP-47
EMPTY_MESSAGE = "条件に合う人がいません。条件を減らして探してみてください"  # SP-52
PRIVATE_TEXT = "非公開"
SELF_PRIVATE_NOTE = "（他の人には非公開）"
PAGE_SIZE = 20  # SP-51
COLUMNS = 3
LOCATIONS = ["東京", "大阪"]
SLOTS = ["平日夜", "土曜午前", "土曜午後", "日曜"]
NO_CLUB = None  # 所属部活の「指定なし」

_LIMIT_KEY = "employee_search_limit"  # いま表示する件数（もっと見るで増える）
_NAME_KEY = "employee_search_name"
_MULTI_KEYS = {  # 検索条件のキー -> 入力欄の名前
    "depts": "employee_search_depts",
    "locations": "employee_search_locations",
    "interests": "employee_search_interests",
    "slots": "employee_search_slots",
}
_CLUB_KEY = "employee_search_club"


def _restore_inputs(saved):
    """入力欄の初期値を、覚えておいた検索条件から戻す（すでに値があるときは何もしない）。"""
    st.session_state.setdefault(_NAME_KEY, saved.get("name", ""))
    for condition_key, key in _MULTI_KEYS.items():
        st.session_state.setdefault(key, saved.get(condition_key, []))
    st.session_state.setdefault(_CLUB_KEY, saved.get("club_id", NO_CLUB))


def _render_inputs():
    """入力欄を出し、入力された内容を検索条件の dict にして返す。選んでいない項目は入れない。"""
    conditions = {}
    activities = search_service.list_activities()
    activity_names = {a["id"]: a["name"] for a in activities}
    clubs = search_service.search_clubs({})
    club_names = {c["club_id"]: c["name"] for c in clubs}

    name = st.text_input("名前", key=_NAME_KEY, placeholder="名前で探す（スペースは無視）").strip()
    if name:
        conditions["name"] = name

    columns = st.columns(5)
    depts = columns[0].multiselect("部署", search_service.list_departments(), key=_MULTI_KEYS["depts"])
    locations = columns[1].multiselect("拠点", LOCATIONS, key=_MULTI_KEYS["locations"])
    interests = columns[2].multiselect("興味・活動", list(activity_names), key=_MULTI_KEYS["interests"],
                                       format_func=lambda activity_id: activity_names[activity_id])
    slots = columns[3].multiselect("参加可能時間", SLOTS, key=_MULTI_KEYS["slots"])
    club_id = columns[4].selectbox("所属部活", [NO_CLUB] + list(club_names), key=_CLUB_KEY,
                                   format_func=lambda value: "指定なし" if value is NO_CLUB else club_names[value])
    for condition_key, selected in (("depts", depts), ("locations", locations), ("interests", interests), ("slots", slots)):
        if selected:
            conditions[condition_key] = selected
    if club_id is not NO_CLUB:
        conditions["club_id"] = club_id
    return conditions


def _interests_text(employee):
    """興味の表示。公開の状態（visibility）を見て、文言を出す。"""
    visibility = employee["interests_visibility"]
    if visibility == "hidden":
        return PRIVATE_TEXT
    items = employee["interests"] or []
    text = "、".join(f"{i['activity_name']}（{i['level']}）" for i in items) or "未登録"
    return text + (SELF_PRIVATE_NOTE if visibility == "self_private" else "")


def _render_card(employee):
    with st.container(border=True):
        st.markdown(f"#### {employee['name']}")
        st.write(f"{employee['dept']}・{employee['location']}・{employee['joined_year']}年入社・{employee['entry_type']}")
        st.write(f"興味：{_interests_text(employee)}")
        clubs = "、".join(c["name"] for c in employee["clubs"]) or "なし"
        st.write(f"所属部活：{clubs}")
        if st.button("プロフィールを見る", key=f"employee_search_profile_{employee['id']}"):
            state.go(state.EMPLOYEE_PROFILE, employee_id=employee["id"])


def _render_results(employees, total):
    if total == 0:
        st.info(EMPTY_MESSAGE)  # SP-52
        return
    st.write(f"{total}名見つかりました")  # SP-50
    for start in range(0, len(employees), COLUMNS):
        for column, employee in zip(st.columns(COLUMNS), employees[start : start + COLUMNS]):
            with column:
                _render_card(employee)
    if len(employees) < total:  # SP-51
        if st.button("もっと見る", key="employee_search_more"):
            st.session_state[_LIMIT_KEY] += PAGE_SIZE
            st.rerun()


def render():
    st.title("人を探す")
    st.info(NOTICE)  # SP-47
    saved = st.session_state["employee_search_conditions"]
    _restore_inputs(saved)
    conditions = _render_inputs()
    if conditions != saved:  # 条件が変わったら、表示件数を最初の20件に戻す
        st.session_state[_LIMIT_KEY] = PAGE_SIZE
    st.session_state["employee_search_conditions"] = conditions  # プロフィールから戻っても残す
    st.session_state.setdefault(_LIMIT_KEY, PAGE_SIZE)

    employees, total = search_service.search_employees(
        conditions, st.session_state["employee_id"], limit=st.session_state[_LIMIT_KEY], offset=0
    )
    _render_results(employees, total)
