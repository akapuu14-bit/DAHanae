#!/usr/bin/env bash
# 部活コンシェルジュ：タスクバックログ.md Wave0-4 を GitHub Issue 化する下書きスクリプト
#
# 位置づけ：issues_seed.md の一覧をそのまま gh issue create に落としたもの。
# scripts/setup_github.sh が既に作った既存ラベル（area:be/ui/pdm, type:*, prio:*）・
# 既存マイルストーン（〜9/29 アプリのカタチ／〜10/2 8割／10/7-12 最終）に乗せる。
# 追加で wave:0〜4 ラベルを作成する。
#
# 【裁定：Issue二重化解消】Wave0-4の36件（本スクリプト）が正式なタスクIssue。
# setup_github.sh のseed Issue作成は行わない（setup_github.shはLabel/Milestone作成のみに
# 変更済み前提。kurosu横断レビュー指摘S-2に基づく。setup_github.sh本体の修正はterao担当）。
#
# 前提：
#   - scripts/setup_github.sh を先に実行し、既存Label/Milestoneが作成済みであること
#     （本スクリプトは既存Label/Milestoneの作成は行わない。wave:0-4のみ新規作成）
#   - gh CLI がインストール・認証済み（gh auth login 済み）
#   - --assignee は指定しない（issues_seed.md 0.3節のとおり、担当割り当ては人間が実行時に行う。
#     各Issue本文末尾の「担当: @handle」を参照してPM/担当者が手動でassignすること）
#
# 再実行しても壊れないよう、作成前に既存タイトルの重複を確認する（setup_github.shと同方式）。
#
# 使い方（PM/担当者がgh認証・admin権限を確認した上で実行）：
#   chmod +x 02_プロジェクト/bukatsu_concierge/実装ガイド/create_issues.sh
#   ./02_プロジェクト/bukatsu_concierge/実装ガイド/create_issues.sh

set -euo pipefail

if ! command -v gh >/dev/null 2>&1; then
  echo "エラー: gh CLI が見つかりません。docs/github-管理セットアップ.md の手順でインストールしてください。" >&2
  exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "エラー: gh が未認証です。'gh auth login' を先に実行してください。" >&2
  exit 1
fi

REPO="$(gh repo view --json nameWithOwner --jq .nameWithOwner)"
echo "対象リポジトリ: ${REPO}"

# ---------------------------------------------------------------------------
# 0. wave:0-4 ラベルを追加作成（既存のarea/type/prioラベルはsetup_github.sh側の責務）
# ---------------------------------------------------------------------------
echo ""
echo "== wave ラベル追加 =="

create_label() {
  local name="$1" color="$2" desc="$3"
  if gh label list --limit 200 --json name --jq '.[].name' | grep -Fxq "$name"; then
    echo "  skip (既存): $name"
  else
    gh label create "$name" --color "$color" --description "$desc"
    echo "  created: $name"
  fi
}

create_label "wave:0" "c5def5" "Wave0：DB基盤"
create_label "wave:1" "bfd4f2" "Wave1：repositories"
create_label "wave:2" "bfe5bf" "Wave2：services"
create_label "wave:3" "f9d0c4" "Wave3：画面の実データ接続"
create_label "wave:4" "d4c5f9" "Wave4：結合・テスト"

# ---------------------------------------------------------------------------
# 1. Issue 作成
# ---------------------------------------------------------------------------
echo ""
echo "== Issue 作成（タスクバックログ.md Wave0-4） =="
echo "  (注) --assignee は指定しません。本文末尾の「担当」欄を見てPM/担当者が手動で割り当ててください。"

create_issue() {
  local title="$1" body="$2" labels="$3" milestone="$4"
  if gh issue list --state all --search "in:title \"$title\"" --json title --jq '.[].title' | grep -Fxq "$title"; then
    echo "  skip (既存): $title"
  else
    gh issue create --title "$title" --body "$body" --label "$labels" --milestone "$milestone" >/dev/null
    echo "  created: $title"
  fi
}

M_KATACHI="〜9/29 アプリのカタチ"
M_HACHIWARI="〜10/2 8割"
M_SAISHU="10/7-12 最終"

# --- Wave 0：DB基盤 ---------------------------------------------------------

create_issue \
  "[Wave0][BE] Supabaseスキーマ作成（10テーブル）" \
  $'タスクバックログ.md T-B00 より。設計.md3章の型・制約・インデックス方針どおりに10テーブルを作成する。\n\n対応: 仕様.md3章, 設計.md3章, N-02\n依存: なし\n受入基準: 外部キー・一意制約（club_members, employee_interests）が設計.md3章どおりに入っている\n触るファイル: Supabase側スキーマ定義\n\n担当: @Hiroki0023（terao支援）' \
  "area:be,type:feature,wave:0" "$M_KATACHI"

create_issue \
  "[Wave0][BE] db/client.py：Supabaseクライアント初期化" \
  $'タスクバックログ.md T-B01 より。Secretsから接続情報を読み、モジュールレベルで1クライアントを生成する。\n\n対応: 設計.md6章, N-02, N-04\n依存: T-B00\n受入基準: st.secretsから接続情報を読み1クライアントを生成できる\n触るファイル: app/frontend/db/client.py\n\n担当: @Hiroki0023（terao支援）' \
  "area:be,type:feature,wave:0" "$M_KATACHI"

create_issue \
  "[Wave0][PDM] Secrets雛形作成" \
  $'タスクバックログ.md T-B02 より。supabase_url/supabase_key/common_passwordのキー名をdb/client.pyと一致させた雛形を用意する。\n\n対応: N-04\n依存: T-B00\n受入基準: T-B01とキー名が一致している\n触るファイル: app/frontend/.streamlit/secrets.toml.example\n\n担当: @HanaeSakamoto（takahiro支援）' \
  "area:pdm,type:feature,wave:0" "$M_KATACHI"

create_issue \
  "[Wave0-] scripts/reset_data.py：ダミーデータ生成" \
  $'タスクバックログ.md T-D01 より。社員500名・部活15件、seed固定、実在情報不使用でダミーデータを生成・初期化するスクリプト。\n\n対応: SP-78, N-07〜N-09, 仕様.md7章\n依存: T-B00\n受入基準: 実行で全テーブルが空になり再投入される。同じseedで同じ結果になる\n触るファイル: scripts/reset_data.py（アプリソース外）\n\n担当: @HanaeSakamoto' \
  "area:pdm,type:feature,wave:0" "$M_KATACHI"

# --- Wave 1：repositories＋共通エラー ---------------------------------------

create_issue \
  "[Wave1][BE] services/errors.py：共通例外定義" \
  $'タスクバックログ.md T-B03 より。I-F契約.md0.4の共通例外5種（ValidationError/NotFoundError/ConflictError/AuthenticationError/PermissionDeniedError）を定義する。\n\n対応: I-F契約.md0.4\n依存: なし\n受入基準: 5種すべてが他モジュールからimportできる\n触るファイル: app/frontend/services/errors.py\n\n担当: @Hiroki0023' \
  "area:be,type:feature,wave:1" "$M_KATACHI"

create_issue \
  "[Wave1][BE] repositories/employees_repo.py" \
  $'タスクバックログ.md T-B04 より。I-F契約.md2.1の全関数（get_by_id/search/count/update_public_settings/get_interests/set_interests）を実装する。\n\n対応: F-35〜F-43\n依存: T-B01\n受入基準: get_by_idが大文字小文字を区別せず引ける\n触るファイル: app/frontend/repositories/employees_repo.py\n\n担当: @Hiroki0023' \
  "area:be,type:feature,wave:1" "$M_KATACHI"

create_issue \
  "[Wave1][BE] repositories/activities_repo.py" \
  $'タスクバックログ.md T-B05 より。I-F契約.md2.2の全関数（list_all/get）を実装する。\n\n対応: F-13, F-35\n依存: T-B01\n受入基準: 全関数が実装される\n触るファイル: app/frontend/repositories/activities_repo.py\n\n担当: @Hiroki0023' \
  "area:be,type:feature,wave:1" "$M_KATACHI"

create_issue \
  "[Wave1][BE] repositories/clubs_repo.py" \
  $'タスクバックログ.md T-B06 より。I-F契約.md2.3の全関数（get/search/list_by_organizer/list_all_for_admin/create/update）を実装する。\n\n対応: F-17, F-44〜F-45\n依存: T-B01, T-B05\n受入基準: searchがSP-20のAND/OR組み合わせに対応する\n触るファイル: app/frontend/repositories/clubs_repo.py\n\n担当: @Hiroki0023' \
  "area:be,type:feature,wave:1" "$M_KATACHI"

create_issue \
  "[Wave1][BE] repositories/club_members_repo.py" \
  $'タスクバックログ.md T-B07 より。I-F契約.md2.4の全関数（is_member/list_members/add_member/remove_member）を実装する。\n\n対応: F-42, F-48\n依存: T-B01\n受入基準: 全関数が実装される\n触るファイル: app/frontend/repositories/club_members_repo.py\n\n担当: @Hiroki0023' \
  "area:be,type:feature,wave:1" "$M_KATACHI"

create_issue \
  "[Wave1][BE] repositories/events_repo.py" \
  $'タスクバックログ.md T-B08 より。I-F契約.md2.5の全関数（get/list_upcoming_by_club/list_upcoming_all_with_club/get_last_meeting_place/create/update/set_status）を実装する。\n\n対応: F-18, F-46〜F-47\n依存: T-B01, T-B06\n受入基準: list_upcoming_by_clubが過去の開催を除外する\n触るファイル: app/frontend/repositories/events_repo.py\n\n担当: @Hiroki0023' \
  "area:be,type:feature,wave:1" "$M_KATACHI"

create_issue \
  "[Wave1][BE] repositories/applications_repo.py" \
  $'タスクバックログ.md T-B09 より。I-F契約.md2.6の全関数（get/exists_active/insert/update_status/has_past_non_canceled/list_by_applicant/list_by_organizer_club/list_participants）を実装する。\n\n対応: F-19〜F-20, F-26〜F-29\n依存: T-B01, T-B08\n受入基準: exists_activeが「申込済み」状態のみを見る\n触るファイル: app/frontend/repositories/applications_repo.py\n\n担当: @Hiroki0023（terao支援）' \
  "area:be,type:feature,wave:1" "$M_KATACHI"

create_issue \
  "[Wave1][BE] repositories/messages_repo.py" \
  $'タスクバックログ.md T-B10 より。I-F契約.md2.7の全関数（list_by_application/insert）を実装する。\n\n対応: F-25, F-28\n依存: T-B01, T-B09\n受入基準: 全関数が実装される\n触るファイル: app/frontend/repositories/messages_repo.py\n\n担当: @Hiroki0023（terao支援）' \
  "area:be,type:feature,wave:1" "$M_KATACHI"

create_issue \
  "[Wave1][BE] repositories/notifications_repo.py" \
  $'タスクバックログ.md T-B11 より。I-F契約.md2.8の全関数（count_unread/list_by_recipient/insert/mark_read/mark_read_all）を実装する。\n\n対応: F-01, F-30, F-32〜F-34\n依存: T-B01\n受入基準: count_unreadがread_at IS NULLで数える\n触るファイル: app/frontend/repositories/notifications_repo.py\n\n担当: @Hiroki0023（terao支援）' \
  "area:be,type:feature,wave:1" "$M_KATACHI"

create_issue \
  "[Wave1][BE] repositories/action_logs_repo.py" \
  $'タスクバックログ.md T-B12 より。I-F契約.md2.9の全関数（insert/get_last）を実装する。\n\n対応: F-49〜F-50\n依存: T-B01\n受入基準: get_lastが指定actionの最新1件を返す\n触るファイル: app/frontend/repositories/action_logs_repo.py\n\n担当: @Hiroki0023（terao支援）' \
  "area:be,type:feature,wave:1" "$M_KATACHI"

# --- Wave 2：services --------------------------------------------------------

create_issue \
  "[Wave2][BE] services/auth_service.py" \
  $'タスクバックログ.md T-B13 より。I-F契約.md1.1のlogin/get_roleを実装する。\n\n対応: SP-63, SP-11\n依存: T-B03, T-B04\n受入基準: 大文字小文字を無視した認証ができる\n触るファイル: app/frontend/services/auth_service.py\n\n担当: @Hiroki0023' \
  "area:be,type:feature,wave:2" "$M_KATACHI"

create_issue \
  "[Wave2][BE] services/search_service.py" \
  $'タスクバックログ.md T-B14 より。I-F契約.md1.2の3関数（search_clubs/search_employees/get_recommendations）を実装する。\n\n対応: SP-64, SP-65, SP-75\n依存: T-B03, T-B04, T-B06, T-B08\n受入基準: search_employeesが非公開項目を除外する\n触るファイル: app/frontend/services/search_service.py\n\n担当: @Hiroki0023' \
  "area:be,type:feature,wave:2" "$M_KATACHI"

create_issue \
  "[Wave2][BE] services/action_log_service.py" \
  $'タスクバックログ.md T-B15 より。I-F契約.md1.5の3関数（record_search/record_view_club/record_apply）を実装する。\n\n対応: SP-76\n依存: T-B03, T-B12\n受入基準: view_clubの連続同一部活は記録しない\n触るファイル: app/frontend/services/action_log_service.py\n\n担当: @Hiroki0023（terao支援）' \
  "area:be,type:feature,wave:2" "$M_KATACHI"

create_issue \
  "[Wave2][BE] services/notification_service.py" \
  $'タスクバックログ.md T-B16 より。I-F契約.md1.4の5関数（count_unread/list_notifications/mark_read_for_messages_screen/mark_read_all/notify）を実装する。\n\n対応: SP-70〜SP-72\n依存: T-B03, T-B11\n受入基準: 5関数が実装される\n触るファイル: app/frontend/services/notification_service.py\n\n担当: @Hiroki0023（terao支援）' \
  "area:be,type:feature,wave:2" "$M_KATACHI"

create_issue \
  "[Wave2][BE] services/application_service.py" \
  $'タスクバックログ.md T-B17 より。I-F契約.md1.3の5関数（apply/cancel/list_my_applications/list_received_applications/confirm_stamp）を実装する。\n\n対応: SP-66〜SP-68, SP-72\n依存: T-B03, T-B07〜T-B10, T-B15〜T-B16\n受入基準: 設計.md5.1〜5.4の手順どおりに動く（申込→初参加判定→通知→操作履歴の順）\n触るファイル: app/frontend/services/application_service.py\n\n担当: @Hiroki0023（terao支援）' \
  "area:be,type:feature,prio:high,wave:2" "$M_KATACHI"

# --- 共通部品／画面（Milestone: 〜10/2 8割） --------------------------------

create_issue \
  "[Wave1-3][UI] app.py：ログイン判定＋ルーティング" \
  $'タスクバックログ.md T-F01 より。設計.md D-01/D-02のsession_stateルーティングを実装する。\n\n対応: SP-63, SP-13\n依存: T-B02\n受入基準: 未ログイン/ログイン済みで表示画面が切り替わる\n触るファイル: app/frontend/app.py\n\n担当: @akapuu14-bit' \
  "area:ui,type:feature,wave:1" "$M_HACHIWARI"

create_issue \
  "[Wave1-3][UI] state.py：session_stateキー定義" \
  $'タスクバックログ.md T-F02 より。設計.md4章のキーを初期化ヘルパーとして用意する。\n\n対応: 設計.md4章\n依存: T-F01\n受入基準: 4章のキーがすべて用意される\n触るファイル: app/frontend/state.py\n\n担当: @akapuu14-bit' \
  "area:ui,type:feature,wave:1" "$M_HACHIWARI"

create_issue \
  "[Wave1-3][UI] components/sidebar.py・club_card.py" \
  $'タスクバックログ.md T-F03 より。サイドバー（未読件数・メニュー出し分け）と部活カードを実装する。\n\n対応: SP-01, SP-21, SP-16, SP-55\n依存: T-F02\n受入基準: 未読件数・メニュー出し分けが表示され、部活カードが3.3の形で再利用できる\n触るファイル: app/frontend/components/sidebar.py, app/frontend/components/club_card.py\n\n担当: @akapuu14-bit（mirin支援）' \
  "area:ui,type:feature,wave:1" "$M_HACHIWARI"

create_issue \
  "[Wave1-3][PDM] components/rule_notice.py・error_banner.py" \
  $'タスクバックログ.md T-F04 より。運営ルールの一文とDB接続エラー文言を固定表示として実装する。\n\n対応: SP-04, SP-06\n依存: なし\n受入基準: 固定表示として再利用できる\n触るファイル: app/frontend/components/rule_notice.py, app/frontend/components/error_banner.py\n\n担当: @HanaeSakamoto（takahiro支援）' \
  "area:pdm,type:feature,wave:1" "$M_HACHIWARI"

create_issue \
  "[Wave1-3][UI] screens/login.py（S01）" \
  $'タスクバックログ.md T-F05 より。ログイン画面を実装する。\n\n対応: SP-09〜SP-12\n依存: T-F01\n受入基準: SP-09〜12どおりの表示・エラー文言\n触るファイル: app/frontend/screens/login.py\n\n担当: @akapuu14-bit' \
  "area:ui,type:feature,wave:2" "$M_HACHIWARI"

create_issue \
  "[Wave1-3][UI] screens/home.py（S02）" \
  $'タスクバックログ.md T-F06 より。ホーム画面を実装する。\n\n対応: SP-14〜SP-18\n依存: T-F01, T-F03\n受入基準: 0件時案内文含めSP-14〜18どおり\n触るファイル: app/frontend/screens/home.py\n\n担当: @akapuu14-bit' \
  "area:ui,type:feature,wave:2" "$M_HACHIWARI"

create_issue \
  "[Wave1-3][UI] screens/club_search.py（S03）" \
  $'タスクバックログ.md T-F07 より。部活検索画面を実装する。\n\n対応: SP-19〜SP-23\n依存: T-F03, T-B14\n受入基準: 検索条件変更で即座に結果が変わり、0件文言・操作履歴記録が動く\n触るファイル: app/frontend/screens/club_search.py\n\n担当: @akapuu14-bit' \
  "area:ui,type:feature,wave:3" "$M_HACHIWARI"

create_issue \
  "[Wave1-3][UI] screens/club_detail.py（S04）" \
  $'タスクバックログ.md T-F08 より。部活詳細・申込フォームを実装する。\n\n対応: SP-24〜SP-32\n依存: T-F03, T-F04, T-B17\n受入基準: 申込フォーム送信でapplication_service.applyが呼ばれS05へ遷移する\n触るファイル: app/frontend/screens/club_detail.py\n\n担当: @akapuu14-bit' \
  "area:ui,type:feature,prio:high,wave:3" "$M_HACHIWARI"

create_issue \
  "[Wave1-3][PDM] screens/application_complete.py（S05）" \
  $'タスクバックログ.md T-F09 より。申込完了画面を実装する。\n\n対応: SP-33〜SP-34\n依存: T-F04\n受入基準: SP-33の6項目順表示。情報がない状態で開かれたらホームへ遷移\n触るファイル: app/frontend/screens/application_complete.py\n\n担当: @HanaeSakamoto' \
  "area:pdm,type:feature,wave:2" "$M_HACHIWARI"

create_issue \
  "[Wave1-3][UI] screens/messages.py（S06）" \
  $'タスクバックログ.md T-F10 より。メッセージ画面を実装する。\n\n対応: SP-35〜SP-43\n依存: T-B16, T-B17\n受入基準: 自分の申込／届いた申込タブ、キャンセル、スタンプ、既読化が動く\n触るファイル: app/frontend/screens/messages.py\n\n担当: @akapuu14-bit' \
  "area:ui,type:feature,wave:3" "$M_HACHIWARI"

create_issue \
  "[Wave1-3][PDM] screens/notifications.py（S07）" \
  $'タスクバックログ.md T-F11 より。通知一覧画面を実装する。\n\n対応: SP-44〜SP-46\n依存: T-B16\n受入基準: 新しい順・未読太字、開いたら全既読\n触るファイル: app/frontend/screens/notifications.py\n\n担当: @HanaeSakamoto' \
  "area:pdm,type:feature,wave:2" "$M_HACHIWARI"

create_issue \
  "[Wave1-3][UI] screens/employee_search.py（S08）" \
  $'タスクバックログ.md T-F12 より。社員検索画面を実装する。\n\n対応: SP-47〜SP-52\n依存: T-B14\n受入基準: 20件ずつ表示＋もっと見る、非公開項目の扱いがSP-49どおり\n触るファイル: app/frontend/screens/employee_search.py\n\n担当: @akapuu14-bit' \
  "area:ui,type:feature,wave:3" "$M_HACHIWARI"

create_issue \
  "[Wave1-3][UI] screens/employee_profile.py（S09）" \
  $'タスクバックログ.md T-F13 より。社員プロフィール画面を実装する。\n\n対応: SP-53〜SP-57\n依存: T-B04, T-B13\n受入基準: 公開設定の切り替え保存、所属部活カード表示が動く\n触るファイル: app/frontend/screens/employee_profile.py\n\n担当: @akapuu14-bit' \
  "area:ui,type:feature,wave:3" "$M_HACHIWARI"

create_issue \
  "[Wave1-3][UI] screens/club_admin.py（S10）" \
  $'タスクバックログ.md T-F14 より。部活・開催の管理画面を実装する。\n\n対応: SP-58〜SP-62\n依存: T-B06, T-B08, T-B13\n受入基準: 権限に応じた表示出し分け、必須チェック・日時エラーが動く\n触るファイル: app/frontend/screens/club_admin.py\n\n担当: @akapuu14-bit' \
  "area:ui,type:feature,wave:3" "$M_HACHIWARI"

# --- Wave 4：結合・テスト（Milestone: 10/7-12 最終） -------------------------

create_issue \
  "[Wave4] 画面×サービス×DB通し確認・単体テスト添付" \
  $'タスクバックログ.md T-I01 より。各実装者が担当分を通しで確認し、単体テストを添付する。\n\n依存: Wave1〜3の全タスク\n受入基準: テスト設計.mdのU-xxが各担当のタスクに添付される\n\n担当: @akapuu14-bit, @Hiroki0023, @HanaeSakamoto' \
  "type:feature,prio:high,wave:4" "$M_SAISHU"

create_issue \
  "[Wave4] 結合テスト実行（I-001〜I-120）" \
  $'タスクバックログ.md T-I02 より。kurosuが結合テストを実行する。\n\n依存: T-I01\n受入基準: テスト結果.mdに合否と実行ログが記録される\n\n担当: 未定（kurosu実行、確認・クローズ担当はPMが実行時に決定）' \
  "type:feature,prio:high,wave:4" "$M_SAISHU"

create_issue \
  "[Wave4] システムテスト実行（S-01〜S-60）" \
  $'タスクバックログ.md T-I03 より。kurosuがシステムテストを実行する。\n\n依存: T-I02\n受入基準: テスト結果.mdに合否と実行ログが記録される\n\n担当: 未定（kurosu実行、確認・クローズ担当はPMが実行時に決定）' \
  "type:feature,prio:high,wave:4" "$M_SAISHU"

echo ""
echo "完了。GitHub Projects（board）への紐付けは docs/github-管理セットアップ.md の手順に従ってください。"
