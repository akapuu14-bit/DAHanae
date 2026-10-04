"""S04 部活詳細画面（仕様 SP-24〜SP-32）。

上から順に、
  1. 見出し（← 戻る・アイコン＋部活名・雰囲気タグ・レベル・運営ルールの一文）  SP-24
  2. 基本情報・どんな部活？・参加の前に・活動後の過ごし方                    SP-25
  3. 開催一覧（今日以降）と、開催ごとの「申し込む」ボタン・申込フォーム        SP-26, 27, 29, 30, 31
  4. 幹事とメンバー                                                          SP-28
を並べる。情報はサービスからまとめて受け取り、この画面では「並べる」ことと
「申込ボタンの出し分け」だけをする。開いたときに閲覧履歴を記録する（SP-32）。
"""

import streamlit as st

import state
from components import club_card
from services.errors import ConflictError, NotFoundError

# 本物ができたら、次の 3 行を
#     from services import action_log_service, application_service, search_service
# に書き換える（get_club_detail は I-F契約への追加待ち）。ほかは変えなくてよい。
from mocks import action_log_service, application_service, search_service

# SP-04: 全部活共通の運営ルールの一文
RULE_NOTICE = "体験参加は入部ではありません／参加は毎回でなくてOK／活動後の集まりは任意です／キャンセルもできます"
MESSAGE_ALREADY_APPLIED = "すでに申し込み済みです"  # SP-31
MESSAGE_NOT_OPEN = "この開催には申し込みできません"  # SP-31
MESSAGE_NOT_FOUND = "この部活は見つかりませんでした"

_FORM_EVENT_KEY = "club_detail_form_event_id"  # 申込フォームを開いている開催
_CLUB_KEY = "club_detail_club_id"  # いま詳細を出している部活（切り替わったらフォームを閉じる）


# ---- 表示用の小さな整形 -------------------------------------------------------

def _hhmm(value):
    """時刻を「19:00」の形にする。"19:00:00" のような文字列でも time でも受ける。"""
    if hasattr(value, "strftime"):
        return value.strftime("%H:%M")
    return str(value)[:5]


def _minutes(value):
    hour, minute = _hhmm(value).split(":")
    return int(hour) * 60 + int(minute)


def _duration(start, end):
    """所要時間を「1時間30分」の形にする。"""
    total = _minutes(end) - _minutes(start)
    hours, minutes = divmod(total, 60)
    if hours and minutes:
        return f"{hours}時間{minutes}分"
    return f"{hours}時間" if hours else f"{minutes}分"


def _participant_label(participant):
    """参加者の表示。初参加に印、自分に「あなた」の印（SP-26）。"""
    label = participant["name"]
    if participant["is_first_time"]:
        label += " 🔰"
    if participant["is_self"]:
        label += "（あなた）"
    return label


# ---- 部品ごとの表示 ---------------------------------------------------------

def _render_missing():
    st.info(MESSAGE_NOT_FOUND)
    if st.button("← 戻る", key="club_detail_back_missing"):
        state.back()


def _render_header(club):
    if st.button("← 戻る", key="club_detail_back"):  # SP-02
        state.back()
    st.title(f"{club['icon']} {club['name']}")
    st.caption(f"{' ／ '.join(club['mood_tags'] or [])}　レベル：{club['level']}")
    st.info(RULE_NOTICE)  # SP-04


def _render_about(club, member_count):
    st.subheader("基本情報")
    schedule = club["slot"] + (f"（{club['schedule_note']}）" if club["schedule_note"] else "")
    for column, (label, value) in zip(
        st.columns(4),
        (("拠点", club["location"]), ("いつもの活動時間", schedule),
         ("頻度", club["frequency"]), ("メンバー数", f"{member_count}名")),
    ):
        column.caption(label)
        column.write(value)

    st.subheader("どんな部活？")
    st.write(club["message"] or "")
    st.write(f"社会人から始めた人：{club['fact_adult_starters']}")

    st.subheader("参加の前に")
    fee = club["fee"] + (f"（{club['fee_note']}）" if club["fee_note"] else "")
    st.write(f"費用：{fee}")
    st.write(f"持ち物：{_belongings(club)}")
    st.write(f"途中参加・途中で抜ける：{club['join_leave']}")

    st.subheader("活動後の過ごし方")
    st.write(club["after_activity"])


def _belongings(club):
    """「貸し出しあり／なし」＋持ち物の文章（SP-25）。"""
    text = f"貸し出し{club['rental']}"
    if club["belongings_note"]:
        text += f"／{club['belongings_note']}"
    return text


def _render_events(detail, employee_id):
    st.subheader("開催一覧")
    events = detail["events"]
    if not events:
        st.info("これからの開催予定はまだありません")
        return
    for event in events:
        _render_event(event, detail, employee_id)


def _render_event(event, detail, employee_id):
    with st.container(border=True):
        date_text = club_card.format_date(event["event_date"])
        st.markdown(
            f"**{date_text}　{_hhmm(event['start_time'])}〜{_hhmm(event['end_time'])}"
            f"（{_duration(event['start_time'], event['end_time'])}）**"
        )
        meeting = event["meeting_place"]
        if event.get("meeting_time"):
            meeting += f"　集合 {_hhmm(event['meeting_time'])}"
        st.write(f"集合：{meeting}")
        st.write(f"参加：{event['participant_count']}名（うち初参加 {event['first_timer_count']}名）")
        if event["participants"]:
            st.caption("参加者：" + "、".join(_participant_label(p) for p in event["participants"]))

        _render_action(event, detail, employee_id)


def _render_action(event, detail, employee_id):
    """開催の状態でボタンを出し分ける（SP-27）。"""
    if event["status"] != "予定":
        st.write("中止")  # ボタンなし
        return
    if event["my_application"] == "申込済み":
        st.write("✅ 申込済み")  # キャンセルはメッセージ画面から
        return
    if st.button("申し込む", key=f"club_detail_apply_{event['event_id']}"):
        st.session_state[_FORM_EVENT_KEY] = event["event_id"]
    if st.session_state.get(_FORM_EVENT_KEY) == event["event_id"]:
        _render_apply_form(event, detail, employee_id)


def _render_apply_form(event, detail, employee_id):
    """申込フォーム（SP-29, SP-30）。"""
    event_id = event["event_id"]
    with st.form(f"club_detail_form_{event_id}"):
        st.write(
            f"申し込む開催：{club_card.format_date(event['event_date'])}　"
            f"{_hhmm(event['start_time'])}〜　集合場所：{event['meeting_place']}"
        )
        st.caption(RULE_NOTICE)
        st.caption("キャンセルもできます")
        message = st.text_area("幹事への一言・質問（任意）", key=f"club_detail_message_{event_id}")
        submit_column, close_column = st.columns(2)
        submitted = submit_column.form_submit_button("この開催に申し込む", type="primary")
        closed = close_column.form_submit_button("やめる")

    if closed:
        st.session_state[_FORM_EVENT_KEY] = None
        st.rerun()
    if submitted:
        _submit_application(event, detail, employee_id, message.strip())


def _submit_application(event, detail, employee_id, message):
    try:
        result = application_service.apply(event["event_id"], employee_id, message or None)
    except ConflictError as error:  # SP-31: 理由で文言を出し分ける
        st.error(MESSAGE_ALREADY_APPLIED if error.reason == "already_applied" else MESSAGE_NOT_OPEN)
        return
    except NotFoundError:
        st.error(MESSAGE_NOT_OPEN)
        return

    club = detail["club"]
    # 申込完了画面(S05)に渡す内容。キー名は仮（S05 の担当と確認する）
    st.session_state["pending_application_context"] = {
        "application_id": result["application_id"],
        "is_first_time": result["is_first_time"],
        "club_name": club["name"],
        "organizer_name": detail["organizer"]["name"],
        "event_date": event["event_date"],
        "start_time": event["start_time"],
        "end_time": event["end_time"],
        "meeting_place": event["meeting_place"],
        "meeting_time": event.get("meeting_time"),
        "belongings": _belongings(club),
        "message_text": message,
    }
    st.session_state[_FORM_EVENT_KEY] = None
    state.go(state.APPLICATION_COMPLETE, event_id=event["event_id"])  # SP-30


def _render_people(detail):
    """幹事とメンバー（SP-28）。名前や「プロフィールを見る」を押すとS09へ。"""
    organizer = detail["organizer"]
    st.subheader("幹事")
    st.write(
        f"{organizer['name']}（{organizer['dept']}・{organizer['joined_year']}年入社・{organizer['entry_type']}）"
    )
    if st.button("プロフィールを見る", key="club_detail_organizer"):
        state.go(state.EMPLOYEE_PROFILE, employee_id=organizer["id"])

    with st.expander(f"メンバー（{detail['member_count']}名）"):
        for member in detail["members"]:
            if st.button(f"{member['name']}（{member['dept']}）", key=f"club_detail_member_{member['id']}"):
                state.go(state.EMPLOYEE_PROFILE, employee_id=member["id"])


def render():
    club_id = st.session_state["target_club_id"]
    employee_id = st.session_state["employee_id"]
    if club_id is None:
        _render_missing()
        return
    try:
        detail = search_service.get_club_detail(club_id, employee_id)
    except NotFoundError:
        _render_missing()
        return

    # 別の部活に移ってきたら、開きっぱなしの申込フォームは閉じる
    if st.session_state.get(_CLUB_KEY) != club_id:
        st.session_state[_CLUB_KEY] = club_id
        st.session_state[_FORM_EVENT_KEY] = None

    # SP-32: 開いたときに履歴を記録（連続して同じ部活なら記録しないのはサービスの役目）
    action_log_service.record_view_club(employee_id, club_id)

    _render_header(detail["club"])
    _render_about(detail["club"], detail["member_count"])
    _render_events(detail, employee_id)
    _render_people(detail)
