"""L-C: サイドバー・ログイン・ホーム・部活検索の画面（偽repo＋AppTest）。"""
import unittest

from lc_base import LcTestCase


def sidebar_labels(at):
    return [b.label for b in at.sidebar.button]


class ShellAndLogin(LcTestCase):
    def test_I001_menu_order_and_unread_label(self):
        # 一般社員: 未読0 → 件数なし、「部活の管理」なし
        at = self.app("E003")
        self.assertEqual(sidebar_labels(at),
                         ["ホーム", "部活を探す", "人を探す", "メッセージ", "通知", "自分のプロフィール", "ログアウト"])
        # 未読1件 → メッセージ（1）。種類「中止」も数える（SP-70）
        self.w.add_notification("E003", "中止")
        at = self.app("E003")
        self.assertIn("メッセージ（1）", sidebar_labels(at))
        # 幹事・運営者には「部活の管理」が規定位置（プロフィールの次）に出る
        for eid in ("E002", "E001"):
            at = self.app(eid)
            labels = sidebar_labels(at)
            self.assertEqual(labels[labels.index("自分のプロフィール") + 1], "部活の管理", eid)
        # 一般社員（幹事でも運営者でもない）E005 には出ない
        self.assertNotIn("部活の管理", sidebar_labels(self.app("E005")))

    def test_I001_sidebar_shows_name_dept_id(self):
        at = self.app("E003")
        self.assertIn("**一般三郎**", [m.value for m in at.sidebar.markdown])
        self.assertIn("営業／E003", [c.value for c in at.sidebar.caption])

    def test_I009_I013_login_screen_texts(self):
        at = self.app()
        self.assertEqual(at.title[0].value, "部活コンシェルジュ")
        self.assertIn("自分に合う部活を見つけて、体験参加まで。", [m.value for m in at.markdown])
        self.assertIn("デモ用：社員ID E001〜E500／パスワードは共有のもの", [c.value for c in at.caption])
        self.assertEqual([t.label for t in at.text_input], ["社員ID", "パスワード"])

    def _login(self, at, eid, pw):
        at.text_input[0].set_value(eid)
        at.text_input[1].set_value(pw)
        at.button[0].click()
        return at.run()

    def test_I010_login_goes_home(self):
        at = self._login(self.app(), "E003", "test-common-password")
        self.assertEqual(at.session_state["current_page"], "home")
        self.assertEqual(at.session_state["employee_id"], "E003")
        self.assertIn("一般三郎さん、こんにちは。", [m.value for m in at.markdown])

    def test_I011_lowercase_id_is_normalized(self):
        at = self._login(self.app(), "e003", "test-common-password")
        self.assertEqual(at.session_state["employee_id"], "E003")

    def test_I012_wrong_id_and_wrong_password_same_message(self):
        msg = "社員IDかパスワードが違います。入力内容を確認してください"
        for eid, pw in (("E999", "test-common-password"), ("E003", "wrong")):
            at = self._login(self.app(), eid, pw)
            self.assertEqual([e.value for e in at.error], [msg])
            self.assertIsNone(at.session_state["employee_id"])

    def test_I014_logout_clears_and_returns_to_login(self):
        at = self.app("E003")
        at.sidebar.button(key="sidebar_logout").click()
        at.run()
        self.assertIsNone(at.session_state["employee_id"])
        self.assertIsNone(at.session_state["employee"])
        self.assertEqual(at.title[0].value, "部活コンシェルジュ")
        self.assertEqual(len(at.sidebar.button), 0)


class Home(LcTestCase):
    def test_I015_greeting(self):
        at = self.app("E003")
        self.assertEqual(at.title[0].value, "部活コンシェルジュ")
        self.assertIn("一般三郎さん、こんにちは。", [m.value for m in at.markdown])

    def test_I016_buttons_navigate(self):
        at = self.app("E003")
        at.button(key="home_to_club_search").click()
        at.run()
        self.assertEqual(at.session_state["current_page"], "club_search")
        at = self.app("E003")
        at.button(key="home_to_employee_search").click()
        at.run()
        self.assertEqual(at.session_state["current_page"], "employee_search")

    def test_home_empty_messages(self):
        at = self.app("E003")
        infos = [i.value for i in at.info]
        for m in ("今週開催予定の部活はまだありません", "今月はまだ人気部活のデータがありません",
                  "今はおすすめできる部活がありません"):
            self.assertIn(m, infos)

    def test_home_week_card_and_popular_rank(self):
        self.w.add_event(1, day_offset=0)
        at = self.app("E003")
        self.assertFalse(at.exception)
        self.assertNotIn("今週開催予定の部活はまだありません", [i.value for i in at.info])


class ClubSearch(LcTestCase):
    def test_I029_zero_result_message(self):
        # 偽repoは条件で絞り込まない（repo条件はL-B）ので、部活0件の状態を作って0件表示を確認する
        self.w.clubs.clear()
        at = self.app("E003", page="club_search")
        self.assertIn("条件に合う部活がありません。条件を減らして探してみてください",
                      [i.value for i in at.info])

    def test_I028_count_shown(self):
        at = self.app("E003", page="club_search")
        self.assertFalse(at.exception)
        texts = [m.value for m in at.markdown]
        self.assertTrue(any("件の部活が見つかりました" in t for t in texts), texts)

    def test_I030_search_records_conditions_only_when_set(self):
        self.app("E003", page="club_search")
        self.assertEqual(self.w.action_logs, [])  # 開いただけでは記録しない
        at = self.app("E003", page="club_search")
        at.text_input(key="club_search_keyword").set_value("テスト").run()
        self.assertEqual([a["action"] for a in self.w.action_logs], ["search_club"])

    def test_I003_conditions_kept_in_session(self):
        at = self.app("E003", page="club_search")
        at.text_input(key="club_search_keyword").set_value("テスト").run()
        self.assertEqual(at.session_state["club_search_conditions"], {"keyword": "テスト"})


if __name__ == "__main__":
    unittest.main()
