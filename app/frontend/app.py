"""エントリポイント（設計.md D-01, D-02）。起動: streamlit run app/frontend/app.py

このファイルは「受付係」。やることは 2 つだけ。
  1. ログイン済みかを見る（employee_id があるか）
  2. 未ログインならログイン画面、ログイン済みなら current_page の画面を出す
画面の中身（表示や入力）は screens/<画面名>.py に任せる。
"""

import importlib

import streamlit as st

import state
from components import sidebar, theme
from services import auth_service, notification_service

st.set_page_config(page_title="部活コンシェルジュ", page_icon="📌", layout="wide")
theme.apply()  # 見た目（assets/style.css）を全画面に当てる


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


def _unread_count(employee_id, page):
    """未読件数。保持値を使い、取り直すのは SP-84① の契機だけ（設計 D-06）。

    取り直す契機：まだ取っていないとき（ログイン直後）／通知・メッセージ画面を開いているとき／
    既読化の直後（画面側が state.invalidate_unread() で保持値を捨てる）。
    """
    held = st.session_state["unread_count"]
    if held is None or page in (state.MESSAGES, state.NOTIFICATIONS):
        held = notification_service.count_unread(employee_id)
        st.session_state["unread_count"] = held
    return held


def _can_manage(employee_id):
    """「部活の管理」を出すか。ログイン後に1回取って保持し、幹事・メンバーの変更の直後だけ取り直す。"""
    held = st.session_state["can_manage"]
    if held is None:
        # 仕様 SP-01：「部活の管理」は幹事・運営者に出す。
        # 運営者は get_role、幹事（どこかの部活の担当）は is_organizer で判定する。
        held = (
            auth_service.get_role(employee_id) == auth_service.ROLE_ADMIN
            or auth_service.is_organizer(employee_id)
        )
        st.session_state["can_manage"] = held
    return held


def _render_sidebar(page):
    """ログイン中の人の情報を集めて、サイドバー（部品）に渡す。

    サイドバー本体は「表示だけ」の部品なので、名前・未読件数・権限は
    ここ（受付係）で集めてから渡す。未読件数と権限は session_state に保持し、
    再実行のたびには services に聞かない（設計 D-06、仕様 SP-84）。
    """
    employee_id = st.session_state["employee_id"]
    employee = state.current_employee()
    sidebar.render(
        name=employee.get("name", employee_id),
        dept=employee.get("dept", ""),
        employee_id=employee_id,
        unread_count=_unread_count(employee_id, page),
        can_manage=_can_manage(employee_id),
    )


def _scroll_to_top_on_page_change(page):
    """画面が切り替わった再実行のときだけ、本文のスクロールを先頭へ戻す。

    Streamlit は画面を切り替えても、ブラウザのスクロール位置をそのまま残す。
    下へスクロールした状態で別の画面（社員プロフィールなど）を開くと、
    新しい画面の途中から見えて見出しや名前が隠れてしまう。
    画面ごとに script の中身が変わるので、同じ画面での再実行では走らない。
    表示だけの処理で、DB には触れない（D-06/D-07/D-08 の往復回数は変わらない）。
    """
    if st.session_state.get("_scrolled_page") == page:
        return
    first_run = "_scrolled_page" not in st.session_state
    st.session_state["_scrolled_page"] = page
    if first_run:
        return  # 開いた直後は、もともと先頭にいる
    st.html(
        f"""<script>
        /* page={page} */
        (function () {{
          function top() {{
            var main = document.querySelector('[data-testid="stMain"]');
            if (main) main.scrollTo(0, 0);
            window.scrollTo(0, 0);
          }}
          top();
          setTimeout(top, 100);
        }})();
        </script>""",
        unsafe_allow_javascript=True,
    )


def main():
    state.init()

    page = state.LOGIN if not state.is_logged_in() else st.session_state["current_page"]

    _scroll_to_top_on_page_change(page)

    if state.is_logged_in():
        _render_sidebar(page)

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
