# L-B ハーネス（実repo＋実DB）実走手順

対象: テスト結果.md 3章で「未実行(権限)」の I-xx 17件のうち、読取専用で確認できる15件
（I-008, I-022〜026, I-064〜068, I-140, I-178〜180）。I-026（有効データ分）は読取。I-026（センチネル）・I-090/I-091 は書込が必要なため `test_lb_writes.py`（LB_WRITE=1・下記）。

## 実行コマンド（god が実DBで回す）

```
python3 -m pytest tests/test_lb_*.py -v -rs
```

- 実DB（共有Supabase `*.supabase.co`）への接続が要る。Bash tool の `allowed_domains=["*.supabase.co"]` と運営の承認が必要。
- 秘匿値は リポジトリ直下 `.streamlit/secrets.toml`（`supabase_url` / `supabase_key`）。worktree で回すときは本体直下も自動で探す。別の場所は `LB_SECRETS=<path>`。
- **L-A/L-C（偽repo）とは別プロセスで回す**。`pytest tests` のように同じプロセスで混ぜると、L-B は「偽の db.client が入っている」で自動 skip になる。
- 接続できない・secrets が無い・キーが足りないときは、失敗にせず自動 skip（`-rs` で理由が出る）。強制 skip は `LB_SKIP=1`。
- この実行コマンドでは書込は一切しない（select のみ。`test_lb_writes.py` は LB_WRITE=1 が無いので skip）。`scripts/reset_data.py` は使わない。

## テストとI-xxの対応

| ファイル | テスト | I-xx | 期待結果 | 期待値の作り方 |
| --- | --- | --- | --- | --- |
| test_lb_clubs_search.py | test_I022 | I-022 | カテゴリ×拠点はAND | 生の clubs/activities から組み立て |
| 〃 | test_I023 | I-023 | 拠点2つはOR（和集合） | 同上 |
| 〃 | test_I024 | I-024 | 未選択は全件（is_active=trueのみ） | 同上（`{}`・空・None の3通り） |
| 〃 | test_I025 | I-025 | 部活名/活動名/ひとことの一部で部分一致 | 同上（実データから3文字を切り出す） |
| 〃 | test_I026 | I-026 | is_active=false は出ない | 実DBに無効部活が無ければ skip |
| test_lb_employees_search.py | test_I064 | I-064 | 名前・部署・拠点・興味・所属・時間の組合せ（項目間AND・項目内OR） | 生の employees/employee_interests/club_members から組み立て。count()も照合 |
| 〃 | test_I065 | I-065 | 半角スペースを無視して部分一致 | スペース無し入力と同じ集合 |
| 〃 | test_I140 | I-140 | 全角スペースも無視 | 同上 |
| 〃 | test_I066 | I-066 | interests_public=false は興味条件の検索に出ない | 実データの非公開社員 |
| 〃 | test_I067 | I-067 | slots_public=false は時間条件の検索に出ない | 同上 |
| 〃 | test_I068 | I-068 | interests_public=true は出る（対照） | 同上 |
| test_lb_dates_jst.py | test_I008 | I-008 | 日曜23:59は日曜のみ／月曜0:00で次の週（今日〜今週日曜、両端含む） | 時刻を固定し、生の events/clubs から範囲を計算 |
| 〃 | test_I178 | I-178 | 今日の開催だけ → 過去に含まれない → 初参加 | 実データの申込から候補を探し、時刻を固定 |
| 〃 | test_I179 | I-179 | 昨日の開催 → 過去 → 初参加でない | 同上 |
| 〃 | test_I180 | I-180 | JST 0:00〜9:00・TZ=UTC/JST/LA でも I-178/179 と同じ | 時刻とTZを変えて繰り返す |
| test_lb_writes.py | test_I026 / test_I090 / test_I091 | I-026 / I-090 / I-091 | 非公開は出ない／重複登録は拒否される | **LB_WRITE=1 のときだけ**（下の「書込テスト」）|

## 合否の読み方（god が結果を書くとき）

- passed → その I-xx は「実DB（実repo）で合格」。備考に「実DB読取専用・時刻固定」と書く。
- skipped（データ不足）→ 合否は付けず「未実行」のまま、skip理由を備考に書く（例: 無効部活が実DBに無い）。合格にしない。
- failed → 不合格。差分（期待/実測）を 7.2 に書く。
- I-178/I-179/I-180 は、実DBから探した「その部活で最も古い申込が1日だけの人」を使い、`has_past_non_canceled` と `_is_first_time`（読取のみ）を確認する。
  所属者でない候補が見つからない場合は、`has_past_non_canceled` のみの確認になり、I-178 は skip（初参加まで確認できないため）。
  「別の開催に申込む」の保存（insert）は行っていない。

## 書込テスト（I-026 / I-090 / I-091）— 運営承認済み・LB_WRITE=1 のときだけ

### 実行コマンド（god が実DBで回す。`allowed_domains=["*.supabase.co"]`）

```
LB_WRITE=1 python3 -m pytest tests/test_lb_writes.py -v -rs
```

- `LB_WRITE=1` が無いと、3件とも「LB_WRITE=1 のときだけ」で skip（普段の `pytest tests/test_lb_*.py` は書かない）。接続不可・secrets無しも skip。
- 1回の実走で書込が起きるのは、センチネル行の insert/delete だけ（下記）。`scripts/reset_data.py` は使わない。

| テスト | I-xx | 投入する行（センチネル） | 検証 | 後始末 |
| --- | --- | --- | --- | --- |
| test_I026_inactive_sentinel_club_is_excluded_from_search | I-026 | 社員 E999、部活1件（name=`LB-TEST-I026-<6桁hex>`・is_active=false） | `clubs_repo.get` で実在確認 →`clubs_repo.search` の条件なし/部活名/拠点/カテゴリ/時間帯/レベルのどれにも出ない | 部活→E999 を削除 |
| test_I090_duplicate_employee_interest_is_rejected | I-090 | E999 の `employee_interests` 1組（E999×最小idの活動・level=初心者） | 同じ組をもう一度 insert → unique_violation(23505)。E999 の行は1のまま・全体は +1 のまま | E999 の行→E999 を削除 |
| test_I091_duplicate_club_member_is_rejected | I-091 | センチネル部活1件＋`club_members` 1組（その部活×E999） | 素の insert を重ねる → 23505。所属は1のまま（参考: `add_member` を重ねても1） | 所属→部活→E999 を削除 |

### 設計メモ（衝突回避・後始末）

- 一意制約は実スキーマ（`supabase/migrations/202609280001_create_initial_schema.sql`）どおり: `employee_interests (employee_id, activity_id)`、`club_members (club_id, employee_id)`。エラーは PostgREST の `code=23505`。
- **センチネルの選び方**: `employees.id` は `^E[0-9]{3}$` のCHECK制約があり "LB-TEST" 形式にできない。seed（E001〜E500）の範囲外の `E999`（name=`LB-TEST-employee`、interests_public/slots_public=false）を使う。部活は名前が `LB-TEST-` で始まるものだけ（`_ % ,` は検索のエスケープ対象なので使わない）。FKの参照先に使う活動IDは**読むだけ**で変更しない。実在ユーザーの行は触らない。
- **E999 が実社員として既にあれば**（name が `LB-TEST-employee` でない）何も書かずに skip。消さない。前回の異常終了の残り（E999＋`LB-TEST-%` 部活・その子行）があれば、最初に消してから始める。
- **後始末**: `addCleanup` で必ず実行（テストが失敗しても）。`purge_sentinels` は **E999 と `LB-TEST-%` 部活のキーだけ**で子→親の順に delete する。一意制約が無かった場合でも、消すのはセンチネル行だけで実データは巻き込まない。
- **件数照合**: テスト前に `employees / clubs / club_members / employee_interests` の件数を控え、後始末後に before==after とセンチネル残り0を assert。他の人が同時に書いていると件数がずれて落ちうる（その場合は再実行して確認）。
- **残る副作用（戻せない）**: `clubs.id` は identity 採番なので、実走のたびに次の id が1つ（I-026・I-091 で計2つ）進む。行は残らないが、あとの新規部活の id に欠番ができる。
- 一過性の見え方: 投入〜削除の間（数百ms）、E999 が社員検索の名前検索に出うる。センチネル部活は is_active=false なので部活検索には出ない。
- 参考として、既存データに重複が無いことの読取確認（`test_lb_constraints.py::test_reference_no_duplicate_rows_in_existing_data`）は残してあるが、制約の証明ではないので I-090/I-091 の合否には使わない。

### 合否の読み方

- passed → 「実DBの一意制約が重複を拒否した（23505）／非公開部活は検索に出なかった」。備考に「実DB書込（センチネル行のみ・削除済み・件数 before==after 確認）」と書く。
- failed（`Exception not raised`）→ 一意制約が効いていない＝不合格。センチネル行は後始末で消えているが、`sentinel_leftovers` の件数が0かをログで確認する。
- skipped → 合否を付けない（理由: LB_WRITE無し／接続不可／E999が実社員）。

## ハーネス自体の確認（実DB不要）

- `python3 tests/lb_dryrun.py` … 合成データ＋メモリ内clientで 18件を回す（ハーネスの書き間違い検出用。実DBの合否ではない）。
- `python3 tests/lb_dryrun.py utc-date|ignore-public|week-end-today|or-as-and` … 意図的な不具合を入れ、該当テストが落ちることを確認する。
- 証拠: `02_プロジェクト/bukatsu_concierge/evidence/test/I/lb-offline-verify.log`
- `LB_WRITE=1 python3 tests/lb_writes_dryrun.py [no-unique|active-leak|real-e999|leftover]` … 書込テストをメモリ内DB（一意制約・FK・identity付き）で回し、投入→検証→後始末→件数照合を確認する。`no-unique`（一意制約なし）と `active-leak`（is_active無視）ではテストが落ちること、どの場合もセンチネルが残らないこと、`real-e999`（E999が実社員）では何も書かずskipすること、`leftover`（前回の残り）を片付けて通ること。実DBの合否ではない。

## 申込・キャンセルの書込テスト（S-19 / S-20 DB分 / S-25 / S-26）— α-W・運営承認済み・LB_WRITE=1 のときだけ

層は α-W（`application_service.apply` / `cancel` を実repo＋実DBで呼ぶ。画面は通さない）。方式は上の I-026/090/091 と同じ（センチネルを投入 → 検証 → 必ず後始末）。

### 実行コマンド（god が実DBで回す。`allowed_domains=["*.supabase.co"]`）

```
LB_WRITE=1 python3 -m pytest tests/test_sxx_appt_aw_apply_cancel.py -v -rs
```

- `LB_WRITE=1` が無い・secrets 無し・接続不可は、4件とも自動 skip。L-A/L-C（偽repo）とは別プロセスで回す（同居すると skip）。
- `scripts/reset_data.py` は使わない。書くのは下のセンチネルの行だけ。

| テスト | S-xx | 検証すること（期待結果の根拠: テスト設計.md S-xx・仕様.md SP-66/SP-67） |
| --- | --- | --- |
| test_S19_apply_writes_application_message_notification_and_log | S-19 | 申込で `applications` 1行（申込済み・初参加・canceled_at空）、一言ありなら `messages` 1行、幹事あて通知1件（種類「申込」・未読）、操作履歴 apply 1件。一言が空/空白/None なら `messages` は増えない |
| test_S25_cancel_updates_status_and_notifies_organizer | S-25 | キャンセルで status=キャンセル・canceled_at が入り、幹事あてに種類「キャンセル」の通知。やり取り（messages）は残る |
| test_S26_reapply_after_cancel_is_a_new_application | S-26 | キャンセル後の再申込は別の application_id。(開催, 申込者) の行は キャンセル1＋申込済み1、有効は1行。やり取りは申込ごとに別 |
| test_S20_db_rejects_second_active_application_for_same_event | S-20（DB分） | service の再申込は `ConflictError(already_applied)`。service を通さず「申込済み」を直接 insert → unique_violation(23505)（部分一意インデックス）。有効な申込は1行のまま |

### 設計メモ（センチネル・後始末）

- 投入する行: 社員 `E998`（幹事役）・`E999`（申込者役）＝どちらも name=`LB-TEST-employee`（`employees.id` の CHECK `^E[0-9]{3}$` のため seed 範囲外の E998/E999）。部活（名前 `LB-TEST-<S番号>-<hex>`・is_active=false・幹事=E998）、その開催（30日後・予定・10:00〜12:00・場所 `LB-TEST-place`）。申込が副作用で書く行（applications・messages・notifications・action_logs）はサービスが作る。
- **副作用の後始末**: 4件とも `addCleanup` で必ず実行。`purge_sentinels` は子→親の順（messages → notifications → action_logs → applications → club_members → employee_interests → events → clubs → employees）で、条件は **E998/E999・`LB-TEST-%` 部活・その部活の開催・その申込の id だけ**。先に全表の条件を作ってから消す。実在の行は、この条件のどれにも紐づかないので巻き込まない。
- **件数照合**: 9表（employees/clubs/club_members/employee_interests/events/applications/messages/notifications/action_logs）の件数を前後で比べ、センチネル残り0を assert。**他の人が同時に操作すると（特に action_logs・notifications）件数がずれて落ちうる。** その場合は再実行し、`センチネル残り` が全表0かをログで確認する。
- E998/E999 のどちらかが実社員として既にあれば（name が `LB-TEST-employee` でない）何も書かず skip。前回の異常終了の残り（センチネルだけ）は開始時に消す。
- **残る副作用（戻せない）**: identity 採番が進む。1回の実走（4件・全て通った場合）の採番の進みは、メモリ内DBでの実測で clubs +4、events +7、applications +8、messages +5、notifications +10、action_logs +8。実DBでは S-20 の拒否された重複 insert でも applications の採番が1つ進む（PostgreSQL の挙動の見立て・未確認）ので applications は +9 前後。行は残らないが欠番ができる。失敗や再実行で増える。
- 一過性の見え方: 投入〜削除の間、E998/E999 が社員検索の名前検索に出うる。部活は is_active=false なので部活検索には出ない。センチネルの開催は非公開部活の下なので、ホーム/検索の開催一覧には出ない。
- スコープ外（足していない）: S-61（中止の通知）、幹事本人の申込、他人のキャンセル・開始後のキャンセル、画面経由の操作。

### オフライン検証（実DB不要）

`LB_WRITE=1 python3 tests/sxx_aw_dryrun.py [no-unique|no-cancel-notice|reapply-blocked|purge-miss|real-e998|leftover]` … メモリ内DB（FK・identity・既定値・「申込済み」の部分一意インデックス付き）に実の application_service をつなぐ。通常=4件通り・DBが元と同一、`no-unique`=S-20が落ちる、`no-cancel-notice`=S-25が落ちる、`reapply-blocked`=S-26が落ちる（いずれも残り0）、`purge-miss`（通知の消し漏らし）=残り検出で全件失敗、`real-e998`=skip、`leftover`=前回の残りを片付けて通る。実DBの合否ではない。証拠: `02_プロジェクト/bukatsu_concierge/evidence/test/S/sxx-aw-offline-verify.log`
