"""性能改善 T3（設計 D-07、仕様 SP-84、実装計画 6.5）：読み取りキャッシュと書込み後の無効化（偽repo）。

確かめること：
  - キャッシュが効く（同じ引数の2回目は、repo を呼ばない）
  - 自分の書込みの直後は、古い値が見えない（SP-84②。申込・キャンセル・プロフィール保存・部活/開催/メンバーの変更）
  - 権限が古いまま残らない（部活の管理は、担当が外れたら次の描画で空になる）
  - 他の人の操作（サービスを通らない変更）による古さは許容される（SP-84③）。ただし、だれかが書き込めば全員ぶん捨てられる
  - 日が変われば別のキャッシュになる／時間（TTL）では更新しない／エラーはキャッシュしない
  - メッセージ・通知はキャッシュ対象外
"""
from datetime import date
from unittest import mock

from fakes import LaTestCase
from repositories import employees_repo, events_repo
from services import application_service as apps
from services import cache_service, club_admin_service as admin, notification_service, search_service as ss
from services import profile_service as prof
from services.errors import NotFoundError


class CacheTestCase(LaTestCase):
    def setUp(self):
        super().setUp()
        p = mock.patch.object(cache_service, "ENABLED", True)
        p.start()
        self.addCleanup(p.stop)
        cache_service.clear_all()
        self.addCleanup(cache_service.clear_all)


class CacheHits(CacheTestCase):
    def test_home_second_call_does_not_query(self):
        with mock.patch.object(events_repo, "list_upcoming_all_with_club",
                               wraps=events_repo.list_upcoming_all_with_club) as m:
            first = ss.get_home_page("E003")
            second = ss.get_home_page("E003")
            self.assertEqual(m.call_count, 1)
            ss.get_home_page("E005")  # 社員ごとに別のキャッシュ
            self.assertEqual(m.call_count, 2)
        self.assertEqual(first, second)

    def test_other_cached_screens_hit(self):
        with mock.patch.object(employees_repo, "search", wraps=employees_repo.search) as es, \
             mock.patch.object(employees_repo, "list_departments", wraps=employees_repo.list_departments) as dep:
            for _ in range(2):
                ss.search_employees({}, "E003", 20, 0)
                ss.list_departments()
                ss.list_activities()
            self.assertEqual((es.call_count, dep.call_count), (1, 1))
            ss.search_employees({"name": "x"}, "E003", 20, 0)  # 条件が違えば別
            self.assertEqual(es.call_count, 2)
        with mock.patch.object(events_repo, "list_upcoming_all_with_club",
                               wraps=events_repo.list_upcoming_all_with_club) as ev:
            ss.search_clubs({}); ss.search_clubs({})
            self.assertEqual(ev.call_count, 1)
            ss.search_clubs({"keyword": "a"})
            self.assertEqual(ev.call_count, 2)

    def test_not_found_is_not_cached(self):
        for _ in range(2):
            with self.assertRaises(NotFoundError):
                ss.get_club_detail(99, "E003")
        self.w.add_club(99, organizer_id="E002", name="新部活")
        self.assertEqual(ss.get_club_detail(99, "E003")["club"]["club_id"], 99)

    def test_messages_and_notifications_are_not_cached(self):
        self.w.add_notification("E003", "メッセージ")
        self.assertEqual(notification_service.count_unread("E003"), 1)
        self.w.add_notification("E003", "メッセージ")
        self.assertEqual(notification_service.count_unread("E003"), 2)  # 毎回取り直す
        self.assertFalse(hasattr(apps.get_messages_page, "clear_cache"))
        self.assertFalse(hasattr(apps.list_my_applications, "clear_cache"))


class DayAndTtl(CacheTestCase):
    def test_new_day_is_a_different_cache(self):
        with mock.patch.object(events_repo, "list_upcoming_all_with_club",
                               wraps=events_repo.list_upcoming_all_with_club) as m:
            ss.get_home_page("E003")
            ss.get_home_page("E003")
            self.assertEqual(m.call_count, 1)
            with mock.patch.object(ss, "_today", return_value=date(2026, 10, 15)):
                ss.get_home_page("E003")  # 日が変わった
            self.assertEqual(m.call_count, 2)

    def test_no_time_based_expiry(self):
        # TTL を使わない（SP-84：一定時間で更新する方式は採らない）。st.cache_data に ttl を渡していない
        import inspect
        self.assertNotIn("ttl", inspect.getsource(cache_service))
        ss.get_home_page("E003")
        with mock.patch("time.time", return_value=10**10):  # 時刻が大きく進んでも
            with mock.patch.object(events_repo, "list_upcoming_all_with_club") as m:
                ss.get_home_page("E003")
        self.assertEqual(m.call_count, 0)  # キャッシュのまま


class OwnWritesInvalidate(CacheTestCase):
    def setUp(self):
        super().setUp()
        self.event = self.w.add_event(1, day_offset=2)

    def test_apply_and_cancel_update_detail_search_home_immediately(self):
        d0 = ss.get_club_detail(1, "E003")
        self.assertFalse(next(e for e in d0["events"] if e["event_id"] == self.event)["is_applied"])
        ss.get_home_page("E003"); ss.search_clubs({})
        result = apps.apply(self.event, "E003", None)
        d1 = ss.get_club_detail(1, "E003")
        self.assertTrue(next(e for e in d1["events"] if e["event_id"] == self.event)["is_applied"])
        self.assertEqual(next(e for e in d1["events"] if e["event_id"] == self.event)["participant_count"], 1)
        apps.cancel(result["application_id"], "E003")
        d2 = ss.get_club_detail(1, "E003")
        self.assertFalse(next(e for e in d2["events"] if e["event_id"] == self.event)["is_applied"])

    def test_apply_by_other_user_refreshes_everyones_detail(self):
        before = ss.get_club_detail(1, "E005")  # E005 の表示をキャッシュ
        apps.apply(self.event, "E003", None)  # 別の人が申込（サービスを通る書込み）
        after = ss.get_club_detail(1, "E005")
        count = lambda d: next(e for e in d["events"] if e["event_id"] == self.event)["participant_count"]
        self.assertEqual((count(before), count(after)), (0, 1))

    def test_stamp_invalidates_detail(self):
        aid = apps.apply(self.event, "E003", None)["application_id"]
        ss.get_club_detail(1, "E003")
        with mock.patch.object(cache_service, "invalidate", wraps=cache_service.invalidate) as inv:
            apps.confirm_stamp(aid, "E002")
        inv.assert_called_with(cache_service.APPLICATION)

    def test_profile_save_updates_profile_search_home(self):
        self.assertEqual(prof.get_profile("E003", "E003")["interests"], [])
        ss.search_employees({}, "E003", 20, 0); ss.get_home_page("E003")
        prof.save_profile("E003", "E003", [{"activity_id": 1, "level": "初心者"}], ["日曜"])
        p = prof.get_profile("E003", "E003")
        self.assertEqual([i["activity_id"] for i in p["interests"]], [1])
        self.assertEqual(p["available_slots"], ["日曜"])
        rows, _ = ss.search_employees({}, "E003", 20, 0)
        me = next(r for r in rows if r["id"] == "E003")
        self.assertEqual([i["activity_id"] for i in me["interests"]], [1])

    def test_public_setting_change_hides_value_from_others_immediately(self):
        self.w.interests["E003"] = [{"activity_id": 1, "level": "初心者"}]
        self.w.employees["E003"].update(interests_public=True)
        self.assertIsNotNone(prof.get_profile("E003", "E005")["interests"])  # 他人の表示をキャッシュ
        prof.update_public_settings("E003", "E003", interests_public=False)
        self.assertIsNone(prof.get_profile("E003", "E005")["interests"])  # 非公開にした直後から他人には出ない

    def test_failed_write_still_invalidates(self):
        prof.get_profile("E003", "E003")
        with mock.patch.object(employees_repo, "set_available_slots", side_effect=RuntimeError("db")):
            with self.assertRaises(RuntimeError):
                prof.save_profile("E003", "E003", [{"activity_id": 1, "level": "初心者"}], ["日曜"])
        # 興味の保存は済んでいたので、キャッシュは捨てられて新しい値が見える
        self.assertEqual([i["activity_id"] for i in prof.get_profile("E003", "E003")["interests"]], [1])


class ClubAdminCache(CacheTestCase):
    def test_member_and_event_changes_show_immediately(self):
        page = admin.get_club_admin_page("E002", 1)
        n_members, n_events = len(page["members"]), len(page["events"])
        admin.add_club_member(1, "E002", "E005")
        self.assertEqual(len(admin.get_club_admin_page("E002", 1)["members"]), n_members + 1)
        admin.remove_club_member(1, "E002", "E005")
        self.assertEqual(len(admin.get_club_admin_page("E002", 1)["members"]), n_members)
        from datetime import time
        admin.create_event(1, "E002", {"event_date": date(2026, 10, 20), "start_time": time(19, 0),
                                       "end_time": time(21, 0), "meeting_place": "会議室"})
        events = admin.get_club_admin_page("E002", 1)["events"]
        self.assertEqual(len(events), n_events + 1)
        admin.set_event_status(events[-1]["event_id"], "E002", "中止")
        self.assertEqual(admin.get_club_admin_page("E002", 1)["events"][-1]["status"], "中止")

    def test_permission_not_stale_after_organizer_change(self):
        self.assertTrue(admin.get_club_admin_page("E002", 1)["clubs"])  # 幹事の管理画面をキャッシュ
        fields = {"organizer_id": "E004"}
        admin.update_club(1, "E001", fields)  # 運営者が幹事を替える（書込み）
        self.assertFalse([c for c in admin.get_club_admin_page("E002", 1)["clubs"] if c["club_id"] == 1])
        self.assertTrue([c for c in admin.get_club_admin_page("E004", 1)["clubs"] if c["club_id"] == 1])

    def test_club_edit_shows_in_search_detail_home(self):
        ss.search_clubs({}); ss.get_club_detail(1, "E003")
        admin.update_club(1, "E002", {"name": "改名した部活"})
        self.assertIn("改名した部活", [c["name"] for c in ss.search_clubs({})])
        self.assertEqual(ss.get_club_detail(1, "E003")["club"]["name"], "改名した部活")


class OthersChangesMayBeStale(CacheTestCase):
    def test_change_without_service_write_is_stale_until_next_invalidation(self):
        # SP-84③：他の人の操作（ここではサービスを通らない直接の変更）による古さは許容する
        ss.search_clubs({})
        self.w.clubs[1]["name"] = "直接書き換え"
        self.assertNotIn("直接書き換え", [c["name"] for c in ss.search_clubs({})])
        cache_service.invalidate(cache_service.CLUB)  # だれかの書込みで無効化されれば見える
        self.assertIn("直接書き換え", [c["name"] for c in ss.search_clubs({})])
