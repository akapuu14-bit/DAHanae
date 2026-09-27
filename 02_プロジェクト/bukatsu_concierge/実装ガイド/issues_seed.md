# 部活コンシェルジュ Wave0-4 Issue化 下書き

作成：Takahiro（設計担当）　作成日：2026-09-28

## 0. 本書の位置づけ

`タスクバックログ.md`（Wave0〜4、全37タスク。T-B0S「共有Supabaseプロジェクトの作成と接続情報の共有」追加後）を、`scripts/setup_github.sh`が既に作った既存のラベル体系・マイルストーンにそのまま乗る形でGitHub Issue化する下書き。実行スクリプトは`create_issues.sh`に分離し、本書はレビュー用の一覧（タイトル・本文要旨・ラベル・マイルストーン・担当）を示す。

**Wave0-4の37件（本書＋`create_issues.sh`）が正式なタスクIssue。`setup_github.sh`のseed Issue作成は行わない**（`setup_github.sh`はLabel/Milestone作成のみに変更済み前提。kurosu横断レビュー指摘S-2、Issue二重化の裁定に基づく。`setup_github.sh`本体の修正はterao担当）。

### 0.1 既存のラベル・マイルストーン体系（setup_github.sh確認済み）

- Label: `area:be` / `area:ui` / `area:pdm` / `type:feature` / `type:bug` / `prio:high` / `prio:mid` / `prio:low`
- Milestone: `〜9/29 アプリのカタチ` / `〜10/2 8割` / `10/7-12 最終`
- 本書では、上記に加えて新規ラベル `wave:0`〜`wave:4`（タスクバックログのWave区分をIssue上でも追えるようにするため）を`create_issues.sh`側で作成する。色・説明は`create_issues.sh`参照。

### 0.2 マイルストーン対応方針（新規の判断）

タスクバックログのWave区分と、実装計画.md R-48のスケジュール（9/23〜29 アプリのカタチ／9/30〜10/6 8割／10/7〜10/12 最終）を突き合わせ、以下で対応づける：

| Wave | 対応するMilestone |
|---|---|
| Wave 0（DB基盤）／Wave 1（repositories）／Wave 2（services） | `〜9/29 アプリのカタチ` |
| Wave 3（画面の実データ接続・ダミーデータ投入） | `〜10/2 8割` |
| Wave 4（結合・テスト） | `10/7-12 最終` |

画面タスク（T-F01〜T-F14）はUIのモック着手自体はWave0〜1と並行可能だが、実データ接続の完了時期を基準にWave3寄りの`〜10/2 8割`を割り当てる（タスクバックログ.md 5章の推奨着手順に準拠）。

### 0.3 担当（GitHubハンドル）の扱い

担当のGitHubハンドル（はなえ=`HanaeSakamoto` / だーあさ=`Hiroki0023` / あかぷ=`akapuu14-bit`）は各Issueの本文末尾に「担当: @handle」として記載する。**`create_issues.sh`では`--assignee`は指定しない**（実行時にPM/担当者が手動で割り当てる。setup_github.shの既存Seed Issueと同じ運用に合わせた）。AIスタッフ（terao/mirin/takahiro）が支援する領域であることは本文中に注記するのみで、担当（アサイン対象）は人間のGitHubハンドルのみとする。

## 1. Wave 0：DB基盤（Milestone: 〜9/29 アプリのカタチ）

| ID | タイトル | 目的 | 対応SP/N | 依存 | 受入基準 | 触るファイル | ラベル | 担当 |
|---|---|---|---|---|---|---|---|---|
| T-B0S | [Wave0][BE] 共有Supabaseプロジェクトの作成と接続情報の共有 | PM決定：Supabaseはチームで1プロジェクト共有（各自個別ではない）とし、その基盤を最初に整える | 実装計画.md1.1表, N-02 | なし | チーム共有のSupabaseプロジェクトが1つ存在し、接続URL/anon keyがSecrets運用の手順で全員に共有されている（実キーはコミットしない） | Supabaseダッシュボード＋各自の`.streamlit/secrets.toml`（コード変更なし） | area:be, type:feature, wave:0 | @Hiroki0023 |
| T-B00 | [Wave0][BE] Supabaseスキーマ作成（10テーブル） | 設計.md3章の型・制約・インデックス方針どおりに10テーブルを作成する（T-B0Sで作成する共有プロジェクト上に作る） | 仕様.md3章, 設計.md3章, N-02 | T-B0S | 外部キー・一意制約（club_members, employee_interests）が設計.md3章どおり | Supabase側スキーマ定義 | area:be, type:feature, wave:0 | @Hiroki0023（terao支援） |
| T-B01 | [Wave0][BE] db/client.py：Supabaseクライアント初期化 | Secretsから接続情報を読みモジュールレベルで1クライアントを生成する | 設計.md6章, N-02, N-04 | T-B00 | `st.secrets`から接続情報を読める | `app/frontend/db/client.py` | area:be, type:feature, wave:0 | @Hiroki0023（terao支援） |
| T-B02 | [Wave0][PDM] Secrets雛形作成 | supabase_url/supabase_key/common_passwordのキー名をT-B01と一致させた雛形を用意する | N-04 | T-B00 | T-B01とキー名が一致 | `app/frontend/.streamlit/secrets.toml.example` | area:pdm, type:feature, wave:0 | @HanaeSakamoto（takahiro支援） |

## 2. Wave 1：repositories＋共通エラー（Milestone: 〜9/29 アプリのカタチ）

| ID | タイトル | 目的 | 対応SP/F | 依存 | 受入基準 | 触るファイル | ラベル | 担当 |
|---|---|---|---|---|---|---|---|---|
| T-B03 | [Wave1][BE] services/errors.py：共通例外定義 | I-F契約.md0.4の共通例外5種を定義する | I-F契約.md0.4 | なし | 5種すべてimport可能 | `app/frontend/services/errors.py` | area:be, type:feature, wave:1 | @Hiroki0023 |
| T-B04 | [Wave1][BE] repositories/employees_repo.py | I-F契約.md2.1の全関数を実装する | F-35〜F-43 | T-B01 | `get_by_id`が大文字小文字を区別せず引ける | `app/frontend/repositories/employees_repo.py` | area:be, type:feature, wave:1 | @Hiroki0023 |
| T-B05 | [Wave1][BE] repositories/activities_repo.py | I-F契約.md2.2の全関数を実装する | F-13, F-35 | T-B01 | 全関数実装 | `app/frontend/repositories/activities_repo.py` | area:be, type:feature, wave:1 | @Hiroki0023 |
| T-B06 | [Wave1][BE] repositories/clubs_repo.py | I-F契約.md2.3の全関数を実装する | F-17, F-44〜F-45 | T-B01, T-B05 | `search`がSP-20のAND/ORに対応 | `app/frontend/repositories/clubs_repo.py` | area:be, type:feature, wave:1 | @Hiroki0023 |
| T-B07 | [Wave1][BE] repositories/club_members_repo.py | I-F契約.md2.4の全関数を実装する | F-42, F-48 | T-B01 | 全関数実装 | `app/frontend/repositories/club_members_repo.py` | area:be, type:feature, wave:1 | @Hiroki0023 |
| T-B08 | [Wave1][BE] repositories/events_repo.py | I-F契約.md2.5の全関数を実装する | F-18, F-46〜F-47 | T-B01, T-B06 | `list_upcoming_by_club`が過去開催を除外 | `app/frontend/repositories/events_repo.py` | area:be, type:feature, wave:1 | @Hiroki0023 |
| T-B09 | [Wave1][BE] repositories/applications_repo.py | I-F契約.md2.6の全関数を実装する | F-19〜F-20, F-26〜F-29 | T-B01, T-B08 | `exists_active`が「申込済み」状態のみ見る | `app/frontend/repositories/applications_repo.py` | area:be, type:feature, wave:1 | @Hiroki0023（terao支援） |
| T-B10 | [Wave1][BE] repositories/messages_repo.py | I-F契約.md2.7の全関数を実装する | F-25, F-28 | T-B01, T-B09 | 全関数実装 | `app/frontend/repositories/messages_repo.py` | area:be, type:feature, wave:1 | @Hiroki0023（terao支援） |
| T-B11 | [Wave1][BE] repositories/notifications_repo.py | I-F契約.md2.8の全関数を実装する | F-01, F-30, F-32〜F-34 | T-B01 | `count_unread`がread_at IS NULLで数える | `app/frontend/repositories/notifications_repo.py` | area:be, type:feature, wave:1 | @Hiroki0023（terao支援） |
| T-B12 | [Wave1][BE] repositories/action_logs_repo.py | I-F契約.md2.9の全関数を実装する | F-49〜F-50 | T-B01 | `get_last`が指定actionの最新1件を返す | `app/frontend/repositories/action_logs_repo.py` | area:be, type:feature, wave:1 | @Hiroki0023（terao支援） |

## 3. Wave 2：services（Milestone: 〜9/29 アプリのカタチ）

| ID | タイトル | 目的 | 対応SP | 依存 | 受入基準 | 触るファイル | ラベル | 担当 |
|---|---|---|---|---|---|---|---|---|
| T-B13 | [Wave2][BE] services/auth_service.py | I-F契約.md1.1の`login`/`get_role`を実装する | SP-63, SP-11 | T-B03, T-B04 | 大文字小文字を無視した認証ができる | `app/frontend/services/auth_service.py` | area:be, type:feature, wave:2 | @Hiroki0023 |
| T-B14 | [Wave2][BE] services/search_service.py | I-F契約.md1.2の3関数を実装する | SP-64, SP-65, SP-75 | T-B03, T-B04, T-B06, T-B08 | `search_employees`が非公開項目を除外 | `app/frontend/services/search_service.py` | area:be, type:feature, wave:2 | @Hiroki0023 |
| T-B15 | [Wave2][BE] services/action_log_service.py | I-F契約.md1.5の3関数を実装する | SP-76 | T-B03, T-B12 | view_clubの連続同一部活は記録しない | `app/frontend/services/action_log_service.py` | area:be, type:feature, wave:2 | @Hiroki0023（terao支援） |
| T-B16 | [Wave2][BE] services/notification_service.py | I-F契約.md1.4の5関数を実装する | SP-70〜SP-72 | T-B03, T-B11 | 5関数実装 | `app/frontend/services/notification_service.py` | area:be, type:feature, wave:2 | @Hiroki0023（terao支援） |
| T-B17 | [Wave2][BE] services/application_service.py | I-F契約.md1.3の5関数を実装する | SP-66〜SP-68, SP-72 | T-B03, T-B07〜T-B10, T-B15〜T-B16 | 設計.md5.1〜5.4の手順どおりに動く | `app/frontend/services/application_service.py` | area:be, type:feature, prio:high, wave:2 | @Hiroki0023（terao支援） |

## 4. 共通部品／画面（Milestone: 〜10/2 8割）

| ID | タイトル | 目的 | 対応SP/F | 依存 | 受入基準 | 触るファイル | ラベル | 担当 |
|---|---|---|---|---|---|---|---|---|
| T-F01 | [Wave1-3][UI] app.py：ログイン判定＋ルーティング | 設計.md D-01/D-02のルーティングを実装する | SP-63, SP-13 | T-B02 | 未ログイン/ログイン済みで表示画面が切り替わる | `app/frontend/app.py` | area:ui, type:feature, wave:1 | @akapuu14-bit |
| T-F02 | [Wave1-3][UI] state.py：session_stateキー定義 | 設計.md4章のキーを初期化ヘルパーとして用意する | 設計.md4章 | T-F01 | 4章のキーがすべて用意される | `app/frontend/state.py` | area:ui, type:feature, wave:1 | @akapuu14-bit |
| T-F03 | [Wave1-3][UI] components/sidebar.py・club_card.py | サイドバー（未読件数・メニュー出し分け）と部活カードを実装する | SP-01, SP-21, SP-16, SP-55 | T-F02 | 未読件数・メニュー出し分けが表示、カードが3.3の形 | `app/frontend/components/sidebar.py`, `.../club_card.py` | area:ui, type:feature, wave:1 | @akapuu14-bit（mirin支援） |
| T-F04 | [Wave1-3][PDM] components/rule_notice.py・error_banner.py | 運営ルール一文とDB接続エラー文言を固定表示として実装する | SP-04, SP-06 | なし | 固定表示として再利用できる | `app/frontend/components/rule_notice.py`, `.../error_banner.py` | area:pdm, type:feature, wave:1 | @HanaeSakamoto（takahiro支援） |
| T-F05 | [Wave1-3][UI] screens/login.py（S01） | ログイン画面を実装する | SP-09〜SP-12 | T-F01 | SP-09〜12どおりの表示・エラー文言 | `app/frontend/screens/login.py` | area:ui, type:feature, wave:2 | @akapuu14-bit |
| T-F06 | [Wave1-3][UI] screens/home.py（S02） | ホーム画面を実装する | SP-14〜SP-18 | T-F01, T-F03 | 0件時案内文含めSP-14〜18どおり | `app/frontend/screens/home.py` | area:ui, type:feature, wave:2 | @akapuu14-bit |
| T-F07 | [Wave1-3][UI] screens/club_search.py（S03） | 部活検索画面を実装する | SP-19〜SP-23 | T-F03, T-B14 | 検索条件変更で即結果変化・0件文言・操作履歴記録 | `app/frontend/screens/club_search.py` | area:ui, type:feature, wave:3 | @akapuu14-bit |
| T-F08 | [Wave1-3][UI] screens/club_detail.py（S04） | 部活詳細・申込フォームを実装する | SP-24〜SP-32 | T-F03, T-F04, T-B17 | 申込送信でapplication_service.applyが呼ばれS05へ遷移 | `app/frontend/screens/club_detail.py` | area:ui, type:feature, prio:high, wave:3 | @akapuu14-bit |
| T-F09 | [Wave1-3][PDM] screens/application_complete.py（S05） | 申込完了画面を実装する | SP-33〜SP-34 | T-F04 | SP-33の6項目順表示、情報なしでホームへ遷移 | `app/frontend/screens/application_complete.py` | area:pdm, type:feature, wave:2 | @HanaeSakamoto |
| T-F10 | [Wave1-3][UI] screens/messages.py（S06） | メッセージ画面を実装する | SP-35〜SP-43 | T-B16, T-B17 | 2タブ・キャンセル・スタンプ・既読化が動く | `app/frontend/screens/messages.py` | area:ui, type:feature, wave:3 | @akapuu14-bit |
| T-F11 | [Wave1-3][PDM] screens/notifications.py（S07） | 通知一覧画面を実装する | SP-44〜SP-46 | T-B16 | 新しい順・未読太字、開いたら全既読 | `app/frontend/screens/notifications.py` | area:pdm, type:feature, wave:2 | @HanaeSakamoto |
| T-F12 | [Wave1-3][UI] screens/employee_search.py（S08） | 社員検索画面を実装する | SP-47〜SP-52 | T-B14 | 20件ずつ＋もっと見る、非公開項目の扱いがSP-49どおり | `app/frontend/screens/employee_search.py` | area:ui, type:feature, wave:3 | @akapuu14-bit |
| T-F13 | [Wave1-3][UI] screens/employee_profile.py（S09） | 社員プロフィール画面を実装する | SP-53〜SP-57 | T-B04, T-B13 | 公開設定切替保存・所属部活カード表示が動く | `app/frontend/screens/employee_profile.py` | area:ui, type:feature, wave:3 | @akapuu14-bit |
| T-F14 | [Wave1-3][UI] screens/club_admin.py（S10） | 部活・開催管理画面を実装する | SP-58〜SP-62 | T-B06, T-B08, T-B13 | 権限出し分け・必須チェック・日時エラーが動く | `app/frontend/screens/club_admin.py` | area:ui, type:feature, wave:3 | @akapuu14-bit |

## 5. ダミーデータ（Milestone: 〜9/29 アプリのカタチ）

| ID | タイトル | 目的 | 対応SP/N | 依存 | 受入基準 | 触るファイル | ラベル | 担当 |
|---|---|---|---|---|---|---|---|---|
| T-D01 | [Wave0-] scripts/reset_data.py：ダミーデータ生成 | 社員500名・部活15件、seed固定、実在情報不使用でダミーデータを生成・初期化する | SP-78, N-07〜N-09, 仕様.md7章 | T-B00 | 実行で全テーブル空→再投入、同seedで同結果 | `scripts/reset_data.py`（アプリソース外） | area:pdm, type:feature, wave:0 | @HanaeSakamoto |

## 6. Wave 4：結合・テスト（Milestone: 10/7-12 最終）

| ID | タイトル | 目的 | 依存 | 受入基準 | ラベル | 担当 |
|---|---|---|---|---|---|---|
| T-I01 | [Wave4] 画面×サービス×DB通し確認・単体テスト添付 | 各実装者が担当分を通しで確認し単体テストを添付する | Wave1〜3の全タスク | テスト設計.mdのU-xxが各タスクに添付される | type:feature, prio:high, wave:4 | @akapuu14-bit, @Hiroki0023, @HanaeSakamoto |
| T-I02 | [Wave4] 結合テスト実行（I-001〜I-120） | kurosuが結合テストを実行する | T-I01 | テスト結果.mdに合否・実行ログが記録される | type:feature, prio:high, wave:4 | （kurosu実行、担当欄は運営に相談） |
| T-I03 | [Wave4] システムテスト実行（S-01〜S-60） | kurosuがシステムテストを実行する | T-I02 | 同上 | type:feature, prio:high, wave:4 | （kurosu実行、担当欄は運営に相談） |

## 7. 保留

- T-I02・T-I03の担当（GitHub上のassignee）は、kurosu（AIスタッフ）の実行結果を人間の誰が確認・クローズするか未確定。実行時にPMが決めることとし、ここでは推測で割り当てていない。
- 本書・`create_issues.sh`は下書きであり、実際の`gh issue create`実行はgh認証・write(コラボレーター)権限が揃ってから(adminは不要)、PM/担当者が判断して行う（実装計画.mdの承認プロセスに準じ、Issue一括作成そのものについても実行前にひと声かけることを推奨）。
