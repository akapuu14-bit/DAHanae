"""S06 メッセージ画面（仕様 SP-35〜SP-42）。

タブは 2 つ。
  - 自分の申込   … 自分が出した申込。やり取り・キャンセルができる（SP-37〜39）
  - 届いた申込   … 自分が幹事の部活に届いた申込（幹事だけに出る）。やり取り・「確認したよ」（SP-40〜41）
開いた時点で、自分あての関連通知を既読にする（SP-36）。
この画面では「並べる」「入力を受け取る」だけをして、送信・キャンセルなどの判断はサービスに任せる。
"""

from datetime import datetime, timedelta, timezone

import streamlit as st

from services.errors import ConflictError, NotFoundError, PermissionDeniedError, ValidationError

# 本物のサービスを使う（mocks/ の仮実装から差し替え済み）
from services import application_service, auth_service, notification_service

_JST = timezone(timedelta(hours=9))  # Windows には時間帯DBが無いので、固定の +9時間を使う

TAB_MINE = "自分の申込"
TAB_RECEIVED = "届いた申込"
STATUS_APPLIED = "申込済み"
STATUS_CANCELED = "キャンセル"

MESSAGE_EMPTY_MINE = "まだ申込はありません。部活を探して、気になる開催に申し込んでみましょう。"  # SP-42
MESSAGE_EMPTY_RECEIVED = "まだ申込は届いていません。"  # SP-42
MESSAGE_EMPTY_BODY = "メッセージを入力してから送信してください"
MESSAGE_VIEW_ONLY = "キャンセル済みのため、やり取りは閲覧のみです"
MESSAGE_CANCEL_FAILED = "この申込はキャンセルできません（すでに開始済み、またはキャンセル済みです）"
MESSAGE_ALREADY_CONFIRMED = "すでに確認済みです"
MESSAGE_SEND_FAILED = "送信できませんでした。もう一度お試しください"
MESSAGE_NO_MESSAGES = "まだやり取りはありません"

_CANCEL_TARGET_KEY = "messages_cancel_target"  # キャンセルの確認中の申込ID


# ---- 表示用の小さな整形 -------------------------------------------------------

def _hhmm(value):
    if hasattr(value, "strftime"):
        return value.strftime("%H:%M")
    return str(value)[:5]


def _to_date(value):
    if hasattr(value, "year") and not isinstance(value, str):
        return value.date() if isinstance(value, datetime) else value
    return datetime.fromisoformat(str(value)).date()


def _format_event(event):
    """開催の日時を「10/12(月) 19:00〜20:30」の形にする。"""
    day = _to_date(event["event_date"])
    weekday = "月火水木金土日"[day.weekday()]
    return f"{day.month}/{day.day}({weekday}) {_hhmm(event['start_time'])}〜{_hhmm(event['end_time'])}"


def _start_datetime(event):
    day = _to_date(event["event_date"])
    hh, mm = _hhmm(event["start_time"]).split(":")
    return datetime(day.year, day.month, day.day, int(hh), int(mm), tzinfo=_JST)


def _format_sent_at(value):
    """送信日時を「10/05 14:30」の形（日本時間）にする。文字列でも datetime でも受ける。"""
    moment = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    if moment.tzinfo is not None:
        moment = moment.astimezone(_JST)
    return moment.strftime("%m/%d %H:%M")


def _can_cancel(application):
    return application["status"] == STATUS_APPLIED and _start_datetime(application["events"]) > datetime.now(_JST)


# ---- やり取り（両タブ共通）----------------------------------------------------

def _render_thread(application, me, other_name, mode):
    """やり取りの一覧と送信フォーム。キャンセル済みは閲覧のみ（SP-39）。"""
    messages = application["messages"]
    with st.expander(f"やり取り（{len(messages)}件）", expanded=bool(messages)):
        if not messages:
            st.caption(MESSAGE_NO_MESSAGES)
        for message in messages:  # 古い順
            who = "あなた" if message["sender_id"] == me else other_name
            st.markdown(f"**{who}**　<small>{_format_sent_at(message['sent_at'])}</small>", unsafe_allow_html=True)
            st.text(message["body"])

        if application["status"] == STATUS_CANCELED:
            st.caption(MESSAGE_VIEW_ONLY)
            return

        with st.form(f"messages_form_{mode}_{application['id']}", clear_on_submit=True):
            body = st.text_area("メッセージ", key=f"messages_body_{mode}_{application['id']}", label_visibility="collapsed",
                                placeholder="メッセージを入力")
            submitted = st.form_submit_button("送信する")
        if submitted:
            if not (body or "").strip():
                st.warning(MESSAGE_EMPTY_BODY)
                return
            try:
                application_service.send_message(application["id"], me, body)
            except (ValidationError, ConflictError, NotFoundError, PermissionDeniedError):
                st.error(MESSAGE_SEND_FAILED)
                return
            st.rerun()


# ---- 自分の申込タブ -----------------------------------------------------------

def _render_cancel(application, me):
    if not _can_cancel(application):
        return
    pending = st.session_state.get(_CANCEL_TARGET_KEY) == application["id"]
    if not pending:
        if st.button("この申込をキャンセルする", key=f"messages_cancel_open_{application['id']}"):
            st.session_state[_CANCEL_TARGET_KEY] = application["id"]
            st.rerun()
        return
    st.warning("この開催の申込をキャンセルしますか？")
    left, right = st.columns(2)
    if left.button("キャンセルする", key=f"messages_cancel_do_{application['id']}", type="primary"):
        st.session_state.pop(_CANCEL_TARGET_KEY, None)
        try:
            application_service.cancel(application["id"], me)
        except (ConflictError, NotFoundError, PermissionDeniedError):
            st.error(MESSAGE_CANCEL_FAILED)
            return
        st.rerun()
    if right.button("やめる", key=f"messages_cancel_stop_{application['id']}"):
        st.session_state.pop(_CANCEL_TARGET_KEY, None)
        st.rerun()


def _render_mine(me, applications):
    if not applications:
        st.info(MESSAGE_EMPTY_MINE)
        return
    for application in applications:
        event = application["events"]
        club = event["clubs"]
        organizer = application.get("organizer") or {}
        with st.container(border=True):
            st.subheader(f"{club.get('icon', '')} {club['name']}".strip())
            st.write(f"{_format_event(event)}　／　{event['meeting_place']}")
            st.caption(f"幹事：{organizer.get('name', '—')}　／　状態：{application['status']}")
            if application["status"] == STATUS_APPLIED and application.get("confirmed_at"):
                st.success("✅ 幹事が確認しました")
            _render_thread(application, me, organizer.get("name", "幹事"), "mine")
            _render_cancel(application, me)


# ---- 届いた申込タブ -----------------------------------------------------------

def _render_stamp(application, me):
    if application["status"] != STATUS_APPLIED or not application["is_first_time"]:
        return
    if application.get("confirmed_at"):
        st.caption("✅ 確認済み")
        return
    if st.button("確認したよ👍", key=f"messages_stamp_{application['id']}"):
        try:
            application_service.confirm_stamp(application["id"], me)
        except ConflictError:
            st.info(MESSAGE_ALREADY_CONFIRMED)
            return
        except (NotFoundError, PermissionDeniedError):
            st.error(MESSAGE_SEND_FAILED)
            return
        st.rerun()


def _render_received(me, applications):
    if not applications:
        st.info(MESSAGE_EMPTY_RECEIVED)
        return
    for application in applications:
        event = application["events"]
        club = event["clubs"]
        applicant = application["employees"]
        with st.container(border=True):
            badge = " 🔰初参加" if application["is_first_time"] else ""
            st.subheader(f"{applicant['name']}{badge}")
            st.write(f"{club['name']}　／　{_format_event(event)}")
            st.caption(f"{applicant.get('dept', '')}・{applicant.get('entry_type', '')}　／　状態：{application['status']}")
            _render_stamp(application, me)
            _render_thread(application, me, applicant["name"], "received")


# ---- 画面の入口 ---------------------------------------------------------------

def render():
    me = st.session_state["employee_id"]
    is_organizer = auth_service.is_organizer(me)

    # 先に一覧を取ってから、既読にする（順番が大事）。
    # 一覧は「未読の通知がある申込を先頭に」並べる作り（SP-40）。先に既読にすると、その並びが効かなくなる。
    mine = application_service.list_my_applications(me)
    received = application_service.list_received_applications(me) if is_organizer else []
    notification_service.mark_read_for_messages_screen(me)  # SP-36

    st.title("メッセージ")
    if is_organizer:
        tab_mine, tab_received = st.tabs([TAB_MINE, TAB_RECEIVED])
        with tab_mine:
            _render_mine(me, mine)
        with tab_received:
            _render_received(me, received)
    else:
        _render_mine(me, mine)
