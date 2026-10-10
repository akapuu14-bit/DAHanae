"""サイドバー（仕様 SP-01）。画面の左に、ログイン中の人とメニューを出す。

このファイルは「表示だけ」を担当する。名前や未読件数は、呼び出す側が調べて渡す。
ここで DB やサービスを呼ばないのは、
  (1) DB につなぐ前でも部品を作って確かめられる
  (2) 渡す値を変えるだけで、いろいろな場合を試せる
ため。
"""

import streamlit as st

import state

# (表示名, 移動先の画面)。並びは SP-01 で決まっている順番どおり。
_MENU = (
    ("ホーム", state.HOME),
    ("部活を探す", state.CLUB_SEARCH),
    ("人を探す", state.EMPLOYEE_SEARCH),
    ("メッセージ", state.MESSAGES),
    ("通知", state.NOTIFICATIONS),
    ("自分のプロフィール", state.EMPLOYEE_PROFILE),
    ("部活の管理", state.CLUB_ADMIN),
)


def _label(label, page, unread_count):
    """メッセージだけ、未読が1件以上のときに件数をつける（0件のときは出さない）。"""
    if page == state.MESSAGES and unread_count > 0:
        return f"{label}（{unread_count}）"
    return label


def render(*, name, dept, employee_id, unread_count=0, can_manage=False):
    """サイドバーを描く。

    name / dept / employee_id : ログイン中の人の名前・部署・社員ID
    unread_count              : 未読件数（SP-70 の算出値をそのまま渡す）
    can_manage                : 幹事または運営者なら True（「部活の管理」を出すか）
    """
    current = st.session_state["current_page"]
    with st.sidebar:
        st.markdown(f"**{name}**")
        st.caption(f"{dept}／{employee_id}")

        for label, page in _MENU:
            if page == state.CLUB_ADMIN and not can_manage:
                continue
            pressed = st.button(
                _label(label, page, unread_count),
                key=f"sidebar_{page}",
                width="stretch",
                # いま開いている画面は色を変えて目立たせる
                type="primary" if page == current else "secondary",
            )
            if pressed:
                if page == state.EMPLOYEE_PROFILE:
                    # 「自分のプロフィール」は、表示する人を自分に書き換えてから移動する
                    # （書き換えないと、直前に見た他の人のIDが target_employee_id に残る）
                    state.go(page, employee_id=employee_id)
                else:
                    state.go(page)

        st.divider()
        if st.button("ログアウト", key="sidebar_logout", width="stretch"):
            state.logout()
            st.rerun()
