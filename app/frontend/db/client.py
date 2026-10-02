"""Supabaseクライアントの共有インスタンス。

各 repository は、このモジュールのモジュールレベル変数 ``supabase`` を
同じ名前で import して共有する（import 根は ``app/frontend/`` なので
``from db.client import supabase``）。9本の repository を複数人で実装するため、
呼び名を ``supabase`` に統一し、ずれを防ぐ（I-F契約.md 0.1）。
Streamlit は毎回スクリプトを再実行するが、この変数はモジュールレベルで
一度だけ生成されるため、全 repository で同一インスタンスを共有する。
"""

import streamlit as st
from supabase import Client, create_client


supabase: Client = create_client(
    st.secrets["supabase_url"],
    st.secrets["supabase_key"],
)
