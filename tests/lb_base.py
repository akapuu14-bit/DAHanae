"""L-B（実repo＋実DB）ハーネスの共通部分。

- 対象: repo層の条件絞り込み・日付JST・実DB必須のI-xx（テスト結果.md 3章）。READ-ONLY（書込なし）。
- 秘匿値は リポジトリ直下 .streamlit/secrets.toml だけ（supabase_url / supabase_key / common_password）。
  素のpytestでは streamlit が直下を拾えないため、tomllib で読んで st.secrets に流し込む。
  値はログにも出力にも残さない（件数・ID・件名のみ）。
- 実DBに繋がらないときは unittest.SkipTest（pytest では skip）にする。偽repo(L-A)・AppTest(L-C)は壊さない。
  - secrets が無い／キーが足りない → skip
  - 偽の db.client（tests/fakes.py）が同じプロセスに入っている → skip（L-Bは別プロセスで回す）
  - 疎通（activities の件数を1回読む）に失敗 → skip
- 期待値は、DBの生テーブルを読んでPythonで組み立てる（repoの実装をなぞらず、仕様の定義から作る）。
"""

import os
import subprocess
import sys
import tomllib
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app" / "frontend"))

JST = ZoneInfo("Asia/Tokyo")
_REQUIRED_KEYS = ("supabase_url", "supabase_key")


def _secret_candidates() -> list[Path]:
    """secrets.toml の探し場所。環境変数 LB_SECRETS → 直下 → git worktree の本体直下。"""
    if os.environ.get("LB_SECRETS"):  # 明示指定があればそれだけを見る（オフライン検証用）
        return [Path(os.environ["LB_SECRETS"])]
    paths = []
    paths.append(ROOT / ".streamlit" / "secrets.toml")
    try:
        common = subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "--path-format=absolute", "--git-common-dir"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip()
        if common:
            paths.append(Path(common).parent / ".streamlit" / "secrets.toml")
    except Exception:  # git が無い等。見つからなければ skip になるだけ
        pass
    return paths


_TABLES: dict[str, list[dict]] = {}
_ENV = None  # (env, None) か (None, skip理由)。1プロセスで1回だけ判定する。


def load_env():
    """実repo＋実clientを使える状態にして (env, None) を返す。使えなければ (None, 理由)。"""
    global _ENV
    if _ENV is not None:
        return _ENV
    _ENV = _load_env()
    return _ENV


def _load_env():
    if os.environ.get("LB_SKIP") == "1":
        return None, "LB_SKIP=1 のためL-Bを実行しない"
    existing = sys.modules.get("db.client")
    if existing is not None and not hasattr(existing, "__file__"):
        return None, "偽の db.client（tests/fakes.py）が入っている。L-Bは別プロセスで実行する"

    secrets_path = next((p for p in _secret_candidates() if p.is_file()), None)
    if secrets_path is None:
        return None, ".streamlit/secrets.toml が見つからない"
    try:
        secrets = tomllib.loads(secrets_path.read_text(encoding="utf-8"))
    except Exception as e:
        return None, f"secrets.toml を読めない（{type(e).__name__}）"
    missing = [k for k in _REQUIRED_KEYS if not secrets.get(k)]
    if missing:
        return None, f"secrets.toml にキーが無い: {', '.join(missing)}"

    import streamlit as st

    st.secrets._secrets = dict(secrets)  # 実repo/clientが使う st.secrets["..."] に流し込む（メモリ上のみ）
    try:
        from db.client import supabase
        from repositories import (
            applications_repo,
            club_members_repo,
            clubs_repo,
            employees_repo,
            events_repo,
        )
        from services import application_service, search_service
    except Exception as e:
        return None, f"実repo/clientを読み込めない（{type(e).__name__}）"

    try:
        supabase.table("activities").select("id", count="exact").limit(1).execute()
    except Exception as e:  # メッセージにURLが入りうるので型名だけ残す
        return None, f"実DBに接続できない（{type(e).__name__}）"

    env = mock.Mock()
    env.supabase = supabase
    env.applications_repo = applications_repo
    env.club_members_repo = club_members_repo
    env.clubs_repo = clubs_repo
    env.employees_repo = employees_repo
    env.events_repo = events_repo
    env.application_service = application_service
    env.search_service = search_service
    return env, None


# id 列を持たない表の並び替えキー（range のページングは順序が決まっていないと行が重複・欠落する）。
_ORDER = {
    "club_members": ("club_id", "employee_id"),
    "employee_interests": ("employee_id", "activity_id"),
}


def fetch_all(client, table: str, columns: str = "*") -> list[dict]:
    """テーブルの全行を読む（PostgRESTの1回あたり上限を避けて range で繰り返す）。READ-ONLY。"""
    rows, start, size = [], 0, 500
    while True:
        query = client.table(table).select(columns)
        for key in _ORDER.get(table, ("id",)):
            query = query.order(key)
        chunk = query.range(start, start + size - 1).execute().data
        rows.extend(chunk)
        if len(chunk) < size:
            return rows
        start += size


def frozen_datetime(instant: datetime):
    """datetime.now() を固定した datetime のサブクラス。instant はタイムゾーン付き。"""

    class _Frozen(datetime):
        @classmethod
        def now(cls, tz=None):
            return instant.astimezone(tz) if tz else instant.replace(tzinfo=None)

    return _Frozen


def jst(y, m, d, hh=12, mm=0, ss=0) -> datetime:
    return datetime(y, m, d, hh, mm, ss, tzinfo=JST)


class LbTestCase(unittest.TestCase):
    """実DBが使えないときはクラスごと skip する。使えるときは self.env / 読み込み済みの表を持つ。"""

    @classmethod
    def setUpClass(cls):
        env, reason = load_env()
        if env is None:
            raise unittest.SkipTest(f"L-B skip: {reason}")
        cls.env = env
        cls.db = env.supabase

    # 表の全行（プロセス内で1回だけ読む）。読み取りのみ。
    @classmethod
    def table(cls, name: str) -> list[dict]:
        if name not in _TABLES:
            _TABLES[name] = fetch_all(cls.db, name)
        return _TABLES[name]

    def freeze(self, instant: datetime, *modules):
        """modules の datetime を固定版に差し替える（テスト終了で戻る）。"""
        fake = frozen_datetime(instant)
        for module in modules:
            patcher = mock.patch.object(module, "datetime", fake)
            patcher.start()
            self.addCleanup(patcher.stop)

    @staticmethod
    def week_sunday(d: date) -> date:
        return d + timedelta(days=6 - d.weekday())


# ---------------------------------------------------------------------------
# 書込テスト用（I-026 / I-090 / I-091）。READ-ONLYのL-B（上のクラス）とは分け、LB_WRITE=1 のときだけ動かす。
# 共有DBに触るのは、下のセンチネル（社員 E999 と、名前が "LB-TEST-" で始まる部活）に紐づく行だけ。
# 実在の行は読む（FKの参照先に使う活動IDなど）が、変更・削除しない。後始末は必ず purge_sentinels で行う。
# ---------------------------------------------------------------------------

SENTINEL_EMP_ID = "E999"  # employees.id は ^E[0-9]{3}$ の制約があり "LB-TEST" 形式は使えない。seed は E001〜E500。
SENTINEL_EMP_NAME = "LB-TEST-employee"
SENTINEL_CLUB_PREFIX = "LB-TEST-"  # '_' '%' ',' などは clubs_repo の検索で除外/エスケープされるので使わない
SENTINEL_EMP_ID_2 = "E998"  # 申込のテストで「幹事」役にする2人目（幹事≠申込者でないと幹事あて通知が出ない）
SENTINEL_EMP_IDS = (SENTINEL_EMP_ID_2, SENTINEL_EMP_ID)
# 申込のテスト（S-19/25/26/20）が触る表まで含める。件数照合・残り確認・後始末の対象はこの全表。
WRITE_TABLES = (
    "employees", "clubs", "club_members", "employee_interests",
    "events", "applications", "messages", "notifications", "action_logs",
)
_PK = {"club_members": ("club_id", "employee_id"), "employee_interests": ("employee_id", "activity_id")}


def count_rows(client, table: str) -> int:
    """テーブルの全件数（行は取らない）。"""
    column = {"club_members": "club_id", "employee_interests": "employee_id"}.get(table, "id")
    return client.table(table).select(column, count="exact").limit(1).execute().count


def snapshot_counts(client) -> dict[str, int]:
    return {t: count_rows(client, t) for t in WRITE_TABLES}


def _sentinel_club_ids(client) -> list[int]:
    rows = client.table("clubs").select("id").ilike("name", f"{SENTINEL_CLUB_PREFIX}%").execute().data
    return [r["id"] for r in rows]


def _ids(client, table: str, column: str, values: list) -> list:
    """column が values のどれかの行の id（値が空なら読まない）。"""
    if not values:
        return []
    return [r["id"] for r in client.table(table).select("id").in_(column, values).execute().data]


def _sentinel_filters(client) -> dict[str, list[tuple[str, list]]]:
    """表ごとの『センチネルの行』の条件（子→親の削除順）。条件は E998/E999・センチネル部活・その開催・その申込だけ。

    実在の行は、センチネルの社員・部活・開催・申込のどれにも紐づかないので、この条件に入らない。
    """
    emp = list(SENTINEL_EMP_IDS)
    club_ids = _sentinel_club_ids(client)
    event_ids = _ids(client, "events", "club_id", club_ids)
    app_ids = sorted(set(_ids(client, "applications", "applicant_id", emp) + _ids(client, "applications", "event_id", event_ids)))
    return {
        "messages": [("sender_id", emp), ("application_id", app_ids)],
        "notifications": [("recipient_id", emp), ("application_id", app_ids), ("event_id", event_ids)],
        "action_logs": [("employee_id", emp), ("club_id", club_ids)],
        "applications": [("applicant_id", emp), ("event_id", event_ids)],
        "club_members": [("employee_id", emp), ("club_id", club_ids)],
        "employee_interests": [("employee_id", emp)],
        "events": [("club_id", club_ids)],
        "clubs": [("id", club_ids)],
        "employees": [("id", emp)],
    }


def sentinel_leftovers(client) -> dict[str, int]:
    """センチネルに紐づく行の件数（全部0なら残っていない）。表をまたいで重複する行は1件と数える。"""
    counts = {}
    for table, filters in _sentinel_filters(client).items():
        pk = _PK.get(table, ("id",))
        rows = set()
        for column, values in filters:
            if values:
                data = client.table(table).select(",".join(pk)).in_(column, values).execute().data
                rows |= {tuple(r[k] for k in pk) for r in data}
        counts[table] = len(rows)
    return counts


def purge_sentinels(client) -> None:
    """センチネル行だけを、FKの子から順に消す。キーは E998/E999・名前prefix・その開催/申込のidだけで絞る。

    重複拒否の制約が無かった場合でも、消すのはセンチネルに紐づく行だけなので実データは巻き込まない。
    先に全表の条件を作ってから消す（親を消した後に子を探せなくならないように）。
    """
    for table, filters in _sentinel_filters(client).items():
        for column, values in filters:
            if values:
                client.table(table).delete().in_(column, values).execute()


def is_unique_violation(exc: Exception) -> bool:
    """PostgreSQL の unique_violation（23505）か。PostgREST のエラーは code に入る。"""
    return getattr(exc, "code", None) == "23505" or "duplicate key" in str(exc).lower()


class LbWriteTestCase(LbTestCase):
    """書込を伴うL-B。LB_WRITE=1 が無ければ skip（普段の `pytest tests/test_lb_*.py` で共有DBに書かない）。"""

    @classmethod
    def setUpClass(cls):
        if os.environ.get("LB_WRITE") != "1":
            raise unittest.SkipTest("L-B書込: LB_WRITE=1 のときだけ実行（共有DBへ書くため。運営承認済みの実走用）")
        super().setUpClass()

    def start_write_test(self, *, second_employee: bool = False):
        """前提確認→件数の控え→センチネル社員の投入。終了時（成功・失敗とも）に必ず後始末して件数を照合する。

        self.activity_id に実在の活動ID（FKの参照だけで変更しない）を入れる。
        second_employee=True なら E998（幹事役）も投入する（E999 は申込者役）。
        """
        db = self.db
        for emp_id in SENTINEL_EMP_IDS:  # どちらかが実社員なら、どちらも使わず何も書かない
            existing = db.table("employees").select("id, name").eq("id", emp_id).execute().data
            if existing and existing[0]["name"] != SENTINEL_EMP_NAME:
                self.skipTest(f"{emp_id} が実社員として存在する。センチネルに使えないので何も書かない")
        if any(sentinel_leftovers(db).values()):  # 前回の異常終了の残り（センチネルだけ）。消してから始める
            purge_sentinels(db)
        activities = db.table("activities").select("id").order("id").limit(1).execute().data
        if not activities:
            self.skipTest("activities が空でFKの参照先が無い")
        self.activity_id = activities[0]["id"]

        before = snapshot_counts(db)
        self.addCleanup(self._finish_write_test, before)  # 以降に失敗しても必ず実行される
        for emp_id in ((SENTINEL_EMP_ID_2, SENTINEL_EMP_ID) if second_employee else (SENTINEL_EMP_ID,)):
            db.table("employees").insert({
                "id": emp_id, "name": SENTINEL_EMP_NAME, "dept": "LB-TEST", "location": "東京",
                "joined_year": 2000, "entry_type": "新卒", "interests_public": False, "slots_public": False,
                "is_admin": False,
            }).execute()

    def _finish_write_test(self, before):
        purge_sentinels(self.db)
        after = snapshot_counts(self.db)
        self.assertEqual(sentinel_leftovers(self.db), {t: 0 for t in WRITE_TABLES}, "センチネル行が残っている")
        self.assertEqual(after, before, "テスト前後で件数が戻っていない（他者の同時書込の可能性もある。再実行して確認）")

    def insert_sentinel_event(self, club_id: int, *, days_ahead: int = 30) -> dict:
        """センチネル部活の開催（予定・days_ahead 日後の 10:00〜12:00・日本時間）を events_repo.create で1件投入し、その行を返す。

        開始時刻が未来でないと申込できない（SP-66）ので、既定は30日後。
        """
        data = {
            "club_id": club_id, "event_date": (datetime.now(JST).date() + timedelta(days=days_ahead)).isoformat(),
            "start_time": "10:00:00", "end_time": "12:00:00", "meeting_place": f"{SENTINEL_CLUB_PREFIX}place",
            "status": "予定",
        }
        return {**data, "id": self.env.events_repo.create(data)}

    def insert_sentinel_club(self, tag: str, *, organizer_id: str = SENTINEL_EMP_ID) -> dict:
        """is_active=false のセンチネル部活を repo の create で1件投入し、その行（id付き）を返す。"""
        import uuid

        data = {
            "name": f"{SENTINEL_CLUB_PREFIX}{tag}-{uuid.uuid4().hex[:6]}", "activity_id": self.activity_id,
            "location": "東京", "slot": "平日夜", "frequency": "不定期", "level": "レベル問わず",
            "fact_adult_starters": "いない", "fee": "無料", "rental": "なし", "join_leave": "要相談",
            "after_activity": "なし", "organizer_id": organizer_id, "is_active": False,
        }
        return {**data, "id": self.env.clubs_repo.create(data)}
