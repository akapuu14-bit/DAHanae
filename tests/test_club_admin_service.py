"""club_admin_service（S10）の L-A テスト（偽repo）。

画面の文言・ボタン表示（I-078/079/085/080/081/087/088/082 の表示部分）は L-C のため対象外。
ここでは権限・判定順・理由コード・保存結果・通知を確認する。
"""

import unittest
from datetime import datetime, timezone

from fakes import CLUB_FIELDS, JST, LaTestCase
from services import club_admin_service as ca
from services.errors import ConflictError, NotFoundError, PermissionDeniedError, ValidationError

REQUIRED = ("name", "icon", "activity_id", "location", "slot", "frequency", "level",
            "fact_adult_starters", "message", "fee", "rental", "join_leave", "after_activity",
            "organizer_id")
CHOICE_KEYS = ("location", "slot", "frequency", "level", "fact_adult_starters", "fee", "rental",
               "join_leave", "after_activity")


def reason(cm):
    return str(cm.exception)


class ListManageableTests(LaTestCase):
    def test_I078_organizer_sees_own_clubs_including_inactive(self):
        self.w.add_club(3, organizer_id="E002", name="非公開", is_active=False)
        got = ca.list_manageable_clubs("E002")
        self.assertEqual([c["club_id"] for c in got], [1, 3])
        self.assertFalse(got[1]["is_active"])

    def test_I079_admin_sees_all(self):
        self.w.add_club(3, organizer_id="E002", is_active=False)
        self.assertEqual([c["club_id"] for c in ca.list_manageable_clubs("E001")], [1, 2, 3])

    def test_I148_general_employee_gets_empty_list(self):
        self.assertEqual(ca.list_manageable_clubs("E003"), [])


class ClubFieldTests(LaTestCase):
    def test_I080_save_updates_fields(self):
        ca.update_club(1, "E002", {"name": "新名称", "message": "更新"})
        self.assertEqual((self.w.clubs[1]["name"], self.w.clubs[1]["message"]), ("新名称", "更新"))

    def test_I153_I081_I080_each_required_field_blank_is_rejected(self):
        for key in REQUIRED:
            for blank in ("", None):
                with self.assertRaises(ValidationError, msg=f"{key}={blank!r}") as cm:
                    ca.update_club(1, "E001", {key: blank})
                self.assertEqual(reason(cm), f"required:{key}")

    def test_I153_create_club_missing_required_key(self):
        for key in REQUIRED:
            fields = {k: v for k, v in CLUB_FIELDS.items() if k != key}
            with self.assertRaises(ValidationError, msg=key) as cm:
                ca.create_club("E001", fields)
            self.assertEqual(reason(cm), f"required:{key}")
        self.assertEqual(sorted(self.w.clubs), [1, 2])

    def test_I154_whitespace_only_same_as_blank(self):
        for key in REQUIRED:
            with self.assertRaises(ValidationError, msg=key) as cm:
                ca.update_club(1, "E001", {key: "   "})
            self.assertEqual(reason(cm), f"required:{key}")

    def test_I155_optional_fields_may_be_empty(self):
        ca.update_club(1, "E002", {"schedule_note": "", "fee_note": None, "belongings_note": "", "mood_tags": []})
        self.assertEqual(self.w.clubs[1]["mood_tags"], [])

    def test_I156_values_outside_choices_rejected(self):
        for key in CHOICE_KEYS:
            with self.assertRaises(ValidationError, msg=key) as cm:
                ca.update_club(1, "E002", {key: "選択肢外"})
            self.assertEqual(reason(cm), f"invalid:{key}")

    def test_I157_unknown_activity_or_organizer_rejected(self):
        with self.assertRaises(ValidationError) as cm:
            ca.update_club(1, "E001", {"activity_id": 99})
        self.assertEqual(reason(cm), "invalid:activity_id")
        with self.assertRaises(ValidationError) as cm:
            ca.update_club(1, "E001", {"organizer_id": "E999"})
        self.assertEqual(reason(cm), "invalid:organizer_id")
        self.assertEqual(self.w.clubs[1]["organizer_id"], "E002")

    def test_I158_mood_tags_limit_and_allowed_values(self):
        four = ["ゆるめ", "しっかり練習", "黙々と集中", "わいわい賑やか"]
        for tags in (four, ["未知タグ"]):
            with self.assertRaises(ValidationError) as cm:
                ca.update_club(1, "E002", {"mood_tags": tags})
            self.assertEqual(reason(cm), "invalid:mood_tags")
        ca.update_club(1, "E002", {"mood_tags": four[:3]})
        self.assertEqual(self.w.clubs[1]["mood_tags"], four[:3])

    def test_unknown_key_rejected(self):
        with self.assertRaises(ValidationError) as cm:
            ca.update_club(1, "E002", {"nonexistent": 1})
        self.assertEqual(reason(cm), "unknown:nonexistent")

    def test_I082_organizer_cannot_change_organizer_or_is_active(self):
        with self.assertRaises(PermissionDeniedError):
            ca.update_club(1, "E002", {"organizer_id": "E003"})
        with self.assertRaises(PermissionDeniedError):
            ca.update_club(1, "E002", {"is_active": False})
        self.assertEqual((self.w.clubs[1]["organizer_id"], self.w.clubs[1]["is_active"]), ("E002", True))

    def test_I159_same_values_ignored_other_fields_saved(self):
        ca.update_club(1, "E002", {"organizer_id": "e002", "is_active": True, "message": "ひとこと更新"})
        self.assertEqual(self.w.clubs[1]["message"], "ひとこと更新")
        self.assertEqual(self.w.clubs[1]["organizer_id"], "E002")

    def test_I160_admin_can_change_organizer_and_is_active(self):
        ca.update_club(1, "E001", {"organizer_id": "E003", "is_active": False})
        self.assertEqual((self.w.clubs[1]["organizer_id"], self.w.clubs[1]["is_active"]), ("E003", False))

    # ---- create_club の判定順（契約 1.7 create_club）----
    def test_I203_create_club_permission_comes_before_validation(self):
        with self.assertRaises(PermissionDeniedError):
            ca.create_club("E002", {})  # 幹事・入力は空
        with self.assertRaises(PermissionDeniedError):
            ca.create_club("E003", dict(CLUB_FIELDS, name=""))  # 一般社員・必須が空
        self.assertEqual(sorted(self.w.clubs), [1, 2])
        with self.assertRaises(ValidationError):
            ca.create_club("E001", {})  # 運営者なら入力エラーになる

    def test_I204_create_club_multiple_required_missing_reports_first_in_listed_order(self):
        # 必須が複数そろっていないとき、契約の列挙順で最初の1件だけを返す。
        for drop in (("icon", "message"), ("activity_id", "level", "organizer_id"), ("organizer_id", "after_activity")):
            fields = {k: v for k, v in CLUB_FIELDS.items() if k not in drop}
            first = next(k for k in REQUIRED if k in drop)
            with self.assertRaises(ValidationError, msg=str(drop)) as cm:
                ca.create_club("E001", fields)
            self.assertEqual(reason(cm), f"required:{first}")
        blanks = dict(CLUB_FIELDS, slot="", fee="  ")  # 空白でも列挙順で最初（slot が fee より前）
        with self.assertRaises(ValidationError) as cm:
            ca.create_club("E001", blanks)
        self.assertEqual(reason(cm), "required:slot")
        self.assertEqual(sorted(self.w.clubs), [1, 2])

    def test_I161_create_club_registers_organizer_as_member(self):
        cid = ca.create_club("E001", dict(CLUB_FIELDS, organizer_id="E003"))
        self.assertTrue(self.w.clubs[cid]["is_active"])
        self.assertIn(("E003"), [m["employee_id"] for m in self.w.members if m["club_id"] == cid])

    def test_I162_organizer_change_auto_registers_new_and_keeps_old(self):
        ca.update_club(1, "E001", {"organizer_id": "E003"})
        members = {m["employee_id"] for m in self.w.members if m["club_id"] == 1}
        self.assertEqual(members, {"E002", "E003"})

    def test_I113_non_admin_cannot_create_club(self):
        for who in ("E002", "E003"):
            with self.assertRaises(PermissionDeniedError):
                ca.create_club(who, dict(CLUB_FIELDS))
        self.assertEqual(sorted(self.w.clubs), [1, 2])

    def test_I177_update_club_error_order(self):
        with self.assertRaises(NotFoundError):
            ca.update_club(999, "E003", {"name": ""})
        with self.assertRaises(PermissionDeniedError):
            ca.update_club(1, "E003", {"name": ""})  # 権限なし＋不正入力 → 権限が先
        with self.assertRaises(ValidationError):
            ca.update_club(1, "E002", {"name": ""})


class EventTests(LaTestCase):
    VALID = {"event_date": "2026-10-20", "start_time": "19:00", "end_time": "21:00", "meeting_place": "会議室A"}

    def test_I083_create_event_status_planned_and_default_place(self):
        self.assertIsNone(ca.get_last_meeting_place(1))
        eid = ca.create_event(1, "E002", dict(self.VALID))
        self.assertEqual(self.w.events[eid]["status"], "予定")
        self.assertEqual(self.w.events[eid]["club_id"], 1)
        self.assertEqual(ca.get_last_meeting_place(1), "会議室A")

    def test_I084_update_event_applied(self):
        eid = self.w.add_event(1, day_offset=2)
        ca.update_event(eid, "E002", {"meeting_place": "別室"})
        self.assertEqual(self.w.events[eid]["meeting_place"], "別室")

    def test_I087_I149_end_not_after_start_rejected(self):
        for end in ("18:00", "19:00"):
            with self.assertRaises(ValidationError, msg=end) as cm:
                ca.create_event(1, "E002", dict(self.VALID, end_time=end))
            self.assertEqual(reason(cm), "end_before_start")
        self.assertEqual(self.w.club_events(1), [])

    def test_I088_I150_past_date_rejected_today_allowed_jst(self):
        self.w.now = datetime(2026, 10, 13, 20, 0, tzinfo=timezone.utc)  # = JST 10/14 05:00
        with self.assertRaises(ValidationError) as cm:
            ca.create_event(1, "E002", dict(self.VALID, event_date="2026-10-13"))
        self.assertEqual(reason(cm), "past_date")
        eid = ca.create_event(1, "E002", dict(self.VALID, event_date="2026-10-14"))
        self.assertIn(eid, self.w.events)

    def test_I151_update_past_event_other_fields_ok_but_past_date_rejected(self):
        eid = self.w.add_event(1, day_offset=-3)
        ca.update_event(eid, "E002", {"meeting_place": "変更"})
        self.assertEqual(self.w.events[eid]["meeting_place"], "変更")
        with self.assertRaises(ValidationError) as cm:
            ca.update_event(eid, "E002", {"event_date": "2026-10-01"})
        self.assertEqual(reason(cm), "past_date")

    def test_I152_validation_order_required_then_past_then_end_before_start(self):
        with self.assertRaises(ValidationError) as cm:
            ca.create_event(1, "E002", {"event_date": "2026-10-01", "start_time": "19:00", "end_time": "21:00"})
        self.assertEqual(reason(cm), "required:meeting_place")
        with self.assertRaises(ValidationError) as cm:
            ca.create_event(1, "E002", dict(self.VALID, event_date="2026-10-01", end_time="18:00"))
        self.assertEqual(reason(cm), "past_date")

    # ---- unknown:<key>（status 等を混ぜて通知なしで中止にする抜け道を塞ぐ。契約 1.7 create_event / update_event）----
    def test_I196_create_event_unknown_key_rejected_and_nothing_saved(self):
        for key in ("status", "id", "club_id", "nonexistent"):
            with self.assertRaises(ValidationError, msg=key) as cm:
                ca.create_event(1, "E002", dict(self.VALID, **{key: "中止" if key == "status" else 1}))
            self.assertEqual(reason(cm), f"unknown:{key}")
        self.assertEqual(self.w.club_events(1), [])

    def test_I197_update_event_unknown_status_cannot_cancel_without_notification(self):
        eid = self.w.add_event(1, day_offset=2)
        self.w.add_application(eid, "E003", "申込済み")
        with self.assertRaises(ValidationError) as cm:
            ca.update_event(eid, "E002", {"status": "中止"})
        self.assertEqual(reason(cm), "unknown:status")
        self.assertEqual(self.w.events[eid]["status"], "予定")  # 変わっていない
        self.assertEqual(self.w.notes_for("E003", "中止"), [])
        for key in ("id", "club_id", "nonexistent"):
            with self.assertRaises(ValidationError, msg=key) as cm:
                ca.update_event(eid, "E002", {key: 1})
            self.assertEqual(reason(cm), f"unknown:{key}")

    def test_I198_unknown_comes_before_required_in_create_and_update(self):
        # 必須（meeting_place）が欠けていても、想定外のキーがあれば unknown が先（unknown → required）
        fields = {"event_date": "2026-10-20", "start_time": "19:00", "end_time": "21:00", "status": "中止"}
        with self.assertRaises(ValidationError) as cm:
            ca.create_event(1, "E002", fields)
        self.assertEqual(reason(cm), "unknown:status")
        eid = self.w.add_event(1, day_offset=2)
        with self.assertRaises(ValidationError) as cm:
            ca.update_event(eid, "E002", {"meeting_place": "", "status": "中止"})
        self.assertEqual(reason(cm), "unknown:status")  # 空の必須項目より先
        with self.assertRaises(ValidationError) as cm:
            ca.update_event(eid, "E002", {"meeting_place": ""})
        self.assertEqual(reason(cm), "required:meeting_place")

    def test_I199_unknown_is_after_not_found_and_permission(self):
        # 判定順は NotFound → Permission → Validation。権限が無い人の unknown は権限エラー。
        with self.assertRaises(PermissionDeniedError):
            ca.create_event(1, "E003", dict(self.VALID, status="中止"))
        with self.assertRaises(NotFoundError):
            ca.create_event(999, "E003", dict(self.VALID, status="中止"))

    # ---- update_event の end_before_start（fields に無いキーは現在値。契約 1.7 update_event）----
    def test_I200_update_event_end_before_start_uses_current_value_for_missing_key(self):
        eid = self.w.add_event(1, day_offset=2)  # 現在の開始・終了は fakes の既定値
        start = self.w.events[eid]["start_time"]
        end = self.w.events[eid]["end_time"]
        # 終了だけ変える: 現在の開始時刻より前・同時刻は不可
        with self.assertRaises(ValidationError) as cm:
            ca.update_event(eid, "E002", {"end_time": "00:30"})
        self.assertEqual(reason(cm), "end_before_start")
        with self.assertRaises(ValidationError) as cm:
            ca.update_event(eid, "E002", {"end_time": str(start)[:5]})
        self.assertEqual(reason(cm), "end_before_start")
        # 開始だけ変える: 現在の終了時刻以降は不可
        with self.assertRaises(ValidationError) as cm:
            ca.update_event(eid, "E002", {"start_time": "23:59"})
        self.assertEqual(reason(cm), "end_before_start")
        self.assertEqual((self.w.events[eid]["start_time"], self.w.events[eid]["end_time"]), (start, end))  # 保存されない
        # 現在値より後なら通る
        ca.update_event(eid, "E002", {"end_time": "23:30"})
        self.assertEqual(str(self.w.events[eid]["end_time"])[:5], "23:30")

    def test_I165_meeting_time_optional(self):
        eid = ca.create_event(1, "E002", dict(self.VALID))
        self.assertIsNone(self.w.events[eid]["meeting_time"])
        eid2 = ca.create_event(1, "E002", dict(self.VALID, meeting_time=None))  # 契約は time | None。空文字は契約に書かれていない
        self.assertIsNone(self.w.events[eid2]["meeting_time"])

    def test_I163_list_events_from_today_ordered_including_canceled(self):
        w = self.w
        yesterday = w.add_event(1, day_offset=-1)
        today = w.add_event(1, day_offset=0)
        t1 = w.add_event(1, day_offset=2)
        t2 = w.add_event(1, day_offset=2, status="中止")
        got = ca.list_club_events(1, "E002")
        self.assertEqual([e["event_id"] for e in got], [today, t1, t2])
        self.assertNotIn(yesterday, [e["event_id"] for e in got])
        self.assertEqual(got[2]["status"], "中止")

    def test_I164_applicant_count_counts_only_applied(self):
        ev = self.w.add_event(1, day_offset=1)
        self.w.add_application(ev, "E003", "申込済み")
        self.w.add_application(ev, "E005", "キャンセル")
        self.assertEqual(ca.list_club_events(1, "E002")[0]["applicant_count"], 1)

    def test_I166_no_events_or_unknown_club_returns_none(self):
        self.assertIsNone(ca.get_last_meeting_place(1))
        self.assertIsNone(ca.get_last_meeting_place(999))


class EventStatusTests(LaTestCase):
    def setUp(self):
        super().setUp()
        self.ev = self.w.add_event(1, day_offset=1)
        self.a1 = self.w.add_application(self.ev, "E003", "申込済み")
        self.a2 = self.w.add_application(self.ev, "E005", "申込済み")
        self.a3 = self.w.add_application(self.ev, "E004", "キャンセル")

    def test_I085_I111_I167_cancel_notifies_applied_only_and_keeps_applications(self):
        ca.set_event_status(self.ev, "E002", "中止")
        self.assertEqual(self.w.events[self.ev]["status"], "中止")
        for who in ("E003", "E005"):
            notes = self.w.notes_for(who, "中止")
            self.assertEqual(len(notes), 1, who)
            self.assertEqual(notes[0]["body"], "開催が中止になりました")
            self.assertEqual(notes[0]["event_id"], self.ev)
        self.assertEqual(self.w.notes_for("E004"), [])
        self.assertEqual([self.w.applications[a]["status"] for a in (self.a1, self.a2, self.a3)], ["申込済み", "申込済み", "キャンセル"])

    def test_I086_I112_I168_restore_has_no_notification_and_recancel_notifies_again(self):
        ca.set_event_status(self.ev, "E002", "中止")
        before = len(self.w.notifications)
        ca.set_event_status(self.ev, "E002", "予定")
        self.assertEqual(self.w.events[self.ev]["status"], "予定")
        self.assertEqual(len(self.w.notifications), before)
        ca.set_event_status(self.ev, "E002", "中止")
        self.assertEqual(len(self.w.notes_for("E003", "中止")), 2)

    def test_I169_same_status_conflict_and_invalid_status(self):
        with self.assertRaises(ConflictError) as cm:
            ca.set_event_status(self.ev, "E002", "予定")
        self.assertEqual(cm.exception.reason, "same_status")
        ca.set_event_status(self.ev, "E002", "中止")
        n = len(self.w.notifications)
        with self.assertRaises(ConflictError):
            ca.set_event_status(self.ev, "E002", "中止")
        self.assertEqual(len(self.w.notifications), n)
        with self.assertRaises(ValidationError) as cm:
            ca.set_event_status(self.ev, "E002", "延期")
        self.assertEqual(reason(cm), "invalid:status")

    def test_I177_set_status_error_order(self):
        with self.assertRaises(NotFoundError):
            ca.set_event_status(9999, "E003", "中止")
        with self.assertRaises(PermissionDeniedError):
            ca.set_event_status(self.ev, "E003", "延期")  # 権限なし＋不正状態 → 権限が先
        with self.assertRaises(ValidationError):
            ca.set_event_status(self.ev, "E002", "延期")
        with self.assertRaises(ValidationError):  # 不正状態＋同じ状態 → 入力が先は「予定→予定」ではなく不正値で確認
            ca.set_event_status(self.ev, "E002", "")


class MemberTests(LaTestCase):
    def test_I089_add_and_remove_member(self):
        ca.add_club_member(1, "E002", "E005")
        self.assertTrue(any(m["employee_id"] == "E005" for m in self.w.members if m["club_id"] == 1))
        ca.remove_club_member(1, "E002", "E005")
        self.assertFalse(any(m["employee_id"] == "E005" for m in self.w.members if m["club_id"] == 1))

    def test_I170_already_member_conflict(self):
        self.w.add_member(1, "E005")
        with self.assertRaises(ConflictError) as cm:
            ca.add_club_member(1, "E002", "E005")
        self.assertEqual(cm.exception.reason, "already_member")

    def test_I171_cannot_remove_organizer_until_changed(self):
        with self.assertRaises(ConflictError) as cm:
            ca.remove_club_member(1, "E002", "E002")
        self.assertEqual(cm.exception.reason, "organizer")
        ca.update_club(1, "E001", {"organizer_id": "E003"})
        ca.remove_club_member(1, "E001", "E002")
        self.assertNotIn("E002", [m["employee_id"] for m in self.w.members if m["club_id"] == 1])

    def test_I172_remove_non_member_not_found(self):
        with self.assertRaises(NotFoundError):
            ca.remove_club_member(1, "E002", "E005")

    def test_I201_add_member_unknown_employee_is_not_found_before_permission(self):
        with self.assertRaises(NotFoundError):
            ca.add_club_member(1, "E002", "E999")  # 権限あり: 社員が居ない
        with self.assertRaises(NotFoundError):
            ca.add_club_member(1, "E003", "E999")  # 権限なし: NotFound が先（契約の判定順）
        with self.assertRaises(NotFoundError):
            ca.add_club_member(999, "E003", "E005")  # 部活が居ない
        self.assertEqual([m["employee_id"] for m in self.w.members if m["club_id"] == 1], ["E002"])

    def test_I202_remove_member_permission_and_order(self):
        self.w.add_member(1, "E005")
        for who in ("E003", "E004"):  # 一般社員・他部活の幹事
            with self.assertRaises(PermissionDeniedError, msg=who):
                ca.remove_club_member(1, who, "E005")
        self.assertIn("E005", [m["employee_id"] for m in self.w.members if m["club_id"] == 1])
        # NotFound（所属でない）が権限より先
        with self.assertRaises(NotFoundError):
            ca.remove_club_member(1, "E003", "E003")
        # 権限が先、Conflict(organizer) が後
        with self.assertRaises(PermissionDeniedError):
            ca.remove_club_member(1, "E003", "E002")
        for who in ("E001", "E002"):
            self.w.add_member(1, "E005") if not any(
                m["club_id"] == 1 and m["employee_id"] == "E005" for m in self.w.members) else None
            ca.remove_club_member(1, who, "E005")
            self.assertNotIn("E005", [m["employee_id"] for m in self.w.members if m["club_id"] == 1])

    def test_I173_list_members_marks_organizer(self):
        self.w.add_member(1, "E005")
        got = {m["id"]: m["is_organizer"] for m in ca.list_club_members(1, "E002")}
        self.assertEqual(got, {"E002": True, "E005": False})

    def test_I174_selectable_employees_all_sorted_by_name_then_id_with_id_name_only(self):
        # 偽repoの並びに合わせず契約（name昇順・同名は id 昇順・列は id と name のみ）で期待値を作る。
        # id 順と name 順が食い違い、同名が居る世界にする。
        self.w.employees["E003"].update(interests_public=False, slots_public=False)
        self.w.add_employee("E010", name="アキラ")
        self.w.add_employee("E009", name="アキラ")  # 同名: id 昇順なら E009 が先
        self.w.add_employee("E011", name="ゼン")
        expected_ids = [e["id"] for e in sorted(self.w.employees.values(), key=lambda e: (e["name"], e["id"]))]
        self.assertNotEqual(expected_ids, sorted(expected_ids))  # 並びの検証が id 順と区別できる世界であること
        for who in ("E001", "E002"):
            got = ca.list_selectable_employees(who)
            self.assertEqual([e["id"] for e in got], expected_ids)
            self.assertLess([e["id"] for e in got].index("E009"), [e["id"] for e in got].index("E010"))
            self.assertTrue(all(set(e) == {"id", "name"} for e in got))
            self.assertIn("E003", [e["id"] for e in got])  # 非公開設定でも含まれる

    def test_I175_selectable_employees_general_denied(self):
        with self.assertRaises(PermissionDeniedError):
            ca.list_selectable_employees("E003")


class PermissionMatrixTests(LaTestCase):
    """I-114 / I-176 / I-177：運営者と当該幹事は可、他部活の幹事と一般社員は不可。"""

    def _ops(self, who):
        w = self.w
        ev = w.add_event(1, day_offset=3)
        w.add_employee("E006", name="所属六郎")
        w.add_member(1, "E006")  # 削除の権限確認用（所属者でないと NotFound が先になる）
        valid = {"event_date": "2026-10-25", "start_time": "19:00", "end_time": "21:00", "meeting_place": "X"}
        return [
            lambda: ca.get_club(1, who),
            lambda: ca.update_club(1, who, {"message": "m"}),
            lambda: ca.list_club_events(1, who),
            lambda: ca.create_event(1, who, dict(valid)),
            lambda: ca.update_event(ev, who, {"meeting_place": "Y"}),
            lambda: ca.set_event_status(ev, who, "中止"),
            lambda: ca.list_club_members(1, who),
            lambda: ca.add_club_member(1, who, "E005"),
            lambda: ca.add_club_member(1, who, "E003"),
            lambda: ca.remove_club_member(1, who, "E006"),
        ]

    def test_I176_allowed_roles_can_do_everything(self):
        for who in ("E001", "E002"):
            self.setUp()  # 偽DBを作り直す（前の操作の影響を残さない）
            for i, op in enumerate(self._ops(who)):
                try:
                    op()
                except Exception as e:  # noqa: BLE001
                    self.fail(f"{who} op#{i} raised {e!r}")

    def test_I114_I176_other_organizer_and_general_denied_everywhere(self):
        for who in ("E004", "E003"):
            self.setUp()
            for i, op in enumerate(self._ops(who)):
                with self.assertRaises(PermissionDeniedError, msg=f"{who} op#{i}"):
                    op()

    def test_I177_unknown_ids_not_found_even_without_permission(self):
        with self.assertRaises(NotFoundError):
            ca.get_club(999, "E003")
        with self.assertRaises(NotFoundError):
            ca.list_club_events(999, "E003")
        with self.assertRaises(NotFoundError):
            ca.update_event(9999, "E003", {"meeting_place": "x"})
        with self.assertRaises(NotFoundError):
            ca.create_event(999, "E003", {})


if __name__ == "__main__":
    unittest.main()
