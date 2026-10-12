"""S-xx 黒箱 α-W 書込テスト（test_sxx_appt_aw_apply_cancel.py）の動作確認（ドライラン）。実DBには一切つながない。

メモリ内DB（FK・identity・既定値・「申込済み」の部分一意インデックス付き）に、実の application_service / repositories を
つないで、4件の「投入→検証→後始末→9表の件数照合」が動くことを確かめる。実DBの合否の代わりにはならない。

実行（リポジトリ直下）:
  LB_WRITE=1 python3 tests/sxx_aw_dryrun.py                   … 4件とも通り、DBが元と同一・センチネル残り0
  LB_WRITE=1 python3 tests/sxx_aw_dryrun.py no-unique         … 部分一意インデックスが無いDB。S-20が落ち、それでもセンチネルが残らない
  LB_WRITE=1 python3 tests/sxx_aw_dryrun.py no-cancel-notice  … キャンセルで幹事に通知しない実装。S-25が落ち、残り0
  LB_WRITE=1 python3 tests/sxx_aw_dryrun.py reapply-blocked   … キャンセル後の再申込を弾く実装。S-26が落ち、残り0
  LB_WRITE=1 python3 tests/sxx_aw_dryrun.py purge-miss        … 後始末が通知を消し漏らす。残り検出で全件エラーになる（検出力の確認）
  LB_WRITE=1 python3 tests/sxx_aw_dryrun.py real-e998         … E998が実社員。何も書かずskipし、実社員を消さない
  LB_WRITE=1 python3 tests/sxx_aw_dryrun.py leftover          … 前回の残り（申込・通知まで）を最初に片付けて通る
  python3 tests/sxx_aw_dryrun.py                              … LB_WRITE無しは全skip
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

from lb_writes_dryrun import MemoryDb, base_tables  # noqa: E402


def world(mode: str) -> dict:
    tables = base_tables()
    tables["events"] = [{"id": 1, "club_id": 1, "event_date": "2099-01-01", "start_time": "10:00:00",
                         "end_time": "12:00:00", "meeting_place": "公園", "meeting_time": None, "status": "予定"}]
    tables["applications"] = [{"id": 1, "event_id": 1, "applicant_id": "E002", "status": "申込済み", "is_first_time": True,
                               "applied_at": "2026-10-01T00:00:00+09:00", "canceled_at": None, "confirmed_at": None}]
    tables["notifications"] = [{"id": 1, "recipient_id": "E001", "type": "申込", "application_id": 1, "event_id": 1,
                                "body": "新しい申込があります", "created_at": "2026-10-01T00:00:00+09:00", "read_at": None}]
    tables["messages"] = []
    tables["action_logs"] = [{"id": 1, "employee_id": "E002", "action": "apply", "club_id": 1, "conditions": None,
                              "created_at": "2026-10-01T00:00:00+09:00"}]
    tables["clubs"][0]["organizer_id"] = "E001"
    tables["clubs"][1]["organizer_id"] = "E001"
    if mode == "real-e998":
        tables["employees"].append({"id": "E998", "name": "本物の社員"})
    if mode == "leftover":  # 前回の異常終了: センチネルの社員・部活・開催・申込・通知・履歴が残っている
        for emp_id in ("E998", "E999"):
            tables["employees"].append({"id": emp_id, "name": "LB-TEST-employee"})
        tables["clubs"].append({"id": 7, "name": "LB-TEST-old-abc123", "activity_id": 1, "location": "東京", "slot": "平日夜",
                                "level": "レベル問わず", "message": None, "is_active": False, "organizer_id": "E998"})
        tables["events"].append({"id": 7, "club_id": 7, "event_date": "2099-02-01", "start_time": "10:00:00",
                                 "end_time": "12:00:00", "meeting_place": "LB-TEST-place", "meeting_time": None, "status": "予定"})
        tables["applications"].append({"id": 7, "event_id": 7, "applicant_id": "E999", "status": "申込済み", "is_first_time": True,
                                       "applied_at": "2026-10-10T00:00:00+09:00", "canceled_at": None, "confirmed_at": None})
        tables["messages"].append({"id": 7, "application_id": 7, "sender_id": "E999", "body": "old", "sent_at": "2026-10-10T00:00:00+09:00"})
        tables["notifications"].append({"id": 7, "recipient_id": "E998", "type": "申込", "application_id": 7, "event_id": 7,
                                        "body": "old", "created_at": "2026-10-10T00:00:00+09:00", "read_at": None})
        tables["action_logs"].append({"id": 7, "employee_id": "E999", "action": "apply", "club_id": 7, "conditions": None,
                                      "created_at": "2026-10-10T00:00:00+09:00"})
    return tables


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    import streamlit as st

    st.secrets._secrets = {"supabase_url": "http://dry.run", "supabase_key": "dry-run"}
    tables = world(mode)
    db = MemoryDb(tables, unique=True, active_unique=(mode != "no-unique"))
    original = copy.deepcopy(tables)

    fake_client = types.ModuleType("db.client")
    fake_client.supabase = db
    sys.modules["db"] = types.ModuleType("db")
    sys.modules["db.client"] = fake_client
    from repositories import applications_repo, club_members_repo, clubs_repo, events_repo
    from services import application_service

    import lb_base

    if mode == "no-cancel-notice":
        real_notify = application_service.notification_service.notify

        def notify(recipient, type_, **kw):
            if type_ != "キャンセル":
                real_notify(recipient, type_, **kw)

        application_service.notification_service = types.SimpleNamespace(notify=notify)
    if mode == "reapply-blocked":
        applications_repo.exists_active = lambda event_id, applicant_id: any(
            r["event_id"] == event_id and r["applicant_id"] == applicant_id for r in db.tables["applications"])
    if mode == "purge-miss":
        real_filters = lb_base._sentinel_filters
        lb_base._sentinel_filters = lambda client: {k: v for k, v in real_filters(client).items() if k != "notifications"}

    env = mock.Mock()
    env.supabase, env.clubs_repo, env.events_repo = db, clubs_repo, events_repo
    env.club_members_repo, env.application_service = club_members_repo, application_service
    lb_base._ENV = (env, None)

    suite = unittest.defaultTestLoader.loadTestsFromName("test_sxx_appt_aw_apply_cancel")
    result = unittest.TextTestRunner(verbosity=2).run(suite)

    def strip(t):
        return {k: sorted(map(str, v)) for k, v in t.items()}

    restored = strip(db.tables) == strip(original)
    if mode == "purge-miss":
        lb_base._sentinel_filters = real_filters
    left = lb_base.sentinel_leftovers(db) if mode != "real-e998" else "(E998は実社員のため対象外)"
    print(f"\n[aw-dryrun mode={mode or 'normal'}] 後始末後のDBは元と同一: {restored} / センチネル残り: {left}")

    if mode == "leftover":
        restored = not any(
            (str(v).startswith("LB-TEST-") or v in ("E998", "E999")) for rows in db.tables.values() for r in rows for v in r.values()
        )
        print(f"[aw-dryrun leftover] 前回の残りが片付いている: {restored}")
    if mode in ("", "leftover"):
        sys.exit(0 if result.wasSuccessful() and restored else 1)
    if mode == "real-e998":
        sys.exit(0 if restored and result.skipped and not result.failures and not result.errors else 1)
    if mode == "purge-miss":  # 後始末漏れは検出される（エラー）こと
        sys.exit(0 if (result.errors or result.failures) and not restored else 1)
    # no-unique / no-cancel-notice / reapply-blocked: テストは落ちるのが正しい。落ちてもDBは元に戻ること
    sys.exit(0 if (not result.wasSuccessful()) and restored else 1)


if __name__ == "__main__":
    main()
