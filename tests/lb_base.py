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
