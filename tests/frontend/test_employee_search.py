"""S08 社員検索画面の単体テスト（AppTest）。

対応する仕様：SP-47（注意文）, SP-50（n名見つかりました・プロフィールを見る）, SP-52（0人の案内文）。
UI/UX再設計（#142）で社員カードに見た目用の key を付けたので、カードの表示と
「プロフィールを見る」の動きが変わっていないことを守る。

DB には繋がない。検索サービスは偽物に差し替える。
"""

from streamlit.testing.v1 import AppTest

from services import search_service

SCRIPT = """
import state
from screens import employee_search
state.init()
employee_search.render()
"""


def _employee(number, name):
    return {
        "id": f"E{number:03d}", "name": name, "dept": "営業", "location": "東京",
        "joined_year": 2020, "entry_type": "新卒", "interests_visibility": "public",
        "interests": [{"activity_name": "テニス", "level": "初心者"}], "clubs": [{"name": "テニス部"}],
    }


def _open(monkeypatch, employees):
    monkeypatch.setattr(search_service, "list_activities", lambda: [{"id": 1, "name": "テニス"}])
    monkeypatch.setattr(search_service, "list_departments", lambda: ["営業", "開発"])
    monkeypatch.setattr(search_service, "search_clubs", lambda conditions: [])
    monkeypatch.setattr(
        search_service, "search_employees",
        lambda conditions, me, limit=20, offset=0: (employees, len(employees)),
    )
    at = AppTest.from_string(SCRIPT)
    at.session_state["employee_id"] = "E001"
    at.run()
    return at


def test_notice_and_count_and_cards(monkeypatch):  # SP-47 / SP-50
    at = _open(monkeypatch, [_employee(2, "高橋拓海"), _employee(3, "佐藤花子")])
    assert any("本人が公開にしたものだけが検索・表示されます" in i.value for i in at.info)
    assert any(m.value == "2名見つかりました" for m in at.markdown)
    keys = [b.key for b in at.button]
    assert "employee_search_profile_E002" in keys and "employee_search_profile_E003" in keys


def test_profile_button_goes_to_profile(monkeypatch):  # SP-50
    at = _open(monkeypatch, [_employee(2, "高橋拓海")])
    at.button(key="employee_search_profile_E002").click().run()
    assert at.session_state["current_page"] == "employee_profile"
    assert at.session_state["target_employee_id"] == "E002"


def test_no_result_shows_guidance(monkeypatch):  # SP-52
    at = _open(monkeypatch, [])
    assert any("条件に合う人がいません" in i.value for i in at.info)
