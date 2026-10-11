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
