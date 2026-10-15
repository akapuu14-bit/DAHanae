"""性能改善 T2-3（設計 D-08）：ホームの一括取得 get_home_page（偽repo）。

今週・人気・おすすめが、個別の関数（get_this_week_clubs・get_popular_clubs・get_recommendations）と
同じ中身で、問い合わせは種類ごとに1回であることを確かめる。
"""
from unittest import mock

from fakes import LaTestCase
from repositories import applications_repo, clubs_repo, events_repo
from services import search_service as ss


class HomePage(LaTestCase):
    def setUp(self):
        super().setUp()
        w = self.w
        w.add_club(3, organizer_id="E004", name="部活C")
        e1 = w.add_event(1, day_offset=0)
        e2 = w.add_event(2, day_offset=0)
        e3 = w.add_event(3, day_offset=0, status="中止")
        w.add_application(e1, "E003", is_first_time=True)
        w.add_application(e1, "E004", is_first_time=True)
        w.add_application(e2, "E005", is_first_time=True)
        w.add_application(e2, "E003", is_first_time=True, status="キャンセル")  # 数えない
        w.add_application(e3, "E005", is_first_time=True)                        # 中止の開催は数えない
        w.add_application(e1, "E005", is_first_time=False)                       # 初参加でなければ数えない

    def test_same_as_individual_functions(self):
        for eid in ("E003", "E005", "E999"):
            page = ss.get_home_page(eid)
            self.assertEqual(page["week"], ss.get_this_week_clubs(), eid)
            self.assertEqual(page["popular"], ss.get_popular_clubs(), eid)
            self.assertEqual(page["recommendations"], ss.get_recommendations(eid), eid)
        self.assertTrue(ss.get_home_page("E003")["popular"])  # 比較が空同士にならない

    def test_one_query_per_kind(self):
        with mock.patch.object(events_repo, "list_upcoming_all_with_club",
                               wraps=events_repo.list_upcoming_all_with_club) as ev, \
             mock.patch.object(clubs_repo, "search", wraps=clubs_repo.search) as cl, \
             mock.patch.object(applications_repo, "count_first_time_by_club_in_month",
                               wraps=applications_repo.count_first_time_by_club_in_month) as ap, \
             mock.patch.object(applications_repo, "list_by_organizer_club") as per_club:
            ss.get_home_page("E003")
        self.assertEqual((ev.call_count, cl.call_count, ap.call_count, per_club.call_count), (1, 1, 1, 0))
