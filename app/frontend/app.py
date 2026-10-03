"""エントリポイント（設計.md D-01, D-02）。起動: streamlit run app/frontend/app.py

このファイルは「受付係」。やることは 2 つだけ。
  1. ログイン済みかを見る（employee_id があるか）
  2. 未ログインならログイン画面、ログイン済みなら current_page の画面を出す
画面の中身（表示や入力）は screens/<画面名>.py に任せる。
"""

import importlib

import streamlit as st

import state
from components import sidebar
from services import auth_service, notification_service

st.set_page_config(page_title="部活コンシェルジュ", page_icon="📌", layout="wide")


def _load_screen(page):
    """screens/<page>.py を読み込む。まだ無い画面なら None を返す。

    画面は T-F05 以降で 1 枚ずつ作るので、未作成のものがあっても
    アプリ全体が落ちないよう、ここで受ける。
    """
    module_name = f"screens.{page}"
    try:
        return importlib.import_module(module_name)
    except ModuleNotFoundError as error:
        # 画面ファイル(または screens フォルダ)自体が無いときだけ受ける。
        # 画面の中の import ミスは隠さず、そのままエラーにする。
        if error.name in (module_name, "screens"):
            return None
        raise


def _render_sidebar():
    """ログイン中の人の情報を集めて、サイドバー（部品）に渡す。

    サイドバー本体は「表示だけ」の部品なので、名前・未読件数・権限は
    ここ（受付係）で services に聞いてから渡す。
    """
    employee_id = st.session_state["employee_id"]
    employee = state.current_employee()
    sidebar.render(
        name=employee.get("name", employee_id),
        dept=employee.get("dept", ""),
        employee_id=employee_id,
        unread_count=notification_service.count_unread(employee_id),
        # 仕様 SP-01 は「幹事・運営者」。いまの get_role(社員ID) だけでは
        # 幹事を判定できないため、運営者(admin)のみ。幹事の判定は契約の確定待ち。
        can_manage=auth_service.get_role(employee_id) == auth_service.ROLE_ADMIN,
    )


def main():
    state.init()

    page = state.LOGIN if not state.is_logged_in() else st.session_state["current_page"]

    if state.is_logged_in():
        _render_sidebar()

    screen = _load_screen(page)
    if screen is None:
        st.info(f"画面「{page}」はまだ実装されていません。")
        if state.is_logged_in() and page != state.HOME:
            if st.button("ホームへ戻る"):
                state.go(state.HOME)
        return

    # 約束: 各画面は引数なしの render() を持つ。
    screen.render()


main()
