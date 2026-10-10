"""search_service / profile_service の L-A テスト（偽repo）。

部活・社員の条件絞り込み（キーワード・拠点・非公開の除外など）は repository 側の責務で、偽repoは絞り込まない。
その範囲（I-022〜026, I-064〜068 等）はこのファイルの対象外。
"""

import unittest
from datetime import datetime, timezone

from fakes import JST, LaTestCase
from services import profile_service as prof
from services import search_service as ss
from services.errors import NotFoundError, PermissionDeniedError, ValidationError


def jst(y, m, d, hh=12, mm=0):
    return datetime(y, m, d, hh, mm, tzinfo=JST)


class HomeWeekTests(LaTestCase):
    def ids(self):
        return [c["club_id"] for c in ss.get_this_week_clubs()]

    def test_I121_week_range_wed_sun_and_next_monday(self):
        w = self.w
        w.add_event(1, event_date=jst(2026, 10, 18).date())            # 日曜
        w.add_event(2, event_date=jst(2026, 10, 12).date())            # 月曜（水曜から見て過去）
        w.add_event(2, event_date=jst(2026, 10, 13).date())            # 火曜（同上）
        w.now = jst(2026, 10, 14)                                      # 水曜
        self.assertEqual(self.ids(), [1])                              # 月・火だけの部活は出ず、日曜は出る
        w.now = jst(2026, 10, 18, 9)                                   # 日曜：当日のみ
        self.assertEqual(self.ids(), [1])
        w.add_club(3, organizer_id="E004", name="部活C")
        w.add_event(3, event_date=jst(2026, 10, 19).date())            # 翌週月曜
        self.assertEqual(self.ids(), [1])                              # 日曜は翌週月曜の開催を含まない
        w.now = datetime(2026, 10, 18, 15, 30, tzinfo=timezone.utc)    # = JST 10/19(月) 0:30
        self.assertEqual(self.ids(), [3])                              # 新しい週（月曜〜）に切り替わる

    def test_I017_five_or_more_clubs_all_returned_sorted_by_date(self):
        for cid in (3, 4, 5):
            self.w.add_club(cid, organizer_id="E004", name=f"部活{cid}")
        for off, cid in zip((4, 3, 2, 1, 0), (1, 2, 3, 4, 5)):
            self.w.add_event(cid, day_offset=off)
        got = ss.get_this_week_clubs()
        self.assertEqual([c["club_id"] for c in got], [5, 4, 3, 2, 1])  # 4件への絞り込みは画面側

    def test_I018_zero_cases(self):
        self.assertEqual(ss.get_this_week_clubs(), [])
        self.w.add_event(1, event_date=jst(2026, 10, 12).date())        # 月曜〜昨日のみ
        self.w.add_event(2, event_date=jst(2026, 10, 19).date())        # 来週のみ
        self.assertEqual(ss.get_this_week_clubs(), [])

    def test_I122_inactive_club_excluded(self):
        self.w.clubs[1]["is_active"] = False
        self.w.add_event(1, day_offset=1)
        self.assertEqual(ss.get_this_week_clubs(), [])

    def test_I123_all_canceled_events_excluded(self):
        self.w.add_event(1, day_offset=1, status="中止")
        self.assertEqual(ss.get_this_week_clubs(), [])


class PopularTests(LaTestCase):
    def setUp(self):
        super().setUp()
        for cid in (3, 4):
            self.w.add_club(cid, organizer_id="E004", name=f"部活{cid}")

    def _apply(self, club, n, *, status="申込済み", first=True, event_status="予定", day_offset=1):
        ev = self.w.add_event(club, day_offset=day_offset, status=event_status)
        for i in range(n):
            self.w.add_application(ev, f"E00{3 + i % 3}", status, first)

    def test_I019_ranking_by_first_time_non_canceled_desc(self):
        self._apply(1, 1); self._apply(2, 3); self._apply(3, 2)
        self._apply(4, 5, status="キャンセル"); self._apply(4, 4, first=False)
        got = ss.get_popular_clubs()
        self.assertEqual([(c["club_id"], c["rank"]) for c in got], [(2, 1), (3, 2), (1, 3)])

    def test_I124_canceled_event_applications_not_counted(self):
        self._apply(1, 2, event_status="中止")
        self.assertEqual(ss.get_popular_clubs(), [])

    def test_I125_ties_by_club_id_with_sequential_rank(self):
        self._apply(3, 2); self._apply(1, 2); self._apply(2, 2)
        got = ss.get_popular_clubs()
        self.assertEqual([(c["club_id"], c["rank"]) for c in got], [(1, 1), (2, 2), (3, 3)])

    def test_I126_month_boundary_uses_jst(self):
        self.w.now = jst(2026, 10, 31, 23, 30)
        ev_oct = self.w.add_event(1, event_date=jst(2026, 10, 31).date())
        ev_nov = self.w.add_event(2, event_date=jst(2026, 11, 1).date())
        self.w.add_application(ev_oct, "E003", "申込済み", True)
        self.w.add_application(ev_nov, "E003", "申込済み", True)
        self.assertEqual([c["club_id"] for c in ss.get_popular_clubs()], [1])
        self.w.now = datetime(2026, 10, 31, 15, 30, tzinfo=timezone.utc)  # = JST 11/1 0:30
        self.assertEqual([c["club_id"] for c in ss.get_popular_clubs()], [2])

    def test_I127_no_counts_returns_empty(self):
        self.assertEqual(ss.get_popular_clubs(), [])


class RecommendTests(LaTestCase):
    def test_I128_no_match_returns_empty(self):
        self.w.add_employee("E010", location="福岡")
        self.assertEqual(ss.get_recommendations("E010"), [])
        self.assertEqual(ss.get_recommendations("E999"), [])

    def test_I129_joined_clubs_not_recommended(self):
        self.w.interests["E003"] = [{"activity_id": 1, "level": "初心者"}]
        self.w.employees["E003"]["location"] = "東京"
        self.assertEqual({c["club_id"] for c in ss.get_recommendations("E003")}, {1, 2})
        self.w.add_member(1, "E003")
        self.assertEqual({c["club_id"] for c in ss.get_recommendations("E003")}, {2})

    def test_I020_score_reason_and_sort(self):
        self.w.interests["E003"] = [{"activity_id": 1, "level": "初心者"}]
        self.w.employees["E003"].update(location="東京", available_slots=["平日夜"])
        self.w.clubs[2]["activity_id"] = 2
        got = ss.get_recommendations("E003")
        self.assertEqual([(c["club_id"], c["score"]) for c in got], [(1, 3), (2, 2)])
        self.assertIn("興味（スポーツ）", got[0]["reason"])

    def test_I129_non_public_settings_still_used_for_self(self):
        self.w.interests["E003"] = [{"activity_id": 1, "level": "初心者"}]
        self.w.employees["E003"].update(interests_public=False, location="福岡")
        self.assertTrue(ss.get_recommendations("E003"))  # 裁定#19：本人分は非公開でも使う

    def test_I130_card_has_level(self):
        for card in ss.get_this_week_clubs() + ss.search_clubs({}):
            self.assertIn("level", card)
        self.assertEqual(ss.search_clubs({})[0]["level"], "初心者歓迎")


class SearchClubsTests(LaTestCase):
    def test_I027_I131_I132_next_event_ordering_and_none_last(self):
        w = self.w
        w.now = datetime(2026, 10, 13, 15, 30, tzinfo=timezone.utc)  # = JST 10/14 0:30
        for cid in (3, 4, 5):
            w.add_club(cid, organizer_id="E004", name=f"部活{cid}")
        w.add_event(1, event_date=jst(2026, 10, 14).date())            # 日本時間の今日
        w.add_event(2, event_date=jst(2026, 10, 13).date())            # 昨日のみ
        w.add_event(3, day_offset=1, status="中止")                     # 中止のみ
        w.add_event(4, day_offset=2)
        got = ss.search_clubs({})
        self.assertEqual([c["club_id"] for c in got], [1, 4, 2, 3, 5])
        self.assertEqual([c["next_event_date"] is None for c in got], [False, False, True, True, True])
        self.assertEqual(str(got[0]["next_event_date"]), "2026-10-14")

    def test_service_builds_cards_only_from_repo_rows(self):
        # is_active の絞り込み自体は repo の責務。service は repo の返した部活だけをカードにする。
        self.w.clubs[2]["is_active"] = False
        self.assertEqual([c["club_id"] for c in ss.search_clubs({})], [1])


class ClubDetailTests(LaTestCase):
    def test_I133_unknown_club_not_found(self):
        with self.assertRaises(NotFoundError):
            ss.get_club_detail(999, "E003")

    def test_I134_counts_only_applied_and_canceled_event_listed(self):
        w = self.w
        ev = w.add_event(1, day_offset=1)
        w.add_application(ev, "E003", "申込済み", True)
        w.add_application(ev, "E005", "申込済み", False)
        w.add_application(ev, "E004", "キャンセル", True)
        ev_c = w.add_event(1, day_offset=2, status="中止")
        d = ss.get_club_detail(1, "E003")
        e = next(x for x in d["events"] if x["event_id"] == ev)
        self.assertEqual((e["participant_count"], e["first_timer_count"]), (2, 1))
        self.assertEqual([p["id"] for p in e["participants"]], ["E003", "E005"])
        self.assertTrue(e["is_applied"])
        self.assertIn(ev_c, [x["event_id"] for x in d["events"]])

    def test_I135_members_include_organizer(self):
        d = ss.get_club_detail(1, "E003")
        self.assertIn("E002", [m["id"] for m in d["members"]])
        self.assertEqual(d["member_count"], len(d["members"]))

    def test_I137_returned_columns_are_limited(self):
        w = self.w
        ev = w.add_event(1, day_offset=1)
        w.add_application(ev, "E003", "申込済み", True)
        d = ss.get_club_detail(1, "E005")
        self.assertEqual(set(d["organizer"]), {"id", "name", "dept", "joined_year", "entry_type"})
        self.assertEqual(set(d["members"][0]), {"id", "name", "dept"})
        self.assertEqual(set(d["events"][0]["participants"][0]), {"id", "name", "is_first_time", "is_self"})
        self.assertFalse(d["events"][0]["is_applied"])

    def test_I193_repeated_fetch_does_not_log(self):
        for _ in range(3):
            ss.get_club_detail(1, "E003")
        self.assertEqual(self.w.action_logs, [])

    def test_inactive_club_detail_still_returned_button_is_screen_side(self):
        # 申込ボタンの出し分け（H-6）は画面側（L-C）。service は非公開部活も返す（PM裁定）。
        self.w.clubs[1]["is_active"] = False
        self.assertFalse(ss.get_club_detail(1, "E003")["club"]["is_active"])


class SearchEmployeesVisibilityTests(LaTestCase):
    def test_I073_I069_private_values_hidden_from_others_not_self(self):
        w = self.w
        w.employees["E003"].update(interests_public=False, slots_public=False, available_slots=["日曜"])
        w.interests["E003"] = [{"activity_id": 1, "level": "初心者"}]
        rows, total = ss.search_employees({}, "E005", 20, 0)
        r = next(x for x in rows if x["id"] == "E003")
        self.assertEqual((r["interests"], r["available_slots"]), (None, None))
        self.assertEqual((r["interests_visibility"], r["slots_visibility"]), ("hidden", "hidden"))
        rows, _ = ss.search_employees({}, "e003", 20, 0)
        r = next(x for x in rows if x["id"] == "E003")
        self.assertEqual(r["available_slots"], ["日曜"])
        self.assertEqual(r["interests_visibility"], "self_private")

    def test_search_employees_total_and_page_size(self):
        rows, total = ss.search_employees({}, "E003", 2, 0)
        self.assertEqual((len(rows), total), (2, 5))

    def test_clubs_shown_regardless_of_privacy(self):
        self.w.employees["E002"].update(interests_public=False)
        rows, _ = ss.search_employees({}, "E005", 20, 0)
        r = next(x for x in rows if x["id"] == "E002")
        self.assertEqual([c["club_id"] for c in r["clubs"]], [1])


class ProfileTests(LaTestCase):
    def setUp(self):
        super().setUp()
        self.w.interests["E003"] = [{"activity_id": 1, "level": "初心者"}]
        self.w.employees["E003"].update(available_slots=["日曜"], interests_public=False, slots_public=False)

    def test_I072_basic_fields_and_is_self(self):
        p = prof.get_profile("E003", "E003")
        self.assertTrue(p["is_self"])
        self.assertEqual(set(p["employee"]), {"id", "name", "dept", "location", "joined_year", "entry_type"})
        self.assertFalse(prof.get_profile("E003", "E005")["is_self"])

    def test_I073_private_hidden_from_others(self):
        p = prof.get_profile("E003", "E005")
        self.assertEqual((p["interests"], p["available_slots"]), (None, None))

    def test_I141_self_sees_values_and_flags(self):
        p = prof.get_profile("E003", "e003")
        self.assertEqual(p["available_slots"], ["日曜"])
        self.assertEqual(len(p["interests"]), 1)
        self.assertEqual((p["interests_public"], p["slots_public"]), (False, False))

    def test_I142_only_active_clubs_in_id_order(self):
        w = self.w
        w.add_club(3, organizer_id="E004", name="部活C")
        w.add_club(4, organizer_id="E004", name="部活D", is_active=False)
        for cid in (3, 4, 1):
            w.add_member(cid, "E003")
        self.assertEqual([c["club_id"] for c in prof.get_profile("E003", "E005")["clubs"]], [1, 3])

    def test_I074_club_cards_have_ids(self):
        self.w.add_member(1, "E003")
        self.assertEqual(prof.get_profile("E003", "E005")["clubs"][0]["club_id"], 1)

    def test_I147_unknown_employee_not_found(self):
        with self.assertRaises(NotFoundError):
            prof.get_profile("E999", "E003")

    def test_I075_self_can_toggle_public(self):
        prof.update_public_settings("E003", "E003", interests_public=True, slots_public=True)
        self.assertEqual((self.w.employees["E003"]["interests_public"], self.w.employees["E003"]["slots_public"]), (True, True))

    def test_I143_others_cannot_toggle_public(self):
        for other in ("E005", "E002", "E001"):
            with self.assertRaises(PermissionDeniedError):
                prof.update_public_settings("E003", other, interests_public=True)
        self.assertFalse(self.w.employees["E003"]["interests_public"])

    def test_I077_self_save_profile(self):
        prof.save_profile("E003", "E003", [{"activity_id": 2, "level": "経験あり"}], ["平日夜", "日曜"])
        self.assertEqual(self.w.interests["E003"], [{"activity_id": 2, "level": "経験あり"}])
        self.assertEqual(self.w.employees["E003"]["available_slots"], ["平日夜", "日曜"])

    def test_I144_others_cannot_save(self):
        for other in ("E005", "E001"):
            with self.assertRaises(PermissionDeniedError):
                prof.save_profile("E003", other, [], [])
        self.assertEqual(len(self.w.interests["E003"]), 1)

    def test_I145_invalid_input_validation_and_nothing_saved(self):
        bad = [
            ([{"activity_id": 99, "level": "初心者"}], ["日曜"]),
            ([{"activity_id": 1, "level": "達人"}], ["日曜"]),
            ([{"activity_id": 1, "level": "初心者"}, {"activity_id": 1, "level": "経験あり"}], ["日曜"]),
            ([{"activity_id": 1, "level": "初心者"}], ["深夜"]),
            ([{"activity_id": 1, "level": "初心者"}], ["日曜", "日曜"]),
        ]
        for interests, slots in bad:
            with self.assertRaises(ValidationError):
                prof.save_profile("E003", "E003", interests, slots)
        self.assertEqual(self.w.interests["E003"], [{"activity_id": 1, "level": "初心者"}])
        self.assertEqual(self.w.employees["E003"]["available_slots"], ["日曜"])

    def test_I146_empty_lists_save_zero(self):
        prof.save_profile("E003", "E003", [], [])
        self.assertEqual(self.w.interests["E003"], [])
        self.assertEqual(self.w.employees["E003"]["available_slots"], [])

    def test_I143_error_order_permission_before_not_found(self):
        with self.assertRaises(PermissionDeniedError):
            prof.update_public_settings("E999", "E003", interests_public=True)
        with self.assertRaises(NotFoundError):
            prof.update_public_settings("E999", "E999", interests_public=True)


if __name__ == "__main__":
    unittest.main()
