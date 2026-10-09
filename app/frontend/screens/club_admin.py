"""S10 部活・開催の管理画面（仕様 SP-58〜SP-62）。

幹事は担当の部活、運営者はすべての部活を選んで管理する。運営者には「部活を新しく作る」ボタンも出す。
タブは 3 つ：「部活情報」（SP-59）／「開催」（SP-60, SP-61）／「メンバー」（SP-62, Should）。
「誰が何を変えられるか」「入力が正しいか」の最終判断は、すべてサービスがする。
この画面がやるのは、入力欄を並べることと、必須が空のときに先に知らせること（親切）、
サービスが返したエラーを、仕様どおりの文言にして出すこと。
"""

from datetime import datetime, time, timedelta, timezone

import streamlit as st

import state
from services.errors import AppError, ConflictError, NotFoundError, PermissionDeniedError, ValidationError

# 本物ができたら、次の 3 行を
#     from services import auth_service, club_admin_service, search_service
# に書き換える。ただし club_admin_service は I-F契約への追加待ち（依頼予定）。
from mocks import auth_service, club_admin_service, search_service

# 選択肢（仕様.md 3.2）。サービスの契約には定数が無いので、画面が持つ（選択肢の最終チェックはサービスがする）
LOCATIONS = ["東京", "大阪"]
SLOTS = ["平日夜", "土曜午前", "土曜午後", "日曜"]
FREQUENCIES = ["毎週", "月2回", "月1回", "不定期"]
LEVELS = ["初心者歓迎", "レベル問わず", "経験者向け"]
FACT_ADULT_STARTERS = ["多い", "少しいる", "いない"]
MOOD_TAGS = ["ゆるめ", "しっかり練習", "黙々と集中", "わいわい賑やか", "おしゃべり多め", "少人数"]
FEES = ["無料", "500円以下", "1,000円以下", "それ以上"]
RENTALS = ["あり", "なし"]
JOIN_LEAVES = ["OK", "できれば最初から", "要相談"]
AFTER_ACTIVITIES = ["なし", "ランチ・お茶", "飲み会", "日による"]
STATUS_PLANNED = "予定"
STATUS_CANCELED = "中止"
MAX_MOOD_TAGS = 3

MESSAGE_SAVED = "保存しました"  # SP-59
MESSAGE_SAVE_FAILED = "保存できませんでした。もう一度お試しください"
MESSAGE_NO_CLUBS = "管理できる部活がありません"
MESSAGE_NO_EVENTS = "これからの開催予定はまだありません"
MESSAGE_CONFIRM_CANCEL = "この開催を中止にしますか？申込済みの人にも中止と表示されます"  # SP-60
MESSAGE_END_BEFORE_START = "終了時刻は開始時刻より後にしてください"  # SP-61
MESSAGE_PAST_DATE = "今日以降の日付を選んでください"  # SP-61
MESSAGE_TOO_MANY_TAGS = f"雰囲気タグは{MAX_MOOD_TAGS}つまで選べます"
MESSAGE_NO_PERMISSION = "この操作はできません（権限がありません）"

# (サービスのキー, 表示名) 保存に必須の項目。必須が空なら「○○を入力してください」（SP-59）
_LABELS = {
    "name": "部活名", "icon": "アイコン", "activity_id": "活動", "location": "拠点", "slot": "曜日・時間帯",
    "frequency": "頻度", "level": "レベル", "fact_adult_starters": "社会人から始めた人", "message": "ひとこと",
    "fee": "費用", "rental": "道具の貸し出し", "join_leave": "途中参加・途中で抜ける",
    "after_activity": "活動後の過ごし方", "organizer_id": "幹事",
}
_EVENT_LABELS = {"event_date": "開催日", "start_time": "開始時刻", "end_time": "終了時刻", "meeting_place": "集合場所"}

_SELECTED_KEY = "club_admin_selected"  # 管理中の部活ID（"new" なら新規作成）
_FLASH_KEY = "club_admin_flash"  # 保存後に1回だけ出す案内
_EDIT_EVENT_KEY = "club_admin_edit_event"  # 編集中の開催ID
_CANCEL_EVENT_KEY = "club_admin_cancel_event"  # 中止の確認中の開催ID
NEW = "new"


def _today():
    """「今日」は日本時間（サーバーの時計が海外でもずれないように）。"""
    return datetime.now(timezone(timedelta(hours=9))).date()


def _employee_labels(employees):
    """{社員ID: 表示名}。同じ名前の人がいるときだけ ID を添えて見分ける。"""
    counts = {}
    for e in employees:
        counts[e["name"]] = counts.get(e["name"], 0) + 1
    return {e["id"]: (f"{e['name']}（{e['id']}）" if counts[e["name"]] > 1 else e["name"]) for e in employees}


def _hhmm(value):
    return value.strftime("%H:%M") if hasattr(value, "strftime") else str(value)[:5]


def _date_text(value):
    return f"{value.month}/{value.day}（{'月火水木金土日'[value.weekday()]}）"


def _flash():
    message = st.session_state.pop(_FLASH_KEY, None)
    if message:
        st.success(message)


# ---- 部活情報タブ -------------------------------------------------------------

def _option(label, options, current, key, *, disabled=False):
    index = options.index(current) if current in options else None
    return st.selectbox(label, options, index=index, key=key, placeholder="選んでください", disabled=disabled)


def _render_club_form(club, is_admin, me, key_prefix):
    """部活情報のフォーム。club が None なら新規作成。"""
    club = club or {}
    k = lambda name: f"{key_prefix}_{name}"
    activities = search_service.list_activities()
    activity_names = {a["id"]: a["name"] for a in activities}
    employee_names = _employee_labels(club_admin_service.list_selectable_employees(me))

    with st.form(k("form")):
        name = st.text_input("部活名", value=club.get("name", ""), key=k("name"))
        icon = st.text_input("アイコン（絵文字1つ）", value=club.get("icon") or "", key=k("icon"))
        activity_id = st.selectbox("活動", list(activity_names), key=k("activity"), format_func=lambda a: activity_names[a],
                                   index=list(activity_names).index(club["activity_id"]) if club.get("activity_id") in activity_names else None,
                                   placeholder="選んでください")
        location = _option("拠点", LOCATIONS, club.get("location"), k("location"))
        slot = _option("曜日・時間帯", SLOTS, club.get("slot"), k("slot"))
        schedule_note = st.text_input("活動時間の補足（任意）", value=club.get("schedule_note") or "", key=k("schedule_note"))
        frequency = _option("頻度", FREQUENCIES, club.get("frequency"), k("frequency"))
        level = _option("レベル", LEVELS, club.get("level"), k("level"))
        starters = _option("社会人から始めた人", FACT_ADULT_STARTERS, club.get("fact_adult_starters"), k("starters"))
        mood_tags = st.multiselect(f"雰囲気タグ（最大{MAX_MOOD_TAGS}つ）", MOOD_TAGS, default=club.get("mood_tags", []), key=k("mood"))
        message = st.text_area("ひとこと", value=club.get("message", ""), key=k("message"))
        fee = _option("費用", FEES, club.get("fee"), k("fee"))
        fee_note = st.text_input("費用の補足（任意）", value=club.get("fee_note") or "", key=k("fee_note"))
        rental = _option("道具の貸し出し", RENTALS, club.get("rental"), k("rental"))
        belongings_note = st.text_input("持ち物（任意）", value=club.get("belongings_note") or "", key=k("belongings"))
        join_leave = _option("途中参加・途中で抜ける", JOIN_LEAVES, club.get("join_leave"), k("join_leave"))
        after_activity = _option("活動後の過ごし方", AFTER_ACTIVITIES, club.get("after_activity"), k("after"))
        # 幹事の変更と公開中の切り替えは運営者だけ（SP-59, SP-74）。幹事には見せるだけ
        organizer_options = list(employee_names)
        organizer_id = st.selectbox(
            "幹事", organizer_options, key=k("organizer"), format_func=lambda e: employee_names.get(e, e),
            index=organizer_options.index(club["organizer_id"]) if club.get("organizer_id") in organizer_options else None,
            placeholder="選んでください", disabled=not is_admin)
        # 公開中の切り替えは既存の部活だけ（新規作成はサービスが公開中で作る）
        is_active = None
        if club:
            is_active = st.checkbox("公開中", value=club.get("is_active", True), key=k("active"), disabled=not is_admin)
        submitted = st.form_submit_button("保存する")

    if not submitted:
        return
    data = {
        "name": name.strip(), "icon": icon.strip(), "activity_id": activity_id, "location": location, "slot": slot,
        "schedule_note": schedule_note.strip() or None, "frequency": frequency, "level": level,
        "fact_adult_starters": starters, "mood_tags": mood_tags, "message": message.strip(), "fee": fee,
        "fee_note": fee_note.strip() or None, "rental": rental, "belongings_note": belongings_note.strip() or None,
        "join_leave": join_leave, "after_activity": after_activity, "organizer_id": organizer_id,
    }
    if club:
        data["is_active"] = is_active
    # 先回りの案内（親切）。最終的な判断はサービスがする
    for key, label in _LABELS.items():
        if data.get(key) in (None, ""):
            st.error(f"{label}を入力してください")  # SP-59
            return
    if len(mood_tags) > MAX_MOOD_TAGS:
        st.error(MESSAGE_TOO_MANY_TAGS)
        return
    try:
        if club.get("club_id") is None:
            new_id = club_admin_service.create_club(me, data)
            st.session_state[_SELECTED_KEY] = new_id
        else:
            club_admin_service.update_club(club["club_id"], me, data)
    except PermissionDeniedError:
        st.error(MESSAGE_NO_PERMISSION)
        return
    except ValidationError as error:
        st.error(_validation_text(error))
        return
    except AppError:
        st.error(MESSAGE_SAVE_FAILED)
        return
    st.session_state[_FLASH_KEY] = MESSAGE_SAVED
    st.rerun()


def _validation_text(error):
    """サービスの ValidationError を、仕様の文言にする。"""
    code = str(error)
    if code.startswith("required:"):
        key = code.split(":", 1)[1]
        return f"{_LABELS.get(key) or _EVENT_LABELS.get(key, key)}を入力してください"
    return {"invalid:mood_tags": MESSAGE_TOO_MANY_TAGS, "end_before_start": MESSAGE_END_BEFORE_START,
            "past_date": MESSAGE_PAST_DATE}.get(code, MESSAGE_SAVE_FAILED)


# ---- 開催タブ -----------------------------------------------------------------

def _event_fields(prefix, event, default_place):
    """開催の入力欄（追加・編集で共通）。値の dict を返す。"""
    event = event or {}
    event_date = st.date_input("開催日", value=event.get("event_date", _today()), key=f"{prefix}_date")
    start = st.time_input("開始時刻", value=event.get("start_time") and _to_time(event["start_time"]) or _to_time("19:00"),
                          key=f"{prefix}_start")
    end = st.time_input("終了時刻", value=event.get("end_time") and _to_time(event["end_time"]) or _to_time("20:30"),
                        key=f"{prefix}_end")
    place = st.text_input("集合場所", value=event.get("meeting_place") or default_place or "", key=f"{prefix}_place")
    meeting = st.time_input("集合時刻（任意）", value=event.get("meeting_time") and _to_time(event["meeting_time"]) or None,
                            key=f"{prefix}_meeting")
    return {"event_date": event_date, "start_time": start, "end_time": end, "meeting_place": place.strip(),
            "meeting_time": meeting}


def _to_time(value):
    if hasattr(value, "hour"):
        return value
    hh, mm = str(value)[:5].split(":")
    return time(int(hh), int(mm))


def _event_error(error):
    return _validation_text(error)


def _render_events(club_id, me):
    events = club_admin_service.list_club_events(club_id, me)
    if not events:
        st.info(MESSAGE_NO_EVENTS)
    for event in events:
        with st.container(border=True):
            meeting = f"　集合 {_hhmm(event['meeting_time'])}" if event.get("meeting_time") else ""
            st.markdown(f"**{_date_text(event['event_date'])}　{_hhmm(event['start_time'])}〜{_hhmm(event['end_time'])}**")
            st.write(f"{event['meeting_place']}{meeting}")
            st.caption(f"状態：{event['status']}　／　申込 {event['applicant_count']}名")
            _render_event_actions(event, club_id, me)

    st.subheader("開催を追加")
    default_place = club_admin_service.get_last_meeting_place(club_id)  # 前回の開催を初期値に（SP-60）
    with st.form(f"club_admin_{club_id}_add_event"):
        data = _event_fields(f"club_admin_{club_id}_add", None, default_place)
        submitted = st.form_submit_button("追加する")
    if submitted:
        try:
            club_admin_service.create_event(club_id, me, data)
        except AppError as error:
            st.error(_event_error(error) if isinstance(error, ValidationError) else MESSAGE_SAVE_FAILED)
            return
        st.session_state[_FLASH_KEY] = "開催を追加しました"
        st.rerun()


def _render_event_actions(event, club_id, me):
    event_id = event["event_id"]
    if st.session_state.get(_EDIT_EVENT_KEY) == event_id:
        with st.form(f"club_admin_event_edit_form_{event_id}"):
            data = _event_fields(f"club_admin_event_edit_{event_id}", event, None)
            save = st.form_submit_button("変更を保存")
        if save:
            try:
                club_admin_service.update_event(event_id, me, data)
            except AppError as error:
                st.error(_event_error(error) if isinstance(error, ValidationError) else MESSAGE_SAVE_FAILED)
                return
            st.session_state.pop(_EDIT_EVENT_KEY, None)
            st.session_state[_FLASH_KEY] = MESSAGE_SAVED
            st.rerun()
        if st.button("やめる", key=f"club_admin_event_edit_stop_{event_id}"):
            st.session_state.pop(_EDIT_EVENT_KEY, None)
            st.rerun()
        return

    if st.session_state.get(_CANCEL_EVENT_KEY) == event_id:
        st.warning(MESSAGE_CONFIRM_CANCEL)  # SP-60
        left, right = st.columns(2)
        if left.button("中止にする", key=f"club_admin_event_cancel_do_{event_id}", type="primary"):
            st.session_state.pop(_CANCEL_EVENT_KEY, None)
            _set_status(event_id, me, STATUS_CANCELED)
        if right.button("やめる", key=f"club_admin_event_cancel_stop_{event_id}"):
            st.session_state.pop(_CANCEL_EVENT_KEY, None)
            st.rerun()
        return

    left, right = st.columns(2)
    if left.button("編集", key=f"club_admin_event_edit_{event_id}"):
        st.session_state[_EDIT_EVENT_KEY] = event_id
        st.rerun()
    if event["status"] == STATUS_PLANNED:
        if right.button("中止にする", key=f"club_admin_event_cancel_{event_id}"):
            st.session_state[_CANCEL_EVENT_KEY] = event_id
            st.rerun()
    elif right.button("予定に戻す", key=f"club_admin_event_restore_{event_id}"):
        _set_status(event_id, me, STATUS_PLANNED)


def _set_status(event_id, me, status):
    try:
        club_admin_service.set_event_status(event_id, me, status)
    except ConflictError:
        st.info("すでにその状態です")
        return
    except AppError:
        st.error(MESSAGE_SAVE_FAILED)
        return
    st.rerun()


# ---- メンバータブ（Should）-------------------------------------------------------

def _render_members(club, me):
    members = club_admin_service.list_club_members(club["club_id"], me)
    for member in members:
        left, right = st.columns([4, 1])
        is_organizer = member["id"] == club["organizer_id"]
        left.write(f"{member['name']}（{member['dept']}）" + ("　幹事" if is_organizer else ""))
        if not is_organizer and right.button("削除", key=f"club_admin_member_remove_{club['club_id']}_{member['id']}"):
            try:
                club_admin_service.remove_club_member(club["club_id"], me, member["id"])
            except ConflictError:
                st.error("幹事はメンバーから外せません。先に幹事を変更してください")
                return
            except AppError:
                st.error(MESSAGE_SAVE_FAILED)
                return
            st.rerun()

    st.subheader("メンバーを追加")
    member_ids = {m["id"] for m in members}
    everyone = club_admin_service.list_selectable_employees(me)
    labels = _employee_labels(everyone)
    candidates = {e["id"]: labels[e["id"]] for e in everyone if e["id"] not in member_ids}
    with st.form(f"club_admin_{club['club_id']}_add_member"):
        employee_id = st.selectbox("社員", list(candidates), format_func=lambda e: candidates[e], index=None,
                                   placeholder="社員を選んでください", key=f"club_admin_{club['club_id']}_member_pick")
        submitted = st.form_submit_button("追加する")
    if submitted:
        if employee_id is None:
            st.error("社員を選んでください")
            return
        try:
            club_admin_service.add_club_member(club["club_id"], me, employee_id)
        except AppError:
            st.error(MESSAGE_SAVE_FAILED)
            return
        st.rerun()


# ---- 画面の入口 ---------------------------------------------------------------

def render():
    me = st.session_state["employee_id"]
    is_admin = auth_service.get_role(me) == auth_service.ROLE_ADMIN
    clubs = club_admin_service.list_manageable_clubs(me)

    st.title("部活の管理")
    if not clubs and not is_admin:
        st.info(MESSAGE_NO_CLUBS)
        return

    ids = [c["club_id"] for c in clubs]
    names = {c["club_id"]: f"{c['icon'] or ''} {c['name']}".strip() + ("" if c["is_active"] else "（非公開）") for c in clubs}
    selected = st.session_state.get(_SELECTED_KEY)
    if selected != NEW and selected not in ids:
        selected = st.session_state[_SELECTED_KEY] = ids[0] if ids else NEW

    _flash()
    top_left, top_right = st.columns([3, 1])
    if selected == NEW:
        top_left.subheader("部活を新しく作る")
        if top_right.button("← 戻る", key="club_admin_new_back") and ids:
            st.session_state[_SELECTED_KEY] = ids[0]
            st.rerun()
        _render_club_form(None, is_admin, me, "club_admin_new")
        return

    chosen = top_left.selectbox("管理する部活", ids, index=ids.index(selected), format_func=lambda i: names[i],
                                key="club_admin_picker")
    if chosen != selected:
        st.session_state[_SELECTED_KEY] = chosen
        st.session_state.pop(_EDIT_EVENT_KEY, None)
        st.session_state.pop(_CANCEL_EVENT_KEY, None)
        st.rerun()
    if is_admin and top_right.button("＋ 部活を新しく作る", key="club_admin_new_open"):  # SP-58
        st.session_state[_SELECTED_KEY] = NEW
        st.rerun()

    club = club_admin_service.get_club(chosen, me)
    tab_info, tab_events, tab_members = st.tabs(["部活情報", "開催", "メンバー"])
    with tab_info:
        _render_club_form(club, is_admin, me, f"club_admin_{chosen}")
    with tab_events:
        _render_events(chosen, me)
    with tab_members:
        _render_members(club, me)
