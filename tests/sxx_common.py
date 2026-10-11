"""S-xx 黒箱テスト（Phase2 T1）の共通部品。偽repo(fakes)にも実DB(lb_base)にも依存しない。

- collect(at): AppTest の画面（本体＋サイドバー）に出ている文字列を全部集める。
- click_label(at, label): ラベルでボタン（フォーム送信ボタンを含む）を押す。
- ReadOnlyGuard: 実DBのclientに被せ、insert/update/delete/upsert を実DBに届けずに握りつぶして記録する。
  α-R（実DB読取）の AppTest は、画面を開くだけで操作履歴の記録・通知の既読化といった書込を行う。
  それを実DBへ流さないための安全装置（READ-ONLYの担保）。
"""

import re
from types import SimpleNamespace

RULE = "体験参加は入部ではありません／参加は毎回でなくてOK／活動後の集まりは任意です／キャンセルもできます"
# S-06: この表記がどの画面にも出ないこと（F-06）。表記ゆれも含める。
FORBIDDEN_SOLO = ("1人参加OK", "１人参加OK", "一人参加OK", "ひとり参加OK", "1人でもOK")
# S-52: 日付時刻の表示形式「9/26（土）19:00」（SP-07 / N-05）。日付と時刻の間の空白は許す。
DATETIME_RE = re.compile(r"\d{1,2}/\d{1,2}（[月火水木金土日]）[\s　]*\d{1,2}:\d{2}")


def collect(at) -> list[str]:
    """画面に出ている文字列（本体・サイドバーの、値・ラベル）を集める。"""
    out: list[str] = []

    def walk(node):
        for attr in ("label", "value"):
            try:
                v = getattr(node, attr)
            except Exception:
                continue
            if isinstance(v, str):
                out.append(v)
        children = getattr(node, "children", None)
        if isinstance(children, dict):
            for child in children.values():
                walk(child)

    walk(at.main)
    walk(at.sidebar)
    return out


def joined(at) -> str:
    return "\n".join(collect(at))


def click_label(at, label: str, nth: int = 0):
    """ラベルが label のボタンを nth 番目から押して再実行する。見つからなければ AssertionError。"""
    matches = [b for b in at.button if b.label == label]
    assert len(matches) > nth, f"ボタン『{label}』が無い: {[b.label for b in at.button]}"
    return matches[nth].click().run()


_WRITE_METHODS = {"insert", "update", "delete", "upsert"}


class _Blocked:
    """書込のクエリ。何を呼んでも自分を返し、execute() は空の結果を返す。"""

    def __init__(self, attempts, table, op):
        self._attempts, self._table, self._op = attempts, table, op

    def __call__(self, *args, **kwargs):
        return self

    def __getattr__(self, name):
        return self

    def execute(self):
        self._attempts.append((self._table, self._op))
        return SimpleNamespace(data=[], count=None)


class _GuardedTable:
    def __init__(self, real, attempts, table):
        self._real, self._attempts, self._table = real, attempts, table

    def __getattr__(self, name):
        if name in _WRITE_METHODS:
            return _Blocked(self._attempts, self._table, name)
        return getattr(self._real, name)


class ReadOnlyGuard:
    """client.table(...) を差し替え、書込を実DBに届けない。rpc は呼ばせない。"""

    def __init__(self, client):
        self.client = client
        self.attempts: list[tuple[str, str]] = []
        self._orig_table = client.table
        self._orig_rpc = getattr(client, "rpc", None)

    def install(self):
        orig = self._orig_table
        self.client.table = lambda name: _GuardedTable(orig(name), self.attempts, name)

        def _no_rpc(*args, **kwargs):
            raise AssertionError("READ-ONLY: rpc は呼べない")

        self.client.rpc = _no_rpc

    def uninstall(self):
        self.client.table = self._orig_table
        if self._orig_rpc is not None:
            self.client.rpc = self._orig_rpc
        else:
            try:
                del self.client.rpc
            except AttributeError:
                pass
