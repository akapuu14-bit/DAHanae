"""テスト共通の設定（pytest が自動で読む）。

やること 2 つ：
  1. app/frontend/ を import の探し場所に入れる（アプリと同じ import 根にそろえる）
  2. DB に繋ぐ db.client を偽物に差し替える（単体テストは本物の DB を使わない）

画面テスト（tests/frontend/）もサービス/リポジトリのテスト（tests/backend/）も、
この設定を共有する。
"""

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

FRONTEND_DIR = Path(__file__).resolve().parents[1] / "app" / "frontend"
if str(FRONTEND_DIR) not in sys.path:
    sys.path.insert(0, str(FRONTEND_DIR))

# 本物の db/client.py は import した瞬間に Supabase へ接続しようとする（secrets が必要）。
# それを防ぐため、import される前に偽物のモジュールを差し込む。
_fake_db = types.ModuleType("db")
_fake_db.__path__ = []  # パッケージとして扱わせる
_fake_client = types.ModuleType("db.client")
_fake_client.supabase = MagicMock(name="fake_supabase")
_fake_db.client = _fake_client
sys.modules["db"] = _fake_db
sys.modules["db.client"] = _fake_client


# ---- 読み取りキャッシュ（services/cache_service.py。設計 D-07）----------------------------------
# 既存のテストは「1テストの中で偽DBを書き換えて同じ関数を呼び直す」作りなので、キャッシュは既定で切る。
# キャッシュ自体を確かめるテスト（test_perf_t3_*）は、setUp で ENABLED を True に戻す。

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _cache_off(monkeypatch):
    from services import cache_service

    monkeypatch.setattr(cache_service, "ENABLED", False)
    cache_service.clear_all()
    yield
    cache_service.clear_all()
