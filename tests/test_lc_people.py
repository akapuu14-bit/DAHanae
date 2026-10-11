"""L-C: 社員検索・社員プロフィールの画面（偽repo＋AppTest）。"""
import unittest

from lc_base import LcTestCase


class EmployeeSearch(LcTestCase):
    def test_I063_notice_at_top(self):
        at = self.app("E003", page="employee_search")
        self.assertEqual(at.info[0].value, "興味・経験と参加可能時間は、本人が公開にしたものだけが検索・表示されます")

    def test_I070_paging_20_and_more_button(self):
        for i in range(6, 31):
            self.w.add_employee(f"E{i:03d}", name=f"社員{i:03d}")
        at = self.app("E003", page="employee_search")
        self.assertFalse(at.exception)
        profile_buttons = [b for b in at.button if b.key and b.key.startswith("employee_search_profile_")]
        self.assertEqual(len(profile_buttons), 20)
        self.assertTrue(any(b.key == "employee_search_more" for b in at.button))
        at.button(key="employee_search_more").click().run()
        profile_buttons = [b for b in at.button if b.key and b.key.startswith("employee_search_profile_")]
        self.assertGreater(len(profile_buttons), 20)

    def test_profile_button_goes_to_profile(self):
        at = self.app("E003", page="employee_search")
        at.button(key="employee_search_profile_E002").click().run()
        self.assertEqual(at.session_state["current_page"], "employee_profile")
        self.assertEqual(at.session_state["target_employee_id"], "E002")


class EmployeeProfile(LcTestCase):
    def prof(self, viewer="E003", target="E005"):
        return self.app(viewer, page="employee_profile", target_employee_id=target)

    def test_I072_basic_fields(self):
        at = self.prof()
        self.assertEqual(at.title[0].value, "一般五郎")
        self.assertIn("開発・東京・2020年入社・新卒", [w.value for w in at.markdown])

    def test_I073_private_shows_hidden_label(self):
        self.w.employees["E005"]["interests_public"] = False
        self.w.employees["E005"]["slots_public"] = False
        at = self.prof()
        self.assertEqual([m.value for m in at.markdown].count("非公開"), 2)

    def test_I076_other_cannot_see_toggles(self):
        at = self.prof("E003", "E005")
        self.assertEqual(len(at.toggle), 0)

    def test_I075_self_sees_toggles_and_saves(self):
        at = self.prof("E005", "E005")
        self.assertEqual([t.label for t in at.toggle], ["興味・経験を公開する", "参加可能時間を公開する"])
        at.toggle(key="profile_toggle_interests").set_value(False).run()
        self.assertFalse(self.w.employees["E005"]["interests_public"])

    def test_I074_club_card_goes_to_detail(self):
        self.w.add_member(1, "E005")
        at = self.prof("E003", "E005")
        btns = [b for b in at.button if b.key and b.key.startswith("employee_profile") and "back" not in b.key]
        self.assertTrue(btns, [b.key for b in at.button])
        btns[0].click().run()
        self.assertEqual(at.session_state["current_page"], "club_detail")
        self.assertEqual(at.session_state["target_club_id"], 1)


if __name__ == "__main__":
    unittest.main()
