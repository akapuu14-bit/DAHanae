# L-B 実DB結果（17行）を テスト結果.md に反映した記録

実施: 2026-10-11 Kurosu。ブランチ `feature/test-lb-result-w3`（#140＝`feature/test-sxx-lc-w3` の 8828b9f から作成）。実DBへは接続していない・`LB_WRITE=1` は付けていない。根拠は godの実走の原本ログのみ。

## 取り込んだもの
- `feature/test-lb-realdb-w3`（42eb7e9）をマージ: tests/lb_base.py、test_lb_clubs_search／employees_search／dates_jst／constraints、lb_dryrun.py、README_LB.md、`lb-offline-verify.log`、`lb-realrun-result.log`。
- `feature/test-lb-writes-w3`（0ccb8c0）をマージ: test_lb_writes.py、lb_writes_dryrun.py、lb_base.py（書込用の拡張）、test_lb_constraints.py の整理、`lb-writes-offline-verify.log`、`lb-writes-realrun-result.log`。
- 衝突なし（どちらも自動マージ）。

## 反映した17行（原本ログと突き合わせ）

| 行 | 原本ログ | 原本ログの記載 | テスト |
|---|---|---|---|
| I-022 | lb-realrun-result.log | 合格（category AND location） | test_lb_clubs_search.…test_I022_category_and_location_are_anded |
| I-023 | 同 | 合格（locations OR） | …test_I023_locations_are_ored |
| I-024 | 同 | 合格（no condition = all active） | …test_I024_no_condition_returns_all_active |
| I-025 | 同 | 合格（keyword matches name/activity/message） | …test_I025_keyword_matches_name_activity_and_message |
| I-008 | 同 | 合格（week switches at Sunday midnight JST） | test_lb_dates_jst.WeekBoundaryLb.test_I008_… |
| I-178 | 同 | 合格（event today is not past） | …FirstTimeJstLb.test_I178_… |
| I-179 | 同 | 合格（event yesterday is past） | …test_I179_… |
| I-180 | 同 | 合格（JST early morning & server timezone） | …test_I180_… |
| I-064 | 同 | 合格（combined AND/OR + count） | test_lb_employees_search.EmployeesSearchLb.test_I064_… |
| I-065 | 同 | 合格（half-width space ignored） | …test_I065_… |
| I-066 | 同 | 合格（private interests hidden） | …test_I066_… |
| I-067 | 同 | 合格（private slots hidden） | …test_I067_… |
| I-068 | 同 | 合格（public interests shown） | …test_I068_… |
| I-140 | 同 | 合格（full-width space ignored） | …test_I140_… |
| I-026 | lb-writes-realrun-result.log | 合格（非公開センチネル部活が検索結果から除外される）。読取側ログでは「is_active=false の部活が実DBに無い」ため skip だった | test_lb_writes.WritesLb.test_I026_… |
| I-090 | 同 | 合格（employee_interests の重複登録が一意制約 23505 で拒否） | …test_I090_… |
| I-091 | 同 | 合格（club_members の重複登録が一意制約で拒否） | …test_I091_… |

- 読取14行: `15 passed, 3 skipped, 52 subtests passed`。ログの skip 3件（I-026／I-090／I-091）は書込側ログで合格になったため、17行すべて合格（ログの記載と一致。14＋3＝17）。
- 書込3行: `3 passed, 6 subtests passed`（LB_WRITE=1。センチネル E999／LB-TEST-%部活を投入→検証→削除）。後始末の確認（godの別途read確認）: センチネル残 E999=0／部活=0、全体件数 employees=500／clubs=15（before==after）。ログの注記: clubs.id の欠番が進む、投入〜削除の数百ms間に E999 が名前検索に出うる、before==after は他者の同時書込時にずれうる。
- 各行の備考に「読取専用（select のみ・書込0件）」または「書込はセンチネル＋後始末確認済み」、実走日 2026-10-11、前回=「未実行(権限)」を記載。L-A／L-C の結果が既にある行は、この17行には無かった（全て「未実行(権限)」だった）。

## 集計（行から再計算）
- I（204件）: 合格166（旧149＋17）／不合格0／対象外0／未実行38（内訳: 一部合格(合否欄は空欄)24、他層送り(空欄)14）。権限で未実行は 17→0。
- S（62件）: 変更なし（合格0／不合格0／対象外1／未実行61）。S-xx（α-0／α-R／α-W／β）の反映は今回の対象外。

## 統合後の pytest（実DBに触れない）
`LB_WRITE` 未設定で `pytest tests`（tests/frontend 含む）: Asia/Tokyo も UTC も **217 passed, 19 skipped**（失敗0）。skip の内訳: L-B 読取16件＝「偽の db.client（tests/fakes.py）が入っている。L-Bは別プロセスで実行する」、L-B 書込3件＝「LB_WRITE=1 のときだけ実行」。ログ: `pytest-lb-merge-Asia-Tokyo.log`、`pytest-lb-merge-UTC.log`。

## 未確認・注意
- 原本ログは実走時のコミット（a8c2cf1／c01e45b）の結果。ブランチ先頭（42eb7e9／0ccb8c0）はその後のログ追加などを含み、テストコードがそのまま同一かは、この記録では比較していない（実走し直してはいない）。
- 実DBの再実走は行っていない（godの実走を根拠にしている）。
- S-xx の実DB系（α-R／α-W など）は未反映。
