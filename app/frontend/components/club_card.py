"""部活カード（仕様 SP-21。ホーム SP-16・プロフィール SP-55 でも同じ形で使う）。

1つの部活を、決まった5行の形で見せる部品。
  1行目: アイコン＋部活名
  2行目: 拠点・いつもの活動時間
  3行目: 次回開催日
  4行目: 雰囲気タグ
  5行目: 費用と活動後の過ごし方
  下部 : 「詳しく見る」（押すと部活詳細へ）

表示だけを担当する。部活の情報は dict で渡してもらう。
"""

from datetime import date, datetime

import streamlit as st

import state

_WEEKDAYS = "月火水木金土日"


def _to_date(value):
    """date でも「2026-10-05」のような文字列でも、date にそろえる。無ければ None。

    DB から返る日付は文字列で、モックなどは date で渡ってくる。
    渡す側が何通りもあるので、変換はこのカード 1 か所にだけ置く。
    """
    if value is None or value == "":
        return None
    if isinstance(value, datetime):  # datetime は date の一種なので先に判定する
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)  # 形式が違えば ValueError（不正なデータは隠さない）


def format_date(value):
    """日付を「9/26（土）」の形にする（SP-07）。date / ISO 文字列 / None を受け付ける。"""
    day = _to_date(value)
    if day is None:
        return None
    return f"{day.month}/{day.day}（{_WEEKDAYS[day.weekday()]}）"


def render(club, *, key_prefix="club"):
    """部活カードを1枚描く。

    club : 次のキーをもつ dict
        club_id, icon, name, location, slot, mood_tags(list),
        fee, after_activity, next_event_date(date / 'YYYY-MM-DD' 文字列 / None)
    key_prefix : ボタンの識別名の頭につける文字。
        同じ部活が1画面に2回出ることがある（ホームの「今週」と「人気」など）。
        ボタンの名前が重なると Streamlit がエラーにするので、場所ごとに変える。
    """
    next_date = format_date(club.get("next_event_date"))
    tags = " ／ ".join(club.get("mood_tags") or [])

    with st.container(border=True):
        st.markdown(f"#### {club['icon']} {club['name']}")
        st.write(f"{club['location']}・{club['slot']}")
        st.write(f"次回開催：{next_date or '予定なし'}")
        if tags:
            st.caption(tags)
        st.write(f"費用：{club['fee']}　活動後：{club['after_activity']}")
        if st.button("詳しく見る", key=f"{key_prefix}_{club['club_id']}"):
            state.go(state.CLUB_DETAIL, club_id=club["club_id"])
