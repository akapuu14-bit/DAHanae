"""【仮の認証】本物の services/auth_service.py ができるまでの代役。

本物の約束（I-F契約.md 1.1）と同じ形にしてある:
    login(employee_id, password) -> 社員の dict
    失敗したら AuthenticationError（ID と パスワード のどちらが誤りかは区別しない）

この仮の版は DB につながない。確かめるのは次の2つだけ。
  - 社員IDが E001〜E500 の形（大文字小文字は区別しない）
  - パスワードが DEMO_PASSWORD と同じ

本物ができたら、screens/login.py の import を 1 行書き換えて、このファイルは使わなくなる。
※ DEMO_PASSWORD は画面確認用のダミー。本物の共通パスワードではない。
"""

from services.errors import AuthenticationError

DEMO_PASSWORD = "demo"


def login(employee_id, password):
    # 本物の約束: 大文字小文字の違いは、ここ（サービス側）で吸収する
    normalized = (employee_id or "").strip().upper()

    is_valid_id = (
        len(normalized) == 4
        and normalized[0] == "E"
        and normalized[1:].isdigit()
        and 1 <= int(normalized[1:]) <= 500
    )
    if not is_valid_id or password != DEMO_PASSWORD:
        # どちらが違うのかは教えない（SP-11）
        raise AuthenticationError()

    return {"id": normalized, "name": f"デモ社員 {normalized}", "dept": "デモ部"}
