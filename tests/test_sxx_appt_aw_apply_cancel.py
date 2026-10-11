"""S-xx 黒箱 α-W（実DB書込）: 申込・キャンセルの主役4件。S-19 / S-25 / S-26 / S-20（DB分）。

層: α-W（application_service.apply / cancel を実repo＋実DBで呼ぶ。画面は通さない）。
実行は LB_WRITE=1 のときだけ（共有DBへ書くため。運営承認済み）。使う行は全て「センチネル」:
  社員 E998（幹事役）・E999（申込者役）、名前が "LB-TEST-" で始まる is_active=false の部活とその開催（30日後・予定）。
  実在の行は変更・削除しない。各テストは 投入 → 検証 → 後始末（addCleanup。失敗しても必ず実行）→ 9表の件数 before==after。
期待結果の根拠: テスト設計.md S-19/S-20/S-25/S-26、仕様.md SP-66（申込）・SP-67（キャンセルと再申込）。
"""

import unittest

from lb_base import SENTINEL_EMP_ID, SENTINEL_EMP_ID_2, LbWriteTestCase, is_unique_violation
from services.errors import ConflictError

APPLICANT = SENTINEL_EMP_ID  # E999
ORGANIZER = SENTINEL_EMP_ID_2  # E998
_NOTE = "LB-TEST-幹事への一言"


class ApplyCancelAw(LbWriteTestCase):
    # --- 共通 -------------------------------------------------------------
    def setup_world(self, tag: str):
        """E998・E999・センチネル部活（幹事=E998）・その開催1件を投入して (club, event) を返す。"""
        self.start_write_test(second_employee=True)
        club = self.insert_sentinel_club(tag, organizer_id=ORGANIZER)
        return club, self.insert_sentinel_event(club["id"])

    def rows(self, table: str, **eq):
        query = self.db.table(table).select("*")
        for column, value in eq.items():
            query = query.eq(column, value)
        return query.execute().data

    def apply(self, event_id: int, message: str | None = _NOTE) -> dict:
        return self.env.application_service.apply(event_id, APPLICANT, message)

    def cancel(self, application_id: int) -> None:
        self.env.application_service.cancel(application_id, APPLICANT)

    # --- S-19 -------------------------------------------------------------
    def test_S19_apply_writes_application_message_notification_and_log(self):
        """S-19: 予定・未申込の開催に、幹事への一言つきで申込 → 申込が完了する（SP-66）。

        投入: E998/E999・センチネル部活（幹事E998）・開催2件。検証（1件目・一言あり）: applications に1行（申込済み・
        初参加・canceled_at空）、messages に1行（送信者=申込者・本文=一言）、幹事E998あての通知1件（種類「申込」・
        application_id と event_id つき・未読）、操作履歴 apply が1件（申込者・その部活）。
        （2件目・一言が空／空白のみ）→ applications は入り、messages は増えない。
        後始末: 通知・履歴・メッセージ・申込・開催・部活・E998/E999 を削除。9表の件数が元に戻る。
        """
        club, event = self.setup_world("S19")
        result = self.apply(event["id"])
        self.assertEqual(set(result), {"application_id", "is_first_time"})
        application_id = result["application_id"]
        self.assertTrue(result["is_first_time"], "メンバーでなく過去の申込も無い → 初参加（SP-68）")

        (application,) = self.rows("applications", id=application_id)
        self.assertEqual(
            (application["event_id"], application["applicant_id"], application["status"], application["is_first_time"]),
            (event["id"], APPLICANT, "申込済み", True),
        )
        self.assertIsNotNone(application["applied_at"])
        self.assertIsNone(application["canceled_at"])

        (message,) = self.rows("messages", application_id=application_id)
        self.assertEqual((message["sender_id"], message["body"]), (APPLICANT, _NOTE))

        (notice,) = self.rows("notifications", application_id=application_id)
        self.assertEqual(
            (notice["recipient_id"], notice["type"], notice["event_id"]), (ORGANIZER, "申込", event["id"])
        )
        self.assertIsNone(notice["read_at"], "届いた通知は未読")

        (log,) = self.rows("action_logs", employee_id=APPLICANT, action="apply")
        self.assertEqual(log["club_id"], club["id"])

        for blank in ("", "   ", None):
            with self.subTest(message=repr(blank)):
                other = self.insert_sentinel_event(club["id"], days_ahead=31 + ["", "   ", None].index(blank))
                application_id_2 = self.apply(other["id"], blank)["application_id"]
                self.assertEqual(len(self.rows("applications", id=application_id_2)), 1)
                self.assertEqual(self.rows("messages", application_id=application_id_2), [], "一言が空なら messages に入れない")

    # --- S-25 -------------------------------------------------------------
    def test_S25_cancel_updates_status_and_notifies_organizer(self):
        """S-25: 申込済みの申込をキャンセル → 状態「キャンセル」・canceled_at が入り、幹事に通知（SP-67）。

        投入: S-19 と同じ世界で1件申込。検証: applications の status=キャンセル・canceled_at が入る。
        幹事E998あての通知に種類「キャンセル」が1件（同じ application_id・event_id）。やり取り（messages）は残る
        （キャンセルした申込のやり取りは閲覧のみ）。後始末: S-19 と同じ（9表の件数が元に戻る）。
        """
        club, event = self.setup_world("S25")
        application_id = self.apply(event["id"])["application_id"]

        self.cancel(application_id)

        (application,) = self.rows("applications", id=application_id)
        self.assertEqual(application["status"], "キャンセル")
        self.assertIsNotNone(application["canceled_at"])
        notices = {n["type"]: n for n in self.rows("notifications", application_id=application_id)}
        self.assertEqual(set(notices), {"申込", "キャンセル"})
        self.assertEqual(
            (notices["キャンセル"]["recipient_id"], notices["キャンセル"]["event_id"]), (ORGANIZER, event["id"])
        )
        self.assertEqual(len(self.rows("messages", application_id=application_id)), 1, "やり取りは残る")

    # --- S-26 -------------------------------------------------------------
    def test_S26_reapply_after_cancel_is_a_new_application(self):
        """S-26: キャンセル後に同じ開催へ再申込できる。新しい申込として扱われる（SP-67・部分一意インデックス）。

        投入: 1件申込 → キャンセル → 同じ開催へ再申込（どちらも一言つき）。検証: 再申込の application_id は別の値。
        (開催, E999) の申込は2行（キャンセル1・申込済み1）で、有効（申込済み）は1行だけ。やり取りは申込ごとに別
        （messages は両方の申込にそれぞれ1件）。後始末: S-19 と同じ（9表の件数が元に戻る）。
        """
        club, event = self.setup_world("S26")
        first = self.apply(event["id"])["application_id"]
        self.cancel(first)

        second = self.apply(event["id"])["application_id"]

        self.assertNotEqual(first, second)
        rows = self.rows("applications", event_id=event["id"], applicant_id=APPLICANT)
        self.assertEqual(sorted(r["status"] for r in rows), ["キャンセル", "申込済み"])
        (active,) = [r for r in rows if r["status"] == "申込済み"]
        self.assertEqual(active["id"], second)
        for application_id in (first, second):
            with self.subTest(application_id=application_id):
                self.assertEqual(len(self.rows("messages", application_id=application_id)), 1)

    # --- S-20（DB分）-------------------------------------------------------
    def test_S20_db_rejects_second_active_application_for_same_event(self):
        """S-20（DB分）: 既に申込済みの開催への重複申込は、実DBでも入らない（部分一意インデックス）。

        投入: 1件申込。検証: (1) service の再申込は ConflictError(already_applied)。(2) service を通さずに同じ
        (開催, 申込者) の「申込済み」行を直接 insert → unique_violation(23505) で拒否される。
        有効な申込は1行のまま。後始末: S-19 と同じ（9表の件数が元に戻る）。画面のエラー文言は α-0 で確認済み。
        """
        club, event = self.setup_world("S20")
        application_id = self.apply(event["id"])["application_id"]

        with self.assertRaises(ConflictError) as service_error:
            self.apply(event["id"])
        self.assertEqual(service_error.exception.reason, "already_applied")

        duplicate = {"event_id": event["id"], "applicant_id": APPLICANT, "status": "申込済み", "is_first_time": False}
        with self.assertRaises(Exception) as db_error:
            self.db.table("applications").insert(duplicate).execute()
        self.assertTrue(
            is_unique_violation(db_error.exception), f"一意制約違反以外の失敗: {type(db_error.exception).__name__}"
        )

        rows = self.rows("applications", event_id=event["id"], applicant_id=APPLICANT)
        self.assertEqual([r["id"] for r in rows], [application_id], "有効な申込が増えている")


if __name__ == "__main__":
    unittest.main()
