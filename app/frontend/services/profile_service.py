"""社員プロフィール（S09）の参照と本人による更新（I-F契約 1.6, 仕様.md SP-53〜SP-57, SP-65）。

- 「非公開なら他人には値を渡さない」判断はここで行う（画面で出し分けない）。
- 更新は本人のみ。権限 → 社員の存在 → 入力検証 の順に判定し、検証をすべて済ませてから保存する。
- 社員IDの比較は大文字小文字を区別しない（employees_repo.get_by_id と同じ）。
"""

from repositories import (
    activities_repo,
    club_members_repo,
    clubs_repo,
    employees_repo,
)
from services import search_service
from services.errors import NotFoundError, PermissionDeniedError, ValidationError

# 仕様.md 3.2 の選択肢
_SLOT_CHOICES = ("平日夜", "土曜午前", "土曜午後", "日曜")
_LEVEL_CHOICES = ("未経験", "初心者", "経験あり")

_EMPLOYEE_KEYS = ("id", "name", "dept", "location", "joined_year", "entry_type")


def _same_id(a: str | None, b: str | None) -> bool:
    return (a or "").strip().upper() == (b or "").strip().upper()


def _get_employee(employee_id: str) -> dict:
    employee = employees_repo.get_by_id(employee_id)
    if employee is None:
        raise NotFoundError(f"employee {employee_id}")
    return employee


def get_profile(employee_id: str, viewer_id: str) -> dict:
    """社員プロフィール（SP-53〜SP-55, SP-65）。読み取り専用で、操作履歴は記録しない。

    interests / available_slots は、非公開かつ閲覧者が本人でないとき None。本人には常に値を返す。
    clubs は所属部活のうち is_active=true を club_id 昇順の部活カードdictで返す。
    例外: NotFoundError（employee_id の社員が存在しない）。
    """
    employee = _get_employee(employee_id)
    is_self = _same_id(employee["id"], viewer_id)
    show_interests = is_self or bool(employee["interests_public"])
    show_slots = is_self or bool(employee["slots_public"])

    clubs = []
    next_dates = None
    for club_id in club_members_repo.list_clubs_by_member(employee["id"]):
        club = clubs_repo.get(club_id)
        if club is None or not club.get("is_active"):
            continue
        if next_dates is None:
            next_dates = search_service._next_event_dates()
        clubs.append(search_service._card(club, next_dates.get(club["id"])))
    clubs.sort(key=lambda c: c["club_id"])

    return {
        "employee": {key: employee.get(key) for key in _EMPLOYEE_KEYS},
        "is_self": is_self,
        "interests": employees_repo.get_interests(employee["id"]) if show_interests else None,
        "interests_public": bool(employee["interests_public"]),
        "available_slots": (employee.get("available_slots") or []) if show_slots else None,
        "slots_public": bool(employee["slots_public"]),
        "clubs": clubs,
    }


def update_public_settings(
    employee_id: str,
    requester_id: str,
    *,
    interests_public: bool | None = None,
    slots_public: bool | None = None,
) -> None:
    """公開・非公開の切り替え保存（SP-56）。本人のみ。None の項目は変更しない。

    例外: PermissionDeniedError（本人以外）/ NotFoundError（社員が存在しない）。
    """
    if not _same_id(employee_id, requester_id):
        raise PermissionDeniedError("only the employee can change public settings")
    employee = _get_employee(employee_id)
    if interests_public is None and slots_public is None:
        return
    employees_repo.update_public_settings(
        employee["id"], interests_public=interests_public, slots_public=slots_public
    )


def _validate_interests(interests: list[dict]) -> None:
    activity_ids = {a["id"] for a in activities_repo.list_all()}
    seen: set = set()
    for item in interests:
        activity_id = item.get("activity_id")
        if activity_id not in activity_ids:
            raise ValidationError(f"unknown activity_id: {activity_id!r}")
        if item.get("level") not in _LEVEL_CHOICES:
            raise ValidationError(f"invalid level: {item.get('level')!r}")
        if activity_id in seen:
            raise ValidationError(f"duplicate activity_id: {activity_id!r}")
        seen.add(activity_id)


def _validate_slots(available_slots: list[str]) -> None:
    seen: set = set()
    for slot in available_slots:
        if slot not in _SLOT_CHOICES:
            raise ValidationError(f"invalid slot: {slot!r}")
        if slot in seen:
            raise ValidationError(f"duplicate slot: {slot!r}")
        seen.add(slot)


def save_profile(
    employee_id: str, requester_id: str, interests: list[dict], available_slots: list[str]
) -> None:
    """「興味・経験」と「参加可能時間」の編集保存（SP-57）。本人のみ。空リストは0件にする。

    検証（活動の存在・level の選択肢・activity_id と slot の重複・slot の選択肢）をすべて済ませてから
    保存する。1つでも不正なら何も保存しない。2つの保存は別テーブルで、1トランザクションにはしない。
    例外: PermissionDeniedError / NotFoundError / ValidationError。
    """
    if not _same_id(employee_id, requester_id):
        raise PermissionDeniedError("only the employee can save the profile")
    employee = _get_employee(employee_id)
    interests = list(interests or [])
    available_slots = list(available_slots or [])
    _validate_interests(interests)
    _validate_slots(available_slots)

    employees_repo.set_interests(employee["id"], interests)
    employees_repo.set_available_slots(employee["id"], available_slots)
