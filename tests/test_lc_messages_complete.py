"""L-C: メッセージ・申込完了の画面（偽repo＋AppTest）。"""
import unittest

from lc_base import LcTestCase

RULE = "体験参加は入部ではありません／参加は毎回でなくてOK／活動後の集まりは任意です／キャンセルもできます"


class Messages(LcTestCase):
    def labels(self, at):
        return [b.label for b in at.button]

    def test_I046_tabs_only_for_organizer(self):
        self.assertEqual([t.label for t in self.app("E002", page="messages").tabs], ["自分の申込", "届いた申込"])
        self.assertEqual(len(self.app("E003", page="messages").tabs), 0)

    def test_I057_I058_empty_messages(self):
        at = self.app("E002", page="messages")
        infos = [i.value for i in at.info]
        # 画面の実文言（テスト設計の例文と差あり→備考に記録）
        self.assertIn("まだ申込はありません。部活を探して、気になる開催に申し込んでみましょう。", infos)
        self.assertIn("まだ申込は届いていません。", infos)

    def test_I057_wording_per_spec(self):
        """仕様 SP-42: 自分の申込0件は『まだ申込はありません。『部活を探す』から気になる部活を見つけてみてください』。"""
        at = self.app("E003", page="messages")
        self.assertIn("まだ申込はありません。『部活を探す』から気になる部活を見つけてみてください", [i.value for i in at.info])

    def test_I058_wording_per_spec(self):
        """仕様 SP-42: 届いた申込0件は『まだ届いた申込はありません』。"""
        at = self.app("E002", page="messages")
        self.assertIn("まだ届いた申込はありません", [i.value for i in at.info])

    def test_I051_canceled_view_only(self):
        ev = self.w.add_event(1)
        self.w.add_application(ev, "E003", status="キャンセル")
        at = self.app("E003", page="messages")
        self.assertIn("キャンセル済みのため、やり取りは閲覧のみです", [c.value for c in at.caption])
        self.assertEqual(len(at.text_area), 0)

    def test_I054_stamp_button_only_first_time(self):
        ev = self.w.add_event(1)
        self.w.add_application(ev, "E003", is_first_time=True)
        self.w.add_application(ev, "E005", is_first_time=False)
        at = self.app("E002", page="messages")
        self.assertEqual(self.labels(at).count("確認したよ👍"), 1)

    def test_stamp_click_confirms(self):
        ev = self.w.add_event(1)
        aid = self.w.add_application(ev, "E003", is_first_time=True)
        at = self.app("E002", page="messages")
        at.button(key=f"messages_stamp_{aid}").click().run()
        self.assertIsNotNone(self.w.applications[aid]["confirmed_at"])

    def test_I049_cancel_requires_confirmation(self):
        ev = self.w.add_event(1)
        aid = self.w.add_application(ev, "E003")
        at = self.app("E003", page="messages")
        at.button(key=f"messages_cancel_open_{aid}").click().run()
        self.assertIn("この開催の申込をキャンセルしますか？", [w.value for w in at.warning])
        self.assertEqual(self.w.applications[aid]["status"], "申込済み")  # まだ変わらない
        at.button(key=f"messages_cancel_do_{aid}").click().run()
        self.assertEqual(self.w.applications[aid]["status"], "キャンセル")

    def test_cancel_stop_keeps_application(self):
        ev = self.w.add_event(1)
        aid = self.w.add_application(ev, "E003")
        at = self.app("E003", page="messages")
        at.button(key=f"messages_cancel_open_{aid}").click().run()
        at.button(key=f"messages_cancel_stop_{aid}").click().run()
        self.assertEqual(self.w.applications[aid]["status"], "申込済み")

    def test_I055_applicant_sees_confirmed(self):
        ev = self.w.add_event(1)
        self.w.add_application(ev, "E003", is_first_time=True, confirmed_at="t")
        at = self.app("E003", page="messages")
        self.assertIn("幹事が確認しました", [s.value for s in at.success])  # 先頭の✅はアイコンとして分離される

    def test_I059_empty_body_warning(self):
        ev = self.w.add_event(1)
        aid = self.w.add_application(ev, "E003")
        at = self.app("E003", page="messages")
        at.text_area(key=f"messages_body_mine_{aid}").set_value("  ")
        at.button[[b.label for b in at.button].index("送信する")].click().run()
        self.assertIn("メッセージを入力してから送信してください", [w.value for w in at.warning])

    def test_send_message_ok(self):
        ev = self.w.add_event(1)
        aid = self.w.add_application(ev, "E003")
        at = self.app("E003", page="messages")
        at.text_area(key=f"messages_body_mine_{aid}").set_value("こんにちは")
        at.button[[b.label for b in at.button].index("送信する")].click().run()
        self.assertEqual([m["body"] for m in self.w.messages], ["こんにちは"])

    def test_opening_marks_related_notifications_read(self):
        self.w.add_notification("E003", "メッセージ")
        self.app("E003", page="messages")
        self.assertEqual([n for n in self.w.notifications if n["read_at"] is None], [])

    def test_cancel_notice_not_read_by_messages_screen(self):
        """SP-70: 種類「中止」はメッセージ画面では既読にならない（通知一覧では既読）。"""
        self.w.add_notification("E003", "中止", event_id=1)
        self.app("E003", page="messages")
        self.assertEqual(len([n for n in self.w.notifications if n["read_at"] is None]), 1)


class ApplicationComplete(LcTestCase):
    CTX = {"application_id": 1, "is_first_time": True, "club_name": "部活A", "organizer_name": "幹事一郎",
           "event_date": "2026-10-15", "start_time": "19:00:00", "end_time": "21:00:00",
           "meeting_place": "会議室", "meeting_time": None, "belongings": "貸し出しあり", "message_text": "よろしく"}

    def test_I045_no_context_goes_home(self):
        at = self.app("E003", page="application_complete")
        self.assertEqual(at.session_state["current_page"], "home")

    def test_I044_order_of_sections(self):
        at = self.app("E003", page="application_complete", pending_application_context=dict(self.CTX))
        self.assertEqual(at.title[0].value, "申込が完了しました")
        self.assertIn("申し込みました！幹事の幹事一郎さんに届いています", [s.value for s in at.success])
        self.assertEqual([s.value for s in at.subheader], ["申込内容", "次に起きること", "当日の情報"])
        self.assertIn(RULE, [i.value for i in at.info])
        self.assertIn("キャンセルは、メッセージ画面からできます", [c.value for c in at.caption])
        self.assertEqual([b.label for b in at.button if b.key.startswith("application_complete")],
                         ["メッセージを見る", "ほかの部活も見る"])
        writes = [m.value for m in at.markdown]
        self.assertNotIn("集合時刻", " ".join(writes))  # 集合時刻なしは行ごと出ない

    def test_I044_buttons_navigate_and_clear_context(self):
        at = self.app("E003", page="application_complete", pending_application_context=dict(self.CTX))
        at.button(key="application_complete_messages").click().run()
        self.assertEqual(at.session_state["current_page"], "messages")
        self.assertIsNone(at.session_state["pending_application_context"])


if __name__ == "__main__":
    unittest.main()
