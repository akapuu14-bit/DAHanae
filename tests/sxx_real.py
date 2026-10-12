"""S-xx 黒箱 Phase2 T1 / 層 α-R（AppTest＋実DB 読取のみ）の土台。

- 実DBへの接続・secrets の流し込み・接続不可のときの自動 skip は lb_base（L-B）をそのまま使う。
- 画面を開くだけで起きる書込（操作履歴・通知の既読化）は ReadOnlyGuard が握りつぶす。実DBに書込は届かない。
- 偽の db.client（tests/fakes.py）が同じプロセスに居ると lb_base が skip にする。α-R は別プロセスで回す。
"""

from datetime import datetime

from streamlit.testing.v1 import AppTest

from lb_base import ROOT, JST, LbTestCase
from sxx_common import ReadOnlyGuard

APP = str(ROOT / "app" / "frontend" / "app.py")


class RealAppCase(LbTestCase):
    IS_DRY = False

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.guard = ReadOnlyGuard(cls.db)
        cls.guard.install()
        cls.addClassCleanup(cls.guard.uninstall)

    def today(self):
        return datetime.now(JST).date()

    def app(self, employee_id=None, page="home", **session):
        """実在の社員でログイン済みの状態で app.py を起動する（employee_id=None はログイン画面）。"""
        at = AppTest.from_file(APP, default_timeout=60)
        if employee_id:
            employee = self.env.employees_repo.get_by_id(employee_id)
            assert employee is not None, f"社員 {employee_id} が実DBに無い"
            at.session_state["employee_id"] = employee["id"]
            at.session_state["employee"] = employee
            at.session_state["current_page"] = page
            at.session_state["page_history"] = []
        for key, value in session.items():
            at.session_state[key] = value
        return at.run()
