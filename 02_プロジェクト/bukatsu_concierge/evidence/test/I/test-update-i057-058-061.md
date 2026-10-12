# I-057／I-058／I-061 のテスト期待値を現行の仕様.md に追従させた理由メモ

実施: 2026-10-11 Kurosu（PM指示、god依頼）。対象は次の3テストのみ。実装コード・仕様.md は変更していない。

## 背景

仕様.md の SP-42／SP-45 は、はなえPM裁定（2026-10-11）で実装に合わせて改訂済み（d8cf26d）。しかし #140（feature/test-sxx-lc-w3）の L-C テストは旧文言・旧仕様のままで、統合後の `pytest tests` で3件が落ちていた（`pytest-merge137-140-*.log`）。テストの期待値を現行の仕様.md に合わせた。

## 旧期待 → 新期待

| テスト | 旧期待（改訂前の仕様） | 新期待（現行の仕様.md） | 根拠 |
|---|---|---|---|
| tests/test_lc_messages_complete.py `test_I057_wording_per_spec`（E003 でメッセージ画面） | info に『まだ申込はありません。『部活を探す』から気になる部活を見つけてみてください』 | info に『まだ申込はありません。部活を探して、気になる開催に申し込んでみましょう。』 | 仕様.md SP-42「自分の申込が0件のとき『まだ申込はありません。部活を探して、気になる開催に申し込んでみましょう。』…と表示する」 |
| 同 `test_I058_wording_per_spec`（E002 でメッセージ画面） | info に『まだ届いた申込はありません』 | info に『まだ申込は届いていません。』 | 仕様.md SP-42「届いた申込が0件のとき『まだ申込は届いていません。』と表示する」 |
| tests/test_lc_detail_notifications.py `test_I061_cancel_notice_view_goes_to_club_detail`（種類「中止」の通知） | 「見る」ボタンが `["見る"]`（1つ出る） | 「見る」ボタンが `[]`（出ない） | 仕様.md SP-45「ただし種類『中止』の通知は『見る』の対象外とする（MVPの範囲を絞るため）」 |

- 期待の文言・値は仕様.md の本文から取った。仕様.md に書かれていない期待は足していない（3件とも仕様に明記があるため、決められずに残したテストは無い）。
- 参照: feature/test-sxx-phase2-w3 に同じ3件の改訂後の期待がある（読むだけ。cherry-pick／merge はしていない）。docstring には改訂の根拠（はなえPM裁定2026-10-11）を残した。

## 検証

- `pytest tests`（tests/frontend を含む同一プロセス）: Asia/Tokyo も UTC も **217 passed**（失敗0）。ログ: `pytest-fix-i057-058-061-Asia-Tokyo.log`、`pytest-fix-i057-058-061-UTC.log`。
- 修正前（統合直後）は 3 failed, 214 passed（`pytest-merge137-140-*.log`）。

## 未確認

- 画面の文言が実装（screens/messages.py の `MESSAGE_EMPTY_MINE`／`MESSAGE_EMPTY_RECEIVED`、screens/notifications.py の `_VIEW_TARGETS`）と仕様.md で一致していることは、上記のテストの合格で確認した範囲まで（実機の目視は未実施）。
- 実DBを使うテスト（L-B／α-R）は対象外。
