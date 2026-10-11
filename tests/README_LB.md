# L-B ハーネス（実repo＋実DB）実走手順

対象: テスト結果.md 3章で「未実行(権限)」の I-xx 17件のうち、読取専用で確認できる15件
（I-008, I-022〜026, I-064〜068, I-140, I-178〜180）。I-090/I-091 は書込が必要なため skip 固定（下記）。

## 実行コマンド（god が実DBで回す）

```
python3 -m pytest tests/test_lb_*.py -v -rs
```

- 実DB（共有Supabase `*.supabase.co`）への接続が要る。Bash tool の `allowed_domains=["*.supabase.co"]` と運営の承認が必要。
- 秘匿値は リポジトリ直下 `.streamlit/secrets.toml`（`supabase_url` / `supabase_key`）。worktree で回すときは本体直下も自動で探す。別の場所は `LB_SECRETS=<path>`。
- **L-A/L-C（偽repo）とは別プロセスで回す**。`pytest tests` のように同じプロセスで混ぜると、L-B は「偽の db.client が入っている」で自動 skip になる。
- 接続できない・secrets が無い・キーが足りないときは、失敗にせず自動 skip（`-rs` で理由が出る）。強制 skip は `LB_SKIP=1`。
- 書込は一切しない（select のみ）。`scripts/reset_data.py` は使わない。

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
| test_lb_constraints.py | test_I090 / test_I091 | I-090 / I-091 | 重複登録できない | **skip固定（書込が必要）** |

## 合否の読み方（god が結果を書くとき）

- passed → その I-xx は「実DB（実repo）で合格」。備考に「実DB読取専用・時刻固定」と書く。
- skipped（データ不足）→ 合否は付けず「未実行」のまま、skip理由を備考に書く（例: 無効部活が実DBに無い）。合格にしない。
- failed → 不合格。差分（期待/実測）を 7.2 に書く。
- I-178/I-179/I-180 は、実DBから探した「その部活で最も古い申込が1日だけの人」を使い、`has_past_non_canceled` と `_is_first_time`（読取のみ）を確認する。
  所属者でない候補が見つからない場合は、`has_past_non_canceled` のみの確認になり、I-178 は skip（初参加まで確認できないため）。
  「別の開催に申込む」の保存（insert）は行っていない。

## I-090 / I-091 を実行するには（運営承認が必要）

重複 insert が拒否されるのを見るには、実DBに同じ組を書く必要がある。一意制約が無かった場合は重複行が残る。
書込の可否・対象テーブル・後始末（削除）の方法を運営に承認してもらってから、別手順で行う。
参考として、既存データに重複が無いことの読取確認（`test_reference_no_duplicate_rows_in_existing_data`）は置いてあるが、制約の証明ではないので合否には使わない。

## ハーネス自体の確認（実DB不要）

- `python3 tests/lb_dryrun.py` … 合成データ＋メモリ内clientで 18件を回す（ハーネスの書き間違い検出用。実DBの合否ではない）。
- `python3 tests/lb_dryrun.py utc-date|ignore-public|week-end-today|or-as-and` … 意図的な不具合を入れ、該当テストが落ちることを確認する。
- 証拠: `02_プロジェクト/bukatsu_concierge/evidence/test/I/lb-offline-verify.log`
