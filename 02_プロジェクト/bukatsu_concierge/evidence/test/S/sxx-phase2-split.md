# S-xx 黒箱 Phase2 T1: テスト一覧と α-W 再仕分け

作成: Kurosu（2026-10-11）。ブランチ `feature/test-sxx-phase2-w3`（`feature/test-sxx-lc-w3` 起点）。`テスト結果.md` 本体は未変更。
前提: `sxx-coverage-map.md`（Phase1）。だーあさ裁定（α-Wは「中間」）: 主役（申込・キャンセル）だけ実DB書込で黒箱、周辺は画面挙動（偽repo）で充足。

## 1. α-W 15件の再仕分け（主役=T2 terao へ／周辺=T1 で充足）

| S | 区分 | 判定根拠（1行） | 充足するテスト（周辺）／T2への依頼内容（主役） |
| --- | --- | --- | --- |
| S-19 | **主役→T2** | 「申込む」そのものの新規書込（applications・messages・notifications・操作履歴）が要件の本質 | 実DBで申込→各表に1件ずつできる→後始末 |
| S-25 | **主役→T2** | 「キャンセル」の状態更新が要件の本質（やり取りの表示・送信は周辺） | 実DBでキャンセル→状態「キャンセル」・通知が届く→後始末。送信は L-C で充足済み |
| S-26 | **主役→T2** | キャンセル後に同じ開催へ再申込できること（部分一意インデックス）は実DBでしか言えない | 実DBで申込→キャンセル→再申込が新しい申込になる→後始末 |
| S-20（DB分） | **主役→T2**（S-20 本体は α-0） | 二重申込の防止は実DBの部分一意インデックスが担う。画面のエラー文言は α-0 で確認済み | 実DBで同じ開催に重複申込→拒否される（あれば S-19 と同じ後始末に相乗り） |
| S-16 | 周辺→T1 | 検索の操作履歴は付随的な記録。画面が記録を依頼する挙動で足りる | `test_S16_search_changes_are_recorded_with_conditions` |
| S-21 | 周辺→T1 | 閲覧の操作履歴。同上 | `test_S21_opening_club_detail_is_recorded` |
| S-49 | 周辺→T1 | 操作履歴に社員ID・対象・条件が入ること。画面→記録の依頼内容で足りる（社員検索は記録しない） | `test_S49_search_view_apply_are_recorded_…`, `test_S49_employee_search_is_not_recorded` |
| S-50 | 周辺→T1 | 二重記録の防止は画面の再描画での挙動（連続表示・同一条件） | `test_S50_same_conditions_and_same_club_are_not_recorded_twice` |
| S-30 | 周辺→T1 | 通知の既読化は付随的な更新。どの種類を既読にするかは画面→service の挙動で足りる | `test_S30_opening_messages_marks_related_notifications_read` |
| S-34 | 周辺→T1 | 同上（通知一覧を開くと全て既読） | `test_S34_opening_notifications_marks_all_read` |
| S-41 | 周辺→T1 | 公開設定の保存。画面操作→保存の呼び出しと再表示で足りる | `test_S41_both_toggles_save_immediately_and_persist` |
| S-43 | 周辺→T1 | 興味・参加可能時間の編集の保存。同上 | `test_S43_edit_interests_and_slots_are_saved` |
| S-45 | 周辺→T1 | 部活情報の保存・必須エラー。同上（CHECK制約はDB側で別に守られる） | `test_S45_save_changes_and_required_error` |
| S-46 | 周辺→T1 | 開催の登録・編集・中止・予定に戻す。管理操作で、アプリの主役ではない | `test_S46_add_edit_cancel_restore_event` |
| S-48 | 周辺→T1 | メンバーの追加・削除（Should）。管理操作 | `test_S48_member_list_add_remove` |
| S-61 | 周辺→T1（**要確認**） | 中止で申込済みの人にだけ通知が届く。幹事の操作が起点で、申込・キャンセルそのものではない | `test_S61_cancel_event_notifies_only_applied_people_and_keeps_status`（画面をまたぐ） |

**T2（terao）に送る主役サブセット: S-19, S-25, S-26, S-20（DB分）の4件。** 方式は LB書3件と同じ（センチネル社員E999＋`LB-TEST-%`部活を投入→検証→必ず削除）。
**確認したい点:** S-61 は「申込済みの人に中止の通知が届く」という利用者体験に直結するため、実DBで通知の挿入を見たい場合は T2 に足してよい（周辺としたのは「主役＝申込・キャンセル」という裁定の文言どおりに分けたため）。

注意: 周辺 12件の合格は「偽repoに対する画面操作→書込結果の合格」で、実DBへの反映の合格ではない。

## 2. T1 のテスト一覧と実行コマンド

### α-0（AppTest＋偽repo・DB不要）: `tests/test_sxx_appt_a0_screens.py`, `tests/test_sxx_appt_a0_periphery.py`

実行: `python3 -m pytest tests/test_sxx_appt_a0_*.py -v -rs`（TZ=UTC でも同じ結果）。**Kurosu が実行済み**（`evidence/test/S/sxx-a0-run.log`）: **31 passed / 1 failed / 1 skipped**、サブテスト28件合格。

| S | テスト | 要件・期待結果 | 結果 |
| --- | --- | --- | --- |
| S-03 | `test_S03_back_returns_to_previous_screen` | F-03 戻る＝直前の画面（部活検索/社員検索） | 合格 |
| S-04 | `test_S04_conditions_survive_detail_and_back` | F-04 詳細から戻っても検索条件が残る（部活・社員の両方） | 合格 |
| S-05 | `test_S05_rule_on_detail_form_and_complete` | F-05 運営ルールが詳細・申込フォーム・申込完了に出る | 合格 |
| S-06 | `test_S06_no_solo_ok_wording_on_any_screen` | F-06 「1人参加OK」が全画面（10画面）に出ない | 合格 |
| S-10 | `test_S10_home_entries_have_one_line_explanations` | F-10 入口2つに一行説明（文言は仕様に決まりなし。仮置きの一文があることを確認） | 合格 |
| S-20 | `test_S20_already_applied/canceled_event/started_event_error_message` | F-20 重複・中止・開始済みのエラー文言（古い画面を再現するため、サービスの判定だけ差し替え） | 合格（3件） |
| S-31 | `test_S31_empty_messages_both_tabs` | F-31 0件の案内文（SP-42 改訂後） | 合格 |
| S-33 | `test_S33_view_button_targets`, `test_S33_cancel_type_has_no_view_button` | F-33 「見る」→メッセージ。中止は「見る」なし（SP-45 改訂後） | 合格 |
| S-38 | `test_S38_no_employee_found_message` | F-38 0件の案内文（偽repoが絞り込まないので結果を0件に差し替え） | 合格 |
| S-47 | `test_S47_end_same_as_or_before_start_is_error`, `…_past_date_is_error_but_today_is_ok` | F-47 同時刻・以前はエラー、過去日はエラー、今日は可 | 合格 |
| S-51 | `test_S51_demand_without_club_visualization` | F-51（Could）運営者向け可視化 | **skip（未実装）**。app に該当画面・サービスが無い。テスト結果には「未実装」を記録 |
| S-52 | `test_S52_club_detail/application_complete/club_admin_…_datetime_format` | N-05 日時が「9/26（土）19:00」の形式 | 合格（3件） |
| S-52 | `test_S52_messages_event_datetime_format` | 同上（メッセージ画面） | **不合格**: 実測「10/16(金) 19:00〜21:00」（半角括弧）。仕様 SP-07「9/26（土）19:00」（全角括弧）と不一致。`screens/messages.py` の `_format_event` |
| S-56 | `test_S56_no_reset_button_on_screens` | N-09 初期化ボタンが一般画面に無い（9画面＋ログイン） | 合格 |
| S-16, 21, 30, 34, 41, 43, 45, 46, 48, 49, 50, 61 | `tests/test_sxx_appt_a0_periphery.py` の各テスト（表1のとおり） | 周辺の画面挙動 | 全て合格（13件） |

### α-R（AppTest＋実DB 読取のみ）: `tests/test_sxx_appt_ar_real.py`（本体は `tests/sxx_ar_cases.py`）

**実走は god（Kurosu は未接続）。** 実DBが使えないときは自動 skip。

```
python3 -m pytest tests/test_sxx_appt_ar_*.py -v -rs
```
- `allowed_domains=["*.supabase.co"]` が必要。L-A/L-C（偽repo）とは別プロセスで回す（同一プロセスだと「偽のdb.clientが入っている」で自動 skip）。
- secrets は直下 `.streamlit/secrets.toml`（worktree からは本体直下も探す。別の場所は `LB_SECRETS=<path>`）。
- **書込は流れない**: 画面を開くだけで起きる操作履歴の記録・通知の既読化は `ReadOnlyGuard` が握りつぶす（insert/update/delete/upsert を実DBに届けず、rpc は禁止）。ガード自体の確認は `tests/test_sxx_guard.py`（3件合格）。

| S | テスト | 要件・期待結果（期待値は生テーブルから組み立て） |
| --- | --- | --- |
| S-02 | `test_S02_manage_menu_only_for_organizer_and_admin` | 一般社員に「部活の管理」が無い／幹事・運営者には「プロフィール」の次に有る（実在の社員で） |
| S-07 | `test_S07_real_employee_logs_in_to_home` | 実在の社員ID（小文字）＋実の共通パスワードでログイン→ホーム。誤パスワードは固定文言 |
| S-11 | `test_S11_home_week_popular_and_level_toggle` | 今週（今日〜日曜）の部活・今月の人気の並びが生データと一致。初心者向け/経験者向けの切替 |
| S-12 | `test_S12_recommendations_have_score_reason_and_exclude_joined` | 一致度の点数・理由が出る。所属済みの部活は出ない |
| S-13 | `test_S13_search_screen_and_or_matches_data` | 画面の入力（拠点OR・カテゴリ×拠点AND・曜日・レベル・キーワード・組合せ）→件数・カードが生データと一致 |
| S-14 | `test_S14_result_cards_show_required_rows` | カードに名前・拠点/活動時間・次回開催・タグ・費用/活動後が出る |
| S-17 | `test_S17_club_detail_shows_all_sections_and_facts` | 詳細の見出し・基本情報・不安分解項目・幹事・メンバー数・運営ルール |
| S-18 | `test_S18_events_in_date_order_with_counts_and_canceled` | 開催が日付順、参加人数（うち初参加）が申込と一致、中止は「中止」 |
| S-24 | `test_S24_received_tab_only_for_organizer` | 「届いた申込」タブは実在の幹事にのみ |
| S-28 | `test_S28_received_tab_shows_applicants_first_time_mark_and_stamp` | 申込者名・初参加の印・スタンプボタン（初参加・未確認のみ） |
| S-32 | `test_S32_notifications_newest_first_and_unread_bold` | 通知が新しい順、未読は太字 |
| S-35 | `test_S35_employee_search_screen_matches_data` | 名前・部署＋拠点・興味・時間・所属・組合せ→件数が生データと一致 |
| S-36 | `test_S36_private_values_are_not_used_or_shown_in_search`, `…_private_slots_…` | 非公開の興味・時間は条件にも結果表示にも使われない（公開の対照つき） |
| S-37 | `test_S37_result_cards_show_required_fields` | 部署・拠点・入社年・入社区分・興味・所属部活 |
| S-40 | `test_S40_other_profile_follows_public_settings` | 他人のプロフィールが公開設定どおり（非公開は「非公開」） |
| S-44 | `test_S44_admin_scope_and_new_button` | 運営者は全部活（非公開含む）と新規作成ボタン、幹事は担当部活のみ、一般は案内 |
| S-58 | `test_S58_club_detail_people_expose_only_needed_columns` | 幹事・メンバーの返却に管理者フラグ・参加可能時間・公開設定が無い |
| S-60 | `test_S60_action_logs_are_usable_for_kpi` | 操作履歴の行が社員ID・日時・対象（部活 or 条件）を持つ |

データが実DBに無いときは、合格にせず skip＋理由。skip は「未実行」のまま備考に理由を書く運用でお願いします。

## 3. オフライン構造検証（Kurosu 実施。実DBには接続していない）

証拠: `evidence/test/S/sxx-ar-offline-verify.log`

- α-R の収集 19件＋ガード3件。secrets無し→19件すべて理由つき skip。偽repoと同居→skip。
- ドライラン（`python3 tests/sxx_ar_dryrun.py`。L-C の偽の世界に合成データを足して α-R の本体を回す）: **19件 OK**。偽repoは絞り込まないため、絞り込みだけ期待値の定義で差し替えている（配線とハーネスの書き間違いを見るため。実DBの結果ではない）。
- 検出力（意図的な不具合を入れて落ちること）: 今週の範囲（S-11）・非公開の漏れ（S-36）・所属済みのおすすめ（S-12）・曜日の絞り込み無効（S-13）・初参加の印の欠落（S-28/S-11）が、いずれも該当テストで検出された。

## 4. 未確認・限界

- α-R は実DBで未実行。実DBのカラム名・型は repo 実装と I/F 契約からの推定（`employees.is_admin`、`action_logs` の日時列名など）。違えば実走で ERROR/skip になる。
- α-0 の合格は偽repoに対するもの。S-38 は偽repoが絞り込まないため結果を0件に差し替えている。S-20 の3件は、画面が再描画でフォームを消すため、サービスの判定だけ差し替えて「古い画面からの送信」を再現した。
- S-10 の説明文言は仕様に決まりが無く、画面の仮置きの一文があることだけを確認した（文言の正しさは判断していない）。
- 周辺12件の充足は偽repoの範囲。実DBへの反映は L-B書込の一意制約・除外の確認以外、確認していない。
