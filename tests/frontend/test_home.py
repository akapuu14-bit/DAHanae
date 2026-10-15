"""S02 ホーム画面の単体テスト（AppTest）。

対応する仕様：SP-14（あいさつ）, SP-15（入口ボタン2つ）, SP-16〜18（今週・人気・おすすめ。0件の案内文）。
UI/UX再設計（#142）でボタンまわりの並べ方を変えたので、「ボタンの名前・押したときの行き先・説明文」が
変わっていないことを守る。見た目（高さ・折り返し）は style.css の役目で、ここでは確かめない。

DB には繋がない。検索サービスは偽物に差し替える。
"""

from streamlit.testing.v1 import AppTest

import state
from services import search_service

SCRIPT = """
import state
from screens import home
state.init()
home.render()
"""


def _club(club_id, name):
    return {
        "club_id": club_id, "icon": "🎾", "name": name, "location": "東京", "slot": "水曜",
        "mood_tags": ["和やか"], "fee": "無料", "after_activity": "任意",
        "next_event_date": "2099-10-14", "level": "初心者歓迎", "score": 80, "reason": "拠点が同じ",
    }


def _open(monkeypatch, week=(), popular=(), recommend=()):
    # 画面は get_home_page（今週・人気・おすすめを1回で取る。D-08）を呼ぶ
    monkeypatch.setattr(
        search_service, "get_home_page",
        lambda employee_id: {"week": list(week), "popular": list(popular), "recommendations": list(recommend)},
    )
    monkeypatch.setattr(state, "current_employee", lambda: {"name": "加藤健太"})
    at = AppTest.from_string(SCRIPT)
    at.session_state["employee_id"] = "E001"
    at.run()
    return at


def test_greeting_and_two_entry_buttons(monkeypatch):  # SP-14 / SP-15
    at = _open(monkeypatch)
    assert at.title[0].value == "部活コンシェルジュ"
    assert any(m.value == "加藤健太さん、こんにちは。" for m in at.markdown)
    labels = [b.label for b in at.button]
    assert "部活を探す" in labels and "人を探す" in labels
    texts = [m.value for m in at.markdown]
    assert "活動・拠点・曜日などの条件から、自分に合う部活を探せます。" in texts
    assert "名前や部署、興味から、社内の仲間を探せます。" in texts


def test_club_search_button_goes_to_club_search(monkeypatch):  # SP-15
    at = _open(monkeypatch)
    at.button(key="home_to_club_search").click().run()
    assert at.session_state["current_page"] == state.CLUB_SEARCH


def test_employee_search_button_goes_to_employee_search(monkeypatch):  # SP-15
    at = _open(monkeypatch)
    at.button(key="home_to_employee_search").click().run()
    assert at.session_state["current_page"] == state.EMPLOYEE_SEARCH


def test_empty_sections_show_guidance(monkeypatch):  # SP-16 / SP-17 / SP-18
    at = _open(monkeypatch)
    infos = [i.value for i in at.info]
    assert "今週開催予定の部活はまだありません" in infos
    assert "今月はまだ人気部活のデータがありません" in infos
    assert "今はおすすめできる部活がありません" in infos


def test_week_clubs_are_shown_as_cards(monkeypatch):  # SP-16
    at = _open(monkeypatch, week=[_club(1, "テニス部"), _club(2, "写真部")])
    assert any("テニス部" in m.value for m in at.markdown)
    keys = [b.key for b in at.button]
    assert "home_week_1" in keys and "home_week_2" in keys
