"""L-B: 社員検索（employees_repo.search / count）の条件絞り込み。I-064〜I-068・I-140（SP-48, SP-49）。

実DBの employees / employee_interests / club_members を読み、期待値は生テーブルからPythonで組み立てる（READ-ONLY）。
データは実DBから探す。条件に合うデータが無いときは、合格にせず skip にして理由を出す。
"""

import re

from lb_base import LbTestCase

BIG = 1000  # 全件が1ページに入る大きさ（社員は500人）


class EmployeesSearchLb(LbTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employees = cls.table("employees")
        cls.interests = {}
        for row in cls.table("employee_interests"):
            cls.interests.setdefault(row["employee_id"], set()).add(row["activity_id"])
        cls.members = {}
        for row in cls.table("club_members"):
            cls.members.setdefault(row["club_id"], set()).add(row["employee_id"])

    def ids(self, conditions):
        return {e["id"] for e in self.env.employees_repo.search(conditions, BIG, 0)}

    def oracle(self, c):
        """仕様の定義どおりの期待値。項目間AND・同一項目内OR。SP-49: 条件にしたときだけ非公開を除外。"""
        out = set()
        for e in self.employees:
            if c.get("name") and re.sub(r"\s+", "", c["name"]).lower() not in (e["name"] or "").lower():
                continue
            if c.get("depts") and e["dept"] not in c["depts"]:
                continue
            if c.get("locations") and e["location"] not in c["locations"]:
                continue
            if c.get("slots") and not (e["slots_public"] and set(e["available_slots"] or []) & set(c["slots"])):
                continue
            if c.get("interests") and not (
                e["interests_public"] and self.interests.get(e["id"], set()) & set(c["interests"])
            ):
                continue
            if c.get("club_id") is not None and e["id"] not in self.members.get(c["club_id"], set()):
                continue
            out.add(e["id"])
        return out

    def pick_full_profile(self):
        """全項目で絞れる社員（公開・興味あり・時間あり・所属あり）。"""
        for e in self.employees:
            mine = self.interests.get(e["id"], set())
            clubs = [cid for cid, ms in self.members.items() if e["id"] in ms]
            if (
                e["interests_public"] and e["slots_public"] and mine and e["available_slots"]
                and clubs and e["dept"] and e["location"] and len(e["name"] or "") >= 2
            ):
                return e, sorted(mine), clubs[0]
        return None

    # I-064: 名前・部署・拠点・興味・所属部活・参加可能時間を組み合わせて検索 → AND/OR で絞り込まれる。
    def test_I064_combined_conditions_and_or(self):
        picked = self.pick_full_profile()
        if picked is None:
            self.skipTest("全項目の条件を作れる社員（公開・興味/時間/所属あり）が実DBに無い")
        e, mine, club_id = picked
        other_dept = next((x["dept"] for x in self.employees if x["dept"] != e["dept"]), e["dept"])
        other_activity = next(
            (a for a in {i for s in self.interests.values() for i in s} if a not in mine), mine[0]
        )
        full = {
            "name": e["name"][:2],
            "depts": [e["dept"], other_dept],  # 同一項目内はOR
            "locations": [e["location"]],
            "interests": [mine[0], other_activity],
            "club_id": club_id,
            "slots": [e["available_slots"][0]],
        }
        combos = [
            {"depts": full["depts"], "locations": full["locations"]},
            {"name": full["name"], "club_id": club_id},
            {"interests": full["interests"], "slots": full["slots"]},
            {"locations": full["locations"], "club_id": club_id, "slots": full["slots"]},
            full,
        ]
        for conditions in combos:
            with self.subTest(keys=sorted(conditions)):
                got = self.ids(conditions)
                self.assertEqual(got, self.oracle(conditions))
                self.assertEqual(self.env.employees_repo.count(conditions), len(got))
        self.assertIn(e["id"], self.ids(full))
        # 項目を足すほど狭くなる（ANDが効いている）。
        self.assertLessEqual(len(self.ids(full)), len(self.ids({"depts": full["depts"]})))

    def _names_without_space(self):
        return [e for e in self.employees if e["name"] and len(e["name"]) >= 2 and not re.search(r"\s", e["name"])]

    def _space_insensitive(self, space):
        candidates = self._names_without_space()
        if not candidates:
            self.skipTest("スペースを含まない氏名の社員が実DBに無い")
        e = candidates[0]
        plain = e["name"]
        spaced = plain[0] + space + plain[1:]
        got_plain = self.ids({"name": plain})
        got_spaced = self.ids({"name": spaced})
        self.assertIn(e["id"], got_plain)
        self.assertEqual(got_spaced, got_plain)  # スペースなしで入力したときと同じ社員
        self.assertIn(e["id"], got_spaced)

    # I-065: 氏名にスペースが無い社員に、半角スペースを含めて入力 → スペースを無視して部分一致。
    def test_I065_half_width_space_is_ignored(self):
        self._space_insensitive(" ")

    # I-140: 全角スペースを含めて入力（境界値） → 全角スペースも無視して部分一致。
    def test_I140_full_width_space_is_ignored(self):
        self._space_insensitive("　")

    def _with_interest(self, public):
        return [
            e for e in self.employees
            if e["interests_public"] is public and self.interests.get(e["id"])
        ]

    # I-066: interests_public=false の社員は、興味を条件にした検索結果に出ない。
    def test_I066_private_interests_are_hidden(self):
        targets = self._with_interest(False)
        if not targets:
            self.skipTest("interests_public=false で興味を持つ社員が実DBに無い")
        for e in targets[:5]:
            for activity_id in sorted(self.interests[e["id"]])[:2]:
                with self.subTest(employee=e["id"], activity=activity_id):
                    self.assertNotIn(e["id"], self.ids({"interests": [activity_id]}))

    # I-067: slots_public=false の社員は、参加可能時間を条件にした検索結果に出ない。
    def test_I067_private_slots_are_hidden(self):
        targets = [e for e in self.employees if e["slots_public"] is False and e["available_slots"]]
        if not targets:
            self.skipTest("slots_public=false で参加可能時間を持つ社員が実DBに無い")
        for e in targets[:5]:
            for slot in e["available_slots"][:2]:
                with self.subTest(employee=e["id"], slot=slot):
                    self.assertNotIn(e["id"], self.ids({"slots": [slot]}))

    # I-068: interests_public=true（対照ケース） → 興味を条件にした検索結果に出る。
    def test_I068_public_interests_are_shown(self):
        targets = self._with_interest(True)
        if not targets:
            self.skipTest("interests_public=true で興味を持つ社員が実DBに無い")
        for e in targets[:5]:
            activity_id = sorted(self.interests[e["id"]])[0]
            with self.subTest(employee=e["id"], activity=activity_id):
                self.assertIn(e["id"], self.ids({"interests": [activity_id]}))
