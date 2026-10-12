"""S-xx 黒箱 Phase2 T1 / 層 α-0（AppTest＋偽repo。DB不要）: α-W を『中間』に分けた「周辺」。

だーあさ裁定（2026-10-11）: アプリの主役（申込・キャンセル）の新規書込だけを実DBで黒箱（T2）にし、
周辺（操作履歴・既読化・保存・開催/メンバー管理・中止通知）は画面挙動（偽repo）で充足とする。
対象: S-16, S-21, S-30, S-34, S-41, S-43, S-45, S-46, S-48, S-49, S-50, S-61。
合格は「偽repoに対する画面操作→書込結果の合格」で、実DBへの反映の合格ではない。
実行: python3 -m pytest tests/test_sxx_appt_a0_*.py -v   （DB・ネットワーク不要）
"""

import unittest
from datetime import timedelta

from lc_base import LcTestCase
from sxx_common import click_label, joined


def logs(w, action=None, employee="E003"):
    return [r for r in w.action_logs if r["employee_id"] == employee and (action is None or r["action"] == action)]


class Periphery(LcTestCase):
    # ---- S-16（F-16）検索の操作履歴 ----
    def test_S16_search_changes_are_recorded_with_conditions(self):
        at = self.app("E003", page="club_search")
        at.multiselect(key="club_search_locations").set_value(["東京"]).run()
        at.text_input(key="club_search_keyword").set_value("テスト").run()
        rows = logs(self.w, "search_club")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["conditions"], {"locations": ["東京"]})
        self.assertEqual(rows[1]["conditions"], {"locations": ["東京"], "keyword": "テスト"})

    # ---- S-21（F-21）閲覧の操作履歴 ----
    def test_S21_opening_club_detail_is_recorded(self):
        self.app("E003", page="club_detail", target_club_id=1)
        rows = logs(self.w, "view_club")
        self.assertEqual([r["club_id"] for r in rows], [1])

    # ---- S-49（F-49）記録される項目 ----
    def test_S49_search_view_apply_are_recorded_with_employee_and_target(self):
        ev = self.w.add_event(1, day_offset=1)
        at = self.app("E003", page="club_search")
        at.text_input(key="club_search_keyword").set_value("部活").run()
        at.button(key="club_search_1").click().run()  # 部活詳細（view_club）
        at.button(key=f"club_detail_apply_{ev}").click().run()
        click_label(at, "この開催に申し込む")  # 申込完了（apply）
        rows = logs(self.w)
        self.assertEqual([r["action"] for r in rows], ["search_club", "view_club", "apply"])
        self.assertEqual(rows[0]["conditions"], {"keyword": "部活"})
        self.assertEqual([r["club_id"] for r in rows[1:]], [1, 1])
        self.assertTrue(all(r["employee_id"] == "E003" for r in rows))

    def test_S49_employee_search_is_not_recorded(self):
        at = self.app("E003", page="employee_search")
        at.text_input(key="employee_search_name").set_value("一般").run()
        self.assertEqual(logs(self.w), [])

    # ---- S-50（F-50）二重記録されない ----
    def test_S50_same_conditions_and_same_club_are_not_recorded_twice(self):
        at = self.app("E003", page="club_search")
        at.text_input(key="club_search_keyword").set_value("部活").run()
        at.run()
        at.run()
        self.assertEqual(len(logs(self.w, "search_club")), 1)

        at = self.app("E003", page="club_detail", target_club_id=1)
        at.run()
        self.assertEqual(len(logs(self.w, "view_club")), 1)  # 同じ部活を続けて表示
        at = self.app("E003", page="club_detail", target_club_id=2)
        self.assertEqual([r["club_id"] for r in logs(self.w, "view_club")], [1, 2])  # 別の部活は記録

    # ---- S-30（F-30）メッセージ画面で関連通知が既読 ----
    def test_S30_opening_messages_marks_related_notifications_read(self):
        for kind in ("申込", "キャンセル", "メッセージ", "スタンプ", "中止"):
            self.w.add_notification("E003", kind)
        self.app("E003", page="messages")
        unread = {n["type"] for n in self.w.notes_for("E003") if n["read_at"] is None}
        self.assertEqual(unread, {"中止"})  # 中止は通知一覧で既読にする（SP-36）

    # ---- S-34（F-34）通知一覧を開くとすべて既読 ----
    def test_S34_opening_notifications_marks_all_read(self):
        for kind in ("申込", "メッセージ", "中止"):
            self.w.add_notification("E003", kind)
        at = self.app("E003", page="notifications")
        self.assertFalse([n for n in self.w.notes_for("E003") if n["read_at"] is None])
        self.assertEqual(len([m for m in at.markdown if m.value.startswith("**【")]), 3)  # この画面では未読の太字のまま

    # ---- S-41（F-41）公開設定の切り替えは切替時点で保存 ----
    def test_S41_both_toggles_save_immediately_and_persist(self):
        at = self.app("E005", page="employee_profile", target_employee_id="E005")
        at.toggle(key="profile_toggle_interests").set_value(False).run()
        at.toggle(key="profile_toggle_slots").set_value(False).run()
        self.assertFalse(self.w.employees["E005"]["interests_public"])
        self.assertFalse(self.w.employees["E005"]["slots_public"])
        at = self.app("E005", page="employee_profile", target_employee_id="E005")  # 開き直しても保存されている
        self.assertEqual([t.value for t in at.toggle], [False, False])

    # ---- S-43（F-43）興味・経験／参加可能時間の編集 ----
    def test_S43_edit_interests_and_slots_are_saved(self):
        at = self.app("E005", page="employee_profile", target_employee_id="E005")
        at.selectbox(key="profile_edit_level_1").set_value("初心者")
        at.selectbox(key="profile_edit_level_2").set_value("経験あり")
        at.multiselect(key="profile_edit_slots").set_value(["平日夜", "日曜"])
        at = click_label(at, "保存する")
        self.assertEqual(
            sorted(self.w.interests["E005"], key=lambda i: i["activity_id"]),
            [{"activity_id": 1, "level": "初心者"}, {"activity_id": 2, "level": "経験あり"}],
        )
        self.assertEqual(self.w.employees["E005"]["available_slots"], ["平日夜", "日曜"])
        self.assertIn("保存しました", [s.value for s in at.success])
        text = joined(self.app("E003", page="employee_profile", target_employee_id="E005"))
        self.assertIn("スポーツ（初心者）", text)  # 他人にも反映される（公開のとき）

    # ---- S-45（F-45）部活情報の保存・必須エラー ----
    def test_S45_save_changes_and_required_error(self):
        at = self.app("E002", page="club_admin")
        at.text_input(key="club_admin_1_name").set_value("新しい部活名")
        at = click_label(at, "保存する")
        self.assertEqual(self.w.clubs[1]["name"], "新しい部活名")
        self.assertIn("保存しました", [s.value for s in at.success])
        at.text_input(key="club_admin_1_name").set_value("   ")
        at = click_label(at, "保存する")
        self.assertIn("部活名を入力してください", [e.value for e in at.error])
        self.assertEqual(self.w.clubs[1]["name"], "新しい部活名")  # 空白のみは保存されない

    # ---- S-46（F-46）開催の登録・編集・中止・予定に戻す ----
    def test_S46_add_edit_cancel_restore_event(self):
        today = self.w.today()
        at = self.app("E002", page="club_admin")
        at.date_input(key="club_admin_1_add_date").set_value(today + timedelta(days=5))
        at.text_input(key="club_admin_1_add_place").set_value("第2会議室")
        click_label(at, "追加する")
        added = [e for e in self.w.club_events(1) if e["meeting_place"] == "第2会議室"]
        self.assertEqual(len(added), 1)
        self.assertEqual(added[0]["status"], "予定")
        ev = added[0]["id"]

        at = self.app("E002", page="club_admin")  # 編集
        at.button(key=f"club_admin_event_edit_{ev}").click().run()
        at.text_input(key=f"club_admin_event_edit_{ev}_place").set_value("屋上")
        click_label(at, "変更を保存")
        self.assertEqual(self.w.events[ev]["meeting_place"], "屋上")

        at = self.app("E002", page="club_admin")  # 中止（確認あり）
        at.button(key=f"club_admin_event_cancel_{ev}").click().run()
        self.assertIn("この開催を中止にしますか？申込済みの人にも中止と表示されます", [w.value for w in at.warning])
        at.button(key=f"club_admin_event_cancel_do_{ev}").click().run()
        self.assertEqual(self.w.events[ev]["status"], "中止")

        notes = len(self.w.notifications)
        at = self.app("E002", page="club_admin")  # 予定に戻す（通知しない）
        at.button(key=f"club_admin_event_restore_{ev}").click().run()
        self.assertEqual(self.w.events[ev]["status"], "予定")
        self.assertEqual(len(self.w.notifications), notes)

    # ---- S-48（F-48）メンバーの一覧・追加・削除 ----
    def test_S48_member_list_add_remove(self):
        at = self.app("E002", page="club_admin")
        text = joined(at)
        self.assertIn("幹事一郎（開発）　幹事", text)  # 幹事が分かる
        self.assertNotIn("club_admin_member_remove_1_E002", [b.key for b in at.button])  # 幹事は外せない
        at.selectbox(key="club_admin_1_member_pick").set_value("E003")
        click_label(at, "追加する", nth=1)  # 0番目は「開催」タブの追加ボタン
        self.assertIn("E003", [m["employee_id"] for m in self.w.members if m["club_id"] == 1])
        at = self.app("E002", page="club_admin")
        at.button(key="club_admin_member_remove_1_E003").click().run()
        self.assertNotIn("E003", [m["employee_id"] for m in self.w.members if m["club_id"] == 1])

    # ---- S-61（F-46, F-32）中止すると申込済みの人にだけ「中止」の通知 ----
    def test_S61_cancel_event_notifies_only_applied_people_and_keeps_status(self):
        ev = self.w.add_event(1, day_offset=2)
        applied = self.w.add_application(ev, "E003")
        canceled = self.w.add_application(ev, "E005", status="キャンセル")
        at = self.app("E002", page="club_admin")
        at.button(key=f"club_admin_event_cancel_{ev}").click().run()
        at.button(key=f"club_admin_event_cancel_do_{ev}").click().run()
        self.assertEqual(self.w.events[ev]["status"], "中止")
        self.assertEqual(len(self.w.notes_for("E003", "中止")), 1)
        self.assertEqual(self.w.notes_for("E005", "中止"), [])
        self.assertEqual(self.w.applications[applied]["status"], "申込済み")  # 申込の状態は変わらない
        self.assertEqual(self.w.applications[canceled]["status"], "キャンセル")
        # 申込済みの人が通知一覧を開く（画面をまたぐ確認）
        text = joined(self.app("E003", page="notifications"))
        self.assertIn("【中止】", text)
        self.assertNotIn("【中止】", joined(self.app("E005", page="notifications")))


if __name__ == "__main__":
    unittest.main()
