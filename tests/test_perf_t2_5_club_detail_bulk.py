"""性能改善 T2-5（設計 D-08）：部活詳細（get_club_detail）の一括取得（偽repo）。

メンバーの氏名・部署と、開催ごとの参加者を、人数・開催数に関係なく1回ずつ取る。結果の中身は従来と同じ。
"""
from unittest import mock

from fakes import LaTestCase
from repositories import applications_repo, club_members_repo, employees_repo, events_repo
from services import search_service as ss


class ClubDetailBulk(LaTestCase):
    def setUp(self):
        super().setUp()
        w = self.w
        for i in range(10, 16):
            w.add_employee(f"E{i:03d}", name=f"社員{i}", dept="開発")
            w.add_member(1, f"E{i:03d}")
        for off in (1, 2, 3):
            ev = w.add_event(1, day_offset=off)
            for who in ("E003", "E010", "E011"):
                w.add_application(ev, who, is_first_time=(who == "E010"))
            w.add_application(ev, "E012", status="キャンセル")  # 参加者に含めない

    def test_content(self):
        d = ss.get_club_detail(1, "E003")
        self.assertEqual(d["member_count"], len(d["members"]))
        self.assertGreaterEqual(d["member_count"], 7)
        self.assertEqual(len(d["events"]), 3)
        for e in d["events"]:
            self.assertEqual(e["participant_count"], 3)
            self.assertEqual(e["first_timer_count"], 1)
            self.assertTrue(e["is_applied"])
            self.assertNotIn("E012", [p["id"] for p in e["participants"]])

    def test_one_query_per_kind(self):
        with mock.patch.object(club_members_repo, "list_members_with_employees",
                               wraps=club_members_repo.list_members_with_employees) as m1, \
             mock.patch.object(events_repo, "list_upcoming_by_club_with_participants",
                               wraps=events_repo.list_upcoming_by_club_with_participants) as m2, \
             mock.patch.object(applications_repo, "list_participants") as per_event, \
             mock.patch.object(club_members_repo, "list_members") as plain, \
             mock.patch.object(employees_repo, "get_by_id", wraps=employees_repo.get_by_id) as one:
            ss.get_club_detail(1, "E003")
        self.assertEqual((m1.call_count, m2.call_count, per_event.call_count, plain.call_count), (1, 1, 0, 0))
        self.assertEqual(one.call_count, 1)  # 幹事の取得だけ（メンバーごとには取らない）
