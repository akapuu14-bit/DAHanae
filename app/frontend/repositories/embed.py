"""PostgREST の埋め込み select（"clubs(*)" など）の戻りを、決まった形にそろえる小さな関数。

埋め込みは、関係の向きによって dict（多対1）でも list（1対多）でも返り、行が無ければ None になる。
どの形で返っても落ちないよう、読む側は one / many を通して使う（実DBの返り値の形は偽repoでは確かめられないため）。
"""


def one(value) -> dict | None:
    """1件を期待する埋め込み。dict はそのまま、list は先頭の dict、それ以外（None・空・想定外）は None。"""
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        return next((v for v in value if isinstance(v, dict)), None)
    return None


def many(value) -> list[dict]:
    """複数件を期待する埋め込み。list は dict だけを残し、dict は1件のlistに、それ以外は空リスト。"""
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [v for v in value if isinstance(v, dict)]
    return []
