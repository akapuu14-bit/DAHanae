# #45 基本対策の点検報告（実装変更なし）

- 点検日: 2026-10-16 / 点検者: terao-tech0
- 対象: origin/main `787d51e` の作業ツリーと、git 全履歴（`git rev-list --all` で 418 コミット）。ローカルの `git fetch` はネットワーク不可で失敗したため、origin/main はローカルに取得済みの時点のもの。
- 前提: PM 決定（2026-10-16）に従い、Auth＋RLS の実装は保留。デモ版（ダミーデータ・共通パスワード運用）を維持したうえで、基本対策が守られているかだけを点検した。
- 方法: 読み取り専用。`git grep` / `git log -G` で検索し、秘密の値は出力・記録していない。Supabase への接続、SQL 実行、コード・設定の変更はしていない。
- 参考にした設計案 `evidence/security/45-auth-rls-design.md`（PR #191）は、この時点の origin/main に未取り込みのため参照できていない。

## 結論（要対応の有無）

**要対応: 1 件（軽微）／未確認: 2 件（人が画面で確認）／その他は OK。**
本物の鍵・トークン・接続文字列は、作業ツリーにも履歴にも見つからなかった（god への即報告に該当する事象なし）。

| # | 項目 | 結果 |
| --- | --- | --- |
| 1 | リポジトリ・履歴に秘密が残っていないか | OK |
| 2 | .gitignore と secrets.toml.example | **要対応（軽微）** |
| 3 | アプリ内の鍵の参照・露出 | OK |
| 4 | 鍵の種類（anon / service_role） | 未確認（値を見ないため、人が確認） |
| 5 | GitHub Actions の secrets のログ出力 | OK |
| 6 | 共通パスワードの扱い | OK（注記あり） |
| 7 | ダミー以外の個人情報が入りうる箇所 | OK（運用上の注意あり） |
| 8 | Streamlit Cloud の閲覧制限 | 未確認（人が確認。手順は末尾） |

## 1. リポジトリ・履歴に秘密が残っていないか — OK

型ごとに「見つかった／無い」だけを記す。値は出力していない。

| 型 | 作業ツリー | 全履歴 | 検索 |
| --- | --- | --- | --- |
| Supabase の JWT 形式のキー（`eyJ…`.`…`） | 無い | 無い | `git grep -E` / `git log --all -G` |
| Supabase の新形式キー（`sb_secret_` / `sb_publishable_`） | 無い | 無い | 同上 |
| OpenAI 型・GitHub トークン・Slack トークン・AWS アクセスキー | 無い | 無い | 同上 |
| DB 接続文字列（`postgres://user:pass@…`） | 無い | 無い | 同上 |
| `password` / `secret` / `api_key` / `service_role` への文字列代入 | 無い | 無い | 同上（引用符つき代入の形） |
| `.env` / `secrets.toml` が追跡された履歴 | — | 無い（追跡されたのは `.streamlit/secrets.toml.example` のみ） | `git log --all --name-only` |
| 鍵ファイル（`.pem` `.key` `.p12` `id_rsa`） | 無い | 未検索 | `git ls-files` |

- 補足: 検索は上記の型に限る。型に当てはまらない独自形式の文字列までは網羅できない。
- 補足: テスト用の固定値 `"test-common-password"` が `tests/fakes.py:28` にある。偽物の値で、実運用の共通パスワードではない。

## 2. .gitignore と secrets.toml.example — 要対応（軽微）

- OK: `.gitignore` に `.env`（1行目）、`.env.local`（2行目）、`.env.*.local`（3行目）、`.streamlit/secrets.toml`（14行目）がある。`git check-ignore -v` で `.streamlit/secrets.toml` と `.env` が無視対象になることを確認した。
- OK: `.streamlit/secrets.toml.example` の `supabase_key`（2行目）と `common_password`（3行目）は値が空。
- **要対応（軽微）**: `.streamlit/secrets.toml.example` の `supabase_url`（1行目）に、`https://<20文字の英数字>.supabase.co` 形の値が入っている。`xxxx`・`your`・`<>` などのプレースホルダの印は無く、実在するプロジェクトの URL のように見える（値は書かない）。
  - URL だけでは接続できない（anon キーが別に必要）ため、重大度は低い。ただし同じ値がこのファイルにだけあり、履歴では 3 コミットに入っている。
  - 運営資料 `docs/supabase-setup-guide.html` の「雛形へ anon key や Common password の実値を記載しない」の趣旨とも合わない。
  - 対応案: 次の変更で `supabase_url = "https://<project-ref>.supabase.co"` のような明らかなプレースホルダに置き換える。履歴に残る分は、URL が秘密ではないため書き換え不要と見立てるが、判断は god／運営にお願いしたい。

## 3. アプリ内の鍵の参照・露出 — OK

- 参照箇所は次の3つだけ。
  - `app/frontend/db/client.py:15-18` が `st.secrets["supabase_url"]` と `st.secrets["supabase_key"]` で `create_client` する。
  - `app/frontend/services/auth_service.py:27` が `st.secrets["common_password"]` を読む。
  - `scripts/reset_data.py:1761` は、接続先のホスト名を出すために `supabase_url` を読む（鍵は読まない）。
- 画面・ログ・エラー表示: `app/frontend` に `print(` / `logging` / `traceback` / `st.exception` は無い。`except … as error` の 5 箇所（`app.py:30`、`club_admin.py:163,231,247`、`club_detail.py:191`）は、定型文言か業務エラーの文言を出すだけで、例外の中身や `st.secrets` は出さない（`club_admin.py:163` の `_validation_text` は検証エラーの文言）。
- `scripts/reset_data.py` の `get_db_host` は「接続先のホスト名（キーは表示しない）」と書かれ、ホスト名だけを表示する。
- session_state: 鍵・パスワードを入れる箇所は無い（`app/frontend/state.py:65` はキーごとの既定値の設定のみ）。

## 4. 鍵の種類（anon / service_role） — 未確認

- コード上は、鍵が `st.secrets["supabase_key"]` の 1 本のみで、`service_role` という語は `app/` にも `scripts/` にも出てこない（検索で 0 件）。コードからは鍵の種類を区別できず、種類は値（JWT の role）を見ないと確定しない。値は見ない方針のため、**確定できていない**。
- 文書上の方針は明確: `docs/supabase-setup-guide.html` が anon key を「使用する」、service_role / secret キーを「使用・共有しないもの」と明記し、確認項目に「service_role / secret キーを使用していない」がある（275 行付近）。`docs/be-cheatsheet.html` も anon key 前提。
- クライアント側への露出: サーバー側（Streamlit Cloud）で `st.secrets` を読む構成で、ブラウザに鍵を配る仕組み（画面への出力）はコードに無い。
- 人が確認する手順: Streamlit Cloud の Secrets 画面（項目8）で `supabase_key` を開き、Supabase の Project Settings → API Keys で「anon / publishable」の表示と一致するか、`service_role` / `secret` ではないことを目で確認する。値を他人に見せない。

## 5. GitHub Actions — OK

- workflow は `.github/workflows/dashboard.yml` の 1 本のみ。使う secrets は `secrets.GITHUB_TOKEN`（38 行目、自動発行）だけで、Supabase の鍵や共通パスワードは workflow に出てこない。
- `permissions` は `contents: read` / `pages: write` / `id-token: write` と最小限（15-18 行目）。`set -x` や `echo` による secrets の出力は無い。
- `scripts/gen_dashboard.py` はトークンを `Authorization` ヘッダに使うだけで出力しない。API エラー時は `print(...)`（60 行目）にステータスと URL と応答本文を出すが、トークンは含まれない。
- 補足: トリガーに `pull_request` があり、fork からの PR では `GITHUB_TOKEN` が読み取り専用になるのが GitHub の既定動作。この点は確認していない。

## 6. 共通パスワードの扱い — OK（注記あり）

- 保存場所: Streamlit Secrets の `common_password` のみ（`auth_service.py:3,27`）。コード・リポジトリには無い（項目1）。
- 比較方法: `hmac.compare_digest`（`auth_service.py:28-30`）による定数時間比較。社員 ID 不在とパスワード誤りを区別せず `AuthenticationError` 1 種を返す（SP-11、同 5 行目・31-32 行目）。
- ログ出力: パスワードを出力する箇所は無い（項目3）。
- 注記: 共通パスワード 1 本の運用は、PM 決定どおりデモ版の範囲。試行回数の制限は見当たらない（Auth 実装の保留範囲の話）。

## 7. ダミー以外の個人情報が入りうる箇所 — OK（運用上の注意あり）

`supabase/migrations/202609280001_create_initial_schema.sql` で確認した、自由に文字を書ける／個人に結びつく列。

| テーブル | 列 | 内容 |
| --- | --- | --- |
| `employees` | `name` `dept` `location` `joined_year` `available_slots` | 氏名・所属・勤務地・入社年。ID は `E[0-9]{3}` 形式に制約 |
| `messages` | `body` | 参加者間の自由記述メッセージ |
| `notifications` | `body` | 通知の本文（自由記述） |
| `action_logs` | `employee_id` `action` `club_id` `conditions`(jsonb) | 誰がいつ何を見た／申し込んだかの行動記録。`conditions` は検索条件の JSON |
| `clubs` ほか | 名称・説明・集合場所などの自由記述 | 実名や連絡先が書かれうる |

- どれも列構成は架空データ前提で、実名・メール・電話番号を入れる専用の列は無い。ただし `messages.body` / `notifications.body` / 部活の説明は自由記述で、利用者が実在の個人情報を書けてしまう。これはアプリの制約では防げない。
- 運用上の注意案: デモ参加者への周知（実名・連絡先・社外秘は書かない）。RLS 無効・共有 anon キーの限定環境である点は、既存の設計文書（`bukatsu_concierge/設計.md` 209 行付近）の記述と一致する。
- `reset_data.py` は DB を入れ直す運用スクリプトで、今回は実行していない。

## 8. Streamlit Cloud の閲覧制限 — 未確認（人が確認。AI は確認しない）

アプリを招待制（Viewer 制限）にできるかは、Streamlit Community Cloud の画面で人が確認する。手順は次のとおり（画面の文言は変更されうるため、見つからない場合はその旨を記録する）。

1. https://share.streamlit.io にサインインし、アプリの一覧を開く。
2. 対象アプリの右側の「⋮」メニュー → **Settings** を開く。
3. 左のメニュー **Sharing** を開く（画面名は版により異なる）。
4. 公開設定が **Public**（誰でも閲覧可）か、**Only specific people can view this app**（招待制）かを見る。後者にして、閲覧を許すメールアドレスを登録できるかを確認する。
5. 確認した内容（現在の設定、招待制に切り替えられるか、切り替えに必要な条件）を、日付とともに記録する。設定は変えず、まず現状だけ見る（切り替えるかは運営判断）。
6. 同じ画面群の **Secrets** で、項目4の鍵の種類も目で確認する。

## 要対応の一覧

| 優先 | 内容 | 担当案 |
| --- | --- | --- |
| 低 | `.streamlit/secrets.toml.example` 1 行目の実在らしい URL をプレースホルダにする | 次の小変更（承認後） |
| 確認 | 項目4・8（鍵の種類、閲覧制限）を人が画面で確認 | 運営／人間 |
| 周知 | 自由記述欄に実名・連絡先を書かないよう参加者へ周知 | 運営 |
