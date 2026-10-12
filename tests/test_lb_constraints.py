"""L-B: 一意制約。I-090（employee_interests）・I-091（club_members）。

I-090/I-091 の期待は「同じ組を重複登録しようとすると登録できない（DBの一意制約）」。
これを確かめるには、実DBに同じ組をもう一度 insert して拒否されるのを見る必要がある（書込）。
制約が無かった場合は重複行が1件残ってしまうため、READ-ONLY のこのハーネスでは実行しない（skip 固定）。
書込の可否と後始末は運営（PM）の承認が要るため、god に報告して止めている。

代わりに置いてあるのは「既存データに重複が無い」ことの読取確認（参考）。制約があることの証明ではないため、
I-090/I-091 の合否には使わない。
"""

import unittest
from collections import Counter

from lb_base import LbTestCase

_WRITE_REQUIRED = "書込が必要（重複insertの拒否を見る）。READ-ONLY原則のため実行しない。運営承認後に別途"


class UniqueConstraintsLb(LbTestCase):
    @unittest.skip(f"I-090: {_WRITE_REQUIRED}")
    def test_I090_duplicate_employee_interest_is_rejected(self):
        """同じ employee_id × activity_id を重複登録 → 登録できない。"""

    @unittest.skip(f"I-091: {_WRITE_REQUIRED}")
    def test_I091_duplicate_club_member_is_rejected(self):
        """同じ club_id × employee_id を重複登録 → 登録できない。"""

    # 参考（I-090/I-091の合否には使わない）: 既存データに重複が無い。
    def test_reference_no_duplicate_rows_in_existing_data(self):
        for table, keys in (
            ("employee_interests", ("employee_id", "activity_id")),
            ("club_members", ("club_id", "employee_id")),
        ):
            with self.subTest(table=table):
                counts = Counter(tuple(row[k] for k in keys) for row in self.table(table))
                self.assertEqual([k for k, n in counts.items() if n > 1], [])
