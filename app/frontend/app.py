"""エントリポイント（設計.md D-01, D-02）。起動: streamlit run app/frontend/app.py

このファイルは「受付係」。やることは 2 つだけ。
  1. ログイン済みかを見る（employee_id があるか）
  2. 未ログインならログイン画面、ログイン済みなら current_page の画面を出す
画面の中身（表示や入力）は screens/<画面名>.py に任せる。
"""

import importlib

import streamlit as st

import state

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


def main():
    state.init()

    page = state.LOGIN if not state.is_logged_in() else st.session_state["current_page"]

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
