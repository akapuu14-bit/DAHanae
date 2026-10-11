"""application_service の L-A テスト（偽repo）。関数名の I-xxx は テスト設計.md の結合テストID。"""

import unittest

import fakes
from fakes import LaTestCase
from services import application_service as svc
from services import notification_service
from services.errors import ConflictError, NotFoundError, PermissionDeniedError, ValidationError


class ApplyTests(LaTestCase):
    def setUp(self):
        super().setUp()
        self.ev = self.w.add_event(1, day_offset=1)

    def test_I092_apply_creates_all_records(self):
        r = svc.apply(self.ev, "E003", "よろしく")
        app = self.w.applications[r["application_id"]]
        self.assertEqual(app["status"], "申込済み")
        self.assertEqual([m["body"] for m in self.w.messages], ["よろしく"])
        notes = self.w.notes_for("E002", "申込")
        self.assertEqual(len(notes), 1)
        self.assertEqual([(l["action"], l["club_id"], l["employee_id"]) for l in self.w.action_logs], [("apply", 1, "E003")])

    def test_I115_general_employee_can_apply_and_cancel(self):
        a = svc.apply(self.ev, "E005", None)["application_id"]
        svc.cancel(a, "E005")
        self.assertEqual(self.w.applications[a]["status"], "キャンセル")

    def test_I093_empty_message_not_saved_but_rest_runs(self):
        for text in ("", "   ", None):
            w = fakes.World(); fakes.install(w); ev = w.add_event(1)
            svc.apply(ev, "E003", text)
            self.assertEqual(w.messages, [], repr(text))
            self.assertEqual(len(w.notes_for("E002", "申込")), 1)
            self.assertEqual(len(w.action_logs), 1)

    def test_I094_organizer_self_apply_no_notification(self):
        r = svc.apply(self.ev, "E002", "自分で")
        self.assertIn(r["application_id"], self.w.applications)
        self.assertEqual(self.w.notes_for("E002"), [])

    def test_I098_reapply_after_cancel_makes_new_application(self):
        a1 = svc.apply(self.ev, "E003", "最初")["application_id"]
        svc.cancel(a1, "E003")
        a2 = svc.apply(self.ev, "E003", "再申込")["application_id"]
        self.assertNotEqual(a1, a2)
        self.assertEqual(self.w.applications[a1]["status"], "キャンセル")
        self.assertEqual(self.w.applications[a2]["status"], "申込済み")
        self.assertEqual([m["application_id"] for m in self.w.messages], [a1, a2])

    def test_I041_duplicate_apply_conflict_already_applied(self):
        svc.apply(self.ev, "E003", None)
        with self.assertRaises(ConflictError) as cm:
            svc.apply(self.ev, "E003", None)
        self.assertEqual(cm.exception.reason, "already_applied")
        self.assertEqual(len([a for a in self.w.applications.values() if a["applicant_id"] == "E003"]), 1)

    def test_I042_canceled_event_conflict_not_open(self):
        self.w.events[self.ev]["status"] = "中止"
        with self.assertRaises(ConflictError) as cm:
            svc.apply(self.ev, "E003", None)
        self.assertEqual(cm.exception.reason, "not_open")
        self.assertEqual(self.w.applications, {})

    def test_I042_started_event_conflict_not_open(self):
        ev = self.w.add_event(1, event_date=self.w.today(), start="11:00:00", end="13:00:00")
        with self.assertRaises(ConflictError) as cm:
            svc.apply(ev, "E003", None)
        self.assertEqual(cm.exception.reason, "not_open")

    def test_I042_unknown_event_not_found(self):
        with self.assertRaises(NotFoundError):
            svc.apply(9999, "E003", None)

    def test_I181_start_time_boundary(self):
        exact = self.w.add_event(1, event_date=self.w.today(), start="12:00:00", end="13:00:00")
        with self.assertRaises(ConflictError) as cm:
            svc.apply(exact, "E003", None)
        self.assertEqual(cm.exception.reason, "not_open")
        self.assertEqual(self.w.applications, {})
        just_before = self.w.add_event(1, event_date=self.w.today(), start="12:01:00", end="13:00:00")
        self.assertIn("application_id", svc.apply(just_before, "E003", None))


class FirstTimeTests(LaTestCase):
    def setUp(self):
        super().setUp()
        self.ev = self.w.add_event(1, day_offset=1)

    def test_I099_non_member_no_past_is_first_time(self):
        self.assertTrue(svc.apply(self.ev, "E003", None)["is_first_time"])

    def test_I100_member_is_not_first_time(self):
        self.w.add_member(1, "E003")
        self.assertFalse(svc.apply(self.ev, "E003", None)["is_first_time"])

    def test_I101_past_non_canceled_application_is_not_first_time(self):
        past = self.w.add_event(1, day_offset=-3)
        self.w.add_application(past, "E003", "申込済み")
        self.assertFalse(svc.apply(self.ev, "E003", None)["is_first_time"])

    def test_I102_past_canceled_only_is_first_time(self):
        past = self.w.add_event(1, day_offset=-3)
        self.w.add_application(past, "E003", "キャンセル")
        self.assertTrue(svc.apply(self.ev, "E003", None)["is_first_time"])


class CancelTests(LaTestCase):
    def setUp(self):
        super().setUp()
        self.ev = self.w.add_event(1, day_offset=1)
        self.app = svc.apply(self.ev, "E003", "x")["application_id"]
        self.w.notifications.clear()

    def test_I049_I095_cancel_before_start(self):
        svc.cancel(self.app, "E003")
        row = self.w.applications[self.app]
        self.assertEqual(row["status"], "キャンセル")
        self.assertIsNotNone(row["canceled_at"])
        self.assertEqual(len(self.w.notes_for("E002", "キャンセル")), 1)

    def test_I096_other_user_cannot_cancel(self):
        for other in ("E005", "E002", "E001"):
            with self.assertRaises(PermissionDeniedError):
                svc.cancel(self.app, other)
        self.assertEqual(self.w.applications[self.app]["status"], "申込済み")

    def test_I050_I097_start_time_boundary(self):
        for start in ("12:00:00", "11:00:00"):  # ちょうど / 開始後
            ev = self.w.add_event(1, event_date=self.w.today(), start=start, end="13:00:00")
            aid = self.w.add_application(ev, "E003")
            with self.assertRaises(ConflictError):
                svc.cancel(aid, "E003")
            self.assertEqual(self.w.applications[aid]["status"], "申込済み", start)
        ev = self.w.add_event(1, event_date=self.w.today(), start="12:01:00", end="13:00:00")
        aid = self.w.add_application(ev, "E003")
        svc.cancel(aid, "E003")
        self.assertEqual(self.w.applications[aid]["status"], "キャンセル")

    def test_I182_double_cancel_conflict_no_second_notification(self):
        svc.cancel(self.app, "E003")
        with self.assertRaises(ConflictError):
            svc.cancel(self.app, "E003")
        self.assertEqual(len(self.w.notes_for("E002", "キャンセル")), 1)

    def test_I183_organizer_cancel_own_application_no_notification(self):
        a = svc.apply(self.w.add_event(1, day_offset=2), "E002", None)["application_id"]
        self.w.notifications.clear()
        svc.cancel(a, "E002")
        self.assertEqual(self.w.applications[a]["status"], "キャンセル")
        self.assertIsNotNone(self.w.applications[a]["canceled_at"])
        self.assertEqual(self.w.notes_for("E002"), [])

    def test_I095_unknown_application_not_found(self):
        with self.assertRaises(NotFoundError):
            svc.cancel(9999, "E003")


class SendMessageTests(LaTestCase):
    def setUp(self):
        super().setUp()
        self.ev = self.w.add_event(1, day_offset=1)
        self.app = svc.apply(self.ev, "E003", None)["application_id"]
        self.w.notifications.clear()

    def test_I053_I184_trimmed_body_and_notification_both_directions(self):
        svc.send_message(self.app, "E003", "  こんにちは  ")
        self.assertEqual(self.w.messages[-1]["body"], "こんにちは")
        n = self.w.notes_for("E002", "メッセージ")
        self.assertEqual(len(n), 1)
        self.assertEqual(n[0]["body"], "新しいメッセージがあります")
        svc.send_message(self.app, "E002", "\t返信\n")
        self.assertEqual(self.w.messages[-1]["body"], "返信")
        self.assertEqual(len(self.w.notes_for("E003", "メッセージ")), 1)  # I-053 の通知側

    def test_I185_and_I059_empty_body_validation_no_notification(self):
        for body in ("", "   ", "　"):
            with self.assertRaises(ValidationError):
                svc.send_message(self.app, "E003", body)
        self.assertEqual(self.w.messages, [])
        self.assertEqual(self.w.notes_for("E002"), [])

    def test_I186_organizer_self_application_no_notification(self):
        a = svc.apply(self.w.add_event(1, day_offset=2), "E002", None)["application_id"]
        self.w.notifications.clear()
        svc.send_message(a, "E002", "メモ")
        self.assertEqual(self.w.messages[-1]["body"], "メモ")
        self.assertEqual(self.w.notifications, [])

    def test_I103_third_party_cannot_send(self):
        for other in ("E001", "E004", "E005"):  # 運営者・他部活の幹事・一般
            with self.assertRaises(PermissionDeniedError):
                svc.send_message(self.app, other, "割り込み")
        self.assertEqual(self.w.messages, [])

    def test_I104_canceled_application_conflict(self):
        svc.cancel(self.app, "E003")
        with self.assertRaises(ConflictError):
            svc.send_message(self.app, "E003", "まだ送れる？")

    def test_I187_error_order(self):
        with self.assertRaises(NotFoundError):
            svc.send_message(9999, "E003", "")
        with self.assertRaises(PermissionDeniedError):
            svc.send_message(self.app, "E005", "")  # 当事者でない＋空 → 権限が先
        svc.cancel(self.app, "E003")
        with self.assertRaises(ValidationError):
            svc.send_message(self.app, "E003", "")  # キャンセル済み＋空 → 入力が先
        with self.assertRaises(ConflictError):
            svc.send_message(self.app, "E003", "本文あり")


class ConfirmStampTests(LaTestCase):
    def setUp(self):
        super().setUp()
        self.ev = self.w.add_event(1, day_offset=1)
        self.first = svc.apply(self.ev, "E003", None)["application_id"]  # 初参加
        self.w.add_member(1, "E005")
        self.notfirst = svc.apply(self.ev, "E005", None)["application_id"]  # 初参加でない
        self.w.notifications.clear()

    def test_I110_I055_confirm_records_and_notifies_applicant(self):
        svc.confirm_stamp(self.first, "E002")
        self.assertIsNotNone(self.w.applications[self.first]["confirmed_at"])
        self.assertEqual(len(self.w.notes_for("E003", "スタンプ")), 1)

    def test_I056_second_press_conflict(self):
        svc.confirm_stamp(self.first, "E002")
        with self.assertRaises(ConflictError):
            svc.confirm_stamp(self.first, "E002")
        self.assertEqual(len(self.w.notes_for("E003", "スタンプ")), 1)

    def test_I188_canceled_application_conflict(self):
        svc.cancel(self.first, "E003")
        self.w.notifications.clear()
        with self.assertRaises(ConflictError):
            svc.confirm_stamp(self.first, "E002")
        self.assertIsNone(self.w.applications[self.first]["confirmed_at"])
        self.assertEqual(self.w.notifications, [])

    def test_I189_non_organizer_permission(self):
        for other in ("E004", "E001", "E003"):
            with self.assertRaises(PermissionDeniedError):
                svc.confirm_stamp(self.first, other)

    def test_I190_not_first_time_conflict(self):
        with self.assertRaises(ConflictError):
            svc.confirm_stamp(self.notfirst, "E002")

    def test_I191_error_order(self):
        with self.assertRaises(NotFoundError):
            svc.confirm_stamp(9999, "E002")
        with self.assertRaises(PermissionDeniedError):  # 幹事でない＋is_first_time false
            svc.confirm_stamp(self.notfirst, "E004")


class UnreadCountTests(LaTestCase):
    """I-105/107/108/109：申込で作られる通知が未読件数（SP-70）にどう入るか。"""

    def setUp(self):
        super().setUp()
        self.ev = self.w.add_event(1, day_offset=1)

    def test_I107_non_member_new_application_counted(self):
        svc.apply(self.ev, "E003", None)
        self.assertEqual(notification_service.count_unread("E002"), 1)

    def test_I108_existing_member_application_counted(self):
        self.w.add_member(1, "E005")
        svc.apply(self.ev, "E005", None)
        self.assertEqual(notification_service.count_unread("E002"), 1)

    def test_I109_organizer_self_application_not_counted(self):
        svc.apply(self.ev, "E002", None)
        self.assertEqual(notification_service.count_unread("E002"), 0)

    def test_I105_unread_count_matches_unread_rows(self):
        svc.apply(self.ev, "E003", None)
        self.w.add_member(1, "E005")
        svc.apply(self.ev, "E005", None)
        self.assertEqual(notification_service.count_unread("E002"), 2)


class ListTests(LaTestCase):
    def test_I048_my_applications_order(self):
        w = self.w
        e1 = w.add_event(1, day_offset=3)
        e2 = w.add_event(1, day_offset=1)
        e_past = w.add_event(1, day_offset=-2)
        e_cancel = w.add_event(2, day_offset=2)
        a1 = w.add_application(e1, "E003")
        a2 = w.add_application(e2, "E003")
        a_past = w.add_application(e_past, "E003")
        a_cancel = w.add_application(e_cancel, "E003", "キャンセル")
        ids = [a["id"] for a in svc.list_my_applications("E003")]
        self.assertEqual(ids[:2], [a2, a1])  # 前側は開催日が近い順
        self.assertEqual(set(ids[2:]), {a_past, a_cancel})  # 終わった開催・キャンセルは後ろ
        self.assertEqual(ids[2:], [a_cancel, a_past])  # 後ろ側は新しい順（開催日の遅い方が先）
        for a in svc.list_my_applications("E003"):
            self.assertEqual(a["organizer"]["id"] in ("E002", "E004"), True)

    def test_I052_received_applications_unread_first_then_newest(self):
        w = self.w
        ev = w.add_event(1, day_offset=1)
        a1 = w.add_application(ev, "E003")
        a2 = w.add_application(ev, "E005")
        a3 = w.add_application(ev, "E001")
        w.add_notification("E002", "申込", read=False, application_id=a1)
        ids = [a["id"] for a in svc.list_received_applications("E002")]
        self.assertEqual(ids, [a1, a3, a2])  # 未読の a1 が先頭、残りは新しい順

    def test_received_applications_empty_for_non_organizer(self):
        self.assertEqual(svc.list_received_applications("E003"), [])


if __name__ == "__main__":
    unittest.main()
