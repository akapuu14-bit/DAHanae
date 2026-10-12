# U単体・部品確認と担当タスクの対応（2026-10-12）

コード基準: `2da2eeb98ef1adf2af1eb627e729bd0aa85ed433`。実行者: Codex。元の実装担当の代行で今回の実行証拠を整理したもので、本人確認・タスクへの添付完了ではない。既存課題本文200件以内と課題コメント全55件を読み取り、U-数字3桁の既存採番はコメントには無かった。結果表のU枠も空だった。未取得の私的チャット・PRコメント等に採番がある可能性は担当レビューで確認する。

## 採番と確認単位

U-001〜013を本PRで採番。1IDは対象モジュール／観点の検証組。6画面・配色組と7サービス組、184関数、pytest展開185ケース。subTest内の追加アサーションはケース数に加算しない。I/Sとの横断合計は作らない。サービス側153関数はL-A/Iとして既に存在するテストの再利用で、repo自体を置き換えたメモリ上の確認。真のrepository、接続、制約、実機確認を証明しない。

## 担当タスクへの添付用一覧

以下のタスク対応・実装担当はGitHubの課題内容/割当とバックログから照合した確認案。割当を過去の実行者の証明にはしない。BE専用課題の無いclub_admin_serviceはコミット `dbf3264`（Hiroki Asada）の実装を参照し、画面#41の単体合格に転用しない。

| U-ID | 対象 | 担当タスク | 課題割当 | ログ上のケース数 |
|---|---|---|---|---:|
| U-001 | `screens/login.py` | [#32](https://github.com/akapuu14-bit/DAHanae/issues/32) / [#81](https://github.com/akapuu14-bit/DAHanae/issues/81) | akapuu14-bit | 4 |
| U-002 | `screens/home.py` | [#33](https://github.com/akapuu14-bit/DAHanae/issues/33) / [#142](https://github.com/akapuu14-bit/DAHanae/issues/142) | akapuu14-bit | 5 |
| U-003 | `screens/club_detail.py（申込・遷移）` | [#35](https://github.com/akapuu14-bit/DAHanae/issues/35) | akapuu14-bit | 11 |
| U-004 | `screens/club_detail.py（折りたたみ）` | [#35](https://github.com/akapuu14-bit/DAHanae/issues/35) / [#142](https://github.com/akapuu14-bit/DAHanae/issues/142) | akapuu14-bit | 4 |
| U-005 | `screens/employee_search.py` | [#39](https://github.com/akapuu14-bit/DAHanae/issues/39) | akapuu14-bit | 3 |
| U-006 | `assets/style.css / .streamlit/config.toml` | [#142](https://github.com/akapuu14-bit/DAHanae/issues/142) | akapuu14-bit | 5 |
| U-007 | `services/auth_service.py` | [#23](https://github.com/akapuu14-bit/DAHanae/issues/23) / [#103](https://github.com/akapuu14-bit/DAHanae/issues/103) | HanaeSakamoto, Hiroki0023 | 6 |
| U-008 | `services/search_service.py` | [#24](https://github.com/akapuu14-bit/DAHanae/issues/24) / [#82](https://github.com/akapuu14-bit/DAHanae/issues/82) / [#112](https://github.com/akapuu14-bit/DAHanae/issues/112) / [#116](https://github.com/akapuu14-bit/DAHanae/issues/116) | HanaeSakamoto, Hiroki0023 | 26 |
| U-009 | `services/action_log_service.py` | [#25](https://github.com/akapuu14-bit/DAHanae/issues/25) | Hiroki0023 | 9 |
| U-010 | `services/notification_service.py` | [#26](https://github.com/akapuu14-bit/DAHanae/issues/26) | Hiroki0023 | 7 |
| U-011 | `services/application_service.py` | [#27](https://github.com/akapuu14-bit/DAHanae/issues/27) / [#83](https://github.com/akapuu14-bit/DAHanae/issues/83) / [#115](https://github.com/akapuu14-bit/DAHanae/issues/115) | HanaeSakamoto, Hiroki0023 | 39 |
| U-012 | `services/profile_service.py` | [#116](https://github.com/akapuu14-bit/DAHanae/issues/116) | Hiroki0023 | 14 |
| U-013 | `services/club_admin_service.py` | BE専用課題未確認（関連UI #41） | 実装コミット著者 Hiroki Asada / 担当確認待ち | 52 |

添付する文章（対象課題のIDを選ぶ）:

> 単体・部品確認の対応: U-ID＝上表の該当ID、対象＝上表の対象。コード基準2da2eeb、2026-10-12にCodexがDB非接続で検証し合格。実行証拠は `evidence/test/U/u-inventory-main-20261012.log`、テスト名と確認範囲は本対応表。サービス側はL-A/I証拠との重複利用であり、実DBやrepository実装の合格を意味しない。採番・対象・担当対応を実装担当に確認依頼。

GitHubコメント投稿は行っていない。レビュー後に担当タスクへ上記対応と証拠リンクを添付する。#42の通し確認はI/S・実DB証拠と別途照合し、未実行を隠さずPMが判断する。

## 全テスト名（関数単位、パラメータ展開はログを参照）

### U-001: screens/login.py

確認観点: 画面認証・正式ID・エラー文言。4関数/4ケース。

- `tests/frontend/test_login.py::test_shows_app_name_and_tagline`
- `tests/frontend/test_login.py::test_shows_demo_note`
- `tests/frontend/test_login.py::test_wrong_credentials_show_error_and_stay_logged_out`
- `tests/frontend/test_login.py::test_success_records_official_id_not_typed_one`

### U-002: screens/home.py

確認観点: 入口・0件案内・カード。5関数/5ケース。

- `tests/frontend/test_home.py::test_greeting_and_two_entry_buttons`
- `tests/frontend/test_home.py::test_club_search_button_goes_to_club_search`
- `tests/frontend/test_home.py::test_employee_search_button_goes_to_employee_search`
- `tests/frontend/test_home.py::test_empty_sections_show_guidance`
- `tests/frontend/test_home.py::test_week_clubs_are_shown_as_cards`

### U-003: screens/club_detail.py（申込・遷移）

確認観点: 表示条件・フォーム・競合・遷移。10関数/11ケース。

- `tests/frontend/test_club_detail.py::test_apply_button_shown_for_open_unapplied_event`
- `tests/frontend/test_club_detail.py::test_applied_event_shows_applied_and_no_button`
- `tests/frontend/test_club_detail.py::test_cancelled_event_shows_cancelled_and_no_button`
- `tests/frontend/test_club_detail.py::test_view_is_recorded_when_opened`
- `tests/frontend/test_club_detail.py::test_apply_form_opens_and_can_be_closed`
- `tests/frontend/test_club_detail.py::test_apply_success_goes_to_complete_screen`
- `tests/frontend/test_club_detail.py::test_conflict_shows_message_and_does_not_leave`
- `tests/frontend/test_club_detail.py::test_organizer_button_goes_to_profile`
- `tests/frontend/test_club_detail.py::test_close_does_not_apply`
- `tests/frontend/test_club_detail.py::test_member_button_goes_to_profile`

### U-004: screens/club_detail.py（折りたたみ）

確認観点: 初期折りたたみ・内容維持・開催表示。4関数/4ケース。

- `tests/frontend/test_club_detail_sections.py::test_four_sections_are_collapsed_by_default`
- `tests/frontend/test_club_detail_sections.py::test_contents_are_unchanged_inside_collapsed_sections`
- `tests/frontend/test_club_detail_sections.py::test_one_event_is_not_collapsed`
- `tests/frontend/test_club_detail_sections.py::test_next_event_stays_open_and_others_are_collapsed`

### U-005: screens/employee_search.py

確認観点: 件数・0件案内・プロフィール遷移。3関数/3ケース。

- `tests/frontend/test_employee_search.py::test_notice_and_count_and_cards`
- `tests/frontend/test_employee_search.py::test_profile_button_goes_to_profile`
- `tests/frontend/test_employee_search.py::test_no_result_shows_guidance`

### U-006: assets/style.css / .streamlit/config.toml

確認観点: 配色コントラスト・設定一致・reduced motion。5関数/5ケース。

- `tests/frontend/test_theme.py::test_text_is_readable_on_backgrounds`
- `tests/frontend/test_theme.py::test_primary_button_text_is_readable`
- `tests/frontend/test_theme.py::test_primary_color_text_is_readable_on_surfaces`
- `tests/frontend/test_theme.py::test_config_toml_matches_style_css`
- `tests/frontend/test_theme.py::test_reduced_motion_is_respected`

### U-007: services/auth_service.py

確認観点: 認証・大文字小文字・ロール。6関数/6ケース。

- `tests/test_notification_action_auth.py::AuthTests::test_I010_login_ok_returns_employee`
- `tests/test_notification_action_auth.py::AuthTests::test_I011_id_case_insensitive`
- `tests/test_notification_action_auth.py::AuthTests::test_I012_wrong_id_or_password_same_error`
- `tests/test_notification_action_auth.py::AuthTests::test_I120_roles`
- `tests/test_notification_action_auth.py::AuthTests::test_I194_role_edge_cases`
- `tests/test_notification_action_auth.py::AuthTests::test_I195_admin_only_and_organizer_only_both_manage`

### U-008: services/search_service.py

確認観点: 週/月のJST境界・推薦・表示データ・非公開項目。26関数/26ケース。

- `tests/test_search_profile.py::HomeWeekTests::test_I121_week_range_wed_sun_and_next_monday`
- `tests/test_search_profile.py::HomeWeekTests::test_I017_five_or_more_clubs_all_returned_sorted_by_date`
- `tests/test_search_profile.py::HomeWeekTests::test_I018_zero_cases`
- `tests/test_search_profile.py::HomeWeekTests::test_I122_inactive_club_excluded`
- `tests/test_search_profile.py::HomeWeekTests::test_I123_all_canceled_events_excluded`
- `tests/test_search_profile.py::PopularTests::test_I019_ranking_by_first_time_non_canceled_desc`
- `tests/test_search_profile.py::PopularTests::test_I124_canceled_event_applications_not_counted`
- `tests/test_search_profile.py::PopularTests::test_I125_ties_by_club_id_with_sequential_rank`
- `tests/test_search_profile.py::PopularTests::test_I126_month_boundary_uses_jst`
- `tests/test_search_profile.py::PopularTests::test_I127_no_counts_returns_empty`
- `tests/test_search_profile.py::RecommendTests::test_I128_no_match_returns_empty`
- `tests/test_search_profile.py::RecommendTests::test_I129_joined_clubs_not_recommended`
- `tests/test_search_profile.py::RecommendTests::test_I020_score_reason_and_sort`
- `tests/test_search_profile.py::RecommendTests::test_I129_non_public_settings_still_used_for_self`
- `tests/test_search_profile.py::RecommendTests::test_I130_card_has_level`
- `tests/test_search_profile.py::SearchClubsTests::test_I027_I131_I132_next_event_ordering_and_none_last`
- `tests/test_search_profile.py::SearchClubsTests::test_service_builds_cards_only_from_repo_rows`
- `tests/test_search_profile.py::ClubDetailTests::test_I133_unknown_club_not_found`
- `tests/test_search_profile.py::ClubDetailTests::test_I134_counts_only_applied_and_canceled_event_listed`
- `tests/test_search_profile.py::ClubDetailTests::test_I135_members_include_organizer`
- `tests/test_search_profile.py::ClubDetailTests::test_I137_returned_columns_are_limited`
- `tests/test_search_profile.py::ClubDetailTests::test_I193_repeated_fetch_does_not_log`
- `tests/test_search_profile.py::ClubDetailTests::test_inactive_club_detail_still_returned_button_is_screen_side`
- `tests/test_search_profile.py::SearchEmployeesVisibilityTests::test_I073_I069_private_values_hidden_from_others_not_self`
- `tests/test_search_profile.py::SearchEmployeesVisibilityTests::test_search_employees_total_and_page_size`
- `tests/test_search_profile.py::SearchEmployeesVisibilityTests::test_clubs_shown_regardless_of_privacy`

### U-009: services/action_log_service.py

確認観点: 検索/閲覧/申込ログ・重複抑止・入力検証。9関数/9ケース。

- `tests/test_notification_action_auth.py::ActionLogTests::test_I030_search_is_recorded`
- `tests/test_notification_action_auth.py::ActionLogTests::test_I116_same_conditions_not_recorded_twice`
- `tests/test_notification_action_auth.py::ActionLogTests::test_I117_changed_conditions_recorded`
- `tests/test_notification_action_auth.py::ActionLogTests::test_I043_view_club_recorded`
- `tests/test_notification_action_auth.py::ActionLogTests::test_I118_consecutive_same_club_not_recorded_twice`
- `tests/test_notification_action_auth.py::ActionLogTests::test_I192_A_B_A_records_three`
- `tests/test_notification_action_auth.py::ActionLogTests::test_dedup_is_per_employee`
- `tests/test_notification_action_auth.py::ActionLogTests::test_I119_no_employee_search_recorder_exists`
- `tests/test_notification_action_auth.py::ActionLogTests::test_validation_required_fields`

### U-010: services/notification_service.py

確認観点: 既読範囲・未読件数・通知検証。7関数/7ケース。

- `tests/test_notification_action_auth.py::NotificationTests::test_I047_messages_screen_marks_four_types_only`
- `tests/test_notification_action_auth.py::NotificationTests::test_I138_cancel_notice_stays_unread_and_is_counted`
- `tests/test_notification_action_auth.py::NotificationTests::test_I139_I062_notification_list_marks_all_read_including_cancel`
- `tests/test_notification_action_auth.py::NotificationTests::test_I106_each_trigger_reads_its_own_range`
- `tests/test_notification_action_auth.py::NotificationTests::test_I060_list_newest_first_with_unread_flag`
- `tests/test_notification_action_auth.py::NotificationTests::test_I105_count_is_only_own_unread`
- `tests/test_notification_action_auth.py::NotificationTests::test_notify_validation`

### U-011: services/application_service.py

確認観点: 申込/取消/送信/スタンプ・開始時刻境界・副作用。39関数/39ケース。

- `tests/test_application_service.py::ApplyTests::test_I092_apply_creates_all_records`
- `tests/test_application_service.py::ApplyTests::test_I115_general_employee_can_apply_and_cancel`
- `tests/test_application_service.py::ApplyTests::test_I093_empty_message_not_saved_but_rest_runs`
- `tests/test_application_service.py::ApplyTests::test_I094_organizer_self_apply_no_notification`
- `tests/test_application_service.py::ApplyTests::test_I098_reapply_after_cancel_makes_new_application`
- `tests/test_application_service.py::ApplyTests::test_I041_duplicate_apply_conflict_already_applied`
- `tests/test_application_service.py::ApplyTests::test_I042_canceled_event_conflict_not_open`
- `tests/test_application_service.py::ApplyTests::test_I042_started_event_conflict_not_open`
- `tests/test_application_service.py::ApplyTests::test_I042_unknown_event_not_found`
- `tests/test_application_service.py::ApplyTests::test_I181_start_time_boundary`
- `tests/test_application_service.py::FirstTimeTests::test_I099_non_member_no_past_is_first_time`
- `tests/test_application_service.py::FirstTimeTests::test_I100_member_is_not_first_time`
- `tests/test_application_service.py::FirstTimeTests::test_I101_past_non_canceled_application_is_not_first_time`
- `tests/test_application_service.py::FirstTimeTests::test_I102_past_canceled_only_is_first_time`
- `tests/test_application_service.py::CancelTests::test_I049_I095_cancel_before_start`
- `tests/test_application_service.py::CancelTests::test_I096_other_user_cannot_cancel`
- `tests/test_application_service.py::CancelTests::test_I050_I097_start_time_boundary`
- `tests/test_application_service.py::CancelTests::test_I182_double_cancel_conflict_no_second_notification`
- `tests/test_application_service.py::CancelTests::test_I183_organizer_cancel_own_application_no_notification`
- `tests/test_application_service.py::CancelTests::test_I095_unknown_application_not_found`
- `tests/test_application_service.py::SendMessageTests::test_I053_I184_trimmed_body_and_notification_both_directions`
- `tests/test_application_service.py::SendMessageTests::test_I185_and_I059_empty_body_validation_no_notification`
- `tests/test_application_service.py::SendMessageTests::test_I186_organizer_self_application_no_notification`
- `tests/test_application_service.py::SendMessageTests::test_I103_third_party_cannot_send`
- `tests/test_application_service.py::SendMessageTests::test_I104_canceled_application_conflict`
- `tests/test_application_service.py::SendMessageTests::test_I187_error_order`
- `tests/test_application_service.py::ConfirmStampTests::test_I110_I055_confirm_records_and_notifies_applicant`
- `tests/test_application_service.py::ConfirmStampTests::test_I056_second_press_conflict`
- `tests/test_application_service.py::ConfirmStampTests::test_I188_canceled_application_conflict`
- `tests/test_application_service.py::ConfirmStampTests::test_I189_non_organizer_permission`
- `tests/test_application_service.py::ConfirmStampTests::test_I190_not_first_time_conflict`
- `tests/test_application_service.py::ConfirmStampTests::test_I191_error_order`
- `tests/test_application_service.py::UnreadCountTests::test_I107_non_member_new_application_counted`
- `tests/test_application_service.py::UnreadCountTests::test_I108_existing_member_application_counted`
- `tests/test_application_service.py::UnreadCountTests::test_I109_organizer_self_application_not_counted`
- `tests/test_application_service.py::UnreadCountTests::test_I105_unread_count_matches_unread_rows`
- `tests/test_application_service.py::ListTests::test_I048_my_applications_order`
- `tests/test_application_service.py::ListTests::test_I052_received_applications_unread_first_then_newest`
- `tests/test_application_service.py::ListTests::test_received_applications_empty_for_non_organizer`

### U-012: services/profile_service.py

確認観点: 本人/他人・非公開項目・検証順序・0件保存。14関数/14ケース。

- `tests/test_search_profile.py::ProfileTests::test_I072_basic_fields_and_is_self`
- `tests/test_search_profile.py::ProfileTests::test_I073_private_hidden_from_others`
- `tests/test_search_profile.py::ProfileTests::test_I141_self_sees_values_and_flags`
- `tests/test_search_profile.py::ProfileTests::test_I142_only_active_clubs_in_id_order`
- `tests/test_search_profile.py::ProfileTests::test_I074_club_cards_have_ids`
- `tests/test_search_profile.py::ProfileTests::test_I147_unknown_employee_not_found`
- `tests/test_search_profile.py::ProfileTests::test_I075_self_can_toggle_public`
- `tests/test_search_profile.py::ProfileTests::test_I143_others_cannot_toggle_public`
- `tests/test_search_profile.py::ProfileTests::test_I077_self_save_profile`
- `tests/test_search_profile.py::ProfileTests::test_I144_others_cannot_save`
- `tests/test_search_profile.py::ProfileTests::test_I145_invalid_input_validation_and_nothing_saved`
- `tests/test_search_profile.py::ProfileTests::test_I146_empty_lists_save_zero`
- `tests/test_search_profile.py::ProfileTests::test_I143_error_order_not_found_before_permission`
- `tests/test_search_profile.py::ProfileTests::test_I144_I145_save_profile_error_order_not_found_permission_validation`

### U-013: services/club_admin_service.py

確認観点: 一覧・権限・部活/開催/メンバー管理・入力検証。52関数/52ケース。

- `tests/test_club_admin_service.py::ListManageableTests::test_I078_organizer_sees_own_clubs_including_inactive`
- `tests/test_club_admin_service.py::ListManageableTests::test_I079_admin_sees_all`
- `tests/test_club_admin_service.py::ListManageableTests::test_I148_general_employee_gets_empty_list`
- `tests/test_club_admin_service.py::ClubFieldTests::test_I080_save_updates_fields`
- `tests/test_club_admin_service.py::ClubFieldTests::test_I153_I081_I080_each_required_field_blank_is_rejected`
- `tests/test_club_admin_service.py::ClubFieldTests::test_I153_create_club_missing_required_key`
- `tests/test_club_admin_service.py::ClubFieldTests::test_I154_whitespace_only_same_as_blank`
- `tests/test_club_admin_service.py::ClubFieldTests::test_I155_optional_fields_may_be_empty`
- `tests/test_club_admin_service.py::ClubFieldTests::test_I156_values_outside_choices_rejected`
- `tests/test_club_admin_service.py::ClubFieldTests::test_I157_unknown_activity_or_organizer_rejected`
- `tests/test_club_admin_service.py::ClubFieldTests::test_I158_mood_tags_limit_and_allowed_values`
- `tests/test_club_admin_service.py::ClubFieldTests::test_unknown_key_rejected`
- `tests/test_club_admin_service.py::ClubFieldTests::test_I082_organizer_cannot_change_organizer_or_is_active`
- `tests/test_club_admin_service.py::ClubFieldTests::test_I159_same_values_ignored_other_fields_saved`
- `tests/test_club_admin_service.py::ClubFieldTests::test_I160_admin_can_change_organizer_and_is_active`
- `tests/test_club_admin_service.py::ClubFieldTests::test_I203_create_club_permission_comes_before_validation`
- `tests/test_club_admin_service.py::ClubFieldTests::test_I204_create_club_multiple_required_missing_reports_first_in_listed_order`
- `tests/test_club_admin_service.py::ClubFieldTests::test_I161_create_club_registers_organizer_as_member`
- `tests/test_club_admin_service.py::ClubFieldTests::test_I162_organizer_change_auto_registers_new_and_keeps_old`
- `tests/test_club_admin_service.py::ClubFieldTests::test_I113_non_admin_cannot_create_club`
- `tests/test_club_admin_service.py::ClubFieldTests::test_I177_update_club_error_order`
- `tests/test_club_admin_service.py::EventTests::test_I083_create_event_status_planned_and_default_place`
- `tests/test_club_admin_service.py::EventTests::test_I084_update_event_applied`
- `tests/test_club_admin_service.py::EventTests::test_I087_I149_end_not_after_start_rejected`
- `tests/test_club_admin_service.py::EventTests::test_I088_I150_past_date_rejected_today_allowed_jst`
- `tests/test_club_admin_service.py::EventTests::test_I151_update_past_event_other_fields_ok_but_past_date_rejected`
- `tests/test_club_admin_service.py::EventTests::test_I152_validation_order_required_then_past_then_end_before_start`
- `tests/test_club_admin_service.py::EventTests::test_I196_create_event_unknown_key_rejected_and_nothing_saved`
- `tests/test_club_admin_service.py::EventTests::test_I197_update_event_unknown_status_cannot_cancel_without_notification`
- `tests/test_club_admin_service.py::EventTests::test_I198_unknown_comes_before_required_in_create_and_update`
- `tests/test_club_admin_service.py::EventTests::test_I199_unknown_is_after_not_found_and_permission`
- `tests/test_club_admin_service.py::EventTests::test_I200_update_event_end_before_start_uses_current_value_for_missing_key`
- `tests/test_club_admin_service.py::EventTests::test_I165_meeting_time_optional`
- `tests/test_club_admin_service.py::EventTests::test_I163_list_events_from_today_ordered_including_canceled`
- `tests/test_club_admin_service.py::EventTests::test_I164_applicant_count_counts_only_applied`
- `tests/test_club_admin_service.py::EventTests::test_I166_no_events_or_unknown_club_returns_none`
- `tests/test_club_admin_service.py::EventStatusTests::test_I085_I111_I167_cancel_notifies_applied_only_and_keeps_applications`
- `tests/test_club_admin_service.py::EventStatusTests::test_I086_I112_I168_restore_has_no_notification_and_recancel_notifies_again`
- `tests/test_club_admin_service.py::EventStatusTests::test_I169_same_status_conflict_and_invalid_status`
- `tests/test_club_admin_service.py::EventStatusTests::test_I177_set_status_error_order`
- `tests/test_club_admin_service.py::MemberTests::test_I089_add_and_remove_member`
- `tests/test_club_admin_service.py::MemberTests::test_I170_already_member_conflict`
- `tests/test_club_admin_service.py::MemberTests::test_I171_cannot_remove_organizer_until_changed`
- `tests/test_club_admin_service.py::MemberTests::test_I172_remove_non_member_not_found`
- `tests/test_club_admin_service.py::MemberTests::test_I201_add_member_unknown_employee_is_not_found_before_permission`
- `tests/test_club_admin_service.py::MemberTests::test_I202_remove_member_permission_and_order`
- `tests/test_club_admin_service.py::MemberTests::test_I173_list_members_marks_organizer`
- `tests/test_club_admin_service.py::MemberTests::test_I174_selectable_employees_all_sorted_by_name_then_id_with_id_name_only`
- `tests/test_club_admin_service.py::MemberTests::test_I175_selectable_employees_general_denied`
- `tests/test_club_admin_service.py::PermissionMatrixTests::test_I176_allowed_roles_can_do_everything`
- `tests/test_club_admin_service.py::PermissionMatrixTests::test_I114_I176_other_organizer_and_general_denied_everywhere`
- `tests/test_club_admin_service.py::PermissionMatrixTests::test_I177_unknown_ids_not_found_even_without_permission`

## 境界観点の証拠

- 開始時刻ちょうど/直前: U-011の `ApplyTests::test_I181_start_time_boundary`、`CancelTests::test_I050_I097_start_time_boundary`（他の送信/スタンプ観点は上記テスト名とログを参照）。
- 0件: U-002の `test_empty_sections_show_guidance`、U-005の `test_no_result_shows_guidance`、U-008の `HomeWeekTests::test_I018_zero_cases`、U-012の `ProfileTests::test_I146_empty_lists_save_zero`。
- 大文字小文字: U-007の `AuthTests::test_I011_id_case_insensitive`。repoのget_by_id自体は偽repoなので未証明。

## 未確認の単体範囲（採番・実装担当確認の残件）

既存L-B/L-C/Sは参照候補として記す。独立したUに自動変換せず、必要な分離検証があるか担当が確認する。U13組が合格しても以下は全件合格に含めない。

| 対象 | 担当タスク | 不足・既存確認の位置づけ |
|---|---|---|
| `app.py` | #28 | 今回の独立U対象外。L-C/S等の既存確認は再利用可否を担当確認。 |
| `components/club_card.py` | #30 | 今回の独立U対象外。L-C/S等の既存確認は再利用可否を担当確認。 |
| `components/error_banner.py` | #31 | 今回の独立U対象外。L-C/S等の既存確認は再利用可否を担当確認。 |
| `components/rule_notice.py` | #31 | 今回の独立U対象外。L-C/S等の既存確認は再利用可否を担当確認。 |
| `components/sidebar.py` | #30 | 今回の独立U対象外。L-C/S等の既存確認は再利用可否を担当確認。 |
| `components/theme.py` | 課題/所有範囲の確認待ち | 今回の独立U対象外。L-C/S等の既存確認は再利用可否を担当確認。 |
| `db/client.py` | #10 | 今回の独立U対象外。L-C/S等の既存確認は再利用可否を担当確認。 |
| `repositories/action_logs_repo.py` | #22 | 偽repoでは本実装の単体検証にならない。L-B実DB確認は別層。 |
| `repositories/activities_repo.py` | #15 | 偽repoでは本実装の単体検証にならない。L-B実DB確認は別層。 |
| `repositories/applications_repo.py` | #19 | 偽repoでは本実装の単体検証にならない。L-B実DB確認は別層。 |
| `repositories/club_members_repo.py` | #17 | 偽repoでは本実装の単体検証にならない。L-B実DB確認は別層。 |
| `repositories/clubs_repo.py` | #16 | 偽repoでは本実装の単体検証にならない。L-B実DB確認は別層。 |
| `repositories/employees_repo.py` | #14 | 偽repoでは本実装の単体検証にならない。L-B実DB確認は別層。 |
| `repositories/events_repo.py` | #18 | 偽repoでは本実装の単体検証にならない。L-B実DB確認は別層。 |
| `repositories/messages_repo.py` | #20 | 偽repoでは本実装の単体検証にならない。L-B実DB確認は別層。 |
| `repositories/notifications_repo.py` | #21 | 偽repoでは本実装の単体検証にならない。L-B実DB確認は別層。 |
| `screens/application_complete.py` | #36 | 今回の独立U対象外。L-C/S等の既存確認は再利用可否を担当確認。 |
| `screens/club_admin.py` | #41 | 今回の独立U対象外。L-C/S等の既存確認は再利用可否を担当確認。 |
| `screens/club_search.py` | #34 | 今回の独立U対象外。L-C/S等の既存確認は再利用可否を担当確認。 |
| `screens/employee_profile.py` | #40 | 今回の独立U対象外。L-C/S等の既存確認は再利用可否を担当確認。 |
| `screens/messages.py` | #37 | 今回の独立U対象外。L-C/S等の既存確認は再利用可否を担当確認。 |
| `screens/notifications.py` | #38 | 今回の独立U対象外。L-C/S等の既存確認は再利用可否を担当確認。 |
| `services/errors.py` | #13 | 今回の独立U対象外。L-C/S等の既存確認は再利用可否を担当確認。 |
| `state.py` | #29 | 今回の独立U対象外。L-C/S等の既存確認は再利用可否を担当確認。 |
| `scripts/reset_data.py` / スキーマ / Secrets雛形 | #12 / #9 / #11 | dry-runや構造確認の証拠はU別途分類。今回実DBseedやSecrets値の読取は行っていない。 |

担当タスクがCLOSEDでもU証拠の添付済みとは判断しない。特に#142はUI全体の課題で、U-006だけで全画面完了とは扱わない。採番未掲載の範囲には、不足テストを特定した後にU-014以降を付与する。

## 検証結果

限定実行は185 passed、失敗・skipなし。185ケースのすべてを上記U13組へ一意に対応させた。I204行/S62行/A表の内容は本変更で保持。U集計は組単位で13合格。実DBの再実走・初期化、課題close、PRマージは行っていない。
