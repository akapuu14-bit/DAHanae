"""見た目（CSS）を読み込む部品。

assets/style.css を 1 回だけ読み込んで、画面全体に当てる。
見た目の定義はすべて style.css にあり、ここは読み込むだけ。
"""

from pathlib import Path

import streamlit as st

_CSS_PATH = Path(__file__).resolve().parents[1] / "assets" / "style.css"


def apply():
    """app.py の st.set_page_config の直後で 1 回呼ぶ。"""
    st.html(f"<style>{_CSS_PATH.read_text(encoding='utf-8')}</style>")
