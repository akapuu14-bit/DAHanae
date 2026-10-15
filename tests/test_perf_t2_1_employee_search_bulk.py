"""性能改善 T2-1（設計 D-08）：社員検索（search_employees）の一括取得（偽repo）。

所属部活・興味は、表示する社員の人数に関係なく1回ずつ取る。結果の中身は従来と同じ。
"""
from unittest import mock

from fakes import LaTestCase
from repositories import club_members_repo, employees_repo
from services import search_service as ss


class EmployeeSearchBulk(LaTestCase):
    def test_bulk_calls_once_regardless_of_people(self):
        for i in range(10, 30):
            self.w.add_employee(f"E{i:03d}", name=f"社員{i}", dept="開発")
        with mock.patch.object(club_members_repo, "list_active_clubs_for_employees",
                               wraps=club_members_repo.list_active_clubs_for_employees) as m1, \
             mock.patch.object(employees_repo, "get_interests_for",
                               wraps=employees_repo.get_interests_for) as m2, \
             mock.patch.object(employees_repo, "get_interests") as single:
            rows, total = ss.search_employees({}, "E003", 20, 0)
        self.assertGreaterEqual(len(rows), 20)
        self.assertEqual((m1.call_count, m2.call_count, single.call_count), (1, 1, 0))

    def test_hidden_interests_not_requested_and_clubs_listed(self):
        self.w.interests["E003"] = [{"activity_id": 1, "level": "初心者"}]
        self.w.employees["E003"].update(interests_public=False)
        self.w.add_member(1, "E003")
        with mock.patch.object(employees_repo, "get_interests_for",
                               wraps=employees_repo.get_interests_for) as m2:
            rows, _ = ss.search_employees({}, "E005", 20, 0)
        asked = m2.call_args.args[0]
        self.assertNotIn("E003", asked)  # 他人に非公開の人の興味は取りに行かない
        r = next(r for r in rows if r["id"] == "E003")
        self.assertIsNone(r["interests"])
        self.assertIn(1, [c["club_id"] for c in r["clubs"]])

    def test_no_rows_makes_no_bulk_query(self):
        with mock.patch.object(club_members_repo, "list_active_clubs_for_employees",
                               wraps=club_members_repo.list_active_clubs_for_employees) as m1:
            employees_repo.search = lambda c, l, o: []
            employees_repo.count = lambda c: 0
            rows, total = ss.search_employees({"name": "zzz"}, "E003", 20, 0)
        self.assertEqual((rows, total), ([], 0))
        self.assertEqual(m1.call_count, 1)  # 呼ぶが、中で ids 空なら問い合わせない契約（repo側）
