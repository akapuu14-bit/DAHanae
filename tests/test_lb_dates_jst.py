"""L-B: 日付の日本時間(JST)判定。I-008（SP-08 週の切替）、I-178〜I-180（SP-68 初参加判定の「過去の開催」）。

実DBは READ-ONLY のまま、「今」だけを固定する（repo/service の datetime を差し替える）。
データは実DBから探す。条件に合うデータが無いときは、合格にせず skip にして理由を出す。

- I-178〜I-180 の対象は applications_repo.has_past_non_canceled（過去＝event_date < 日本時間の今日）と、
  それを使う application_service._is_first_time（読み取りだけ。申込の保存はしない）。
- 「別の開催に申込む」の保存（insert）はここでは行わない。書込が要るため、初参加の判定部分だけを確認する。
"""

import os
import time
from datetime import timedelta

from lb_base import LbTestCase, jst


class WeekBoundaryLb(LbTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.events = cls.table("events")
        cls.clubs = {c["id"]: c for c in cls.table("clubs")}

    def oracle(self, today):
        """今日〜今週の日曜（両端を含む）に「予定」の開催がある有効な部活の id（仕様 SP-08・乖離H-1）。"""
        sunday = self.week_sunday(today)
        out = set()
        for e in self.events:
            club = self.clubs.get(e["club_id"])
            day = e["event_date"] if not isinstance(e["event_date"], str) else _d(e["event_date"])
            if e["status"] == "予定" and club and club["is_active"] and today <= day <= sunday:
                out.add(club["id"])
        return out

    def this_week(self, instant):
        self.freeze(instant, self.env.search_service, self.env.events_repo)
        return self.env.search_service.get_this_week_clubs()

    # I-008: 週の境界（日曜24:00→月曜0:00）で次の週に切り替わる。範囲は「今日〜今週の日曜（両端を含む）」。
    def test_I008_week_switches_at_sunday_midnight(self):
        days = sorted({_d(e["event_date"]) if isinstance(e["event_date"], str) else e["event_date"] for e in self.events})
        if not days:
            self.skipTest("開催が実DBに無い")
        sunday = self.week_sunday(days[0])
        both = None
        for _ in range(60):  # 日曜の当日と翌週の両方に予定の開催がある週を探す
            if self.oracle(sunday) and self.oracle(sunday + timedelta(days=1)):
                both = sunday
                break
            sunday += timedelta(days=7)
        if both is None:
            self.skipTest("日曜の当日と翌週の両方に予定の開催がある週が実DBに無い")
        s = both
        monday = s + timedelta(days=1)

        sun_late = self.this_week(jst(s.year, s.month, s.day, 23, 59, 59))
        mon_early = self.this_week(jst(monday.year, monday.month, monday.day, 0, 0, 0))
        self.assertEqual({c["club_id"] for c in sun_late}, self.oracle(s))
        self.assertEqual({c["club_id"] for c in mon_early}, self.oracle(monday))
        # 日曜23:59は日曜の開催だけ、月曜0:00は次の週（月曜〜次の日曜）だけ。
        self.assertTrue(all(c["next_event_date"] == s for c in sun_late))
        self.assertTrue(all(monday <= c["next_event_date"] <= self.week_sunday(monday) for c in mon_early))
        # 週の途中（水曜）も、今日〜その週の日曜。
        wed = monday + timedelta(days=2)
        mid = self.this_week(jst(wed.year, wed.month, wed.day, 12, 0, 0))
        self.assertEqual({c["club_id"] for c in mid}, self.oracle(wed))


class FirstTimeJstLb(LbTestCase):
    """I-178〜I-180: キャンセル以外の申込が「日本時間の今日／昨日」の開催にだけある人の初参加判定。"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        events = {e["id"]: e for e in cls.table("events")}
        members = {(m["club_id"], m["employee_id"]) for m in cls.table("club_members")}
        by_pair = {}
        for a in cls.table("applications"):
            if a["status"] == "キャンセル":
                continue
            e = events.get(a["event_id"])
            if e:
                day = _d(e["event_date"]) if isinstance(e["event_date"], str) else e["event_date"]
                by_pair.setdefault((e["club_id"], a["applicant_id"]), []).append(day)
        cls.pairs = []  # (club_id, employee_id, 開催日D, 所属者か)。Dがその人のその部活で最も古い申込の日
        for (club_id, emp), days in by_pair.items():
            first = min(days)
            cls.pairs.append((club_id, emp, first, (club_id, emp) in members))
        # 所属者でなく、その日だけに申込がある人を優先（初参加判定の前提そのもの）。
        cls.pairs.sort(key=lambda p: (p[3], len(by_pair[(p[0], p[1])]), p[0], p[1]))

    def pick(self):
        if not self.pairs:
            self.skipTest("キャンセル以外の申込が実DBに無い")
        return self.pairs[0]

    def has_past(self, club_id, emp, now):
        self.freeze(now, self.env.applications_repo)
        return self.env.applications_repo.has_past_non_canceled(club_id, emp)

    def first_time(self, club_id, emp, now):
        self.freeze(now, self.env.applications_repo)
        return self.env.application_service._is_first_time(club_id, emp)

    # I-178: 今日（日本時間）の開催にだけ申込がある → 今日は「過去」に含まれない → is_first_time=true。
    def test_I178_event_today_is_not_past(self):
        club_id, emp, day, is_member = self.pick()
        now = jst(day.year, day.month, day.day, 12, 0, 0)
        self.assertFalse(self.has_past(club_id, emp, now))
        if is_member:
            self.skipTest("実DBに所属者でない候補が無く、初参加(is_first_time)までは確認できない（has_past_non_canceled=false のみ確認）")
        self.assertTrue(self.first_time(club_id, emp, now))

    # I-179: 日本時間の昨日の開催にある → 「過去」に当たる → is_first_time=false。
    def test_I179_event_yesterday_is_past(self):
        club_id, emp, day, is_member = self.pick()
        now = jst(day.year, day.month, day.day, 12, 0, 0) + timedelta(days=1)
        self.assertTrue(self.has_past(club_id, emp, now))
        self.assertFalse(self.first_time(club_id, emp, now))

    # I-180: 日本時間の0:00〜9:00（サーバーが世界標準時だと日付がずれる時間帯）でも I-178・I-179 と同じ結果。
    def test_I180_jst_early_morning_and_server_timezone(self):
        club_id, emp, day, is_member = self.pick()
        next_day = day + timedelta(days=1)
        old_tz = os.environ.get("TZ")
        self.addCleanup(self._restore_tz, old_tz)
        for tz in ("UTC", "Asia/Tokyo", "America/Los_Angeles"):
            os.environ["TZ"] = tz
            time.tzset()
            for hh, mm, ss in ((0, 0, 0), (0, 30, 0), (8, 59, 59)):
                with self.subTest(tz=tz, time=f"{hh:02d}:{mm:02d}:{ss:02d}", date="当日(I-178と同じ)"):
                    self.assertFalse(self.has_past(club_id, emp, jst(day.year, day.month, day.day, hh, mm, ss)))
                with self.subTest(tz=tz, time=f"{hh:02d}:{mm:02d}:{ss:02d}", date="翌日(I-179と同じ)"):
                    self.assertTrue(
                        self.has_past(club_id, emp, jst(next_day.year, next_day.month, next_day.day, hh, mm, ss))
                    )

    @staticmethod
    def _restore_tz(old_tz):
        if old_tz is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = old_tz
        time.tzset()


def _d(text):
    from datetime import date

    return date.fromisoformat(text[:10])
