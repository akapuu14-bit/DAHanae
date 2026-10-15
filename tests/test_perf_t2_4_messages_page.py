"""性能改善 T2-4（設計 D-08）：メッセージ画面の一括取得 get_messages_page（偽repo）。

個別の関数（list_my_applications・list_received_applications）と同じ中身を、申込・部活の件数に関係なく
少ない問い合わせで返すことを確かめる。
"""
from unittest import mock

from fakes import LaTestCase
from repositories import applications_repo, employees_repo, messages_repo
from services import application_service as svc
from services import auth_service


class MessagesPage(LaTestCase):
    def setUp(self):
        super().setUp()
        w = self.w
        w.add_club(3, organizer_id="E002", name="部活C")
        for cid in (1, 2, 3):
            ev = w.add_event(cid, day_offset=cid)
            for who in ("E003", "E004"):
                aid = w.add_application(ev, who, is_first_time=True)
                w.messages.append({"id": w.next_id("message"), "application_id": aid, "sender_id": who,
                                   "body": f"hi{aid}", "sent_at": "2026-10-01T00:00:00+00:00"})
        w.add_notification("E002", "申込", application_id=2)  # 未読の通知がある申込が先頭

    def test_same_as_individual_functions(self):
        for who in ("E003", "E002", "E001", "e002"):
            page = svc.get_messages_page(who)
            self.assertEqual(page["mine"], svc.list_my_applications(who), who)
            self.assertEqual(page["is_organizer"], auth_service.is_organizer(who), who)
            expected = svc.list_received_applications(who) if page["is_organizer"] else []
            self.assertEqual(page["received"], expected, who)
        self.assertTrue(svc.get_messages_page("E002")["received"])

    def test_one_query_per_kind(self):
        with mock.patch.object(messages_repo, "list_by_applications", wraps=messages_repo.list_by_applications) as m1, \
             mock.patch.object(employees_repo, "get_by_ids", wraps=employees_repo.get_by_ids) as m2, \
             mock.patch.object(applications_repo, "list_by_organizer_clubs",
                               wraps=applications_repo.list_by_organizer_clubs) as m3, \
             mock.patch.object(messages_repo, "list_by_application") as one, \
             mock.patch.object(applications_repo, "list_by_organizer_club") as per_club:
            svc.get_messages_page("E002")  # 幹事（自分の申込は0件、届いた申込が3部活ぶん）
            self.assertEqual((m1.call_count, m2.call_count, m3.call_count), (1, 0, 1))
            svc.get_messages_page("E003")  # 一般（自分の申込が3件、幹事の氏名は部活が違っても1回）
        self.assertEqual((m1.call_count, m2.call_count, m3.call_count), (2, 1, 1))
        self.assertEqual((one.call_count, per_club.call_count), (0, 0))

    def test_no_applications_makes_no_bulk_queries(self):
        with mock.patch.object(messages_repo, "list_by_applications", wraps=messages_repo.list_by_applications) as m1:
            page = svc.get_messages_page("E005")
        self.assertEqual((page["mine"], page["received"], page["is_organizer"]), ([], [], False))
        self.assertEqual(m1.call_count, 0)  # 申込が無ければ、問い合わせ自体をしない
