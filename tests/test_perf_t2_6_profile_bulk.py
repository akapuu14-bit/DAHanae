"""性能改善 T2-6（設計 D-08）：社員プロフィール（get_profile）の所属部活の一括取得（偽repo）。

所属部活は、所属部活の数に関係なく1回で取る。結果の中身は従来と同じ（is_active の部活のみ・club_id 昇順）。
"""
from unittest import mock

from fakes import LaTestCase
from repositories import clubs_repo, club_members_repo, events_repo
from services import profile_service as prof
from services import search_service as ss


class ProfileBulk(LaTestCase):
    def setUp(self):
        super().setUp()
        w = self.w
        for cid in (3, 4, 5):
            w.add_club(cid, organizer_id="E004", name=f"部活{cid}")
            w.add_event(cid, day_offset=cid)
        for cid in (1, 2, 3, 4, 5):
            w.add_member(cid, "E003")
        w.clubs[4]["is_active"] = False

    def test_content_active_only_sorted(self):
        p = prof.get_profile("E003", "E005")
        self.assertEqual([c["club_id"] for c in p["clubs"]], [1, 2, 3, 5])

    def test_club_lookups_are_not_per_club(self):
        with mock.patch.object(clubs_repo, "get") as per_club, \
             mock.patch.object(club_members_repo, "list_clubs_by_member") as ids, \
             mock.patch.object(club_members_repo, "list_active_clubs_by_member",
                               wraps=club_members_repo.list_active_clubs_by_member) as bulk:
            prof.get_profile("E003", "E003")
        self.assertEqual((per_club.call_count, ids.call_count, bulk.call_count), (0, 0, 1))

    def test_next_event_date_from_embedded_events(self):
        # 次回開催日は、個別の関数（get_this_week_clubs の next_event_date 等）と同じ判定：予定・今日以降の最小
        p = prof.get_profile("E003", "E003")
        by_id = {c["club_id"]: c for c in p["clubs"]}
        expected = ss._next_event_dates()
        for cid, card in by_id.items():
            self.assertEqual(card["next_event_date"], expected.get(cid), cid)
        self.assertIsNotNone(by_id[3]["next_event_date"])

    def test_no_separate_event_query(self):
        with mock.patch.object(events_repo, "list_upcoming_all_with_club") as ev:
            prof.get_profile("E003", "E003")
        self.assertEqual(ev.call_count, 0)
