"""S01 ログイン画面の単体テスト（AppTest）。

対応する仕様・結合テスト：
  SP-09 / I-009 … アプリ名とひとことの説明
  SP-10 / I-010, I-011 … 認証成功でログイン状態になる（ID は正式な形で記録）
  SP-11 / I-012 … 認証失敗の文言（どちらが誤りかは示さない）
  SP-12 / I-013 … デモ用の小さな表示

DB には繋がない。認証サービスは偽物に差し替えて「この返事が来たら画面はこうなる」だけを見る。
"""

from streamlit.testing.v1 import AppTest

from screens import login
from services import auth_service
from services.errors import AuthenticationError

# 画面を 1 枚だけ描くための小さなスクリプト（app.py の代わり）
SCRIPT = """
import state
from screens import login
state.init()
login.render()
"""


def _app():
    at = AppTest.from_string(SCRIPT)
    at.run()
    return at


def test_shows_app_name_and_tagline():  # SP-09 / I-009
    at = _app()
    assert at.title[0].value == login.APP_NAME
    assert login.TAGLINE in [m.value for m in at.markdown]


def test_shows_demo_note():  # SP-12 / I-013
    at = _app()
    assert "デモ用：社員ID E001〜E500／パスワードは共有のもの" in [c.value for c in at.caption]


def test_wrong_credentials_show_error_and_stay_logged_out(monkeypatch):  # SP-11 / I-012
    def fake_login(employee_id, password):
        raise AuthenticationError()

    monkeypatch.setattr(auth_service, "login", fake_login)
    at = _app()
    at.text_input[0].set_value("E001")
    at.text_input[1].set_value("wrong")
    at.button[0].click().run()

    # 文言は仕様 SP-11 の原文と直接比べる（画面の定数と比べると、定数ごと壊れても気づけない）
    assert [e.value for e in at.error] == ["社員IDかパスワードが違います。入力内容を確認してください"]
    assert at.session_state["employee_id"] is None


def test_success_records_official_id_not_typed_one(monkeypatch):  # SP-10 / I-010, I-011
    calls = []

    def fake_login(employee_id, password):
        calls.append((employee_id, password))
        return {"id": "E001", "name": "加藤健太", "dept": "営業部"}

    monkeypatch.setattr(auth_service, "login", fake_login)
    at = _app()
    at.text_input[0].set_value("e001")  # 小文字で入力
    at.text_input[1].set_value("secret")
    at.button[0].click().run()

    assert calls == [("e001", "secret")]  # 正規化はサービスの仕事。画面は入力をそのまま渡す
    assert at.session_state["employee_id"] == "E001"  # 記録は正式な ID
    assert at.session_state["employee"]["name"] == "加藤健太"
    assert at.session_state["current_page"] == "home"
