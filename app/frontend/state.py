"""session_state のキー定義とヘルパー（設計.md 4章 / D-02, D-03, D-04, D-05）。

Streamlit は画面を操作するたびにスクリプトを最初から再実行する。
そのため「いまログインしているのは誰か」「どの画面を開いているか」は、
再実行をまたいで残る st.session_state に置く。

このファイルは、そのキーの名前と初期値を 1 か所にまとめる。
画面側は st.session_state["..."] を直接書かず、ここの関数を使う。
"""

import streamlit as st

# 画面の識別子（設計.md 1.1 の screens/ のファイル名と同じ）。
LOGIN = "login"
HOME = "home"
CLUB_SEARCH = "club_search"
CLUB_DETAIL = "club_detail"
APPLICATION_COMPLETE = "application_complete"
MESSAGES = "messages"
NOTIFICATIONS = "notifications"
EMPLOYEE_SEARCH = "employee_search"
EMPLOYEE_PROFILE = "employee_profile"
CLUB_ADMIN = "club_admin"

PAGES = (
    LOGIN,
    HOME,
    CLUB_SEARCH,
    CLUB_DETAIL,
    APPLICATION_COMPLETE,
    MESSAGES,
    NOTIFICATIONS,
    EMPLOYEE_SEARCH,
    EMPLOYEE_PROFILE,
    CLUB_ADMIN,
)

# 設計.md 4章のキー一覧。値は「初期値を作る関数」にしている。
# list や dict をそのまま初期値にすると、全員が同じ 1 個を共有してしまうため。
_DEFAULTS = {
    "employee_id": lambda: None,  # ログイン中の社員ID。None なら未ログイン
    "current_page": lambda: HOME,  # いま表示する画面
    "page_history": list,  # 「← 戻る」用の、前に見ていた画面の積み重ね
    "club_search_conditions": dict,  # 部活検索の条件（詳細から戻っても残す）
    "employee_search_conditions": dict,  # 社員検索の条件（同上）
    "target_club_id": lambda: None,  # 画面間で受け渡す対象ID
    "target_event_id": lambda: None,
    "target_application_id": lambda: None,
    "unread_count": lambda: 0,  # サイドバーに出す未読件数
    "pending_application_context": lambda: None,  # 申込完了画面(S05)に渡す直前の申込内容
}


def init():
    """キーが無いときだけ初期値を入れる。既にある値は上書きしない。

    app.py の先頭で毎回呼ぶ。再実行のたびに呼んでも、ログイン状態などは消えない。
    """
    for key, make_default in _DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = make_default()


def is_logged_in():
    """ログイン済みか。employee_id があるかどうかだけで判定する（設計 D-01）。"""
    return st.session_state.get("employee_id") is not None


def login(employee_id):
    """ログイン成功後に呼ぶ。社員IDを記録し、ホームから始める（SP-10）。"""
    st.session_state["employee_id"] = employee_id
    st.session_state["current_page"] = HOME
    st.session_state["page_history"] = []


def logout():
    """ログイン情報を消してログイン画面に戻る（SP-13）。

    前の人の検索条件や対象IDが次の人に見えないよう、全キーを消して作り直す。
    """
    for key in _DEFAULTS:
        st.session_state.pop(key, None)
    init()


def go(page, *, club_id=None, event_id=None, application_id=None):
    """別の画面へ移る（設計 D-02, D-03, D-05）。

    いまの画面を page_history に積んでから current_page を書き換え、再描画する。
    club_id などを渡すと、移動先の画面が読む target_* に入れる。
    ボタンの if の中で呼ぶこと（on_click コールバックの中では st.rerun が効かない）。
    """
    if page not in PAGES:
        raise ValueError(f"未定義の画面です: {page}")
    current = st.session_state["current_page"]
    if page != current:
        st.session_state["page_history"].append(current)
        st.session_state["current_page"] = page
    if club_id is not None:
        st.session_state["target_club_id"] = club_id
    if event_id is not None:
        st.session_state["target_event_id"] = event_id
    if application_id is not None:
        st.session_state["target_application_id"] = application_id
    st.rerun()


def back():
    """「← 戻る」。直前に見ていた画面に戻る（SP-02）。履歴が空ならホームへ。"""
    history = st.session_state["page_history"]
    st.session_state["current_page"] = history.pop() if history else HOME
    st.rerun()
