"""操作履歴（KPI）の記録サービス（I-F契約 1.5, 仕様.md SP-76）。

- 二重記録の判定は session_state ではなく DB（action_logs_repo.get_last）の最新記録と比較する。
- action ごとの必須項目の事前検証はこの層で行い、不正な入力は ValidationError にする
  （DBの action_logs_shape_check は最後の砦）。
- 社員検索は記録しない（SP-76）。
"""

import json

from repositories import action_logs_repo
from services.errors import ValidationError

_SEARCH_CLUB = "search_club"
_VIEW_CLUB = "view_club"
_APPLY = "apply"


def _as_stored(conditions: dict) -> dict:
    """DB（jsonb）に保存した形に揃える。get_last の戻り値との比較を型の差で外さないため。"""
    return json.loads(json.dumps(conditions, ensure_ascii=False))


def record_search(employee_id: str, conditions: dict) -> None:
    """部活検索（search_club）を記録する。直前の検索条件と同じなら記録しない。"""
    if conditions is None:
        raise ValidationError("conditions is required for search_club")
    stored = _as_stored(conditions)
    last = action_logs_repo.get_last(employee_id, _SEARCH_CLUB)
    if last is not None and last.get("conditions") == stored:
        return
    action_logs_repo.insert(employee_id, _SEARCH_CLUB, conditions=stored)


def record_view_club(employee_id: str, club_id: int) -> None:
    """部活詳細閲覧（view_club）を記録する。直前に記録した view_club と同じ部活なら記録しない。"""
    if club_id is None:
        raise ValidationError("club_id is required for view_club")
    last = action_logs_repo.get_last(employee_id, _VIEW_CLUB)
    if last is not None and last.get("club_id") == club_id:
        return
    action_logs_repo.insert(employee_id, _VIEW_CLUB, club_id=club_id)


def record_apply(employee_id: str, club_id: int) -> None:
    """申込完了（apply）を記録する。申込は1件ごとに別の出来事なので二重記録の判定はしない。"""
    if club_id is None:
        raise ValidationError("club_id is required for apply")
    action_logs_repo.insert(employee_id, _APPLY, club_id=club_id)
