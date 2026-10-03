"""認証・権限判定のサービス（I-F契約 1.1, 仕様.md SP-63, SP-11）。

- 共通パスワードは Streamlit Secrets（st.secrets["common_password"]）から読む。コードには書かない。
- 社員IDの大文字小文字の正規化はこの層で行う（呼び出し側は正規化しない）。
- 認証失敗は AuthenticationError 1種で表し、ID・パスワードのどちらが誤りかは区別しない（SP-11）。
"""

import hmac

import streamlit as st

from repositories import clubs_repo, employees_repo
from services.errors import AuthenticationError, NotFoundError

ROLE_ADMIN = "admin"
ROLE_ORGANIZER = "organizer"
ROLE_MEMBER = "member"


def _normalize_id(employee_id: str) -> str:
    return (employee_id or "").strip().upper()


def login(employee_id: str, password: str) -> dict:
    """社員IDと共通パスワードを照合し、成功時は社員レコード（dict）を返す。失敗は AuthenticationError。"""
    employee = employees_repo.get_by_id(_normalize_id(employee_id))
    expected = str(st.secrets["common_password"])
    password_ok = hmac.compare_digest(
        (password or "").encode("utf-8"), expected.encode("utf-8")
    )
    if employee is None or not password_ok:
        raise AuthenticationError()
    return employee


def get_role(employee_id: str, club_id: int | None = None) -> str:
    """"admin" / "organizer" / "member" を返す。

    club_id を指定した場合のみ幹事判定を行い、その部活が存在しなければ NotFoundError。
    club_id を省略したときは is_admin のみで "admin" / "member"。
    """
    club = None
    if club_id is not None:
        club = clubs_repo.get(club_id)
        if club is None:
            raise NotFoundError(f"club {club_id}")

    employee = employees_repo.get_by_id(_normalize_id(employee_id))
    if employee is None:
        return ROLE_MEMBER
    if employee.get("is_admin"):
        return ROLE_ADMIN
    if club is not None and club["organizer_id"] == employee["id"]:
        return ROLE_ORGANIZER
    return ROLE_MEMBER
