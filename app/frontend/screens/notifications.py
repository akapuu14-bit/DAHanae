"""S07 通知一覧画面（仕様 SP-44〜SP-46）。

自分あての通知を、新しい順に並べて見せる。
  - 未読は太字にする（SP-44）
  - 1件ごとに、種類・文章・日時を出す。「見る」で関係する画面へ移る（SP-45）
  - 画面を開いたときに、すべて既読にする（SP-46）
この画面では「並べる」「ボタンを受け取る」だけをして、既読にするなどの判断はサービスに任せる。
"""

from datetime import datetime, timedelta, timezone

import streamlit as st

import state
from services import notification_service

_JST = timezone(timedelta(hours=9))  # Windows には時間帯DBが無いので、固定の +9時間を使う

MESSAGE_EMPTY = "通知はまだありません。"

# 「見る」で移る画面。ここに無い種類（中止）は「見る」を出さない。
# 中止の通知は開催IDしか持たず、部活詳細へ移るための入口が service に無いため（画面から repository は呼ばない）。
_VIEW_TARGETS = {
    "申込": state.MESSAGES,
    "キャンセル": state.MESSAGES,
    "メッセージ": state.MESSAGES,
    "スタンプ": state.MESSAGES,
}


def _format_created_at(value):
    """通知の日時を「10/05 14:30」の形（日本時間）にする。文字列でも datetime でも受ける。"""
    moment = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    if moment.tzinfo is not None:
        moment = moment.astimezone(_JST)
    return moment.strftime("%m/%d %H:%M")


def _render_notification(notification):
    with st.container(border=True):
        text = f"【{notification['type']}】{notification['body']}"
        st.markdown(f"**{text}**" if notification["is_unread"] else text)  # SP-44
        st.caption(_format_created_at(notification["created_at"]))
        target = _VIEW_TARGETS.get(notification["type"])
        if target and st.button("見る", key=f"notification_view_{notification['id']}"):  # SP-45
            state.go(target)


def render():
    me = st.session_state["employee_id"]

    # 先に一覧を取ってから、既読にする（順番が大事）。先に既読にすると、未読の太字が消える。
    notifications = notification_service.list_notifications(me)
    if any(n["is_unread"] for n in notifications):  # 未読があるときだけ書き込む（再描画のたびに書かない）
        notification_service.mark_read_all(me)  # SP-46

    st.title("通知")
    if not notifications:
        st.info(MESSAGE_EMPTY)
        return
    for notification in notifications:
        _render_notification(notification)
