# S-xx カバレッジ三角測量表（Phase1・机上の突き合わせ）

作成: Kurosu（2026-10-11）。テスト実行・新規テスト実装なし。`テスト結果.md` 本体は未変更。

## 1. 使った証拠と、その限界

| 略称 | 内容 | 証拠 | 限界（判定に効く点） |
| --- | --- | --- | --- |
| LC | L-C 画面（Streamlit AppTest＋**偽repo**）。`tests/test_lc_*.py` 64件。207件中203合格・4不合格（I-136, I-057, I-058, I-061） | `evidence/test/I/unittest-LA-LC-{Asia-Tokyo,UTC}.log` | 偽repoなので「実データ・実DBの挙動」は言えない。偽repoは絞り込まない。ブラウザの見た目は見ていない |
| LC後 | I-136 は修正（`1a581dc`）後に合格。I-057/058/061 は仕様側を実装に合わせて改訂（`d8cf26d`、はなえPM裁定）。**テストの期待値は旧仕様のまま・再実行未** | `evidence/test/I/pytest-I136-fix.log`（I-061のみ不合格） | I-057/058/061 の合格は「旧実測が改訂後の仕様と一致」という記録で、再実行の合格ではない |
| LA | L-A service＋偽repo（143件）。**補助**扱い。画面×実データの両方は言えないので、単独では①にしない | `evidence/test/I/unittest-*.log` | 偽repo |
| LB読 | L-B 実DB・読取専用。15 passed / 3 skipped（14件合格）: I-008, I-022〜025, I-064〜068, I-140, I-178〜180 | `evidence/test/I/lb-realrun-result.log`（`feature/test-lb-realdb-w3` `a8c2cf1`） | repo/service層のみ。画面は通っていない。SELECTのみ |
| LB書 | L-B 実DB・書込3件（センチネル投入→削除）: I-026, I-090, I-091 合格 | `evidence/test/I/lb-writes-realrun-result.log`（`feature/test-lb-writes-w3` `c01e45b`） | 書込の確認は一意制約と is_active 除外のみ。申込・メッセージ・通知・操作履歴の書込は未確認 |
| 件数 | 実DB件数（employees=500, clubs=15 ほか） | `evidence/test/S/db-connectivity-ok.log` | 件数のみ |

## 2. 判定区分の定義

- **①** 既存の LC＋LB で要件充足が言える（黒箱追試不要）。
- **②** 一部のみ。残りが gap。
- **③** 既存では言えない（要黒箱）。根拠が無いものは③に倒した。

gap を埋める方式の見立て（主方式を1つ付け、補助があれば併記）:

- **α-0**: AppTest（偽repoで足りる。実DB不要。テスト追加または再実行）。
- **α-R**: AppTest＋実DB **読取のみ**（god 実走。allowed_domains=`*.supabase.co`）。
- **α-W**: AppTest／service＋実DB **書込**（センチネル＋後始末。運営承認が要る。LB書3件と同じ運用）。
- **β**: だーあさ実機（見た目・実ブラウザ・時間・運営判断）。

判断の原則（下の表で一貫させた点）:

- 画面から実DBの値を**書き込む**要件（申込・キャンセル・既読化・保存・操作履歴）は、LCが偽repo、LBは書込3件のみなので、②（α-W）にした。
- 実在の幹事・運営者・一般社員の**ロール判定**を実DBで見た証拠が無いので、F-02/F-24/F-44 は②（α-R）にした。
- 「検索の入力 → 条件 → 結果」の**画面通し**は LC（偽repo）と LB（repo直）が別々で、つながっていないので②（α-R）にした。

## 3. 仕分け表（61件。S-59 は対象外）

| S | 要件 | 関連 LC（画面・偽repo） | 関連 LB / 他 | 区分 | 根拠 / gap | 方式 |
| --- | --- | --- | --- | --- | --- | --- |
| S-01 | F-01 | `ShellAndLogin.test_I001_menu_order_and_unread_label`, `test_I001_sidebar_shows_name_dept_id` | LA I105（未読件数） | ① | メニュー順・名前/部署/ID・未読表示を画面で確認。値はセッション由来で実データ依存が薄い | — |
| S-02 | F-02 | 同上（一般社員E005に無く、幹事・運営者に規定位置で出る） | LA I120/I194/I195（ロール判定・偽repo） | ② | 偽repoのロールでの表示のみ。実DBの実在の幹事・運営者・一般社員での表示は未確認 | α-R |
| S-03 | F-03 | `ClubDetail.test_I002_back_returns_previous` | — | ② | 部活詳細の戻るのみ。社員検索→社員プロフィール→戻るが未確認 | α-0 |
| S-04 | F-04 | `ClubSearch.test_I003_conditions_kept_in_session` | — | ② | 部活検索の条件保持のみ。社員検索の条件保持と、詳細から戻った後の入力欄の復元が未確認 | α-0 |
| S-05 | F-05 | `ClubDetail.test_I031_header`（運営ルールの一文）, 申込完了 `test_I044_order_of_sections` | — | ② | 部活詳細と申込完了は確認。申込フォーム内の表示は `test_I038_form_contents` に運営ルールの確認が見当たらない | α-0 |
| S-06 | F-06 | （画面横断の禁止語走査なし） | — | ③ | 「1人参加OK」が全画面に出ないことを横断して見たテストが無い | α-0（＋β目視） |
| S-07 | F-07 | `test_I010_login_goes_home`, `test_I011_lowercase_id_is_normalized` | LA I010/I011（偽repo） | ② | 偽repoでの遷移のみ。実DBの実在社員ID＋実の共通パスワードでログイン→ホームが未確認（実repoの `get_by_id` は L-B 未実行） | α-R |
| S-08 | F-08 | `test_I012_wrong_id_and_wrong_password_same_message`, `test_I009_I013_login_screen_texts` | LA I012 | ① | 誤ID・誤パスワードで同じ文言（どちらが誤りか示さない）を確認。文言は実データに依存しない | — |
| S-09 | F-09 | `test_I014_logout_clears_and_returns_to_login` | — | ① | ログアウトでセッションが空になりログイン画面へ戻ることを確認。実ブラウザの再読込は未確認（補助でβ） | — |
| S-10 | F-10 | `Home.test_I016_buttons_navigate`, `test_I015_greeting` | — | ② | 入口ボタンの遷移は確認。各入口の「一行の説明」の表示が未確認 | α-0 |
| S-11 | F-11 | `Home.test_home_week_card_and_popular_rank`, `test_home_empty_messages` | LB I-008（今週の範囲・実DB）, LA I017/I019/I121〜128 | ② | 今週の範囲は実DBで確認済み（repo/service）。画面の人気部活の表示内容、初心者向け/経験者向けの切り替え表示が未確認 | α-R |
| S-12 | F-12 | （ホームのおすすめ表示のLCなし） | LA I020/I129（偽repo） | ③ | 一致度スコア・おすすめ理由の画面表示と、実データでの算出が未確認。すでに所属の部活が出ないことも実データでは未確認 | α-R（＋β見た目） |
| S-13 | F-13 | `ClubSearch.test_I028_count_shown` | LB I-022/I-023/I-024/I-025（実DB・repo直） | ② | カテゴリ・拠点・キーワードの AND/OR は実DBで確認。曜日/時間帯・レベルの単独条件と、画面の入力→条件→結果の通しが未確認 | α-R |
| S-14 | F-14 | `test_I028_count_shown` | LA I130 | ② | 件数は確認。カードの構成（拠点/活動時間・次回開催日・雰囲気タグ・費用/活動後の過ごし方）が未カバー | α-R（＋β見た目） |
| S-15 | F-15 | `test_I029_zero_result_message` | LB I-022〜025（0件も含め絞り込みは実DB確認） | ① | 0件で案内文が出ることを確認（偽repoは絞り込まないので世界を空にして再現）。絞り込み自体は実DBで確認済み | — |
| S-16 | F-16 | `test_I030_search_records_conditions_only_when_set` | LA I030/I116/I117（偽repo） | ② | 実DBの action_logs に検索が記録されることが未確認（書込） | α-W |
| S-17 | F-17 | `test_I031_header`, `test_I032_sections` | LA I137 | ② | 見出しは確認。不安分解項目の各値・幹事情報の表示内容を、実データで見ていない | α-R |
| S-18 | F-18 | `test_I033_future_only_in_date_order`, `test_I034_open_unapplied_shows_apply_button`, `test_I036_canceled_event_shows_text_no_button` | LA I134 | ② | 日付順・過去除外・中止の表示は確認。日時・集合場所/時刻・参加人数・参加者（初参加の印）の表示を実データで見ていない | α-R |
| S-19 | F-19 | `test_I039_submit_applies_and_goes_to_complete` | LA I092（偽repo） | ② | 画面から申込が完了するのは偽repoでのみ。実DBで applications / messages / notifications / action_logs が作られることが未確認（書込） | α-W |
| S-20 | F-20 | `test_I035_applied_shows_label_no_button` | LA I041/I042/I181（偽repo） | ② | 申込済みでボタンが出ないことは確認。重複・中止・開始済みの**エラー文言の画面表示**が未確認。実DBの二重申込防止（部分一意インデックス）も未確認 | α-0（エラー表示）＋α-W |
| S-21 | F-21 | `test_I043_opening_records_view_club` | LA I043/I118/I192（偽repo） | ② | 閲覧の記録が実DBの action_logs に入ることが未確認（書込） | α-W |
| S-62 | F-18, F-20 | `test_I136_inactive_club_hides_apply_button` | LB書 I-026（非公開部活の検索除外・実DB） | ① | 修正（`1a581dc`）後に I-136 合格（`pytest-I136-fix.log`）。`is_active` は列の値で、実データ依存が薄い | — |
| S-22 | F-22 | `ApplicationComplete.test_I044_order_of_sections`, `test_I044_buttons_navigate_and_clear_context` | — | ① | 完了の一言・申込内容・次に起きること・当日の情報・運営ルール・ボタンの順を確認 | — |
| S-23 | F-23 | `test_I045_no_context_goes_home` | — | ① | 申込完了情報が無いときにホームへ遷移 | — |
| S-24 | F-24 | `Messages.test_I046_tabs_only_for_organizer` | LA I120 | ② | 偽repoのロールでのタブ表示のみ。実在の幹事・一般社員での表示が未確認（S-02 と同じ gap） | α-R |
| S-25 | F-25 | `test_I051_canceled_view_only`, `test_I049_cancel_requires_confirmation`, `test_I055_applicant_sees_confirmed`, `test_send_message_ok` | LA I049/I095 | ② | 状態表示・やり取り・キャンセル確認は画面で確認。キャンセルと送信が実DBに反映されることが未確認（書込） | α-W |
| S-26 | F-26 | `test_I049_cancel_requires_confirmation`, `test_cancel_stop_keeps_application` | LA I049/I098（再申込は新しい申込）/I050/I097 | ② | 確認ダイアログ→キャンセルは画面で確認。実DBでキャンセル後に同じ開催へ再申込できること（部分一意インデックス）が未確認（書込） | α-W |
| S-27 | F-27 | `test_I051_canceled_view_only` | LA I104 | ① | キャンセル済みは閲覧のみ・送信不可を確認 | — |
| S-28 | F-28 | `test_I054_stamp_button_only_first_time`, `test_send_message_ok` | LA I052/I110 | ② | 初参加の印・スタンプは確認。幹事側の「届いた申込」の申込者情報の表示と幹事の返信が画面で未確認 | α-R |
| S-29 | F-29 | `test_I054_stamp_button_only_first_time`, `test_stamp_click_confirms` | LA I110/I056/I189/I190 | ① | 初参加の人にだけスタンプが出る・押せることを確認 | — |
| S-30 | F-30 | `test_opening_marks_related_notifications_read` | LA I047/I106（偽repo） | ② | 関連通知が既読になるのは偽repoでのみ。実DBの notifications 更新が未確認（書込） | α-W |
| S-31 | F-31 | `test_I057_I058_empty_messages`, `test_I057_wording_per_spec`, `test_I058_wording_per_spec` | — | ② | 0件の案内文は表示される。ただし期待値が旧SP-42のままで、旧実測は改訂後の仕様と一致するという記録のみ。再実行が未 | α-0（期待値更新＋再実行） |
| S-32 | F-32 | `Notifications.test_I060_unread_bold_and_marked_read` | LA I060（新しい順・偽repo） | ② | 未読の太字は確認。実DBでの並び順（新しい順）が未確認 | α-R |
| S-33 | F-33 | `test_I061_view_navigates_to_messages`（合格）, `test_I061_cancel_notice_view_goes_to_club_detail`（不合格） | — | ② | メッセージへの遷移は確認。中止通知の扱いは SP-45 改訂（`d8cf26d`）後の再実行が未 | α-0（再実行） |
| S-34 | F-34 | `test_I060_unread_bold_and_marked_read` | LA I139/I062（偽repo） | ② | 開くと全部既読になるのは偽repoでのみ。実DBへの反映が未確認（書込） | α-W |
| S-35 | F-35 | `EmployeeSearch.test_I063_notice_at_top`, `test_I070_paging_20_and_more_button` | LB I-064（組合せ・count）, I-065, I-140（実DB・repo直） | ② | 6条件の組合せは実DBで確認（repo直）。画面の入力→条件→結果の通しが未確認 | α-R |
| S-36 | F-36 | `EmployeeProfile.test_I073_private_shows_hidden_label` | LB I-066/I-067/I-068（実DB・検索条件側）, LA I073 | ② | 検索条件での除外は実DBで確認。**検索結果画面**に非公開値が出ないことを実データで見ていない | α-R |
| S-37 | F-37 | `test_I070_paging_20_and_more_button` | LA（search_employees の件数） | ② | ページングと件数は確認。カードの項目（部署/拠点/入社年/入社区分・興味・所属部活）が未確認 | α-R |
| S-38 | F-38 | （社員検索の0件案内のLCなし） | — | ③ | 0件の案内文を確認したテストが無い | α-0 |
| S-39 | F-39 | `EmployeeProfile.test_I072_basic_fields` | LA I072 | ① | 部署・拠点・入社年・入社区分の表示を確認 | — |
| S-40 | F-40 | `test_I073_private_shows_hidden_label`, `test_I076_other_cannot_see_toggles` | LA I073/I141 | ② | 偽repoでの「非公開」表示のみ。実在の公開/非公開混在の社員で、他人から見たときの表示が未確認 | α-R |
| S-41 | F-41 | `test_I075_self_sees_toggles_and_saves`, `test_I076_other_cannot_see_toggles` | LA I075 | ② | 切り替えと保存は偽repoでのみ。実DBへの保存が未確認（書込） | α-W |
| S-42 | F-42 | `test_I074_club_card_goes_to_detail` | LA I074/I142 | ① | 所属部活のカードから部活詳細へ遷移を確認 | — |
| S-43 | F-43 | （編集UIのLCなし） | LA I077/I145/I146（save_profile・偽repo） | ③ | 画面での興味・参加可能時間の編集と保存が未確認。service のみ偽repoで確認 | α-W |
| S-44 | F-44 | `ClubAdminScreen.test_I078_organizer_has_no_new_button`, `test_I079_admin_has_new_button`, `test_I078_organizer_sees_only_own_clubs` | LA I078/I079 | ② | 偽repoのロールでの確認のみ。実在の幹事・運営者で担当部活のみ／全部活が選べることが未確認 | α-R |
| S-45 | F-45 | `test_I080_save_shows_saved_message`, `test_I081_blank_required_shows_error_and_does_not_save` | LA I080/I153〜I156 | ② | 画面の保存メッセージ・必須エラーは偽repoで確認。実DBの保存（CHECK制約含む）が未確認（書込） | α-W |
| S-46 | F-46 | `test_I085_cancel_confirmation_text_and_effect` | LA I083〜I086/I111/I112/I167/I168 | ② | 中止の確認と通知は偽repoで確認。開催の登録・編集・予定に戻すの画面と、実DBへの反映・通知挿入が未確認（書込） | α-W |
| S-47 | F-47 | （画面の入力エラー表示のLCなし） | LA I087/I088/I149〜I152（service・偽repo） | ② | 判定ロジックは service で確認（今日は通る・終了=開始はエラー）。画面にエラーが表示されることが未確認 | α-0 |
| S-48 | F-48 | （メンバータブのLCなし） | LA I089/I170〜I175 | ③ | 画面でのメンバー一覧・追加・削除が未確認。実DBへの反映も未確認 | α-W |
| S-49 | F-49 | `test_I030_search_records_conditions_only_when_set`, `test_I043_opening_records_view_club` | LA I030/I043/I116〜I118/I192 | ② | 記録は偽repoでのみ。実DBの action_logs の列（社員ID・日時・対象・条件）と、申込完了での記録が未確認（書込） | α-W |
| S-50 | F-50 | `test_I030_search_records_conditions_only_when_set` | LA I116/I118/I192/I193 | ② | 二重記録されないのは偽repoでのみ。実DBでの確認が未（書込） | α-W |
| S-51 | F-51 | （LCなし） | — | ③ | Could機能。実装の有無が確認できていない。まずコード確認（未実装なら「未実装」を記録） | α-0（実装があれば）／確認 |
| S-61 | F-46, F-32 | `test_I085_cancel_confirmation_text_and_effect`（通知の確認）, `test_I061_cancel_notice_view_goes_to_club_detail` | LA I085/I111/I167 | ② | 中止で申込済みにだけ通知・申込の状態は変わらない、を偽repoで確認。実DBで通知が届くことと、通知一覧の「中止」表示（SP-45 改訂後の再実行含む）が未確認 | α-W |
| S-52 | N-05 | `test_I033_future_only_in_date_order`（「10/15」を含む日付行） | LB I-178〜I-180（JST判定・repo） | ② | 書式「9/26（土）19:00」の全画面での一致は未確認。実機のタイムゾーン表示も未確認 | α-0（書式）＋β |
| S-53 | N-06 | `test_home_week_card_and_popular_rank` | LB I-008（実DB・週切替、今日〜日曜の両端含む）, LA I121 | ① | 実DBで日曜23:59→月曜0:00の切替と範囲を確認。月曜〜昨日が出ないことも期待値側で確認 | — |
| S-54 | N-07 | — | 件数: employees=500, clubs=15（`db-connectivity-ok.log`） | ② | 件数は実DBで確認。「実在社員の情報が含まれない」は内容の確認が必要で、証拠が無い | β |
| S-55 | N-08 | — | — | ③ | seed固定で毎回同じ結果になることの証拠が無い。共有DBでの `reset_data.py` は運営承認が要る（実行不可）。生成のみをDB書込なしで2回比較できるかの確認が先 | β（運営判断） |
| S-56 | N-09 | （画面横断走査なし） | — | ③ | 一般画面に初期化ボタンが無いことを横断して見たテストが無い | α-0 |
| S-57 | N-11 | — | LB書（センチネル投入→削除。永続の確認ではない） | ③ | アプリ再起動後のデータ残存の証拠が無い | β |
| S-58 | N-12 | `test_I073_private_shows_hidden_label` | LB I-066/I-067/I-068, LA I137（返却列・偽repo） | ② | 検索側は実DBで確認。部活詳細の幹事・メンバーに必要最小限の列だけが出ることを、実DBの返却で見ていない | α-R |
| S-60 | N-14 | `test_I030_…`, `test_I043_…` | LA I030/I043（偽repo）, action_logs 15件（件数のみ） | ② | KPIに使える形（社員ID・日時・対象・条件）が実DBの行で確認できていない | α-R |
| S-59 | N-13 | — | — | 対象外 | 運用ルール（人事評価・ランキングに結びつけない）。画面・データの黒箱では確認できない | — |

N-01〜04・N-10 は黒箱対象外（実装レビュー扱い）で、上の61件に含まれない。

## 4. 集計

| 区分 | 件数 | S-xx |
| --- | --- | --- |
| ① 既存LC＋LBで充足 | **12** | S-01, 08, 09, 15, 22, 23, 27, 29, 39, 42, 53, 62 |
| ② 一部のみ（gapあり） | **40** | 下の表を参照 |
| ③ 既存では言えない（要黒箱） | **9** | S-06, 12, 38, 43, 48, 51, 55, 56, 57 |
| 計 | 61 | |

②の40件: S-02, 03, 04, 05, 07, 10, 11, 13, 14, 16, 17, 18, 19, 20, 21, 24, 25, 26, 28, 30, 31, 32, 33, 34, 35, 36, 37, 40, 41, 44, 45, 46, 47, 49, 50, 52, 54, 58, 60, 61

### gap の方式別（②③の49件。主方式で1件ずつ）

| 方式 | 件数 | S-xx | 前提 |
| --- | --- | --- | --- |
| **α-0** AppTest（偽repoで足りる。DB不要） | 13 | S-03, 04, 05, 06, 10, 20(エラー表示分), 31, 33, 38, 47, 51, 52, 56 | 新規テスト追加または再実行。S-31/33 は I-057/058/061 の期待値を改訂後の仕様に直して再実行 |
| **α-R** AppTest＋実DB **読取** | 18 | S-02, 07, 11, 12, 13, 14, 17, 18, 24, 28, 32, 35, 36, 37, 40, 44, 58, 60 | god 実走。allowed_domains=`*.supabase.co`。SELECTのみ。LB読と同じ運用 |
| **α-W** 実DB **書込**（センチネル＋後始末） | 15 | S-16, 19, 21, 25, 26, 30, 34, 41, 43, 45, 46, 48, 49, 50, 61 | 運営承認が要る。LB書3件と同じくセンチネル投入→検証→必ず削除。clubs.id の欠番など副作用を事前に周知 |
| **β** だーあさ実機 | 3 | S-54, 55, 57 | 実在情報の有無の目視、seed固定の判断、アプリ再起動 |

補足（β を補助に足す候補）: 見た目・レイアウト（S-12, 14）、全画面の目視（S-06）、実機のタイムゾーン表示（S-52）、ログアウト後のブラウザ再読込（S-09）。

## 5. 判断が割れうる点（godの確認がほしい所）

1. **書込を伴う画面要件を②（α-W）にした**（S-16, 19, 21, 25, 26, 30, 34, 41, 45, 46, 49, 50, 61）。LC が偽repoなので、実DBへの反映は言えないという判断。「画面が偽repoで正しく動けば足りる」と見るなら、これらの一部は①に寄る。
2. **ロール判定（S-02, 24, 44）を②にした**。実在の幹事・運営者・一般社員の実DBでの確認が無い。α-R で足りる軽い gap。
3. **S-05**: 運営ルールは部活詳細・申込完了で確認。申込フォーム内の表示だけテストが見当たらず②にした。
4. **S-31/S-33/I-057/058/061**: 仕様が実装に合わせて改訂され、期待値が旧仕様のままのテストは未更新・未再実行。②にしている。テスト側を直して再実行すれば①に上がる見込み。
5. **S-62**: 修正後の合格ログは I-136 の1件（`pytest-I136-fix.log`）。①にした。
6. LA（service＋偽repo）は補助扱いで、単独では①にしていない。

## 6. 未確認・限界

- 机上の突き合わせのみ。テストコードの中身は、判定に効く箇所だけ読んだ。読んでいないテストの内容は、テスト名からの推定を含む（S-05 の `test_I038_form_contents` など）。
- L-C のテストは `feature/test-sxx-lc-w3` ブランチにあり、main にはまだ無い。L-B は `feature/test-lb-realdb-w3`／`feature/test-lb-writes-w3`。
- 実DBの結果は、godが取った2つのログ（読取14件合格・書込3件合格）を転記したもの。この表を作るために実DBには接続していない。
