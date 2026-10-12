"""α-R テスト（sxx_ar_cases.py）の動作確認（ドライラン）。実DBには一切つながない。

目的: 実DBで回す前に、α-R の「データ探し・期待値の組み立て・画面操作・画面の読み取り」が動くことを、
L-C の偽repoの世界（tests/fakes.py）を豊かにした合成データで確認する。実DBの合否の代わりにはならない。
（通ってもスキップが多くても、実DBの結果は何も示さない。書き間違いを先に潰すためのもの。）

実行: python3 tests/sxx_ar_dryrun.py            通常
      python3 tests/sxx_ar_dryrun.py -k S11     一部だけ
"""

import sys
import unittest
from datetime import timedelta
from types import SimpleNamespace

import fakes
from lc_base import LcTestCase
from sxx_ar_cases import ArCases


def enrich(w):
    """偽の世界に、検索・おすすめ・通知・申込などを確かめられるだけのデータを足す。"""
    w.activities[:] = [
        {"id": 1, "name": "スポーツ", "category": "スポーツ"},
        {"id": 2, "name": "音楽", "category": "文化・趣味"},
        {"id": 3, "name": "ボードゲーム", "category": "ゲーム"},
    ]
    depts, locs, slots = ["開発", "営業", "人事"], ["東京", "大阪"], ["平日夜", "土曜午前", "土曜午後", "日曜"]
    for i in range(6, 36):
        w.add_employee(
            f"E{i:03d}", name=f"社員{i:03d}", dept=depts[i % 3], location=locs[i % 2], joined_year=2015 + i % 8,
            entry_type=["新卒", "中途"][i % 2], interests_public=i % 4 != 0, slots_public=i % 5 != 0,
            available_slots=slots[: 1 + i % 3],
        )
        w.interests[f"E{i:03d}"] = [{"activity_id": 1 + i % 3, "level": ["未経験", "初心者", "経験あり"][i % 3]}]
    for eid in ("E003", "E005"):
        w.interests[eid] = [{"activity_id": 1, "level": "初心者"}]
        w.employees[eid]["available_slots"] = ["平日夜"]
    levels = ["初心者歓迎", "レベル問わず", "経験者向け"]
    for n, cid in enumerate(range(3, 8)):
        w.add_club(cid, organizer_id=f"E{6 + n:03d}", name=f"追加部{cid}", location=locs[n % 2], slot=slots[n % 4],
                   level=levels[n % 3], activity_id=1 + n % 3, mood_tags=["ゆるめ"] if n % 2 else [],
                   message=f"追加部{cid}のひとこと", is_active=cid != 7)
    for i in range(6, 20):
        w.add_member(1 + i % 7, f"E{i:03d}")
    for off in range(0, 16):
        cid = 1 + off % 6
        eid = w.add_event(cid, day_offset=off, status="中止" if off % 7 == 3 else "予定")
        if w.events[eid]["status"] == "予定":
            w.add_application(eid, f"E{6 + off:03d}", is_first_time=off % 2 == 0)
    w.add_application(w.add_event(1, day_offset=-5), "E003", is_first_time=False)
    for kind in ("申込", "メッセージ", "スタンプ", "申込"):
        w.add_notification("E003", kind, read=kind == "スタンプ")
    w.add_notification("E002", "申込")
    w.action_logs.append({"id": 1, "employee_id": "E003", "action": "view_club", "club_id": 1, "conditions": None})
    w.action_logs.append({"id": 2, "employee_id": "E003", "action": "search_club", "club_id": None,
                          "conditions": {"keyword": "テ"}})


class FakeAppCase(LcTestCase):
    """α-R の土台と同じ口（self.app / self.table / self.env / self.today）を、偽の世界で与える。"""

    IS_DRY = True

    def setUp(self):
        super().setUp()
        enrich(self.w)
        self.env = SimpleNamespace(search_service=fakes.search_service, employees_repo=fakes.employees_repo)

    def today(self):
        return self.w.today()

    def table(self, name):
        w = self.w
        if name == "clubs":
            return [dict(c) for c in w.clubs.values()]
        if name == "activities":
            return [dict(a) for a in w.activities]
        if name == "employees":
            return [dict(e) for e in w.employees.values()]
        if name == "events":
            return [dict(e) for e in w.events.values()]
        if name == "applications":
            return [dict(a) for a in w.applications.values()]
        if name == "club_members":
            return [dict(m) for m in w.members]
        if name == "employee_interests":
            return [{"employee_id": eid, "activity_id": i["activity_id"], "level": i["level"]}
                    for eid, items in w.interests.items() for i in items]
        if name == "notifications":
            return [dict(n) for n in w.notifications]
        if name == "action_logs":
            return [dict(r, created_at="2026-10-14T12:00:00+09:00") for r in w.action_logs]
        raise KeyError(name)


class Dry(ArCases, FakeAppCase):
    def setUp(self):
        super().setUp()
        # 偽repoは絞り込まない。画面の入力→条件→結果の配線を確かめるため、絞り込みだけ期待値の定義で差し替える。
        # （絞り込み自体の正しさは L-B／実DBで確認する。ここは画面の配線とハーネスの書き間違いを見るためのもの。）
        fakes.clubs_repo.search = lambda c: [dict(x) for x in self.w.clubs.values()
                                             if x["id"] in self.club_oracle(c or {})]
        fakes.employees_repo.search = lambda c, limit, offset: [
            dict(self.w.employees[i]) for i in sorted(self.employee_oracle(c or {}))][offset: offset + limit]
        fakes.employees_repo.count = lambda c: len(self.employee_oracle(c or {}))
        self.apply_mutation(MUTATION)

    def apply_mutation(self, name):
        """意図的な不具合を入れ、テストが落ちること（検出力）を確かめる。--mutate 名前 で指定する。"""
        if not name:
            return
        if name == "week-end-today":  # S-11: 「今週」の終わりを今日にする
            fakes.search_service.timedelta = lambda days=0: timedelta(0)
        elif name == "leak-private":  # S-36: 非公開の興味・時間を結果に出す
            fakes.search_service._visibility = lambda is_public, is_self: "public"
        elif name == "recommend-joined":  # S-12: 所属済みの部活もおすすめに出す
            fakes.club_members_repo.list_clubs_by_member = lambda employee_id: []
        elif name == "ignore-slots":  # S-13: 曜日・時間帯の絞り込みが効かない
            original = fakes.clubs_repo.search
            fakes.clubs_repo.search = lambda c: original({k: v for k, v in (c or {}).items() if k != "slots"})
        elif name == "drop-first-time-mark":  # S-28: 初参加の印を落とす
            original = fakes.applications_repo.list_by_organizer_club
            fakes.applications_repo.list_by_organizer_club = lambda cid: [dict(a, is_first_time=False) for a in original(cid)]
        else:
            raise SystemExit(f"未知の mutate: {name}")


MUTATION = None


def main():
    global MUTATION
    if "--mutate" in sys.argv:
        i = sys.argv.index("--mutate")
        MUTATION = sys.argv[i + 1]
        del sys.argv[i: i + 2]
    loader = unittest.defaultTestLoader
    suite = loader.loadTestsFromTestCase(Dry)
    pattern = None
    if "-k" in sys.argv:
        pattern = sys.argv[sys.argv.index("-k") + 1]
        suite = unittest.TestSuite(t for t in suite if pattern in t.id())
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
