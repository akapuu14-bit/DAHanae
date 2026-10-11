"""L-B: 一意制約の読取確認（READ-ONLY）。

I-090（employee_interests）・I-091（club_members）の本体は書込が必要なため tests/test_lb_writes.py
（LB_WRITE=1・センチネル行のみ・必ず後始末）に移した。ここに置いてあるのは「既存データに重複が無い」ことの
読取確認（参考）で、制約があることの証明ではないため I-090/I-091 の合否には使わない。
"""

from collections import Counter

from lb_base import LbTestCase


class UniqueConstraintsLb(LbTestCase):
    # 参考（I-090/I-091の合否には使わない）: 既存データに重複が無い。
    def test_reference_no_duplicate_rows_in_existing_data(self):
        for table, keys in (
            ("employee_interests", ("employee_id", "activity_id")),
            ("club_members", ("club_id", "employee_id")),
        ):
            with self.subTest(table=table):
                counts = Counter(tuple(row[k] for k in keys) for row in self.table(table))
                self.assertEqual([k for k, n in counts.items() if n > 1], [])
