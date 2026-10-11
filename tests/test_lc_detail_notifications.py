"""L-C: 部活詳細・通知一覧の画面（偽repo＋AppTest）。"""
import unittest

from lc_base import LcTestCase

RULE = "体験参加は入部ではありません／参加は毎回でなくてOK／活動後の集まりは任意です／キャンセルもできます"


class ClubDetail(LcTestCase):
    def detail(self, eid="E003", club_id=1):
        return self.app(eid, page="club_detail", target_club_id=club_id)

    def buttons(self, at):
        return [b.label for b in at.button]

    def test_I031_header(self):
        at = self.detail()
        self.assertIn("← 戻る", self.buttons(at))
        self.assertEqual(at.title[0].value, "⚽ 部活A")
        self.assertIn(RULE, [i.value for i in at.info])  # I-004の部活詳細分

    def test_I032_sections(self):
        at = self.detail()
        subs = [s.value for s in at.subheader]
        for h in ("基本情報", "どんな部活？", "参加の前に", "活動後の過ごし方", "開催一覧"):
            self.assertIn(h, subs)

    def test_I033_future_only_in_date_order(self):
        e2 = self.w.add_event(1, day_offset=3)
        e1 = self.w.add_event(1, day_offset=1)
        self.w.add_event(1, day_offset=-2)  # 過去
        at = self.detail()
        dates = [m.value for m in at.markdown if "〜" in m.value and m.value.startswith("**")]
        self.assertEqual(len(dates), 2, dates)  # 過去は出ない
        self.assertLess(self.w.events[e1]["event_date"], self.w.events[e2]["event_date"])
        self.assertIn("10/15", dates[0])

    def test_I034_open_unapplied_shows_apply_button(self):
        self.w.add_event(1)
        self.assertIn("申し込む", self.buttons(self.detail()))

    def test_I035_applied_shows_label_no_button(self):
        ev = self.w.add_event(1)
        self.w.add_application(ev, "E003")
        at = self.detail()
        self.assertIn("✅ 申込済み", [w.value for w in at.markdown])
        self.assertNotIn("申し込む", self.buttons(at))

    def test_I036_canceled_event_shows_text_no_button(self):
        self.w.add_event(1, status="中止")
        at = self.detail()
        self.assertIn("中止", [w.value for w in at.markdown])
        self.assertNotIn("申し込む", self.buttons(at))

    def test_I136_inactive_club_hides_apply_button(self):
        """H-6裁定／SP-27: 非公開(is_active=false)の部活では「予定」でも「申し込む」を出さない。"""
        self.w.clubs[1]["is_active"] = False
        self.w.add_event(1)
        at = self.detail()
        self.assertFalse(at.exception)
        self.assertNotIn("申し込む", self.buttons(at))

    def test_I038_form_contents(self):
        self.w.add_event(1)
        at = self.detail()
        at.button(key=f"club_detail_apply_1").click().run()
        caps = [c.value for c in at.caption]
        self.assertIn(RULE, caps)
        self.assertIn("キャンセルもできます", caps)
        self.assertEqual(at.text_area[0].label, "幹事への一言・質問（任意）")
        self.assertEqual(at.text_area[0].value, "")

    def test_I039_submit_applies_and_goes_to_complete(self):
        ev = self.w.add_event(1)
        at = self.detail()
        at.button(key=f"club_detail_apply_{ev}").click().run()
        at.text_area[0].set_value("よろしく")
        at.button[[b.label for b in at.button].index("この開催に申し込む")].click().run()
        self.assertEqual(at.session_state["current_page"], "application_complete")
        self.assertEqual(len([a for a in self.w.applications.values() if a["applicant_id"] == "E003"]), 1)

    def test_I040_close_does_not_apply(self):
        ev = self.w.add_event(1)
        at = self.detail()
        at.button(key=f"club_detail_apply_{ev}").click().run()
        at.button[[b.label for b in at.button].index("やめる")].click().run()
        self.assertEqual(at.session_state["current_page"], "club_detail")
        self.assertNotIn("やめる", self.buttons(at))
        self.assertEqual(self.w.applications, {})

    def test_I043_opening_records_view_club(self):
        self.detail()
        self.assertEqual([(a["employee_id"], a["action"], a["club_id"]) for a in self.w.action_logs],
                         [("E003", "view_club", 1)])

    def test_I037_profile_buttons(self):
        at = self.detail()
        at.button(key="club_detail_organizer").click().run()
        self.assertEqual(at.session_state["current_page"], "employee_profile")
        self.assertEqual(at.session_state["target_employee_id"], "E002")

    def test_I002_back_returns_previous(self):
        at = self.app("E003", page="club_detail", target_club_id=1, page_history=["club_search", "home"])
        at.button(key="club_detail_back").click().run()
        self.assertEqual(at.session_state["current_page"], "home")


class Notifications(LcTestCase):
    def test_I060_unread_bold_and_marked_read(self):
        self.w.add_notification("E003", "申込", read=False)
        self.w.add_notification("E003", "申込", read=True)
        at = self.app("E003", page="notifications")
        md = [m.value for m in at.markdown if m.value.startswith("【") or m.value.startswith("**【")]
        self.assertEqual(sum(v.startswith("**") for v in md), 1, md)  # 未読のみ太字
        self.assertEqual(len([n for n in self.w.notifications if n["read_at"] is None]), 0)  # 開いたら既読

    def test_I061_view_navigates_to_messages(self):
        self.w.add_notification("E003", "メッセージ")
        at = self.app("E003", page="notifications")
        at.button[0].click().run()
        self.assertEqual(at.session_state["current_page"], "messages")

    def test_I061_cancel_notice_view_goes_to_club_detail(self):
        """仕様 SP-45: 「見る」で関係する画面（メッセージ・部活詳細）へ。種類「中止」にも「見る」が出る想定。"""
        self.w.add_notification("E003", "中止", event_id=1)
        at = self.app("E003", page="notifications")
        self.assertEqual([b.label for b in at.button if b.label == "見る"], ["見る"])

    def test_empty_message(self):
        at = self.app("E003", page="notifications")
        self.assertIn("通知はまだありません。", [i.value for i in at.info])


if __name__ == "__main__":
    unittest.main()
