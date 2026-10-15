"""読み取り結果のキャッシュと、書込み後の無効化（設計 D-07、仕様 SP-84、実装計画 6.5）。

方針（SP-84）：
  - 一定時間で更新する方式（TTL）は採らない。取り直すのは、無効化の契機が来たときだけ。
  - 自分の書込み（申込・キャンセル・プロフィール保存・部活/開催/メンバーの変更）のあとは、
    関連するキャッシュを即時に無効化する。自分の操作の結果が古いまま表示されることは許容しない。
  - 他の人の操作による古さは許容する。ただし、この関数のキャッシュは全員で共有されるので、
    だれかが書込みをすれば、その種類のキャッシュは全員ぶん捨てられる（下の無効化の契機の表）。
  - 日付で変わる値（今週・今月・次回開催日など）は、日付（日本時間）をキーに含める。日が変われば別のキャッシュになる。
  - 対象は実装計画 6.5 の一覧だけ。メッセージ・通知はキャッシュしない。

使い方：
    @cache_service.cached("home")
    def _home(employee_id, day): ...

    cache_service.invalidate(cache_service.APPLICATION)   # 書込みの直後に呼ぶ

ENABLED が False のとき（テスト・件数の測定）は、キャッシュせず毎回そのまま呼ぶ。
"""

import functools

import streamlit as st

# 無効化の契機（書込みの種類）→ その書込みで捨てるキャッシュの種類（実装計画 6.5 の「再取得・無効化の契機」）
APPLICATION = "application"  # 自分の申込・キャンセル・スタンプ
PROFILE = "profile"  # 自分のプロフィール保存・公開設定の更新
CLUB = "club"  # 部活の登録・編集、開催の追加・編集・中止、メンバーの追加・削除

# キャッシュの種類
HOME = "home"  # ホーム（今週・人気・おすすめ）
CLUB_SEARCH = "club_search"  # 部活を探す（条件ごと）
CLUB_DETAIL = "club_detail"  # 部活詳細（部活ごと）
EMPLOYEE_SEARCH = "employee_search"  # 人を探す（検索結果。条件ごと）
EMPLOYEE_PROFILE = "employee_profile"  # 社員プロフィール（本人ごと）
CLUB_ADMIN = "club_admin"  # 部活の管理（部活ごと）
CHOICES = "choices"  # 選択肢（部署・活動）。書込みで変わらない

_INVALIDATES = {
    APPLICATION: (HOME, CLUB_SEARCH, CLUB_DETAIL, CLUB_ADMIN),
    PROFILE: (HOME, EMPLOYEE_SEARCH, EMPLOYEE_PROFILE),
    CLUB: (HOME, CLUB_SEARCH, CLUB_DETAIL, EMPLOYEE_SEARCH, EMPLOYEE_PROFILE, CLUB_ADMIN),
}

ENABLED = True
MAX_ENTRIES = 500  # 検索条件・社員ごとにキーが増えても、メモリを使い切らない上限（古いものから捨てる。時間では捨てない）
_REGISTRY: dict[str, list] = {}


def cached(kind: str):
    """関数を kind の種類のキャッシュ対象にする。引数が同じなら、書込みで無効化されるまで同じ結果を返す。"""

    def decorate(fn):
        store = st.cache_data(show_spinner=False, max_entries=MAX_ENTRIES)(fn)
        _REGISTRY.setdefault(kind, []).append(store)

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            if not ENABLED:
                return fn(*args, **kwargs)
            return store(*args, **kwargs)

        wrapper.clear_cache = store.clear
        return wrapper

    return decorate


def invalidate(event: str) -> None:
    """書込みの直後に呼ぶ。その書込みに関係する種類のキャッシュをすべて捨てる。"""
    for kind in _INVALIDATES[event]:
        for store in _REGISTRY.get(kind, []):
            store.clear()


def clear_all() -> None:
    """すべてのキャッシュを捨てる（テストの準備用）。"""
    for stores in _REGISTRY.values():
        for store in stores:
            store.clear()
