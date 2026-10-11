# L-A 追加テストの採番対応表（PR#137 はなえレビュー対応）

PM決定により、旧名 test_B_* / test_C_* の9件に、テスト設計.md 2.11（S10）末尾の I-196〜I-204 を新規採番した。
テストは tests/test_club_admin_service.py。名前の変更のみで、テストの中身は変えていない（L-A 153件OK、Asia/Tokyo・UTC）。

| 新ID | 旧テスト名（メソッド） | 新テスト名（メソッド） | 対応SP | 検証していること |
|---|---|---|---|---|
| I-196 | test_B_create_event_unknown_key_rejected_and_nothing_saved | test_I196_create_event_unknown_key_rejected_and_nothing_saved | SP-60, SP-61 | create_event に status/id/club_id/想定外キー → unknown:<key>、開催は作られない |
| I-197 | test_B_update_event_unknown_key_cannot_cancel_without_notification | test_I197_update_event_unknown_status_cannot_cancel_without_notification | SP-60, SP-73 | update_event に status → unknown:status、状態は予定のまま・通知なし |
| I-198 | test_B_unknown_comes_before_required_in_create_and_update | test_I198_unknown_comes_before_required_in_create_and_update | SP-61 | unknown → required の順（create/update） |
| I-199 | test_B_unknown_is_after_permission_and_not_found | test_I199_unknown_is_after_not_found_and_permission | SP-61, SP-74 | 権限なし×unknown は権限エラー、存在しない部活は NotFound が先 |
| I-200 | test_C_update_event_end_before_start_uses_current_value_for_missing_key | test_I200_update_event_end_before_start_uses_current_value_for_missing_key | SP-61 | update_event の end_before_start は fields に無いキーを現在値で判定 |
| I-201 | test_C_add_member_unknown_employee_is_not_found_before_permission | test_I201_add_member_unknown_employee_is_not_found_before_permission | SP-62, SP-74 | 存在しない社員の追加は権限より先に NotFound |
| I-202 | test_C_remove_member_permission_and_order | test_I202_remove_member_permission_and_order | SP-62, SP-74 | remove_club_member の権限、NotFound→権限→Conflict(organizer) の順 |
| I-203 | test_C_create_club_permission_comes_before_validation | test_I203_create_club_permission_comes_before_validation | SP-58, SP-59, SP-74 | create_club は権限が入力より先 |
| I-204 | test_C_create_club_multiple_required_missing_reports_first_in_listed_order | test_I204_create_club_multiple_required_missing_reports_first_in_listed_order | SP-59 | 必須が複数未入力なら列挙順で最初の1件 |

関連: I-114／I-176／I-177 の備考に挙げたテスト名も新名に更新した（権限マトリクスへの remove_club_member 追加は I-114／I-176 のテスト本体に含まれる）。
