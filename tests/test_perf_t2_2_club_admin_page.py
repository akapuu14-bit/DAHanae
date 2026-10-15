"""性能改善 T2-2（設計 D-08）：部活の管理画面の一括取得 get_club_admin_page（偽repo）。

個別の関数（list_manageable_clubs・get_club・list_club_events・list_club_members・
list_selectable_employees・get_last_meeting_place）と同じ中身を、少ない問い合わせで返すことを確かめる。
"""
from fakes import LaTestCase
from services import club_admin_service as svc
from services.errors import PermissionDeniedError


class ClubAdminPage(LaTestCase):
    def setUp(self):
        super().setUp()
        ev = self.w.add_event(1, day_offset=1)
        self.w.add_event(1, day_offset=3, status="中止")
        self.w.add_application(ev, "E003")
        self.w.add_application(ev, "E004", status="キャンセル")  # 申込済みだけ数える
        self.w.add_member(1, "E003")

    def _same_as_individual(self, requester, club_id):
        page = svc.get_club_admin_page(requester, club_id)
        self.assertEqual(page["clubs"], svc.list_manageable_clubs(requester))
        cid = page["club_id"]
        self.assertEqual(page["club"], svc.get_club(cid, requester))
        self.assertEqual(page["events"], svc.list_club_events(cid, requester))
        self.assertEqual(page["members"], svc.list_club_members(cid, requester))
        self.assertEqual(page["employees"], svc.list_selectable_employees(requester))
        self.assertEqual(page["default_place"], svc.get_last_meeting_place(cid))
        return page

    def test_organizer_same_as_individual_functions(self):
        page = self._same_as_individual("E002", 1)
        self.assertEqual(page["events"][0]["applicant_count"], 1)

    def test_admin_same_as_individual_and_unknown_club_falls_back_to_first(self):
        self._same_as_individual("E001", 1)
        page = svc.get_club_admin_page("E001", 999)
        self.assertEqual(page["club_id"], page["clubs"][0]["club_id"])

    def test_default_place_when_no_upcoming_events(self):
        for e in list(self.w.events.values()):
            e["event_date"] = "2026-01-01"  # すべて過去
        page = svc.get_club_admin_page("E002", 1)
        self.assertEqual(page["events"], [])
        self.assertEqual(page["default_place"], svc.get_last_meeting_place(1))

    def test_not_manager_gets_nothing(self):
        page = svc.get_club_admin_page("E005", 1)
        self.assertEqual((page["clubs"], page["employees"], page["club"]), ([], [], None))
        with self.assertRaises(PermissionDeniedError):
            svc.list_selectable_employees("E005")  # 個別関数の拒否は変わらない

    def test_without_detail_for_new_club_form(self):
        page = svc.get_club_admin_page("E001", None, with_detail=False)
        self.assertIsNone(page["club"])
        self.assertTrue(page["employees"])
