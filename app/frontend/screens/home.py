"""S02 ホーム画面（仕様 SP-14〜SP-18）。ログイン後に最初に出る画面。

上から順に、
  1. 見出しとあいさつ（SP-14）
  2. 「部活を探す」「人を探す」の大きなボタン（SP-15）
  3. 今週開催の部活（SP-16）
  4. 今月の人気部活（SP-17）
  5. あなたにおすすめ（SP-18。初心者向け/経験者向けの切り替えつき）
を並べる。部活の情報は検索サービスから受け取り、このファイルでは「並べるだけ」にする。
"""

import streamlit as st

import state
from components import club_card

# 本物の search_service ができたら、次の 1 行を
#     from services import search_service
# に書き換える（関数名の確認は、だーあさ待ち）。
from mocks import search_service

APP_NAME = "部活コンシェルジュ"
WEEK_MAX = 4  # SP-16: 最大4件
POPULAR_MAX = 3  # SP-17: 上位3件

# 仕様に文言が無いので仮置き（SP-15 の「一行の説明」）
EXPLAIN_CLUB = "活動・拠点・曜日などの条件から、自分に合う部活を探せます。"
EXPLAIN_PEOPLE = "名前や部署、興味から、社内の仲間を探せます。"

EMPTY_WEEK = "今週開催予定の部活はまだありません"  # SP-16
EMPTY_POPULAR = "今月はまだ人気部活のデータがありません"  # SP-17（仕様の例文）
EMPTY_RECOMMEND = "今はおすすめできる部活がありません"  # SP-18（仕様の例文）

# 切り替えの選択肢と、それぞれに含める部活のレベル（仕様の読み替え。要確認）
LEVEL_FILTERS = {
    "初心者向け": {"初心者歓迎", "レベル問わず"},
    "経験者向け": {"経験者向け", "レベル問わず"},
}


def _render_week():
    st.subheader("今週開催の部活")
    clubs = search_service.get_this_week_clubs()[:WEEK_MAX]
    if not clubs:
        st.info(EMPTY_WEEK)
        return
    for column, club in zip(st.columns(WEEK_MAX), clubs):
        with column:
            club_card.render(club, key_prefix="home_week")


def _render_popular():
    st.subheader("今月の人気部活")
    clubs = search_service.get_popular_clubs()[:POPULAR_MAX]
    if not clubs:
        st.info(EMPTY_POPULAR)
        return
    for rank, club in enumerate(clubs, start=1):
        name_column, button_column = st.columns([4, 1])
        name_column.write(f"{rank}位　{club['icon']} {club['name']}")
        if button_column.button("見る", key=f"home_popular_{club['club_id']}"):
            state.go(state.CLUB_DETAIL, club_id=club["club_id"])


def _render_recommend(employee_id):
    st.subheader("あなたにおすすめ")
    choice = st.radio(
        "表示する部活", list(LEVEL_FILTERS), horizontal=True, key="home_level_filter"
    )
    clubs = [
        club
        for club in search_service.get_recommendations(employee_id)
        if club["level"] in LEVEL_FILTERS[choice]
    ]
    if not clubs:
        st.info(EMPTY_RECOMMEND)
        return
    for column, club in zip(st.columns(3), clubs[:3]):
        with column:
            club_card.render(club, key_prefix="home_recommend")
            st.caption(f"一致度 {club['score']}点｜{club['reason']}")


def render():
    employee_id = st.session_state["employee_id"]
    name = state.current_employee().get("name", employee_id)

    st.title(APP_NAME)  # SP-14
    st.write(f"{name}さん、こんにちは。")  # SP-14

    # SP-15: 大きなボタン2つ
    club_column, people_column = st.columns(2)
    with club_column:
        st.write(EXPLAIN_CLUB)
        if st.button("部活を探す", key="home_to_club_search", type="primary", width="stretch"):
            state.go(state.CLUB_SEARCH)
    with people_column:
        st.write(EXPLAIN_PEOPLE)
        if st.button("人を探す", key="home_to_employee_search", type="primary", width="stretch"):
            state.go(state.EMPLOYEE_SEARCH)

    _render_week()  # SP-16
    _render_popular()  # SP-17
    _render_recommend(employee_id)  # SP-18
