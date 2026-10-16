# D-07 鮮度テスト2件の失敗：原因の切り分け（調査のみ・修正なし）

- 調査日時: 2026-10-16 23:18 JST（作業機の時計） / 調査者: terao-tech0
- 対象: main `03c0ce0`（PR #193 マージ。mirin の再現コミットと同じ）。worktree はこのコミットから作成。
- 方法: ローカルで pytest 実行。偽 repo のみで、Supabase・本番DBには接続していない。コード・テストは変更していない。

## 結論

**原因は実装の不具合ではなく、テストの日付の固定が実時計に追い抜かれたことに見える。** 2026-10-16 19:00 JST を過ぎてから落ち始める時限式の失敗で、メッセージ画面が実時計を見ているのに、テストの時計だけが 2026-10-14 に固定されている。

## (1) 再現するか — 再現した

`python3 -m pytest tests/test_perf_t4b_d07_freshness.py -q` → **2 failed, 10 passed**。

| テスト | 失敗位置 |
| --- | --- |
| `I217_ApplyIsReflectedImmediately::test_I217_after_apply_all_related_views_are_fresh` | `tests/test_perf_t4b_d07_freshness.py:113` |
| `S65_Flow::test_S65_home_notifications_home_search_apply_result` | 同 `:186` |

どちらも `AssertionError: False is not true`。申込直後の「自分の申込」画面に、キャンセル開始ボタン `messages_cancel_open_<申込ID>` が出ているはず、という検査（`mine.button` にそのキーが無い）。その手前の検査（部活詳細の「✅ 申込済み」、参加人数、`application_complete` への遷移）は通っている。

## (2) いつから落ちているか

- 画面 `app/frontend/screens/messages.py` の最終変更は `bb90feb`（2026-10-15 22:44）。テスト `test_perf_t4b_d07_freshness.py` の追加は `c43bd78`（2026-10-15）。**2026-10-15 の時点では両方とも合格していた**（T3 までの全体 pytest は合格を確認済み）。
- 画面もテストも変わっていないのに落ちるため、原因コミットは無く、**時間の経過で落ち始めた**ように見える。落ち始めの時刻は計算上 **2026-10-16 19:00 JST**（下記）。

## (3) 失敗の中身

- ボタンが出る条件は `messages.py:74-75`:
  `_can_cancel = status == "申込済み" and _start_datetime(events) > datetime.now(_JST)`
  つまり「開催の開始が、今より未来」のときだけキャンセルできる。
- テストの偽の世界 `tests/fakes.py:85` は `w.now = 2026-10-14 12:00 JST` に固定。両テストは `add_event(1, day_offset=2)` で開催を作るため、開催は **2026-10-16 19:00 JST 開始**（`start="19:00:00"` が既定）。
- 時計の固定は `tests/fakes.py:380-385` で `application_service` / `search_service` / `club_admin_service` の `datetime` だけを差し替える。**`screens/messages.py` の `datetime` は差し替え対象に入っていない**ため、画面は実時計（今日は 2026-10-16 23:18 JST）を見る。
- 結果: 期待は「開始 10/16 19:00 ＞ 今」（偽の時計の 10/14 12:00 なら真）だが、実測は「10/16 19:00 ＞ 10/16 23:18」で偽 → ボタンが出ない。
- D-07 の鮮度ロジック（`cache_service`）の不具合ではない。画面の他の部分（申込済み表示・参加人数）は同じテストの中で期待どおりに更新されている。

## 裏づけ（時計を合わせると通る）

リポジトリは変更せず、pytest プラグイン（`$TMPDIR` 内の一時ファイル）で `screens.messages.datetime` を 2026-10-14 12:00 JST に固定して同じファイルを実行 → **12 passed**。時計の食い違い以外に原因が無いことを示す。

## (4) 見立てと修正方針の候補

見立て: 原因はテスト側の時計の取りこぼし。`fakes.py` が画面の `datetime` を固定していない。T2-4 で `messages.py` を一括取得にした時点では、実時計がまだ 10/16 19:00 の前だったため表に出なかったように思える。

修正方針の候補（修正はまだしていない）:

- **A（推奨）: `tests/fakes.py` の時計固定に `screens.messages` も加える。** 画面の `datetime` も `frozen` に差し替える（`screens.club_admin.py:63` も `datetime.now` を使うため同様に加えると、同種の時限式の失敗を防げる）。実装コードは触らず、全テストが偽の時計で一貫する。変更は `fakes.py` の数行。
- B: テストの `day_offset` を大きくする。いま落ちる2件は直るが、期日が先に延びるだけで同じ失敗が将来また起きる。対症療法。
- C: 画面側に現在時刻を注入できるようにする（コード側の変更）。画面の構造に手を入れるため、今回の目的には大きい。

補足: 今後 `day_offset` が小さい他の画面テスト（`test_lc_detail_notifications.py` など）も、画面が実時計を見ている箇所があれば同じ理由で順に落ちうる。A で画面の `datetime` をまとめて固定するのが再発防止になる。

## 未確認

- 全体 pytest（394 passed / 2 failed / 43 skipped）は、今回は再実行していない。mirin の報告値を前提にしている。
- PR #194/#195 のマージ後の main では未確認（今回は `03c0ce0` のみ）。

## 追記：案A適用後の結果（2026-10-16）

- 変更: `tests/fakes.py` の時計固定に `screens.messages` と `screens.club_admin` の `datetime` を追加（3行＋コメント）。実装コードは未変更。
- `tests/test_perf_t4b_d07_freshness.py`: **12 passed**（修正前は 2 failed / 10 passed）。
- 全体 `python3 -m pytest tests`（03c0ce0 土台）: **355 passed / 43 skipped / failed 0**、28 subtests passed。
- 補足: mirin の報告値（394 passed）と passed の数が異なるのは、土台のコミットの違い（mirin はより新しい main と思われる）によるものに見える。未照合。
