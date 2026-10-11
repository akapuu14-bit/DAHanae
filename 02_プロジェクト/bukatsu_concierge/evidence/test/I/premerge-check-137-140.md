# #137／#140 の仮マージ確認（実測）

実施: 2026-10-11 Kurosu。使い捨て worktree（`--detach origin/main`）で `git merge --no-commit --no-ff` → `pytest tests` → `git merge --abort`。コミット・push・PRコメントなし。実装・テストコードの変更なし。
参照した refs は同日に `git fetch` 済み（実行時点の値）: origin/main=07176e8、origin/feature/la-integration-w3=6ee0817、origin/feature/test-sxx-lc-w3(#140)=d8cf26d。秘匿値なし（実DB・secrets 未使用）。

## (a) origin/main に #137 だけをマージして `pytest tests`（tests/frontend を含む同一プロセス）

| 条件 | 件数・結果 |
|---|---|
| origin/main だけ（比較の基準） | 32 passed |
| main ＋ #137 の 0ea838d の親（0b85b5a。ダミー streamlit のまま） | **27 failed, 158 passed**（計185） |
| main ＋ #137 の 6ee0817（0ea838d＝実物streamlit を含む） | **185 passed** |

0b85b5a（修正前）で落ちた27件の内訳: tests/frontend の AppTest 系（test_club_detail 8件・test_club_detail_sections 4件・test_employee_search 3件・test_home 5件・test_login 1件）と、L-A の tests/test_notification_action_auth.py の I-010/011/012 の3件（`StreamlitSecretNotFoundError: No secrets found`）。原因の確認範囲: ログの失敗メッセージの確認まで（ダミー streamlit が sys.modules に残り、同一プロセスの AppTest／secrets 参照に影響したと見られるが、機序の切り分けまではしていない）。
失敗の原文（抜粋）:
- `FAILED tests/frontend/test_home.py::test_greeting_and_two_entry_buttons - IndexError: list index out of range`
- `FAILED tests/frontend/test_club_detail.py::test_view_is_recorded_when_opened - AssertionError: assert [] == [('E001', 1)]`
- `FAILED tests/test_notification_action_auth.py::AuthTests::test_I010_login_ok_returns_employee - streamlit.errors.StreamlitSecretNotFoundError: No secrets found.`

→ はなえ懸念（#137だけ先に main に入ると tests/frontend と同一プロセスの pytest tests が壊れる）は、0ea838d で解消されていることを実測で確認した。

## (b) #137（6ee0817）と #140（d8cf26d）の仮マージ（`git merge-tree --write-tree`。作業ツリーに書かない）

衝突は **1ファイル・6 hunk** のみ: `02_プロジェクト/bukatsu_concierge/テスト結果.md`（content conflict）。
- hunk 1: I-001〜I-016（両側16行）／hunk 2: I-021〜I-076（56行）／hunk 3: I-090〜I-091／hunk 4: I-136〜I-140／hunk 5: I-176〜I-180／hunk 6: 7.3 集計表（#137側 `I（204件）` 空欄、#140側 `S（62件）` `62|0|0|1|61`・`I（195件）` `195|146|4|0|45`）。
- どちらも同じ行を別の記録（#137=L-A の合否・一部合格、#140=L-C／L-B の合否）で書き換えているため。解決は手作業（行ごとに両方の層の結果を統合）が必要。
- `tests/fakes.py` は **自動マージ成功（衝突なし）**。streamlit 部分は両者同一内容。

マージ後のツリー（app と tests のみ。#137＋#140）で `pytest tests`: **3 failed, 214 passed**。
- 失敗3件: `test_lc_detail_notifications::test_I061_cancel_notice_view_goes_to_club_detail`、`test_lc_messages_complete::test_I057_wording_per_spec`、`::test_I058_wording_per_spec`（原文: `AssertionError: Lists differ: [] != ['見る']` ほか）。
- **#140 単独（origin/feature/test-sxx-lc-w3）でも同じ3件が失敗**（3 failed, 204 passed）で、仮マージが原因ではない。仕様.md は SP-42／SP-45 を実装に合わせて改訂済み（d8cf26d）だが、#140 のテストは旧文言のまま。改訂後の文言に合わせた期待は feature/test-sxx-phase2-w3（4b62c79 の前後のコミット）側にある（本確認では取り込んでいない）。

## 未確認・未実行
- 衝突の実際の解決（マージコミット）と、解決後の `テスト結果.md` の集計は未実施。
- #137 と #140 と feature/test-sxx-phase2-w3 を全部入れた状態での `pytest tests` は未実行。
- tests/frontend の失敗27件のうち、機序の切り分け（どの変更が効いたか）は未確認。
- 実DBを使うテスト（L-B／α-R）は対象外（DB不要の範囲のみ）。
