"""S01 ログイン画面（仕様 SP-09〜SP-12）。

このファイルの仕事は「入力欄を出して、押されたら確かめを頼み、結果に応じて画面を変える」こと。
社員IDとパスワードが正しいかどうかの判断は、自分ではしない（認証サービスの仕事）。
"""

import streamlit as st

import state

# 本物の auth_service ができたら、次の 1 行を
#     from services import auth_service
# に書き換える。ほかは変えなくてよい。
from mocks import auth_service
from services.errors import AuthenticationError

APP_NAME = "部活コンシェルジュ"
# ひとこと説明の文言は仕様に決まりがない。仮置き（企画書の中心価値を短くしたもの）。
TAGLINE = "自分に合う部活を見つけて、体験参加まで。"
ERROR_MESSAGE = "社員IDかパスワードが違います。入力内容を確認してください"  # SP-11
DEMO_NOTE = "デモ用：社員ID E001〜E500／パスワードは共有のもの"  # SP-12


def render():
    # 画面の真ん中に細めに置く（左右の余白の列を作る）
    _, center, _ = st.columns([1, 2, 1])
    with center:
        st.title(APP_NAME)  # SP-09
        st.write(TAGLINE)  # SP-09

        with st.form("login_form"):
            employee_id = st.text_input("社員ID")
            password = st.text_input("パスワード", type="password")
            submitted = st.form_submit_button("ログインする")  # SP-10

        if submitted:
            try:
                employee = auth_service.login(employee_id, password)
            except AuthenticationError:
                st.error(ERROR_MESSAGE)  # SP-11
            else:
                # 入力どおり（e001）ではなく、サービスが返した正式なID（E001）を記録する
                state.login(employee["id"], employee)
                st.rerun()

        st.caption(DEMO_NOTE)  # SP-12
