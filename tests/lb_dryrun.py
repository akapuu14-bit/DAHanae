"""L-B ハーネスの動作確認（ドライラン）。実DBには一切つながない。

目的: 実DBで回す前に、test_lb_*.py の「データ探し・期待値の組み立て・固定時刻・repoの呼び出し」が
動くことを、合成データ＋PostgREST風のメモリ内clientで確認する。実DBの結果の代わりにはならない。
（このスクリプトが通っても、実DBの合否は何も示さない。ハーネスの誤り＝書き間違いを先に潰すためのもの。）

実行: python3 tests/lb_dryrun.py
"""

import re
import sys
import types
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app" / "frontend"))
sys.path.insert(0, str(ROOT / "tests"))

JST = ZoneInfo("Asia/Tokyo")


def _like(value, pattern):
    """ilike: % を任意文字列、\\% \\_ \\\\ をそのままの文字として扱う（大文字小文字を区別しない）。"""
    regex, i = "", 0
    while i < len(pattern):
        ch = pattern[i]
        if ch == "\\" and i + 1 < len(pattern):
            regex += re.escape(pattern[i + 1])
            i += 2
            continue
        regex += ".*" if ch == "%" else ("." if ch == "_" else re.escape(ch))
        i += 1
    return re.fullmatch(regex, str(value), flags=re.I | re.S) is not None


def _cmp(row, col, op, val):
    v = row.get(col)
    if op == "eq":
        return v == val
    if op == "neq":
        return v != val
    if op == "lt":
        return v is not None and v < val
    if op == "gte":
        return v is not None and v >= val
    if op == "in":
        return v in val
    if op == "ilike":
        return v is not None and _like(v, val)
    if op == "ov":
        return bool(set(v or []) & set(val))
    raise NotImplementedError(op)


class _Result:
    def __init__(self, data, count):
        self.data, self.count = data, count


class _Query:
    def __init__(self, db, table, columns, count):
        self.db, self.table_name, self.columns, self.want_count = db, table, columns, count
        self.filters, self.orders, self.window = [], [], None

    def _f(self, col, op, val):
        self.filters.append(lambda r: _cmp(r, col, op, val))
        return self

    def eq(self, c, v): return self._f(c, "eq", v)
    def neq(self, c, v): return self._f(c, "neq", v)
    def lt(self, c, v): return self._f(c, "lt", v)
    def gte(self, c, v): return self._f(c, "gte", v)
    def in_(self, c, v): return self._f(c, "in", list(v))
    def ilike(self, c, v): return self._f(c, "ilike", v)
    def overlaps(self, c, v): return self._f(c, "ov", list(v))

    def or_(self, expr):
        parts = []
        for m in re.finditer(r"(\w+)\.(ilike|in)\.(\([^)]*\)|[^,]*)", expr):
            col, op, raw = m.groups()
            val = [int(x) for x in raw.strip("()").split(",")] if op == "in" else raw
            parts.append((col, op, val))
        self.filters.append(lambda r: any(_cmp(r, c, o, v) for c, o, v in parts))
        return self

    def order(self, col, desc=False):
        self.orders.append((col, desc))
        return self

    def range(self, a, b):
        self.window = (a, b + 1)
        return self

    def limit(self, n):
        self.window = (0, n)
        return self

    def execute(self):
        rows = [dict(r) for r in self.db.tables[self.table_name] if all(f(r) for f in self.filters)]
        for col, desc in reversed(self.orders):
            rows.sort(key=lambda r: (r.get(col) is None, r.get(col)), reverse=desc)
        total = len(rows)
        if self.window:
            rows = rows[self.window[0]: self.window[1]]
        embed = re.search(r"(\w+)\(\*\)", self.columns)
        if embed:
            key = embed.group(1)
            for r in rows:
                fk = {"clubs": ("club_id", "clubs")}[key]
                r[key] = next((dict(c) for c in self.db.tables[fk[1]] if c["id"] == r[fk[0]]), None)
        return _Result(rows, total if self.want_count else None)


class FakeClient:
    def __init__(self, tables):
        self.tables = tables

    def table(self, name):
        return _TableRef(self, name)


class _TableRef:
    def __init__(self, db, name):
        self.db, self.name = db, name

    def select(self, columns="*", count=None):
        return _Query(self.db, self.name, columns, count)


def synthetic_tables():
    today = datetime.now(JST).date()
    activities = [
        {"id": 1, "name": "テニス", "category": "スポーツ"},
        {"id": 2, "name": "ランニング", "category": "スポーツ"},
        {"id": 3, "name": "ボードゲーム", "category": "ゲーム"},
    ]
    locs = ["東京", "大阪", "東京", "福岡", "大阪", "東京"]
    clubs = [
        {"id": i + 1, "name": f"部活名{i + 1}号", "activity_id": activities[i % 3]["id"], "location": locs[i],
         "slot": "平日夜", "level": "初心者歓迎", "message": f"ひとこと{i + 1}です", "is_active": i != 5}
        for i in range(6)
    ]
    events = []
    start = today - timedelta(days=14)
    for n in range(35):
        day = start + timedelta(days=n)
        events.append({"id": n + 1, "club_id": clubs[n % 6]["id"], "event_date": day.isoformat(),
                       "status": "中止" if n % 11 == 0 else "予定"})
    dates = [datetime.now(JST).date()]
    employees, interests, members = [], [], []
    for i in range(1, 41):
        employees.append({
            "id": f"E{i:04d}", "name": f"山田太郎{i}" if i % 2 else f"佐藤花子{i}", "dept": ["営業", "開発", "人事"][i % 3],
            "location": ["東京", "大阪"][i % 2], "available_slots": ["平日夜", "土曜午前"][: 1 + i % 2],
            "interests_public": i % 4 != 0, "slots_public": i % 5 != 0,
        })
        interests.append({"employee_id": f"E{i:04d}", "activity_id": 1 + i % 3, "level": "初心者"})
        members.append({"club_id": 1 + i % 6, "employee_id": f"E{i:04d}"})
    applications, aid = [], 1
    for i in range(1, 9):  # 申込: 所属者でない人が、ある部活の1回の開催にだけ申込
        club = 1 + (i + 2) % 6
        ev = next(e for e in events if e["club_id"] == club and date.fromisoformat(e["event_date"]) >= today - timedelta(days=10))
        applications.append({"id": aid, "event_id": ev["id"], "applicant_id": f"E{i:04d}", "status": "申込済み" if i % 2 else "キャンセル"})
        aid += 1
    del dates
    return {"activities": activities, "clubs": clubs, "events": events, "employees": employees,
            "employee_interests": interests, "club_members": members, "applications": applications}


def _mutate(name, applications_repo, employees_repo, search_service, clubs_repo):
    from datetime import timezone

    if name == "utc-date":  # I-178〜180 を落とすはず: 「今日」を世界標準時で数える
        applications_repo.ZoneInfo = lambda _key: timezone.utc
    elif name == "ignore-public":  # I-066/067 を落とすはず: 非公開を除外しない
        original = employees_repo._build_query

        def build(query, conditions, ids):
            query = original(query, conditions, ids)
            query.filters = query.filters[:-1] if conditions.get("slots") or conditions.get("interests") else query.filters
            return query

        employees_repo._build_query = build
    elif name == "week-end-today":  # I-008 を落とすはず: 週の終わりを今日にする
        search_service.timedelta = lambda days=0: __import__("datetime").timedelta(0)
    elif name == "or-as-and":  # I-023 を落とすはず: 拠点を最初の1つだけで絞る
        original = clubs_repo.search
        clubs_repo.search = lambda c: original({**c, "locations": (c.get("locations") or [])[:1]})
    else:
        raise SystemExit(f"未知の mutate: {name}")


def main():
    import streamlit as st

    st.secrets._secrets = {"supabase_url": "http://dry.run", "supabase_key": "dry-run"}
    fake_client = types.ModuleType("db.client")
    fake_client.supabase = FakeClient(synthetic_tables())
    sys.modules["db"] = types.ModuleType("db")
    sys.modules["db.client"] = fake_client
    from repositories import applications_repo, club_members_repo, clubs_repo, employees_repo, events_repo
    from services import application_service, search_service

    import lb_base

    env = mock.Mock()
    env.supabase = fake_client.supabase
    for name, mod in dict(applications_repo=applications_repo, club_members_repo=club_members_repo,
                          clubs_repo=clubs_repo, employees_repo=employees_repo, events_repo=events_repo,
                          application_service=application_service, search_service=search_service).items():
        setattr(env, name, mod)
    lb_base._ENV = (env, None)

    for name in sys.argv[1:]:  # 意図的な不具合を入れて、テストが落ちること（検出力）を確認する
        _mutate(name, applications_repo, employees_repo, search_service, clubs_repo)

    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_lb_*.py")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
