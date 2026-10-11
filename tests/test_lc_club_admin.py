"""L-C: 部活の管理画面（偽repo＋AppTest）。"""
import unittest

from lc_base import LcTestCase


class ClubAdminScreen(LcTestCase):
    def admin(self, eid):
        return self.app(eid, page="club_admin")

    def test_I078_organizer_has_no_new_button(self):
        at = self.admin("E002")
        self.assertEqual(at.title[0].value, "部活の管理")
        self.assertFalse(any(b.key == "club_admin_new_open" for b in at.button))

    def test_I079_admin_has_new_button(self):
        at = self.admin("E001")
        self.assertTrue(any(b.key == "club_admin_new_open" for b in at.button))

    def test_I078_organizer_sees_only_own_clubs(self):
        at = self.admin("E002")
        self.assertEqual(len(at.selectbox(key="club_admin_picker").options), 1)

    def test_I085_cancel_confirmation_text_and_effect(self):
        ev = self.w.add_event(1)
        aid = self.w.add_application(ev, "E003")
        at = self.admin("E002")
        at.button(key=f"club_admin_event_cancel_{ev}").click().run()
        self.assertIn("この開催を中止にしますか？申込済みの人にも中止と表示されます", [w.value for w in at.warning])
        self.assertEqual(self.w.events[ev]["status"], "予定")  # 確認前は変わらない
        at.button(key=f"club_admin_event_cancel_do_{ev}").click().run()
        self.assertEqual(self.w.events[ev]["status"], "中止")
        self.assertEqual(len(self.w.notes_for("E003", "中止")), 1)
        self.assertEqual(self.w.applications[aid]["status"], "申込済み")  # 申込の状態は変わらない

    def test_I080_save_shows_saved_message(self):
        at = self.admin("E002")
        at.button[[b.label for b in at.button].index("保存する")].click().run()
        self.assertIn("保存しました", [s.value for s in at.success])

    def test_I081_blank_required_shows_error_and_does_not_save(self):
        at = self.admin("E002")
        at.text_input(key="club_admin_1_name").set_value("")
        at.button[[b.label for b in at.button].index("保存する")].click().run()
        self.assertIn("部活名を入力してください", [e.value for e in at.error])
        self.assertEqual(self.w.clubs[1]["name"], "部活A")

    def test_no_clubs_message_for_non_organizer(self):
        at = self.admin("E003")
        self.assertIn("管理できる部活がありません", [i.value for i in at.info])


if __name__ == "__main__":
    unittest.main()
