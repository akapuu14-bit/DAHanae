"""性能改善 T1（設計 D-06、仕様 SP-84）：サイドバー値（未読件数・権限）の保持（偽repo＋AppTest）。

確かめること：
- 通知・メッセージ画面を開かない遷移では、未読件数・権限を取り直さない（再取得0回）
- 通知・メッセージ画面を開いたときと、既読化の直後に未読件数を取り直す（SP-84①）
- 幹事・メンバーの変更の直後に権限を取り直す（SP-84）。ログインし直すと前の人の値を引き継がない
"""
import unittest
from unittest import mock

import state
from lc_base import LcTestCase
from services import auth_service, notification_service


def sidebar_labels(at):
    return [b.label for b in at.sidebar.button]


class SidebarHold(LcTestCase):
    def setUp(self):
        super().setUp()
        self.unread = mock.patch.object(
            notification_service, "count_unread", wraps=notification_service.count_unread)
        self.role = mock.patch.object(auth_service, "get_role", wraps=auth_service.get_role)
        self.org = mock.patch.object(auth_service, "is_organizer", wraps=auth_service.is_organizer)
        self.m_unread, self.m_role, self.m_org = self.unread.start(), self.role.start(), self.org.start()
        self.addCleanup(mock.patch.stopall)

    def _reset(self):
        for m in (self.m_unread, self.m_role, self.m_org):
            m.reset_mock()

    def _click(self, at, label):
        at.sidebar.button(key=f"sidebar_{label}").click()
        return at.run()

    def test_first_render_fetches_once_then_holds(self):
        at = self.app("E003")  # ログイン直後の最初の描画
        self.assertEqual(self.m_unread.call_count, 1)
        self.assertEqual(self.m_role.call_count, 1)
        self.assertEqual(self.m_org.call_count, 1)
        self._reset()
        # 通知・メッセージを開かない遷移（ホーム→部活を探す→人を探す→ホーム）は取り直さない
        for page in ("club_search", "employee_search", "home"):
            at = self._click(at, page)
            self.assertEqual(at.session_state["current_page"], page)
        self.assertEqual(self.m_unread.call_count, 0)
        self.assertEqual(self.m_role.call_count, 0)
        self.assertEqual(self.m_org.call_count, 0)

    def test_widget_rerun_does_not_refetch(self):
        at = self.app("E003", page="club_search")
        self._reset()
        at.text_input[0].set_value("部").run()
        self.assertEqual(self.m_unread.call_count, 0)
        self.assertEqual(self.m_role.call_count, 0)

    def test_opening_messages_refetches_and_mark_read_invalidates(self):
        self.w.add_notification("E003", "メッセージ")
        at = self.app("E003")
        self.assertIn("メッセージ（1）", sidebar_labels(at))
        self._reset()
        at = self._click(at, "messages")  # 開いたとき：取り直す（SP-84①）
        self.assertEqual(self.m_unread.call_count, 1)
        # 画面が既読化した直後は保持値を捨てる。表示は次の描画で0件に変わる
        self.assertIsNone(at.session_state["unread_count"])
        self._reset()
        at = self._click(at, "home")
        self.assertEqual(self.m_unread.call_count, 1)  # 既読化の直後の取り直し
        self.assertEqual(at.session_state["unread_count"], 0)
        self.assertNotIn("メッセージ（1）", sidebar_labels(at))
        self._reset()
        at = self._click(at, "club_search")
        self.assertEqual(self.m_unread.call_count, 0)  # そのあとは保持値

    def test_opening_notifications_refetches_and_mark_read_invalidates(self):
        self.w.add_notification("E003", "中止")
        at = self.app("E003")
        self.assertIn("メッセージ（1）", sidebar_labels(at))
        self._reset()
        at = self._click(at, "notifications")
        self.assertEqual(self.m_unread.call_count, 1)
        self.assertIsNone(at.session_state["unread_count"])  # 未読があったので既読化した
        at = self._click(at, "home")
        self.assertEqual(at.session_state["unread_count"], 0)

    def test_unread_increase_by_others_is_allowed_to_be_stale(self):
        # SP-84③：他の人の操作で増えた分は、次の取り直しの契機まで反映されなくてよい
        at = self.app("E003")
        self.w.add_notification("E003", "メッセージ")
        at = self._click(at, "club_search")
        self.assertNotIn("メッセージ（1）", sidebar_labels(at))
        at = self._click(at, "messages")  # 開いたときに取り直す
        self.assertEqual(at.session_state["current_page"], "messages")

    def test_role_is_held_and_menu_matches_role(self):
        for eid, expected in (("E003", False), ("E002", True), ("E001", True)):
            at = self.app(eid)
            self.assertEqual(at.session_state["can_manage"], expected, eid)
            self.assertEqual("部活の管理" in sidebar_labels(at), expected, eid)

    def test_role_invalidated_after_member_change(self):
        # 幹事E002が自分の部活（club 1）のメンバーを外す → 直後に権限の保持値を捨てる（SP-84）
        self.w.add_member(1, "E004")
        at = self.app("E002", page="club_admin")
        self.assertTrue(at.session_state["can_manage"])
        with mock.patch.object(state, "invalidate_role", wraps=state.invalidate_role) as inv:
            at.button(key="club_admin_member_remove_1_E004").click().run()
            self.assertEqual(inv.call_count, 1)
        self.assertNotIn("E004", [m["employee_id"] for m in self.w.members if m["club_id"] == 1])
        self.assertTrue(at.session_state["can_manage"])  # 取り直した結果、幹事のまま

    def test_invalidate_helpers_and_login_reset(self):
        at = self.app("E003")
        at.session_state["unread_count"] = 5
        at.session_state["can_manage"] = True
        # login() は前の人の保持値を引き継がない（直接呼んで確かめる）
        with mock.patch.object(state.st, "session_state", {"employee_id": None, "employee": None,
                                                           "current_page": "home", "page_history": [],
                                                           "unread_count": 5, "can_manage": True}) as ss:
            state.login("E005", {"name": "x"})
            self.assertIsNone(ss["unread_count"])
            self.assertIsNone(ss["can_manage"])


if __name__ == "__main__":
    unittest.main()
