"""notification_service / action_log_service / auth_service の L-A テスト（偽repo）。"""

import unittest

import fakes
from fakes import COMMON_PASSWORD, LaTestCase
from services import action_log_service as logs
from services import auth_service, notification_service as ns
from services.errors import AuthenticationError, NotFoundError, ValidationError


class NotificationTests(LaTestCase):
    def test_I047_messages_screen_marks_four_types_only(self):
        for t in ("申込", "キャンセル", "メッセージ", "スタンプ", "中止"):
            self.w.add_notification("E003", t)
        ns.mark_read_for_messages_screen("E003")
        read = {n["type"] for n in self.w.notes_for("E003") if n["read_at"]}
        self.assertEqual(read, {"申込", "キャンセル", "メッセージ", "スタンプ"})

    def test_I138_cancel_notice_stays_unread_and_is_counted(self):
        self.w.add_notification("E003", "申込")
        self.w.add_notification("E003", "中止")
        ns.mark_read_for_messages_screen("E003")
        self.assertEqual([n["type"] for n in self.w.notes_for("E003") if n["read_at"] is None], ["中止"])
        self.assertEqual(ns.count_unread("E003"), 1)

    def test_I139_I062_notification_list_marks_all_read_including_cancel(self):
        for t in ("申込", "中止"):
            self.w.add_notification("E003", t)
        ns.mark_read_all("E003")
        self.assertEqual(ns.count_unread("E003"), 0)

    def test_I106_each_trigger_reads_its_own_range(self):
        self.w.add_notification("E003", "メッセージ")
        self.w.add_notification("E003", "中止")
        ns.mark_read_for_messages_screen("E003")
        self.assertEqual(ns.count_unread("E003"), 1)
        ns.mark_read_all("E003")
        self.assertEqual(ns.count_unread("E003"), 0)

    def test_I060_list_newest_first_with_unread_flag(self):
        self.w.add_notification("E003", "申込", read=True)
        self.w.add_notification("E003", "メッセージ", read=False)
        rows = ns.list_notifications("E003")
        self.assertEqual([r["type"] for r in rows], ["メッセージ", "申込"])
        self.assertEqual([r["is_unread"] for r in rows], [True, False])

    def test_I105_count_is_only_own_unread(self):
        self.w.add_notification("E003", "申込")
        self.w.add_notification("E003", "申込", read=True)
        self.w.add_notification("E005", "申込")
        self.assertEqual(ns.count_unread("E003"), 1)

    def test_notify_validation(self):
        with self.assertRaises(ValidationError):
            ns.notify("E003", "未知", body="x")
        with self.assertRaises(ValidationError):
            ns.notify("E003", "申込", body="   ")
        self.assertEqual(self.w.notifications, [])


class ActionLogTests(LaTestCase):
    def test_I030_search_is_recorded(self):
        logs.record_search("E003", {"location": ["東京"]})
        self.assertEqual([(l["action"], l["conditions"]) for l in self.w.action_logs], [("search_club", {"location": ["東京"]})])

    def test_I116_same_conditions_not_recorded_twice(self):
        logs.record_search("E003", {"location": ["東京"]})
        logs.record_search("E003", {"location": ["東京"]})
        self.assertEqual(len(self.w.action_logs), 1)

    def test_I117_changed_conditions_recorded(self):
        logs.record_search("E003", {"location": ["東京"]})
        logs.record_search("E003", {"location": ["大阪"]})
        self.assertEqual(len(self.w.action_logs), 2)

    def test_I043_view_club_recorded(self):
        logs.record_view_club("E003", 1)
        self.assertEqual([(l["action"], l["club_id"]) for l in self.w.action_logs], [("view_club", 1)])

    def test_I118_consecutive_same_club_not_recorded_twice(self):
        logs.record_view_club("E003", 1)
        logs.record_view_club("E003", 1)
        self.assertEqual(len(self.w.action_logs), 1)

    def test_I192_A_B_A_records_three(self):
        for cid in (1, 2, 1):
            logs.record_view_club("E003", cid)
        self.assertEqual([l["club_id"] for l in self.w.action_logs], [1, 2, 1])

    def test_dedup_is_per_employee(self):
        logs.record_view_club("E003", 1)
        logs.record_view_club("E005", 1)
        self.assertEqual(len(self.w.action_logs), 2)

    def test_I119_no_employee_search_recorder_exists(self):
        # 社員検索を記録する関数は無い（記録できる action は search_club / view_club / apply のみ）。
        recorders = sorted(n for n in dir(logs) if n.startswith("record_"))
        self.assertEqual(recorders, ["record_apply", "record_search", "record_view_club"])

    def test_validation_required_fields(self):
        with self.assertRaises(ValidationError):
            logs.record_search("E003", None)
        with self.assertRaises(ValidationError):
            logs.record_view_club("E003", None)
        with self.assertRaises(ValidationError):
            logs.record_apply("E003", None)
        self.assertEqual(self.w.action_logs, [])


class AuthTests(LaTestCase):
    def test_I010_login_ok_returns_employee(self):
        self.assertEqual(auth_service.login("E002", COMMON_PASSWORD)["id"], "E002")

    def test_I011_id_case_insensitive(self):
        for eid in ("e002", " E002 ", "E002"):
            self.assertEqual(auth_service.login(eid, COMMON_PASSWORD)["id"], "E002")

    def test_I012_wrong_id_or_password_same_error(self):
        errors = []
        for eid, pw in (("E999", COMMON_PASSWORD), ("E002", "wrong"), ("E999", "wrong"), ("", "")):
            with self.assertRaises(AuthenticationError) as cm:
                auth_service.login(eid, pw)
            errors.append((type(cm.exception), str(cm.exception)))
        self.assertEqual(len(set(errors)), 1)  # どちらが誤りかは区別できない

    def test_I120_roles(self):
        self.assertEqual(auth_service.get_role("E001"), "admin")
        self.assertEqual(auth_service.get_role("E002", 1), "organizer")
        self.assertEqual(auth_service.get_role("E002", 2), "member")
        self.assertEqual(auth_service.get_role("E003", 1), "member")
        self.assertEqual(auth_service.get_role("E001", 1), "admin")

    def test_I194_role_edge_cases(self):
        with self.assertRaises(NotFoundError):
            auth_service.get_role("E001", 999)
        self.assertEqual(auth_service.get_role("E999"), "member")
        self.assertEqual(auth_service.get_role("E002"), "member")  # 部活ID省略は幹事判定しない
        self.assertEqual(auth_service.get_role("E001"), "admin")

    def test_I195_admin_only_and_organizer_only_both_manage(self):
        # サービス層の判定のみ（サイドバー表示は L-C）。app.py と同じ式を使う。
        def can_manage(eid):
            return auth_service.get_role(eid) == auth_service.ROLE_ADMIN or auth_service.is_organizer(eid)
        self.assertTrue(can_manage("E001"))
        self.assertTrue(can_manage("E002"))
        self.assertFalse(can_manage("E003"))
        self.assertFalse(auth_service.is_organizer("E001"))  # 運営者かどうかは見ない
        self.assertFalse(auth_service.is_organizer("E999"))
        self.assertTrue(auth_service.is_organizer("e002"))


if __name__ == "__main__":
    unittest.main()
