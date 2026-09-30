"""サービス層が送出する共通例外（I-F契約.md 0.4）。

エラーメッセージの文言はここでは持たない。画面側が例外の種類に応じて
仕様書どおりの文言を出す。
"""


class AppError(Exception):
    """共通例外の親クラス。画面側で一括して受けたいときに使う。"""


class ValidationError(AppError):
    """入力不正（必須未入力、選択肢外の値など）。"""


class NotFoundError(AppError):
    """対象のレコードが存在しない。"""


class ConflictError(AppError):
    """状態の競合（重複申込・キャンセル期限超過・中止済み開催への申込など）。

    reason に理由コード（"not_open" / "already_applied"）を持たせ、
    画面が SP-31 の文言を出し分けるのに使う。
    """

    def __init__(self, reason=None):
        super().__init__(reason)
        self.reason = reason


class AuthenticationError(AppError):
    """ログイン失敗（SP-11）。ID・パスワードのどちらが誤りかは区別しない。"""


class PermissionDeniedError(AppError):
    """権限不足（SP-74の範囲外の操作）。"""

    
