"""【仮の通知サービス】本物の services/notification_service.py の代役（メッセージ画面用）。

本物（I-F契約 1.4）の mark_read_for_messages_screen と同じ引数にそろえてある。
動作確認のため、呼ばれた社員IDを read_calls に残す。
"""

read_calls = []


def mark_read_for_messages_screen(employee_id):
    """メッセージ画面を開いたときに、自分あての関連通知を既読にする（SP-36）。"""
    read_calls.append(employee_id)
