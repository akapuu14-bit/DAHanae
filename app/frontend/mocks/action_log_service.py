"""【仮の操作履歴サービス】本物の services/action_log_service.py の代役（部活検索用）。

本物（I-F契約 1.5）は、DB に残した「直前の検索条件」と比べて、同じなら記録しない。
ここでは DB の代わりに、メモリ上の辞書（_last）で同じ動きをまねる。
"""

_last = {}  # 社員ID -> 直前に記録した検索条件
records = []  # 記録した履歴（動作確認用に見られるようにしてある）


def record_search(employee_id, conditions):
    """部活検索の操作履歴（SP-23）。直前と同じ条件なら記録しない（二重記録防止）。"""
    if _last.get(employee_id) == conditions:
        return
    _last[employee_id] = dict(conditions)
    records.append((employee_id, dict(conditions)))


_last_view = {}  # 社員ID -> 直前に記録した部活ID


def record_view_club(employee_id, club_id):
    """部活詳細の閲覧履歴（SP-32）。同じ部活を連続で開き直したときは記録しない。"""
    if _last_view.get(employee_id) == club_id:
        return
    _last_view[employee_id] = club_id
    records.append((employee_id, {"view_club": club_id}))
