"""S05 申込完了画面（仕様 SP-33〜SP-34）。

申込が成功した直後だけ出る画面。次の順に表示する（SP-33）。
  ① 完了の一言
  ② 申込内容（部活名・開催日時・送った一言）
  ③ 次に起きること
  ④ 当日の情報（日時・集合場所・集合時刻・持ち物）
  ⑤ 運営ルールの一文＋キャンセルはメッセージ画面からできる旨
  ⑥ 次の行動ボタン（「メッセージを見る」→S06、「ほかの部活も見る」→S03）

表示する内容は、部活詳細（S04）が申込のあとに session_state["pending_application_context"]
へ入れておく。この画面は service を呼ばない。
申込直後以外（再読み込みなどで内容がない）に開かれたら、ホームへ移る（SP-34）。
"""

import streamlit as st

import state
from components import club_card, rule_notice

_CONTEXT_KEY = "pending_application_context"


def _hhmm(value):
    """時刻を「19:00」の形にする。"19:00:00" のような文字列でも time でも受ける。"""
    if hasattr(value, "strftime"):
        return value.strftime("%H:%M")
    return str(value)[:5]


def _event_label(context):
    """開催日時を「10/9（金）19:00〜20:00」の形にする。終了時刻がなければ開始のみ。"""
    label = f"{club_card.format_date(context['event_date'])} {_hhmm(context['start_time'])}〜"
    if context.get("end_time"):
        label += _hhmm(context["end_time"])
    return label


def _leave(page):
    """次の画面へ移る。申込直後の内容は、ここで消す（SP-34）。"""
    st.session_state[_CONTEXT_KEY] = None
    state.go(page)


def render():
    context = st.session_state.get(_CONTEXT_KEY)
    if not context:
        state.go(state.HOME)  # SP-34
        return

    st.title("申込が完了しました")

    # ① 完了の一言
    st.success(f"申し込みました！幹事の{context['organizer_name']}さんに届いています")

    # ② 申込内容
    st.subheader("申込内容")
    st.write(f"部活：{context['club_name']}")
    st.write(f"開催日時：{_event_label(context)}")
    st.write(f"送った一言：{context.get('message_text') or '（なし）'}")

    # ③ 次に起きること
    st.subheader("次に起きること")
    st.write("幹事から返信があると、メッセージに届きます")

    # ④ 当日の情報
    st.subheader("当日の情報")
    st.write(f"日時：{_event_label(context)}")
    st.write(f"集合場所：{context['meeting_place']}")
    if context.get("meeting_time"):  # 空のときは行ごと出さない
        st.write(f"集合時刻：{_hhmm(context['meeting_time'])}")
    st.write(f"持ち物：{context['belongings']}")

    # ⑤ 運営ルールの一文＋キャンセルの案内
    rule_notice.render()
    st.caption("キャンセルは、メッセージ画面からできます")

    # ⑥ 次の行動
    messages_column, search_column = st.columns(2)
    if messages_column.button("メッセージを見る", type="primary", key="application_complete_messages"):
        _leave(state.MESSAGES)
    if search_column.button("ほかの部活も見る", key="application_complete_search"):
        _leave(state.CLUB_SEARCH)
