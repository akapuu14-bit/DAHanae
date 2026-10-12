"""L-B 書込テスト（test_lb_writes.py）の動作確認（ドライラン）。実DBには一切つながない。

目的: 共有DBで回す前に、書込テストの「投入・検証・後始末・件数照合」がメモリ内DBで正しく動くことを確かめる。
メモリ内DBは一意制約・FK・名前のCHECK相当・identity採番を持つ。実DBの合否の代わりにはならない。

実行: LB_WRITE=1 python3 tests/lb_writes_dryrun.py            … 3件とも通り、DBが元に戻ること
      LB_WRITE=1 python3 tests/lb_writes_dryrun.py no-unique   … 一意制約が無いDB。I-090/I-091 が落ち、それでもセンチネルが残らないこと
      LB_WRITE=1 python3 tests/lb_writes_dryrun.py active-leak … is_active を無視する検索。I-026 が落ち、センチネルが残らないこと
      LB_WRITE=1 python3 tests/lb_writes_dryrun.py real-e999   … E999 が実社員として存在。何も書かず skip し、実社員を消さないこと
      LB_WRITE=1 python3 tests/lb_writes_dryrun.py leftover    … 前回の残り（センチネル）を最初に片付けて通ること
      python3 tests/lb_writes_dryrun.py                        … LB_WRITE 無しは全 skip（書込が起きないこと）
"""

import copy
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app" / "frontend"))
sys.path.insert(0, str(ROOT / "tests"))

from lb_dryrun import _Query, _Result  # noqa: E402  メモリ内select（eq/in_/ilike/order/limit/count）を再利用


class DbError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class _Write:
    def __init__(self, fn):
        self.fn = fn

    def execute(self):
        return self.fn()


class _Delete(_Query):
    def execute(self):
        keep, gone = [], []
        for row in self.db.tables[self.table_name]:
            (gone if all(f(row) for f in self.filters) else keep).append(row)
        self.db.tables[self.table_name][:] = keep
        return _Result(gone, None)


class _Update(_Query):
    def __init__(self, db, table, row):
        super().__init__(db, table, "*", None)
        self.row = row

    def execute(self):
        hit = [r for r in self.db.tables[self.table_name] if all(f(r) for f in self.filters)]
        for r in hit:
            r.update(self.row)
        return _Result([dict(r) for r in hit], None)


class _Table:
    def __init__(self, db, name):
        self.db, self.name = db, name

    def select(self, columns="*", count=None):
        return _Query(self.db, self.name, columns, count)

    def delete(self):
        return _Delete(self.db, self.name, "*", None)

    def update(self, row):
        return _Update(self.db, self.name, dict(row))

    def insert(self, row):
        return _Write(lambda: self.db.insert(self.name, dict(row)))

    def upsert(self, row, on_conflict=None, ignore_duplicates=False):
        def run():
            try:
                return self.db.insert(self.name, dict(row))
            except DbError:
                if ignore_duplicates:
                    return _Result([], None)
                raise

        return _Write(run)


_UNIQUE = {"employee_interests": ("employee_id", "activity_id"), "club_members": ("club_id", "employee_id")}
_FK = {
    "employee_interests": (("employee_id", "employees", "id"), ("activity_id", "activities", "id")),
    "club_members": (("club_id", "clubs", "id"), ("employee_id", "employees", "id")),
    "clubs": (("activity_id", "activities", "id"), ("organizer_id", "employees", "id")),
    "events": (("club_id", "clubs", "id"),),
    "applications": (("event_id", "events", "id"), ("applicant_id", "employees", "id")),
    "messages": (("application_id", "applications", "id"), ("sender_id", "employees", "id")),
    "notifications": (("recipient_id", "employees", "id"), ("application_id", "applications", "id"),
                      ("event_id", "events", "id")),
    "action_logs": (("employee_id", "employees", "id"), ("club_id", "clubs", "id")),
}
_IDENTITY = ("clubs", "events", "applications", "messages", "notifications", "action_logs")
_DEFAULTS = {
    "applications": {"status": "申込済み", "applied_at": "now", "canceled_at": None, "confirmed_at": None},
    "messages": {"sent_at": "now"},
    "notifications": {"read_at": None, "created_at": "now", "application_id": None, "event_id": None},
    "action_logs": {"club_id": None, "conditions": None, "created_at": "now"},
    "events": {"status": "予定", "meeting_time": None},
}


class MemoryDb:
    def __init__(self, tables, unique=True, active_unique=True):
        self.tables, self.unique, self.active_unique = tables, unique, active_unique
        for name in _IDENTITY:
            self.tables.setdefault(name, [])
        self.next_id = {n: max((r["id"] for r in self.tables[n]), default=0) + 1 for n in _IDENTITY}

    def table(self, name):
        return _Table(self, name)

    def insert(self, name, row):
        import re

        if name == "employees" and not re.fullmatch(r"E[0-9]{3}", row["id"]):
            raise DbError("23514", "employees_id_format_check")
        if name == "employees" and any(r["id"] == row["id"] for r in self.tables[name]):
            raise DbError("23505", "duplicate key value violates unique constraint employees_pkey")
        for col, parent, key in _FK.get(name, ()):
            if not any(p[key] == row[col] for p in self.tables[parent]):
                raise DbError("23503", f"foreign key violation {col}")
        if self.unique and name in _UNIQUE:
            key = tuple(row[c] for c in _UNIQUE[name])
            if any(tuple(r[c] for c in _UNIQUE[name]) == key for r in self.tables[name]):
                raise DbError("23505", f"duplicate key value violates unique constraint {name}_key")
        if name == "applications":
            if row.get("status", "申込済み") == "キャンセル" and not row.get("canceled_at"):
                raise DbError("23514", "applications_canceled_at_check")
            if self.active_unique and row.get("status", "申込済み") == "申込済み" and any(
                r["event_id"] == row["event_id"] and r["applicant_id"] == row["applicant_id"] and r["status"] == "申込済み"
                for r in self.tables[name]
            ):
                raise DbError("23505", "duplicate key value violates unique constraint applications_one_active_per_employee_idx")
        if name == "messages" and not row["body"].strip():
            raise DbError("23514", "messages_body_not_blank_check")
        row = {**_DEFAULTS.get(name, {}), **row}
        for key, value in row.items():
            if value == "now":
                row[key] = "2026-10-11T00:00:00+09:00"
        if name == "clubs":
            row = {"is_active": True, **row}
        if name in _IDENTITY:
            row["id"] = self.next_id[name]
            self.next_id[name] += 1
        self.tables[name].append(row)
        return _Result([dict(row)], None)


def base_tables():
    acts = [{"id": 1, "name": "テニス", "category": "スポーツ"}, {"id": 2, "name": "将棋", "category": "ゲーム"}]
    emps = [{"id": f"E{i:03d}", "name": f"社員{i}"} for i in range(1, 6)]
    clubs = [
        {"id": 1, "name": "テニス部", "activity_id": 1, "location": "東京", "slot": "平日夜", "level": "初心者歓迎",
         "message": "ひとこと", "is_active": True},
        {"id": 2, "name": "将棋部", "activity_id": 2, "location": "大阪", "slot": "日曜", "level": "経験者向け",
         "message": "ひとこと", "is_active": True},
    ]
    return {
        "activities": acts, "employees": emps, "clubs": clubs,
        "employee_interests": [{"employee_id": "E001", "activity_id": 1, "level": "初心者"}],
        "club_members": [{"club_id": 1, "employee_id": "E001"}],
    }


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    import streamlit as st

    st.secrets._secrets = {"supabase_url": "http://dry.run", "supabase_key": "dry-run"}
    tables = base_tables()
    if mode == "real-e999":
        tables["employees"].append({"id": "E999", "name": "本物の社員"})
    if mode == "leftover":
        tables["employees"].append({"id": "E999", "name": "LB-TEST-employee"})
        tables["clubs"].append({"id": 7, "name": "LB-TEST-old-abc123", "activity_id": 1, "location": "東京",
                                "slot": "平日夜", "level": "レベル問わず", "message": None, "is_active": False})
        tables["club_members"].append({"club_id": 7, "employee_id": "E999"})
    db = MemoryDb(tables, unique=(mode != "no-unique"))
    original = copy.deepcopy(tables)

    fake_client = types.ModuleType("db.client")
    fake_client.supabase = db
    sys.modules["db"] = types.ModuleType("db")
    sys.modules["db.client"] = fake_client
    from repositories import club_members_repo, clubs_repo

    if mode == "active-leak":  # I-026 を落とすはず: is_active=false も検索に出す
        real_search = clubs_repo.search
        clubs_repo.search = lambda cond: [c for c in db.tables["clubs"] if all(
            c.get(k) in v for k, v in (("location", cond.get("locations") or [c.get("location")]),))]
        del real_search

    import lb_base

    env = mock.Mock()
    env.supabase, env.clubs_repo, env.club_members_repo = db, clubs_repo, club_members_repo
    lb_base._ENV = (env, None)

    suite = unittest.defaultTestLoader.loadTestsFromName("test_lb_writes")
    result = unittest.TextTestRunner(verbosity=2).run(suite)

    def strip(t):  # identity の採番以外は完全に元へ戻ること
        return {k: sorted(map(str, v)) for k, v in t.items()}

    restored = strip(db.tables) == strip(original) or (mode == "real-e999" and strip(db.tables) == strip(original))
    print(f"\n[dryrun mode={mode or 'normal'}] 後始末後のDBは元と同一: {restored}"
          f" / センチネル残り: {lb_base.sentinel_leftovers(db) if mode != 'real-e999' else '(E999は実社員のため対象外)'}")
    expected_ok = mode in ("", "leftover")
    if mode == "leftover":
        restored = all(not any(str(v).startswith("LB-TEST-") or v == "E999" for r in rows for v in r.values())
                       for rows in db.tables.values())
        print(f"[dryrun leftover] 残りが片付いている: {restored}")
    if mode == "":
        sys.exit(0 if result.wasSuccessful() and restored else 1)
    if mode == "real-e999":
        sys.exit(0 if restored and result.skipped and not result.failures and not result.errors else 1)
    if mode == "leftover":
        sys.exit(0 if result.wasSuccessful() and restored else 1)
    # no-unique / active-leak: テストは落ちるのが正しい。落ちても DB は元に戻っていること
    sys.exit(0 if (not result.wasSuccessful()) and restored and not expected_ok else 1)


if __name__ == "__main__":
    main()
