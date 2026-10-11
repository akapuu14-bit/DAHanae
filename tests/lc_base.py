"""L-C（画面 AppTest ＋ 偽repo）の土台。実DB・ネットワークは使わない。

app/frontend/app.py を Streamlit の AppTest で動かし、repo は fakes.py の偽repoに差し替える。
合格は「偽repoに対する画面表示・文言・遷移の合格」であり、実DBでの合格ではない。
"""

import os

from streamlit.testing.v1 import AppTest

import fakes
from fakes import LaTestCase

APP = os.path.join(fakes._ROOT, "app", "frontend", "app.py")


class LcTestCase(LaTestCase):
    def app(self, employee_id=None, page="home", **session):
        """ログイン済み（employee_id 指定時）の状態で app.py を起動して返す。"""
        at = AppTest.from_file(APP, default_timeout=10)
        if employee_id:
            at.session_state["employee_id"] = employee_id
            at.session_state["employee"] = fakes.auth_service.get_employee(employee_id) \
                if hasattr(fakes.auth_service, "get_employee") else dict(self.w.employees[employee_id])
            at.session_state["current_page"] = page
            at.session_state["page_history"] = []
        for k, v in session.items():
            at.session_state[k] = v
        return at.run()

    @staticmethod
    def texts(at):
        """画面に出ている文字（markdown・caption・info・error・title・subheader・button）を1つの文字列に。"""
        parts = []
        for group in (at.title, at.header, at.subheader, at.markdown, at.caption, at.info,
                      at.error, at.warning, at.success, at.text):
            parts += [e.value for e in group]
        parts += [b.label for b in at.button]
        parts += [e.label for e in at.sidebar.button] if hasattr(at, "sidebar") else []
        return "\n".join(str(p) for p in parts)
