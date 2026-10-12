"""S-xx 黒箱 Phase2 T1 / 層 α-0（AppTest＋偽repo。DB不要）。画面をまたぐ要件を、画面操作だけで確かめる。

対象: S-03, S-04, S-05, S-06, S-10, S-20, S-31, S-33, S-38, S-47, S-51, S-52, S-56。
合格は「偽repoに対する画面の合格」で、実DBの合格ではない（実DB側の絞り込み・並びは L-B／α-R）。
実行: python3 -m pytest tests/test_sxx_appt_a0_*.py -v   （DB・ネットワーク不要）
"""

import re
import unittest
from datetime import date, time, timedelta
from unittest import mock

import fakes
from lc_base import LcTestCase
from sxx_common import DATETIME_RE, FORBIDDEN_SOLO, RULE, click_label, collect, joined


class ScreenFlows(LcTestCase):
    def apply_flow(self, club_id=1, day_offset=1):
        ev = self.w.add_event(club_id, day_offset=day_offset)
        at = self.app("E003", page="club_detail", target_club_id=club_id)
        at.button(key=f"club_detail_apply_{ev}").click().run()
        return at, ev

    # ---- S-03（F-03）戻る ----
    def test_S03_back_returns_to_previous_screen(self):
        """部活検索→部活詳細→戻る＝部活検索、社員検索→プロフィール→戻る＝社員検索。"""
        at = self.app("E003", page="club_search")
        at.button(key="club_search_1").click().run()
        self.assertEqual(at.session_state["current_page"], "club_detail")
        at.button(key="club_detail_back").click().run()
        self.assertEqual(at.session_state["current_page"], "club_search")

        at = self.app("E003", page="employee_search")
        at.button(key="employee_search_profile_E002").click().run()
        self.assertEqual(at.session_state["current_page"], "employee_profile")
        at.button(key="employee_profile_back").click().run()
        self.assertEqual(at.session_state["current_page"], "employee_search")

    # ---- S-04（F-04）検索条件の保持 ----
    def test_S04_conditions_survive_detail_and_back(self):
        at = self.app("E003", page="club_search")
        at.text_input(key="club_search_keyword").set_value("部活").run()
        at.multiselect(key="club_search_locations").set_value(["東京"]).run()
        at.button(key="club_search_1").click().run()
        at.button(key="club_detail_back").click().run()
        self.assertEqual(at.session_state["current_page"], "club_search")
        self.assertEqual(at.text_input(key="club_search_keyword").value, "部活")
        self.assertEqual(at.multiselect(key="club_search_locations").value, ["東京"])

        at = self.app("E003", page="employee_search")
        at.text_input(key="employee_search_name").set_value("一般").run()
        at.multiselect(key="employee_search_locations").set_value(["大阪"]).run()
        at.button(key="employee_search_profile_E003").click().run()
        at.button(key="employee_profile_back").click().run()
        self.assertEqual(at.session_state["current_page"], "employee_search")
        self.assertEqual(at.text_input(key="employee_search_name").value, "一般")
        self.assertEqual(at.multiselect(key="employee_search_locations").value, ["大阪"])

    # ---- S-05（F-05）運営ルール ----
    def test_S05_rule_on_detail_form_and_complete(self):
        at, ev = self.apply_flow()
        self.assertIn(RULE, [i.value for i in at.info])  # 部活詳細
        self.assertIn(RULE, [c.value for c in at.caption])  # 申込フォーム
        click_label(at, "この開催に申し込む")
        self.assertEqual(at.session_state["current_page"], "application_complete")
        self.assertIn(RULE, [i.value for i in at.info])  # 申込完了

    # ---- S-06（F-06）「1人参加OK」が出ない ----
    def test_S06_no_solo_ok_wording_on_any_screen(self):
        self.w.add_event(1, day_offset=2)
        ev = self.w.add_event(1, day_offset=3)
        aid = self.w.add_application(ev, "E005", is_first_time=True)
        self.w.add_notification("E003", "申込")
        screens = {
            "login": self.app(None),
            "home": self.app("E003"),
            "club_search": self.app("E003", page="club_search"),
            "club_detail": self.app("E003", page="club_detail", target_club_id=1),
            "messages_organizer": self.app("E002", page="messages"),
            "notifications": self.app("E003", page="notifications"),
            "employee_search": self.app("E003", page="employee_search"),
            "employee_profile": self.app("E003", page="employee_profile", target_employee_id="E005"),
            "club_admin": self.app("E002", page="club_admin"),
        }
        at, _ = self.apply_flow(club_id=2, day_offset=4)
        screens["apply_form"] = at
        click_label(at, "この開催に申し込む")
        screens["apply_complete"] = at
        for name, screen in screens.items():
            with self.subTest(screen=name):
                self.assertFalse(screen.exception)
                text = joined(screen)
                for word in FORBIDDEN_SOLO:
                    self.assertNotIn(word, text)

    # ---- S-10（F-10）ホームの入口 ----
    def test_S10_home_entries_have_one_line_explanations(self):
        from screens import home

        at = self.app("E003")
        values = collect(at)
        for button, explanation in (("部活を探す", home.EXPLAIN_CLUB), ("人を探す", home.EXPLAIN_PEOPLE)):
            with self.subTest(entry=button):
                self.assertIn(button, [b.label for b in at.button])
                self.assertIn(explanation, values)
                self.assertNotIn("\n", explanation.strip())  # 一行

    # ---- S-20（F-20）重複・中止・開始済みのエラー表示 ----
    def test_S20_already_applied_error_message(self):
        # 古い画面（別タブ・二度押し）で送信する状況。画面は再描画で申込済みに変わりフォームが消えるため、
        # サービスの重複判定だけを「申込済み」に差し替えて、画面のエラー表示を確かめる。
        at, ev = self.apply_flow()
        with mock.patch.object(fakes.applications_repo, "exists_active", lambda event_id, applicant_id: True):
            click_label(at, "この開催に申し込む")
        self.assertIn("すでに申し込み済みです", [e.value for e in at.error])
        self.assertEqual(at.session_state["current_page"], "club_detail")

    def test_S20_canceled_event_error_message(self):
        # 古い画面で送信する状況（再描画ではフォームが消えるため、サービスが見る開催の状態だけ中止にする）。
        at, ev = self.apply_flow()
        canceled = dict(self.w.events[ev], status="中止")
        with mock.patch.object(fakes.events_repo, "get", lambda event_id: dict(canceled)):
            click_label(at, "この開催に申し込む")
        self.assertIn("この開催には申し込みできません", [e.value for e in at.error])

    def test_S20_started_event_error_message(self):
        ev = self.w.add_event(1, day_offset=0, start="11:00:00", end="13:00:00")  # 12:00固定で開始済み
        at = self.app("E003", page="club_detail", target_club_id=1)
        at.button(key=f"club_detail_apply_{ev}").click().run()
        click_label(at, "この開催に申し込む")
        self.assertIn("この開催には申し込みできません", [e.value for e in at.error])

    # ---- S-31（F-31）0件の案内文（SP-42 改訂後の文言） ----
    def test_S31_empty_messages_both_tabs(self):
        infos = [i.value for i in self.app("E002", page="messages").info]
        self.assertIn("まだ申込はありません。部活を探して、気になる開催に申し込んでみましょう。", infos)
        self.assertIn("まだ申込は届いていません。", infos)
        infos = [i.value for i in self.app("E003", page="messages").info]
        self.assertIn("まだ申込はありません。部活を探して、気になる開催に申し込んでみましょう。", infos)

    # ---- S-33（F-33）通知の「見る」（SP-45 改訂後。中止は対象外） ----
    def test_S33_view_button_targets(self):
        for kind in ("申込", "キャンセル", "メッセージ", "スタンプ"):
            with self.subTest(kind=kind):
                self.setUp()
                self.w.add_notification("E003", kind)
                at = self.app("E003", page="notifications")
                click_label(at, "見る")
                self.assertEqual(at.session_state["current_page"], "messages")

    def test_S33_cancel_type_has_no_view_button(self):
        self.w.add_notification("E003", "中止", event_id=1)
        at = self.app("E003", page="notifications")
        self.assertIn("【中止】", joined(at))
        self.assertNotIn("見る", [b.label for b in at.button])

    # ---- S-38（F-38）社員検索0件 ----
    def test_S38_no_employee_found_message(self):
        # 偽repoは絞り込まないので、検索結果を0件にして画面の案内文だけを確かめる（絞り込み自体は L-B／α-R）
        with mock.patch.object(fakes.employees_repo, "search", lambda c, limit, offset: []), mock.patch.object(
            fakes.employees_repo, "count", lambda c: 0
        ):
            at = self.app("E003", page="employee_search")
            self.assertIn("条件に合う人がいません。条件を減らして探してみてください", [i.value for i in at.info])
            self.assertNotIn("名見つかりました", joined(at))

    # ---- S-47（F-47）開催の入力エラー ----
    def add_event_form(self, end, day):
        at = self.app("E002", page="club_admin")
        at.date_input(key="club_admin_1_add_date").set_value(day)
        at.time_input(key="club_admin_1_add_start").set_value(time(19, 0))
        at.time_input(key="club_admin_1_add_end").set_value(end)
        at.text_input(key="club_admin_1_add_place").set_value("会議室")
        return click_label(at, "追加する")

    def test_S47_end_same_as_or_before_start_is_error(self):
        today = self.w.today()
        for end in (time(19, 0), time(18, 0)):
            with self.subTest(end=end):
                at = self.add_event_form(end, today + timedelta(days=1))
                self.assertIn("終了時刻は開始時刻より後にしてください", [e.value for e in at.error])

    def test_S47_past_date_is_error_but_today_is_ok(self):
        today = self.w.today()
        at = self.add_event_form(time(20, 30), today - timedelta(days=1))
        self.assertIn("今日以降の日付を選んでください", [e.value for e in at.error])
        before = len(self.w.events)
        at = self.add_event_form(time(20, 30), today)
        self.assertEqual(len(self.w.events), before + 1)
        self.assertFalse(at.error)

    # ---- S-51（F-51 Could）運営者向けの可視化 ----
    @unittest.skip("F-51（Could）は未実装: app/frontend に『希望者はいるが部活が存在しない活動』を見せる画面・サービスが無い。テスト結果には『未実装』を記録する")
    def test_S51_demand_without_club_visualization(self):
        """希望者はいるが部活が存在しない活動が可視化されている。"""

    # ---- S-52（N-05）日時の表示形式 ----
    def assertDatetimeFormat(self, text, where):
        self.assertRegex(text, DATETIME_RE, f"{where}: 「9/26（土）19:00」の形式の日時が無い")

    def test_S52_club_detail_event_datetime_format(self):
        self.w.add_event(1, day_offset=2)
        self.assertDatetimeFormat(joined(self.app("E003", page="club_detail", target_club_id=1)), "部活詳細")

    def test_S52_messages_event_datetime_format(self):
        ev = self.w.add_event(1, day_offset=2)
        self.w.add_application(ev, "E003")
        self.assertDatetimeFormat(joined(self.app("E003", page="messages")), "メッセージ")

    def test_S52_application_complete_datetime_format(self):
        at, _ = self.apply_flow(day_offset=2)
        click_label(at, "この開催に申し込む")
        self.assertDatetimeFormat(joined(at), "申込完了")

    def test_S52_club_admin_events_datetime_format(self):
        self.w.add_event(1, day_offset=2)
        self.assertDatetimeFormat(joined(self.app("E002", page="club_admin")), "部活の管理（開催）")

    # ---- S-56（N-09）初期化ボタンが一般画面に無い ----
    def test_S56_no_reset_button_on_screens(self):
        self.w.add_event(1)
        for who, page, extra in (
            ("E003", "home", {}),
            ("E003", "club_search", {}),
            ("E003", "club_detail", {"target_club_id": 1}),
            ("E003", "messages", {}),
            ("E003", "notifications", {}),
            ("E003", "employee_search", {}),
            ("E003", "employee_profile", {"target_employee_id": "E003"}),
            ("E002", "club_admin", {}),
            ("E001", "club_admin", {}),
        ):
            with self.subTest(who=who, page=page):
                at = self.app(who, page=page, **extra)
                text = joined(at)
                self.assertIsNone(re.search(r"初期化|リセット|reset|全データ削除", text, re.I), text[:200])
        self.assertIsNone(re.search(r"初期化|リセット|reset", joined(self.app(None)), re.I))


if __name__ == "__main__":
    unittest.main()
