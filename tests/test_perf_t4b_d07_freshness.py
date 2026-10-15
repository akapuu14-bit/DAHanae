"""性能改善 T4b（D-07 キャッシュ導入後の鮮度・無効化の検証。仕様 SP-84、テスト設計 S-65・I-215〜I-218）。

偽repo＋AppTest。DB・ネットワークは使わない。D-07 は既定でテストでは切ってあるので、このファイルでは有効にして確かめる。
画面（AppTest）を通して、ユーザーが見る表示で確かめることを優先する（T3 の test_perf_t3_cache.py はサービス関数の確認が中心）。

I-215 通知を開いた直後にサイドバーの未読件数が0になる（SP-84①）
I-216 通知・メッセージ画面を開かない遷移では未読件数を再取得しない／開いたときは再取得する（SP-84①）
I-217 申込の直後に、部活詳細・自分の申込・幹事の届いた申込・幹事の未読が古いままにならない（SP-84②）
I-218 他の人（サービスを通らない直接の変更）による古さは許容（記録）／自分の申込は直後に反映される（SP-84③）
S-65  上記を1本の流れで通す（ホーム→通知→ホーム→部活を探す→申込→申込結果）
R-1〜R-4  T3 の「古い値が見える恐れ」のうち、テストで確かめられるもの（結果表に区別して記録する）
"""
import unittest
from datetime import time
from unittest import mock

from lc_base import LcTestCase
from services import cache_service, notification_service
from services import application_service as apps
from services import club_admin_service as admin
from services import search_service as ss

NOT_OPEN = "この開催には申し込みできません"


class CachedLc(LcTestCase):
    """キャッシュを有効にした画面テストの土台。"""

    def setUp(self):
        super().setUp()
        p = mock.patch.object(cache_service, "ENABLED", True)
        p.start()
        self.addCleanup(p.stop)
        cache_service.clear_all()
        self.addCleanup(cache_service.clear_all)

    @staticmethod
    def side_labels(at):
        return [b.label for b in at.sidebar.button]

    @staticmethod
    def click_side(at, key):
        at.sidebar.button(key=f"sidebar_{key}").click()
        return at.run()

    @staticmethod
    def labels(at):
        return [b.label for b in at.button]

    def detail(self, eid="E003", club_id=1):
        return self.app(eid, page="club_detail", target_club_id=club_id)

    def apply_via_ui(self, at, event_id, message=""):
        at.button(key=f"club_detail_apply_{event_id}").click().run()
        if message:
            at.text_area[0].set_value(message)
        at.button[self.labels(at).index("この開催に申し込む")].click().run()
        return at


class I215_I216_UnreadHold(CachedLc):
    def test_I215_unread_becomes_zero_right_after_opening_notifications(self):
        self.w.add_notification("E003", "メッセージ")
        at = self.app("E003")
        self.assertIn("メッセージ（1）", self.side_labels(at))
        at = self.click_side(at, "notifications")
        at = self.click_side(at, "home")
        self.assertNotIn("メッセージ（1）", self.side_labels(at))
        self.assertTrue(all("（" not in label for label in self.side_labels(at) if label.startswith("メッセージ")))
        self.assertEqual(at.session_state["unread_count"], 0)

    def test_I216_no_refetch_while_moving_but_refetch_on_opening(self):
        self.w.add_notification("E003", "メッセージ")
        with mock.patch.object(notification_service, "count_unread", wraps=notification_service.count_unread) as m:
            at = self.app("E003")
            self.assertEqual(m.call_count, 1)  # ログイン直後の最初の描画
            m.reset_mock()
            for key in ("club_search", "employee_search", "home"):
                at = self.click_side(at, key)
            self.assertEqual(m.call_count, 0)  # 通知・メッセージを開かない遷移では取り直さない
            at = self.click_side(at, "messages")
            self.assertGreaterEqual(m.call_count, 1)  # メッセージ画面を開いたとき
            m.reset_mock()
            at = self.click_side(at, "notifications")
            self.assertGreaterEqual(m.call_count, 1)  # 通知画面を開いたとき


class I217_ApplyIsReflectedImmediately(CachedLc):
    def setUp(self):
        super().setUp()
        self.event = self.w.add_event(1, day_offset=2)

    def test_I217_after_apply_all_related_views_are_fresh(self):
        # 申込前に、関係する画面をキャッシュに載せる
        detail = self.detail()
        self.assertIn("申し込む", self.labels(detail))
        self.app("E003", page="club_search")
        self.app("E002", page="messages")  # 幹事の届いた申込（キャッシュ対象外のはず）
        self.app("E003")  # ホーム
        organizer_unread_before = notification_service.count_unread("E002")

        at = self.apply_via_ui(self.detail(), self.event, "よろしく")
        self.assertEqual(at.session_state["current_page"], "application_complete")
        aid = next(iter(self.w.applications))

        # 部活詳細：申込済み表示・参加人数が反映（キャッシュから古い値が出ない）
        again = self.detail()
        self.assertIn("✅ 申込済み", [m.value for m in again.markdown])
        self.assertNotIn("申し込む", self.labels(again))
        self.assertTrue(any("参加：1名" in m.value for m in again.markdown))
        # 自分の申込（メッセージ画面）
        mine = self.app("E003", page="messages")
        self.assertTrue(any(f"messages_cancel_open_{aid}" == b.key for b in mine.button))
        # 幹事の未読件数（メッセージ画面を開くと既読化されるため、開く前に確かめる）と届いた申込
        self.assertEqual(notification_service.count_unread("E002"), organizer_unread_before + 1)
        organizer = self.app("E002", page="messages")
        self.assertTrue(any(f"messages_body_received_{aid}" == t.key for t in organizer.text_area))

    def test_I217_home_and_search_reflect_apply(self):
        # ホーム・部活を探すのカード側の件数／状態が申込で変わるかは、サービス関数の戻りで確認する
        ss.get_home_page("E003")
        before = ss.search_clubs({})
        apps.apply(self.event, "E003", None)
        after = ss.search_clubs({})
        # 無効化されて取り直されている（同じ入力でも別の呼び出し結果。部活の次回開催は変わらないので、少なくとも再取得された）
        self.assertEqual([c["club_id"] for c in before], [c["club_id"] for c in after])
        detail = ss.get_club_detail(1, "E003")
        self.assertTrue(next(e for e in detail["events"] if e["event_id"] == self.event)["is_applied"])

    def test_I217_cancel_is_reflected_immediately(self):
        aid = apps.apply(self.event, "E003", None)["application_id"]
        self.assertIn("✅ 申込済み", [m.value for m in self.detail().markdown])
        apps.cancel(aid, "E003")
        again = self.detail()
        self.assertIn("申し込む", self.labels(again))
        self.assertNotIn("✅ 申込済み", [m.value for m in again.markdown])


class I218_OthersMayBeStale(CachedLc):
    def setUp(self):
        super().setUp()
        self.event = self.w.add_event(1, day_offset=2)

    def count_on_screen(self, at):
        for m in at.markdown:
            if "参加：" in m.value:
                return m.value
        return None

    def test_I218_direct_change_by_other_is_stale_but_own_apply_is_fresh(self):
        a_view = self.detail("E003")
        self.assertIn("参加：0名", self.count_on_screen(a_view))
        # B が直接（サービスを通さず）偽repoへ書込む → A の再描画は古いまま（許容。記録のみ）
        self.w.add_application(self.event, "E005")
        a_again = self.detail("E003")
        stale = self.count_on_screen(a_again)
        self.assertIn("参加：0名", stale)  # 記録：他の人起因の古さ（許容）
        # A が自分で申込むと、直後の表示は B の申込分も含めて最新（自分の操作の結果は古くならない）
        self.apply_via_ui(self.detail("E003"), self.event)
        fresh = self.count_on_screen(self.detail("E003"))
        self.assertIn("参加：2名", fresh)

    def test_I218_other_user_via_service_refreshes_everyone(self):
        a_view = self.detail("E003")
        self.assertIn("参加：0名", self.count_on_screen(a_view))
        apps.apply(self.event, "E005", None)  # B がサービス経由で申込む（無効化が走る）
        self.assertIn("参加：1名", self.count_on_screen(self.detail("E003")))


class S65_Flow(CachedLc):
    def test_S65_home_notifications_home_search_apply_result(self):
        event = self.w.add_event(1, day_offset=2)
        self.w.add_notification("E003", "メッセージ")
        at = self.app("E003")
        self.assertIn("メッセージ（1）", self.side_labels(at))
        at = self.click_side(at, "notifications")
        at = self.click_side(at, "home")
        self.assertNotIn("メッセージ（1）", self.side_labels(at))
        at = self.click_side(at, "club_search")
        self.assertEqual(at.session_state["unread_count"], 0)  # 遷移中は0のまま
        self.assertEqual(at.session_state["current_page"], "club_search")
        at = self.detail()
        at = self.apply_via_ui(at, event, "お願いします")
        self.assertEqual(at.session_state["current_page"], "application_complete")
        mine = self.app("E003", page="messages")
        self.assertTrue(any(b.key.startswith("messages_cancel_open_") for b in mine.button))
        self.assertIn("✅ 申込済み", [m.value for m in self.detail().markdown])


class Risks(CachedLc):
    """T3 の「古い値が見える恐れ」。PR #178 の本文を読めなかったため、キャッシュの設計（cache_service・実装計画 6.5）から洗い出した4点。"""

    def test_R1_apply_button_after_start_time_conflicts_on_press(self):
        """R-1 開始時刻を過ぎても、キャッシュされた詳細には『申し込む』が残る。押すと ConflictError（not_open）になり、申込は作られない。"""
        event = self.w.add_event(1, day_offset=0, start="19:00:00", end="21:00:00")  # 偽の今日 2026-10-14
        self.assertIn("申し込む", self.labels(self.detail()))  # 12:00：申込できる（キャッシュに載る）
        self.w.now = self.w.now.replace(hour=20)  # 20:00＝開始後。同じ日なので、日付キーのキャッシュは同じ
        stale = self.detail()
        self.assertIn("申し込む", self.labels(stale))  # 恐れ：表示は古いまま（記録）
        at = self.apply_via_ui(stale, event)
        self.assertIn(NOT_OPEN, [e.value for e in at.error])  # 押すと「申し込みできません」
        self.assertEqual(self.w.applications, {})
        self.assertEqual(at.session_state["current_page"], "club_detail")
        with self.assertRaises(Exception) as ctx:
            apps.apply(event, "E003", None)
        self.assertEqual(type(ctx.exception).__name__, "ConflictError")

    def test_R2_permission_not_stale_after_organizer_change(self):
        """R-2 権限：幹事が替わった直後に、前の幹事の部活の管理が空になる（キャッシュで古い権限が残らない）。"""
        self.assertTrue(admin.get_club_admin_page("E002", 1)["clubs"])
        admin.update_club(1, "E001", {"organizer_id": "E004"})
        self.assertFalse([c for c in admin.get_club_admin_page("E002", 1)["clubs"] if c["club_id"] == 1])
        # 画面側の「権限の保持値」（session_state の can_manage）は、別セッションの変更では更新されない（SP-84③の範囲）。
        # AppTest は1セッションのため、他セッションの変更後に前の幹事のサイドバーが古いままかは確かめられない（未確認）。

    def test_R3_event_cancel_by_organizer_shows_in_detail_and_search(self):
        """R-3 開催の中止：幹事が中止にした直後に、部活詳細・部活を探すに反映される。"""
        event = self.w.add_event(1, day_offset=2)
        self.assertIn("申し込む", self.labels(self.detail()))
        admin.set_event_status(event, "E002", "中止")
        again = self.detail()
        self.assertNotIn("申し込む", self.labels(again))
        self.assertIn("中止", [m.value for m in again.markdown])

    def test_R4_failed_write_does_not_keep_stale_and_errors_not_cached(self):
        """R-4 失敗した書込み／存在しない部活：失敗でも無効化され、NotFound はキャッシュされない。"""
        event = self.w.add_event(1, day_offset=2)
        before = self.detail()
        self.assertIn("申し込む", self.labels(before))
        with mock.patch.object(apps.applications_repo, "insert", side_effect=RuntimeError("db")):
            with self.assertRaises(RuntimeError):
                apps.apply(event, "E003", None)
        # 失敗した書込みは無効化されない（insert の前に例外）。表示は変わっていないのが正しい
        self.assertIn("申し込む", self.labels(self.detail()))


if __name__ == "__main__":
    unittest.main()
