"""L-B: 部活検索（clubs_repo.search）の条件絞り込み。I-022〜I-026（SP-20）。

実DBの clubs / activities を読み、期待値は生テーブルからPythonで組み立てる（READ-ONLY）。
データは実DBから探す。条件に合うデータが無いときは、合格にせず skip にして理由を出す。
"""

from lb_base import LbTestCase

_FORBIDDEN = set(',()"%_\\')


class ClubsSearchLb(LbTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.clubs = cls.table("clubs")
        cls.activities = {a["id"]: a for a in cls.table("activities")}

    def search_ids(self, conditions):
        return {c["id"] for c in self.env.clubs_repo.search(conditions)}

    def active(self):
        return [c for c in self.clubs if c["is_active"]]

    def category(self, club):
        return (self.activities.get(club["activity_id"]) or {}).get("category")

    # I-022: 活動カテゴリ×拠点を設定 → 両条件のANDを満たす部活のみ。
    def test_I022_category_and_location_are_anded(self):
        pairs = {(self.category(c), c["location"]) for c in self.active()}
        cats = {c for c, _ in pairs}
        locs = {l for _, l in pairs}

        def oracle(cat, loc):
            return {c["id"] for c in self.active() if self.category(c) == cat and c["location"] == loc}

        # AND が単独条件より狭くなる組を優先（絞り込みが効いていることを見せる）。
        candidates = sorted(
            ((cat, loc) for cat in cats for loc in locs if oracle(cat, loc)),
            key=lambda p: (
                len(oracle(*p)) == len(self.search_ids({"categories": [p[0]]})),
                p[0] or "",
                p[1] or "",
            ),
        )
        if not candidates:
            self.skipTest("カテゴリ×拠点の両方に合う有効な部活が実DBに無い")
        cat, loc = candidates[0]
        got = self.search_ids({"categories": [cat], "locations": [loc]})
        self.assertEqual(got, oracle(cat, loc))
        for club in self.env.clubs_repo.search({"categories": [cat], "locations": [loc]}):
            self.assertEqual(club["location"], loc)
            self.assertEqual(self.category(club), cat)

    # I-023: 拠点を2つ選択 → ORで、どちらかに合う部活。
    def test_I023_locations_are_ored(self):
        locs = sorted({c["location"] for c in self.active() if c["location"]})
        if len(locs) < 2:
            self.skipTest("有効な部活の拠点が2種類以上ない")
        a, b = locs[0], locs[1]
        got = self.search_ids({"locations": [a, b]})
        want = {c["id"] for c in self.active() if c["location"] in (a, b)}
        self.assertEqual(got, want)
        self.assertEqual(got, self.search_ids({"locations": [a]}) | self.search_ids({"locations": [b]}))
        self.assertGreater(len(got), len(self.search_ids({"locations": [a]})))

    # I-024: すべて未選択 → 全件（is_active=true のみ）。未指定は条件として扱われない。
    def test_I024_no_condition_returns_all_active(self):
        want = {c["id"] for c in self.active()}
        self.assertTrue(want, "有効な部活が0件では確認できない")
        empty = {"categories": [], "locations": [], "slots": [], "levels": [], "keyword": ""}
        none = {"categories": None, "locations": None, "slots": None, "levels": None, "keyword": None}
        for conditions in ({}, empty, none):
            with self.subTest(conditions=conditions):
                self.assertEqual(self.search_ids(conditions), want)

    # I-025: キーワードが 部活名・活動名・ひとこと の一部 → それぞれ部分一致でヒット。
    def test_I025_keyword_matches_name_activity_and_message(self):
        def pieces(text):
            text = (text or "").strip()
            if len(text) < 2 or any(ch in _FORBIDDEN or ch.isspace() for ch in text[:3]):
                return None
            return text[:3] if len(text) >= 3 else text

        def oracle(keyword):
            k = keyword.lower()
            out = set()
            for c in self.active():
                act = (self.activities.get(c["activity_id"]) or {}).get("name") or ""
                if k in (c["name"] or "").lower() or k in (c["message"] or "").lower() or k in act.lower():
                    out.add(c["id"])
            return out

        targets = {
            "部活名": lambda c: c["name"],
            "活動名": lambda c: (self.activities.get(c["activity_id"]) or {}).get("name"),
            "ひとこと": lambda c: c["message"],
        }
        checked = 0
        for label, pick in targets.items():
            for club in self.active():
                keyword = pieces(pick(club))
                if keyword is None:
                    continue
                with self.subTest(kind=label, keyword=keyword):
                    got = self.search_ids({"keyword": keyword})
                    self.assertIn(club["id"], got)
                    self.assertEqual(got, oracle(keyword))
                checked += 1
                break
        if checked == 0:
            self.skipTest("キーワードにできる部活名・活動名・ひとことが実DBに無い")

    # I-026: is_active=false の部活は結果に出ない。
    def test_I026_inactive_clubs_are_excluded(self):
        inactive = [c for c in self.clubs if not c["is_active"]]
        if not inactive:
            self.skipTest("is_active=false の部活が実DBに無い（読取専用では作れない。データ投入の相談が必要）")
        inactive_ids = {c["id"] for c in inactive}
        self.assertFalse(inactive_ids & self.search_ids({}))
        for club in inactive:
            keyword = (club["name"] or "").strip()[:3]
            if len(keyword) >= 2 and not any(ch in _FORBIDDEN for ch in keyword):
                with self.subTest(keyword=keyword):
                    self.assertNotIn(club["id"], self.search_ids({"keyword": keyword}))
            if club["location"]:
                with self.subTest(location=club["location"]):
                    self.assertNotIn(club["id"], self.search_ids({"locations": [club["location"]]}))
