"""S04 部活詳細画面の「折りたたみ」の単体テスト（AppTest）。

対応する仕様：SP-25（基本情報・どんな部活？・参加の前に・活動後の過ごし方）。
見た目の変更（UI/UX再設計 #142）で、この4つを「押して開く」形（最初は閉じる）にした。
確かめること：
  ・4つが折りたたみ（expander）になっていて、最初は閉じている
  ・閉じていても、中身の文言は変わらず画面の中にある（内容は変えていない）
  ・開催一覧は、直近の1件を開いたまま見せ、2件目以降だけ「ほかの開催」に折りたたむ

DB には繋がない。検索・履歴のサービスは偽物に差し替える。
"""

from streamlit.testing.v1 import AppTest

from services import action_log_service, search_service

SCRIPT = """
import state
from screens import club_detail
state.init()
club_detail.render()
"""

SECTIONS = ["基本情報", "どんな部活？", "参加の前に", "活動後の過ごし方"]


def _event(event_id, day):
    return {
        "event_id": event_id, "event_date": f"2099-10-{day}", "start_time": "19:00:00",
        "end_time": "20:30:00", "meeting_place": "コート前", "meeting_time": None,
        "status": "予定", "is_applied": False,
        "participant_count": 3, "first_timer_count": 1, "participants": [],
    }


def _detail(event_count=1):
    return {
        "club": {
            "icon": "🎾", "name": "テニス部", "mood_tags": ["和やか"], "level": "初心者歓迎",
            "slot": "水曜 19:00", "schedule_note": None, "location": "東京", "frequency": "週1",
            "message": "気軽に打ち合います", "fact_adult_starters": "多数",
            "fee": "無料", "fee_note": None, "rental": "あり", "belongings_note": None,
            "join_leave": "自由", "after_activity": "任意",
        },
        "events": [_event(10 + i, 14 + i) for i in range(event_count)],
        "organizer": {"id": "E002", "name": "高橋拓海", "dept": "営業", "joined_year": 2020, "entry_type": "新卒"},
        "members": [{"id": "E002", "name": "高橋拓海", "dept": "営業"}],
        "member_count": 1,
    }


def _open(monkeypatch, event_count=1):
    monkeypatch.setattr(search_service, "get_club_detail", lambda club_id, viewer_id: _detail(event_count))
    monkeypatch.setattr(action_log_service, "record_view_club", lambda e, c: None)
    at = AppTest.from_string(SCRIPT)
    at.session_state["employee_id"] = "E001"
    at.session_state["target_club_id"] = 1
    at.run()
    return at


def test_four_sections_are_collapsed_by_default(monkeypatch):  # SP-25
    at = _open(monkeypatch)
    by_label = {e.label: e for e in at.expander}
    for title in SECTIONS:
        assert title in by_label, f"「{title}」の折りたたみが見つからない"
        assert by_label[title].proto.expanded is False


def test_contents_are_unchanged_inside_collapsed_sections(monkeypatch):  # SP-25
    at = _open(monkeypatch)
    texts = [m.value for m in at.markdown]
    captions = [c.value for c in at.caption]
    assert "気軽に打ち合います" in texts
    assert "費用：無料" in texts
    assert "任意" in texts
    assert "東京" in texts and "拠点" in captions


def test_one_event_is_not_collapsed(monkeypatch):  # SP-26
    at = _open(monkeypatch, event_count=1)
    assert not any(e.label.startswith("ほかの開催") for e in at.expander)
    assert any(s.value == "開催一覧" for s in at.subheader)
    assert [b.key for b in at.button if b.label == "申し込む"] == ["club_detail_apply_10"]


def test_next_event_stays_open_and_others_are_collapsed(monkeypatch):  # SP-26 / SP-27
    at = _open(monkeypatch, event_count=3)
    others = [e for e in at.expander if e.label.startswith("ほかの開催")]
    assert len(others) == 1
    assert others[0].label == "ほかの開催（2件）"
    assert others[0].proto.expanded is False
    # 直近の1件の「申し込む」は折りたたみの外にある。残り2件は折りたたみの中にある
    inside = {b.key for b in others[0].button}
    assert inside == {"club_detail_apply_11", "club_detail_apply_12"}
    outside = {b.key for b in at.button if b.label == "申し込む"} - inside
    assert outside == {"club_detail_apply_10"}
