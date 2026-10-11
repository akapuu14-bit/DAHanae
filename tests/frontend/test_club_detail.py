"""S04 部活詳細画面の単体テスト（AppTest）。

対応する仕様・結合テスト：
  SP-27 / I-034, I-035, I-036 … 開催の状態によるボタンの出し分け
  SP-29 / I-038             … 申込フォームの中身（運営ルール・キャンセル案内）
  SP-30 / I-039, I-040      … 申し込む → 完了画面へ／やめる → 閉じる
  SP-31 / I-041, I-042      … 重複申込・申込不可の文言（★重複申込防止）
  SP-32 / I-043             … 開いたとき閲覧履歴を記録する
  SP-28 / I-037             … 幹事名から社員プロフィールへ

DB には繋がない。検索・申込・履歴のサービスは偽物に差し替える。
"""

import pytest
from streamlit.testing.v1 import AppTest

from services import action_log_service, application_service, search_service
from services.errors import ConflictError

SCRIPT = """
import state
from screens import club_detail
state.init()
club_detail.render()
"""


def _club():
    return {
        "icon": "🎾", "name": "テニス部", "mood_tags": ["和やか"], "level": "初心者歓迎",
        "slot": "水曜 19:00", "schedule_note": None, "location": "東京", "frequency": "週1",
        "message": "気軽に打ち合います", "fact_adult_starters": "多数",
        "fee": "無料", "fee_note": None, "rental": "あり", "belongings_note": None,
        "join_leave": "自由", "after_activity": "任意",
    }


def _event(event_id=10, status="予定", is_applied=False):
    return {
        "event_id": event_id, "event_date": "2099-10-14", "start_time": "19:00:00",
        "end_time": "20:30:00", "meeting_place": "コート前", "meeting_time": None,
        "status": status, "is_applied": is_applied,
        "participant_count": 3, "first_timer_count": 1, "participants": [],
    }


def _detail(events):
    return {
        "club": _club(),
        "events": events,
        "organizer": {"id": "E002", "name": "高橋拓海", "dept": "営業", "joined_year": 2020, "entry_type": "新卒"},
        "members": [{"id": "E002", "name": "高橋拓海", "dept": "営業"}],
        "member_count": 1,
    }


@pytest.fixture
def open_screen(monkeypatch):
    """偽のサービスを入れて画面を開く関数を返す。記録した履歴の呼び出しも一緒に返す。"""

    def _open(events):
        views = []
        monkeypatch.setattr(search_service, "get_club_detail", lambda club_id, viewer_id: _detail(events))
        monkeypatch.setattr(action_log_service, "record_view_club", lambda e, c: views.append((e, c)))
        at = AppTest.from_string(SCRIPT)
        at.session_state["employee_id"] = "E001"
        at.session_state["target_club_id"] = 1
        at.run()
        return at, views

    return _open


def _labels(at):
    return [b.label for b in at.button]


def test_apply_button_shown_for_open_unapplied_event(open_screen):  # SP-27 / I-034
    at, _ = open_screen([_event()])
    assert "申し込む" in _labels(at)


def test_applied_event_shows_applied_and_no_button(open_screen):  # SP-27 / I-035
    at, _ = open_screen([_event(is_applied=True)])
    assert any("申込済み" in m.value for m in at.markdown)
    assert "申し込む" not in _labels(at)


def test_cancelled_event_shows_cancelled_and_no_button(open_screen):  # SP-27 / I-036
    at, _ = open_screen([_event(status="中止")])
    assert any(m.value == "中止" for m in at.markdown)
    assert "申し込む" not in _labels(at)


def test_view_is_recorded_when_opened(open_screen):  # SP-32 / I-043
    _, views = open_screen([_event()])
    assert views == [("E001", 1)]


def test_apply_form_opens_and_can_be_closed(open_screen):  # SP-29 / I-038, SP-30 / I-040
    at, _ = open_screen([_event()])
    at.button(key="club_detail_apply_10").click().run()
    captions = [c.value for c in at.caption]
    assert "キャンセルもできます" in captions
    assert any("体験参加は入部ではありません" in c for c in captions)
    assert at.text_area  # 幹事への一言欄

    close = next(b for b in at.button if b.label == "やめる")
    close.click().run()
    assert not at.text_area  # フォームが閉じる


def test_apply_success_goes_to_complete_screen(open_screen, monkeypatch):  # SP-30 / I-039
    calls = []

    def fake_apply(event_id, applicant_id, message_text):
        calls.append((event_id, applicant_id, message_text))
        return {"application_id": 99, "is_first_time": True}

    monkeypatch.setattr(application_service, "apply", fake_apply)
    at, _ = open_screen([_event()])
    at.button(key="club_detail_apply_10").click().run()
    at.text_area[0].set_value("初めてです")
    submit = next(b for b in at.button if b.label == "この開催に申し込む")
    submit.click().run()

    assert calls == [(10, "E001", "初めてです")]
    assert at.session_state["current_page"] == "application_complete"
    assert at.session_state["pending_application_context"]["application_id"] == 99


@pytest.mark.parametrize(
    "reason, expected",
    [  # 文言は仕様 SP-31 の原文と直接比べる（★重複申込防止）
        ("already_applied", "すでに申し込み済みです"),  # I-041
        ("not_open", "この開催には申し込みできません"),  # I-042
    ],
)
def test_conflict_shows_message_and_does_not_leave(open_screen, monkeypatch, reason, expected):  # SP-31
    def fake_apply(event_id, applicant_id, message_text):
        raise ConflictError(reason)

    monkeypatch.setattr(application_service, "apply", fake_apply)
    at, _ = open_screen([_event()])
    at.button(key="club_detail_apply_10").click().run()
    next(b for b in at.button if b.label == "この開催に申し込む").click().run()

    assert [e.value for e in at.error] == [expected]
    assert at.session_state["current_page"] != "application_complete"


def test_organizer_button_goes_to_profile(open_screen):  # SP-28 / I-037
    at, _ = open_screen([_event()])
    at.button(key="club_detail_organizer").click().run()
    assert at.session_state["current_page"] == "employee_profile"
    assert at.session_state["target_employee_id"] == "E002"
