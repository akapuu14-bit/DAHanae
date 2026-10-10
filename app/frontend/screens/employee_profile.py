"""S09 社員プロフィール画面（仕様 SP-53〜SP-57）。

上から順に、
  1. 見出し（← 戻る・名前。本人なら「（あなた）」）と基本情報        SP-53
  2. 興味・経験／参加可能時間（他の人には、非公開なら「非公開」）      SP-54
  3. 所属部活のカード（押すと部活詳細へ）                              SP-55
  4. 本人だけ：公開の切り替え2つ（切り替えた時点で保存）と、編集      SP-56, SP-57
「非公開の人の値を渡さない」判断はサービスがしている。この画面は受け取った値を並べるだけ。
開く社員は session_state["target_employee_id"]（無ければ自分）。
"""

import streamlit as st

import state
from components import club_card
from services.errors import AppError, NotFoundError, ValidationError

# 本物ができたら、次の 1 行を
#     from services import profile_service, search_service
# に書き換える。ほかは変えなくてよい。
from mocks import profile_service, search_service

PRIVATE_TEXT = "非公開"
SELF_PRIVATE_NOTE = "（他の人には非公開）"  # SP-65：本人には値と一緒に出す
NO_CLUBS_TEXT = "所属している部活はありません"
NOT_FOUND_TEXT = "この社員は見つかりませんでした"
SAVED_TEXT = "保存しました"
SAVE_FAILED_TEXT = "保存できませんでした。もう一度お試しください"
COLUMNS = 3
NOT_SELECTED = "選択しない"
# 選択肢は契約に無いので画面の定数にする（仕様 3.2）。活動の一覧だけは search_service.list_activities() から取る。
EXPERIENCE_LEVELS = ["未経験", "初心者", "経験あり"]
SLOTS = ["平日夜", "土曜午前", "土曜午後", "日曜"]
LEVEL_COLUMNS = 4  # 活動の経験レベルは、この数ずつ並べて全部出す
_SAVED_FLAG = "profile_saved"


def _render_header(profile):
    employee = profile["employee"]
    if st.button("← 戻る", key="employee_profile_back"):  # SP-02
        state.back()
    suffix = "（あなた）" if profile["is_self"] else ""
    st.title(f"{employee['name']}{suffix}")
    st.write(f"{employee['dept']}・{employee['location']}・{employee['joined_year']}年入社・{employee['entry_type']}")


def _render_interests(profile):
    st.subheader("興味・経験")
    interests = profile["interests"]
    if interests is None:
        st.write(PRIVATE_TEXT)
        return
    if not interests:
        st.caption("まだ登録されていません")
    for item in interests:
        st.write(f"・{item['activity_name']}（{item['level']}）")
    if profile["is_self"] and not profile["interests_public"]:
        st.caption(SELF_PRIVATE_NOTE)


def _render_slots(profile):
    st.subheader("参加可能時間")
    slots = profile["available_slots"]
    if slots is None:
        st.write(PRIVATE_TEXT)
        return
    st.write("、".join(slots) if slots else "まだ登録されていません")
    if profile["is_self"] and not profile["slots_public"]:
        st.caption(SELF_PRIVATE_NOTE)


def _render_clubs(profile):
    st.subheader("所属部活")
    clubs = profile["clubs"]
    if not clubs:
        st.caption(NO_CLUBS_TEXT)
        return
    for start in range(0, len(clubs), COLUMNS):
        for column, club in zip(st.columns(COLUMNS), clubs[start : start + COLUMNS]):
            with column:
                club_card.render(club, key_prefix="employee_profile")


def _render_public_toggles(profile, me):
    """SP-56：切り替えた時点で保存する。"""
    st.subheader("公開設定")
    interests_public = st.toggle("興味・経験を公開する", value=profile["interests_public"], key="profile_toggle_interests")
    slots_public = st.toggle("参加可能時間を公開する", value=profile["slots_public"], key="profile_toggle_slots")
    if interests_public != profile["interests_public"] or slots_public != profile["slots_public"]:
        try:
            profile_service.update_public_settings(me, me, interests_public=interests_public, slots_public=slots_public)
        except AppError:
            st.error(SAVE_FAILED_TEXT)
            return
        st.rerun()


def _render_editor(profile, me):
    """SP-57：興味・経験と参加可能時間の編集。"""
    current = {i["activity_id"]: i["level"] for i in (profile["interests"] or [])}
    with st.expander("興味・経験と参加可能時間を編集する"):
        with st.form("profile_edit_form"):
            st.write("活動ごとの経験レベル")
            levels = {}
            options = [NOT_SELECTED] + EXPERIENCE_LEVELS
            activities = search_service.list_activities()
            # 活動の数にかかわらず、LEVEL_COLUMNS 個ずつの行に分けて全部出す（保存は置き換えなので、出さない活動の興味は消えてしまう）
            for start in range(0, len(activities), LEVEL_COLUMNS):
                row = activities[start : start + LEVEL_COLUMNS]
                for column, activity in zip(st.columns(LEVEL_COLUMNS), row):
                    activity_id = activity["id"]
                    levels[activity_id] = column.selectbox(activity["name"], options,
                                                           index=options.index(current.get(activity_id, NOT_SELECTED)),
                                                           key=f"profile_edit_level_{activity_id}")
            slots = st.multiselect("参加可能時間", SLOTS, default=profile["available_slots"] or [],
                                   key="profile_edit_slots")
            submitted = st.form_submit_button("保存する")
        if submitted:
            interests = [{"activity_id": a, "level": level} for a, level in levels.items() if level != NOT_SELECTED]
            try:
                profile_service.save_profile(me, me, interests, slots)
            except (ValidationError, AppError):
                st.error(SAVE_FAILED_TEXT)
                return
            st.session_state[_SAVED_FLAG] = True
            st.rerun()


def render():
    me = st.session_state["employee_id"]
    target = st.session_state.get("target_employee_id") or me
    try:
        profile = profile_service.get_profile(target, me)
    except NotFoundError:
        st.info(NOT_FOUND_TEXT)
        if st.button("← 戻る", key="employee_profile_back_missing"):
            state.back()
        return

    _render_header(profile)
    if st.session_state.pop(_SAVED_FLAG, False):
        st.success(SAVED_TEXT)
    _render_interests(profile)
    _render_slots(profile)
    _render_clubs(profile)
    if profile["is_self"]:
        st.divider()
        _render_public_toggles(profile, me)
        _render_editor(profile, me)
