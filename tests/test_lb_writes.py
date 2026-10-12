"""L-B 書込: I-026（非公開部活の除外）・I-090（興味の重複拒否）・I-091（所属の重複拒否）。

実行は LB_WRITE=1 のときだけ（共有DBへ書くため。運営承認済み）。使う行は全て「センチネル」:
社員 E999（name="LB-TEST-employee"）と、名前が "LB-TEST-" で始まる is_active=false の部活。実在の行は変更・削除しない。
各テストは 投入 → 検証 → 後始末（addCleanup。失敗しても必ず実行）→ 件数が before==after、の順。
"""

import unittest

from lb_base import SENTINEL_EMP_ID, LbWriteTestCase

_DUPLICATE_CODE = "23505"  # PostgreSQL unique_violation


def _is_unique_violation(exc: Exception) -> bool:
    return getattr(exc, "code", None) == _DUPLICATE_CODE or "duplicate key" in str(exc).lower()


class WritesLb(LbWriteTestCase):
    def test_I026_inactive_sentinel_club_is_excluded_from_search(self):
        """I-026: is_active=false の部活は検索結果に出ない。

        投入: センチネル部活1件（is_active=false）。検証: 行が実在すること（clubs_repo.get）→
        search の「条件なし／部活名／拠点／活動カテゴリ／時間帯／レベル」のどれにも出ない。
        後始末: その部活を削除（社員E999も削除）。件数は clubs/employees とも元に戻る。
        """
        self.start_write_test()
        club = self.insert_sentinel_club("I026")
        stored = self.env.clubs_repo.get(club["id"])
        self.assertIsNotNone(stored, "投入した部活が取得できない（除外の確認にならない）")
        self.assertFalse(stored["is_active"])

        category = (
            self.db.table("activities").select("category").eq("id", club["activity_id"]).execute().data[0]["category"]
        )
        conditions = {
            "条件なし": {},
            "部活名": {"keyword": club["name"]},
            "拠点": {"locations": [club["location"]]},
            "活動カテゴリ": {"categories": [category]},
            "時間帯": {"slots": [club["slot"]]},
            "レベル": {"levels": [club["level"]]},
        }
        for label, cond in conditions.items():
            with self.subTest(condition=label):
                ids = {c["id"] for c in self.env.clubs_repo.search(cond)}
                self.assertNotIn(club["id"], ids)

    def test_I090_duplicate_employee_interest_is_rejected(self):
        """I-090: 同じ employee_id × activity_id を重複登録 → 一意制約で拒否される。

        投入: E999 × 実在の活動 の1組（1回目は成功）。検証: 同じ組をもう一度 insert → unique_violation(23505)、
        E999 の employee_interests は1行のまま。後始末: E999 の行を削除。employee_interests 件数が元に戻る。
        """
        self.start_write_test()
        before_total = self.db.table("employee_interests").select("employee_id", count="exact").limit(1).execute().count
        row = {"employee_id": SENTINEL_EMP_ID, "activity_id": self.activity_id, "level": "初心者"}
        self.db.table("employee_interests").insert(row).execute()

        with self.assertRaises(Exception) as ctx:
            self.db.table("employee_interests").insert(row).execute()
        self.assertTrue(_is_unique_violation(ctx.exception), f"一意制約違反以外の失敗: {type(ctx.exception).__name__}")

        mine = self.db.table("employee_interests").select("employee_id").eq("employee_id", SENTINEL_EMP_ID).execute().data
        self.assertEqual(len(mine), 1, "重複が増えている")
        total = self.db.table("employee_interests").select("employee_id", count="exact").limit(1).execute().count
        self.assertEqual(total, before_total + 1)

    def test_I091_duplicate_club_member_is_rejected(self):
        """I-091: 同じ club_id × employee_id を重複登録 → 一意制約で拒否される。

        投入: センチネル部活1件＋所属（その部活 × E999）の1組（1回目は成功）。検証: 素の insert を重ねる →
        unique_violation(23505)、所属は1行のまま。参考として repo の add_member（ignore_duplicates）を重ねても1行のまま。
        後始末: 所属・部活・E999 を削除。club_members/clubs 件数が元に戻る。
        """
        self.start_write_test()
        club = self.insert_sentinel_club("I091")
        row = {"club_id": club["id"], "employee_id": SENTINEL_EMP_ID}
        self.db.table("club_members").insert(row).execute()

        with self.assertRaises(Exception) as ctx:
            self.db.table("club_members").insert(row).execute()
        self.assertTrue(_is_unique_violation(ctx.exception), f"一意制約違反以外の失敗: {type(ctx.exception).__name__}")

        self.env.club_members_repo.add_member(club["id"], SENTINEL_EMP_ID)  # 重ねても増えない（repoの二重呼び出し安全）
        mine = self.db.table("club_members").select("club_id").eq("club_id", club["id"]).execute().data
        self.assertEqual(len(mine), 1, "重複が増えている")


if __name__ == "__main__":
    unittest.main()
