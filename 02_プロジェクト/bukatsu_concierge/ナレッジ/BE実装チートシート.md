# だーあさのBE実装チートシート（Wave0 / 1 / 2）

対象読者: 後続チームのBE初心者（Python は読めるが、Supabase・Streamlit・層構成は初めて）
案件: 部活コンシェルジュ（bukatsu_concierge）MVP
範囲: だーあさ担当 17 issue（Wave0 = #8〜#10、Wave1 = #13〜#22、Wave2 = #23〜#27）
記録: yamapi（書記）／ 記録日: 2026-10-04
状態: 初版。コード抜粋は `origin/main`（7834ef0）の実ファイルから引用した。根拠は各節の「出典」と末尾に記載。性能の実測値は取っていないため載せていない。

---

## 0. この記事の読み方

- 各節は **コード → 解説 → 学ぶポイント → ハマりどころ** の順に並べた。
- 「ハマりどころ」は、コードの docstring やコメントに書かれた設計根拠から読み取れるものに限る。実際に誰が何で詰まったかの記録ではない（未確認）。
- 仕様ID（SP-xx）・要件ID（N-xx）・I-F契約の章番号は、そのまま `仕様.md` / `要件.md` / `実装ガイド/I-F契約.md` で引ける。

---

## 1. 導入: 層構成と「層の責務」

```
画面（screens）→ service → repository → DB（Supabase / PostgreSQL）
```

| 層 | 場所 | 責務 | やらないこと |
|---|---|---|---|
| 画面 | `app/frontend/screens/` | 表示、`try/except` で例外を受けて**文言**を出す | DBに直接さわらない |
| service | `app/frontend/services/` | 業務ルール（検証・順序・並び替え・他serviceとの連携） | 画面の文言を組み立てない。SQLを書かない |
| repository | `app/frontend/repositories/` | 1テーブルごとの読み書き（PostgREST の呼び出し） | 業務ルールを持たない |
| DB | `supabase/migrations/` | 型・CHECK制約・一意制約（最後の砦） | — |

**この構成を守る理由（コードから読み取れるもの）**
- 例外の文言は service に持たせない。画面ごとの文言差異（SP-31 の「すでに申し込み済みです」と「この開催には申し込みできません」）に対応しやすくするため（I-F契約 0.4）。
- 検索条件の組み立て（AND/OR）は repository に閉じる。`clubs_repo.py` の docstring に「上位層に漏らさない」とある。
- DB の CHECK 制約は最後の砦。`action_logs_repo.py` の docstring に「事前検証は service 層、ここは薄く保つ」とある。

**学ぶポイント**: 「どの層に何を書くか」を決めてから書く。迷ったら、その処理が *画面の見た目に依存するか*（画面）／*業務ルールか*（service）／*テーブル1枚の読み書きか*（repository）で振り分ける。

---

## 2. Wave0 基盤（#8 #9 #10）

### 2.1 #8 Supabase を「チームで1つ」共有する

`環境セットアップ.md` 2章の PM 決定:「Supabase プロジェクトは個人ごとに作らない。チームで 1 つの共有プロジェクトを使う」。新規作成は Data/BE 担当（だーあさ）が 1 回だけ行い、他のメンバーは共有された URL と anon key を設定するだけ。

**学ぶポイント**
- 全員が同じ DB につながるため、**ダミーデータの再投入やテーブル変更は、実行前にチームへ声をかける**（他メンバーの作業中データも消える・変わる。`環境セットアップ.md` 2章の注記）。
- 現在の MVP は**架空データ限定**で RLS を無効にしている。外部公開・実データ投入の前に Issue #45（Supabase Auth＋RLS 設計）を完了する決まり（`環境セットアップ.md` 2章）。

### 2.2 Secrets は「コードに書かない・コミットしない」

接続先・キー・共通パスワードは `.streamlit/secrets.toml` に置く（N-04）。形式（値はプレースホルダ）:

```toml
supabase_url = "https://<チーム共有プロジェクト>.supabase.co"
supabase_key = "<チーム共有のanon key>"
common_password = "<チームで共有する共通ログインパスワード>"
```

コードからは `st.secrets["supabase_url"]` のように読む。**キーの値をコードや issue・PR に貼らない**。`.gitignore` で除外されているかは次で確認する。

```bash
git check-ignore -v .streamlit/secrets.toml
```

**ハマりどころ**
- Slack 等の非公開チャンネルでの共有は可、GitHub は不可（`環境セットアップ.md` 3章）。
- `common_password` は Supabase Auth ではない。DB 側の利用者識別には使えない（同 2章のセキュリティ境界）。

### 2.3 #9 スキーマ 10 テーブル

`supabase/migrations/202609280001_create_initial_schema.sql` に employees / employee_interests / activities / clubs / club_members / events / applications / messages / notifications / action_logs の 10 テーブルを定義した。**入力の検証は DB の CHECK 制約にも持たせている**。例:

```sql
constraint events_status_check
    check (status in ('予定', '中止')),
constraint events_time_order_check
    check (end_time > start_time)
```

```sql
create unique index applications_one_active_per_employee_idx
    on public.applications (event_id, applicant_id)
    where status = '申込済み';
```

2 つ目は**部分一意インデックス**。「同じ開催に同じ人が *申込済み* の行を 2 つ持てない」を DB が保証する。キャンセル行は対象外なので、キャンセル後の再申込はできる。

後から変更する場合はファイルを書き換えず、**追加のマイグレーション**にする。例: `202609300001_action_logs_apply_requires_club.sql` は既存の `action_logs_shape_check` を drop して付け直している（冒頭コメントに「適用済み DB には本ファイルを追加適用する」とある）。

**学ぶポイント**: アプリ側の検証は「親切なエラーを出すため」、DB の制約は「何があっても壊れないため」。両方ある意味を区別する。

### 2.4 #10 `db/client.py`: 共有クライアント

```python
import streamlit as st
from supabase import Client, create_client


supabase: Client = create_client(
    st.secrets["supabase_url"],
    st.secrets["supabase_key"],
)
```

使い方は全 repository で同じ 1 行。

```python
from db.client import supabase
```

import の根は `app/frontend/`。docstring によれば、9 本の repository を複数人で実装するため、呼び名を `supabase` に統一してずれを防ぐ（I-F契約 0.1）。Streamlit は毎回スクリプトを再実行するが、この変数はモジュールレベルで一度だけ生成されるので、全 repository で同一インスタンスを共有する。

**ハマりどころ**: 各 repository で `create_client` し直さない。`from db.client import supabase` 以外の名前（`client`、`sb` など）を使わない。

---

## 3. Wave1 repository（#13〜#22）

### 3.1 #13 `errors.py`: 例外は 6 種類だけ

```python
class AppError(Exception):
    """共通例外の親クラス。画面側で一括して受けたいときに使う。"""

class ValidationError(AppError): ...
class NotFoundError(AppError): ...
class ConflictError(AppError):
    def __init__(self, reason=None):
        super().__init__(reason)
        self.reason = reason
class AuthenticationError(AppError): ...
class PermissionDeniedError(AppError): ...
```

（`...` は抜粋のための省略。実ファイルには各クラスの docstring がある）

service は**これらだけ**を送出する。メッセージの文言は持たない。

### 3.2 I-F契約 0.4: 「存在しない」は例外にしない

repository の docstring に共通で書かれている方針。

> 「存在しない」は例外にせず None / 空リスト / False で返す（I-F契約 0.4）。DBエラーはそのまま伝播させる。

実例（`activities_repo.py`）:

```python
def get(activity_id: int) -> dict | None:
    """activity_id で1件取得する。存在しなければ None（例外にしない）。"""
    res = (
        supabase.table("activities")
        .select("*")
        .eq("id", activity_id)
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None
```

| 返すもの | 型 | 例 |
|---|---|---|
| 1件取得で無し | `None` | `activities_repo.get` |
| 一覧で無し | `[]`（`res.data or []`） | `list_all` |
| 判定 | `False` | `club_members_repo.is_member` |
| 件数 | `0` | `notifications_repo.count_unread` |

**学ぶポイント**
- 「存在しない」を NotFoundError にするかどうかを決めるのは **service**（例: `auth_service.get_role` は部活が無ければ `NotFoundError`、`application_service.apply` は開催が無ければ `NotFoundError`）。repository は事実を返すだけ。
- `res.data[0] if res.data else None` は 9 本すべてで使う定型句。`res.data` が空リストのとき `[0]` で落ちるのを避ける。

### 3.3 PostgREST idiom（supabase-py の書き方）

`.select(...)` → 条件 → `.order(...)` → `.execute()` の**メソッド連結**。

| やりたいこと | 書き方 | 実例 |
|---|---|---|
| 完全一致 | `.eq("col", v)` | `clubs_repo.get` |
| 複数値のどれか（OR） | `.in_("col", [..])` | `clubs_repo.search` の `locations` |
| 部分一致（大文字小文字無視） | `.ilike("col", "%x%")` | `employees_repo.search` の name |
| 異なる列の OR | `.or_("a.ilike.%x%,b.ilike.%x%")` | `clubs_repo.search` の keyword |
| 範囲 | `.gte` / `.lt` | `events_repo.list_upcoming_by_club` |
| 並び | `.order("col", desc=True)` を連ねる | `events_repo.get_last_meeting_place` |
| NULL 判定 | `.is_("col", "null")` | `notifications_repo.count_unread` |
| 件数 | `.select("id", count="exact")` → `res.count` | `employees_repo.count` |
| join | `.select("*, clubs(*)")` | `events_repo.list_upcoming_all_with_club` |

**AND と OR の作り方（`clubs_repo.search` の docstring）**
- 項目をまたぐ条件は **AND** → メソッドを連結する（`.in_(...)` の後にさらに `.in_(...)`）。
- 同一項目内は **OR** → `in_`（1 列に複数値）。列をまたぐ OR だけ `or_`。

```python
if conditions.get("locations"):
    query = query.in_("location", list(conditions["locations"]))
if conditions.get("slots"):
    query = query.in_("slot", list(conditions["slots"]))
```

「未指定（None・空）のキーは条件にしない」ので、`if` で包んで足していく。

**ハマりどころ**
- `.order("a").order("b")` は「a で並べ、同値なら b」。同日の開催を安定した順にするため、`events_repo` は `order("event_date")` のあとに `order("id")` を足している。
- `.is_("read_at", "null")` — NULL は `= null` では比較できない。`notifications_repo` の docstring に「NULL との比較ではなく IS NULL」とある。

### 3.4 2 層エスケープ: `_escape_like` と `_strip_or_filter_reserved_chars`

キーワード検索には **別の問題が 2 つ**ある。

```python
def _escape_like(value: str) -> str:
    """LIKE/ILIKE のワイルドカードを文字として扱うためのエスケープ。"""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _strip_or_filter_reserved_chars(value: str) -> str:
    for ch in (",", "(", ")", '"'):
        value = value.replace(ch, "")
    return value
```

| 対策 | 守るもの | 無いと起きること |
|---|---|---|
| `_escape_like` | LIKE/ILIKE のワイルドカード（`%` `_` `\`） | `100%` と入力したのに「100 で始まる全部」にマッチする |
| `_strip_or_filter_reserved_chars` | `or_()` の DSL 区切り（`,` `(` `)` `"`） | フィルタ構文が壊れて例外になる |

`clubs_repo.search` での使い方（順序が大事）:

```python
safe_compact = _strip_or_filter_reserved_chars(compact)   # ② 先に区切り文字を除く
if safe_compact:
    pattern = _escape_like(safe_compact)                   # ① ワイルドカードを文字扱いに
    ...
    or_parts = [f"name.ilike.%{pattern}%", f"message.ilike.%{pattern}%"]
    query = query.or_(",".join(or_parts))
```

docstring の判断: PostgREST はカンマ/括弧を含む値をダブルクォートで囲む回避策を案内しているが、クォート内の `"` やバックスラッシュのエスケープ方法が公式ドキュメントに明記されておらず確証が持てない（2026-10-03 docs.postgrest.org 確認時点）。そのため**構文を壊しうる文字そのものを除去する**方針にした。「検索結果が多少広がる/狭まることより、構文破壊で例外になることの方が重大」。

**学ぶポイント**: ユーザー入力を「検索の部品」に埋め込むときは、(1) その部品の言語（LIKE）と (2) それを運ぶ言語（PostgREST フィルタ）の**2 つ**の特殊文字を考える。`employees_repo` の name 検索は `or_` を使わないので `_escape_like` だけ（同じ 1 層でも足りる理由が違う）。

**ハマりどころ**: `_escape_like` は `\` を最初に置換する。`%` を先に処理すると、追加したバックスラッシュがさらにエスケープされてしまう。

### 3.5 日付境界: `events` は「今日を含む」、`applications` は「今日を含まない」

```python
# events_repo.list_upcoming_by_club（今日以降 = 今日を含める）
today = date.today().isoformat()
... .gte("event_date", today) ...

# applications_repo.has_past_non_canceled（過去 = 今日より前）
today = date.today().isoformat()
... .lt("event_date", today) ...
```

SP-26「今日以降の開催を表示（過去は出さない）」の**補集合**として、「過去」は `event_date < 今日`。2 つの関数で境界が食い違うことはない（今日の開催は「今後」側）。`events_repo` の docstring に「開催日と時刻は混ぜず、event_date（date型）だけで比較する」とある。

**ハマりどころ**: 日付は `date.isoformat()` の文字列で PostgREST に渡す。Wave2 の service は日本時間（`Asia/Tokyo`）で今日を出している（5.6 参照）が、repository の `date.today()` は実行環境のローカル日付。この差が実際に問題になるかは未確認。

### 3.6 `exists_active` と `has_past_non_canceled`: 名前どおりの条件

| 関数 | 数える status | 目的 |
|---|---|---|
| `exists_active(event_id, applicant_id)` | **「申込済み」だけ** | 二重申込の検出。キャンセル行は対象外 → キャンセル後の再申込を弾かない |
| `has_past_non_canceled(club_id, employee_id)` | **「キャンセル」以外** | 初参加判定（SP-68 ②）。過去に申し込んでキャンセルしただけの人は初参加扱い |

```python
.eq("status", "申込済み")      # exists_active
.neq("status", "キャンセル")   # has_past_non_canceled
```

DB 側の部分一意インデックス（2.3）と `exists_active` は同じ考え方（申込済みだけが対象）。repository は独自の重複防止を足さない（`applications_repo.py` の docstring: 仕様.md 8 章の保留による）。

**ハマりどころ**: status が今後増えたとき、`eq("申込済み")` と `neq("キャンセル")` は結果が変わる。どちらの意味が欲しいかを関数名で決めている。

### 3.7 その他のパターン

**(a) 冪等な追加: `add_member`**（`club_members_repo.py`）

```python
(
    supabase.table("club_members")
    .upsert(row, on_conflict="club_id,employee_id", ignore_duplicates=True)
    .execute()
)
```

一意制約 `(club_id, employee_id)` に衝突したら**無視**する。2 回呼んでも既存の `joined_at` を上書きしない。`joined_at` が `None` のときは列を送らず、DB の既定値に委ねる。

**(b) 置き換え保存: `set_interests`**（`employees_repo.py`）— 「先に upsert、あとで残りを削除」の順。

```python
supabase.table("employee_interests").upsert(
    rows, on_conflict="employee_id,activity_id"
).execute()
supabase.table("employee_interests").delete().eq(
    "employee_id", employee_id
).not_.in_("activity_id", list(by_activity)).execute()
```

docstring: 「二重登録にならず、途中失敗で全消えにもならない」。「全削除→再挿入」の順だと、途中で失敗したときに 0 件になる。

**(c) None の列は送らない**（`update_status` / `action_logs_repo.insert`）— `None` を送ると「NULL に更新する」になってしまうので、値があるときだけ `row[...]` に入れる。

**(d) 参照ごとに join する**: `applications_repo.list_by_applicant` は `select("*, events(*, clubs(*))")` でネストして取る。並び順は service の責務（docstring「並び順（SP-37）は service 層で行う」）。

**(e) 列の検証は DB に委ねる**: `clubs_repo.create` / `events_repo.update` などの docstring に「列の検証は DB の CHECK 制約に委ねる」。

**(f) 時刻は UTC aware**: `notifications_repo._now_iso()` は `datetime.now(timezone.utc).isoformat()`（N-05）。

---

## 4. Wave2 の前提: service は「順序」と「ルール」を持つ

repository は事実を返す。service は **何をどの順で、誰に許すか** を決める。以降の節は `app/frontend/services/` の 5 本（auth / search / action_log / notification / application）。

---

## 5. Wave2 service（#23〜#27）

### 5.1 #23 `auth_service`: 認証

```python
def login(employee_id: str, password: str) -> dict:
    employee = employees_repo.get_by_id(_normalize_id(employee_id))
    expected = str(st.secrets["common_password"])
    password_ok = hmac.compare_digest(
        (password or "").encode("utf-8"), expected.encode("utf-8")
    )
    if employee is None or not password_ok:
        raise AuthenticationError()
    return employee
```

学ぶポイント 3 つ。

1. **`hmac.compare_digest`**: 文字列を `==` で比べると、先頭から違う位置までの時間差でパスワードを推測される（タイミング攻撃）。`compare_digest` は一致/不一致に関わらず比較時間が一定になるよう作られている。bytes にそろえて渡す。
2. **認証エラーは単一で曖昧に（SP-11）**: ID が無い場合もパスワードが違う場合も `AuthenticationError()` 1 種。どちらが誤りかを返さない（アカウントの存在を教えない）。
   - 実装上の細かい点: `employee is None` でも `compare_digest` を先に実行している。ID 不在のときだけ処理が早く終わらないようにするためかは docstring に書かれておらず、**意図は未確認**。
3. **シークレットはコードに書かない**: `st.secrets["common_password"]`（2.2）。

`_normalize_id` で `strip().upper()` するのは service の責務（docstring「大文字小文字の正規化はこの層で行う」）。`get_role` は `club_id` を渡したときだけ幹事判定をし、部活が無ければ `NotFoundError`。

### 5.2 #27 `ConflictError.reason`: ロジックと文言の分離

```python
if event["status"] != _EVENT_OPEN or _event_datetime(event, "start_time") <= _now():
    raise ConflictError("not_open")
if applications_repo.exists_active(event_id, applicant_id):
    raise ConflictError("already_applied")
```

画面側は例外の `reason` を見て SP-31 の文言を出し分ける（`errors.py` docstring）。service は日本語の文言を一切持たない。

**ハマりどころ**: `cancel` の `ConflictError()` は reason なし（キャンセル済み・開始時刻超過）。reason の有無で画面の分岐が変わるので、画面側と合意してから増やす。

### 5.3 #27 オーケストレーション順序: 検証 → 保存 → 副作用

`apply`（SP-66）の流れ。docstring: 「開催確認→重複確認→初参加判定→申込保存→メッセージ→幹事通知→操作履歴」。

```python
event = events_repo.get(event_id)                     # 1 検証: 開催が存在するか
...
if applications_repo.exists_active(...):              # 2 検証: 重複
    raise ConflictError("already_applied")
is_first_time = _is_first_time(club_id, applicant_id) # 3 判定
application_id = applications_repo.insert(...)        # 4 保存
if message_text and message_text.strip():             # 5 副作用: メッセージ
    messages_repo.insert(application_id, applicant_id, message_text)
...
notification_service.notify(club["organizer_id"], "申込", ...)  # 6 副作用: 幹事通知
action_log_service.record_apply(applicant_id, club_id)          # 7 副作用: 操作履歴
```

- **検証を先にすべて済ませる**: 失敗するなら何も保存しない。
- **保存してから副作用**: 通知・履歴は「申込が保存された」事実を前提にするため。`application_id` も保存の結果として得る。
- 幹事自身が申し込んだときは通知しない（`club["organizer_id"] != applicant_id`）。

**ハマりどころ**: 6〜7 が失敗しても 4 は保存済み。この流れに**トランザクションは無い**（コードに無いので、途中失敗時の巻き戻しは未実装・未確認として扱う）。

### 5.4 #27 service が service を呼ぶ

```python
from services import action_log_service, notification_service
```

`application_service` は通知の作成を `notification_service.notify` に、操作履歴の記録を `action_log_service.record_apply` に任せる。`notification_service` の docstring:「notify は application_service などから呼ばれる共通関数」。

**学ぶポイント**: 通知の検証（種別 5 種・空白のみ不可）は `notify` の 1 箇所に置き、呼び出し側は書かない。逆向き（notification → application）の import を作ると循環 import になるので、依存の向きは一方向にそろえる。

### 5.5 #25 `action_log_service`: JSON 往復で jsonb 比較を正規化する

```python
def _as_stored(conditions: dict) -> dict:
    """DB（jsonb）に保存した形に揃える。get_last の戻り値との比較を型の差で外さないため。"""
    return json.loads(json.dumps(conditions, ensure_ascii=False))

def record_search(employee_id: str, conditions: dict) -> None:
    ...
    stored = _as_stored(conditions)
    last = action_logs_repo.get_last(employee_id, _SEARCH_CLUB)
    if last is not None and last.get("conditions") == stored:
        return
    action_logs_repo.insert(employee_id, _SEARCH_CLUB, conditions=stored)
```

- 直前の記録と**同じなら記録しない**（連続の二重記録防止）。比較対象は `session_state` ではなく **DB の最新記録**（docstring）。Streamlit は再実行のたびに状態が変わりうるため、DB を正とする。
- Python の dict を DB（jsonb）に入れて戻すと、タプルがリストになるなど型が変わる。**比較する側も一度 JSON を往復**させて同じ形にしてから `==` する。
- `record_apply` は二重記録の判定をしない（「申込は 1 件ごとに別の出来事」）。同じ関数群でも **action ごとにルールが違う**。
- 事前検証（必須項目が `None`）はこの層で `ValidationError`。DB の `action_logs_shape_check` は最後の砦（2.3 の追加マイグレーションで apply にも `club_id` を必須にした）。

### 5.6 TZ を明示する（Asia/Tokyo）

```python
_JST = ZoneInfo("Asia/Tokyo")

def _now() -> datetime:
    return datetime.now(_JST)

def _event_datetime(event: dict, time_key: str) -> datetime:
    """events 行の event_date と時刻列（start_time / end_time）から日本時間の datetime を作る。"""
    d = event["event_date"]
    t = event[time_key]
    if not isinstance(d, date):
        d = date.fromisoformat(str(d))
    if not isinstance(t, time):
        t = time.fromisoformat(str(t))
    return datetime.combine(d, t.replace(tzinfo=None), tzinfo=_JST)
```

- N-05: DB はタイムゾーン付きで保存、画面は日本時間。service は `ZoneInfo("Asia/Tokyo")` を**明示**して「いま」と「開催日時」を同じ時間軸にそろえる。
- 開催の `event_date`（date）と `start_time`（time）は**日本時間の壁時計**として扱い、結合して aware な datetime にする（`application_service` の docstring）。
- DB から文字列で返る場合に備え、`isinstance` で型を見て `fromisoformat` で復元する。
- `t.replace(tzinfo=None)` — 時刻列が tz 付きで返っても、いったん外してから JST を付け直す。

**ハマりどころ**: aware（tz 付き）と naive（tz なし）の datetime は `<=` で比較すると `TypeError`。`_now()` も `_event_datetime()` も必ず aware にそろえる。

### 5.7 #24 `search_service`: 並び替えの技

**(a) タプル key の多段ソート**（`_sorted_by_next_event`）

```python
sorted(
    cards,
    key=lambda c: (c["next_event_date"] is None, c["next_event_date"] or date.max, c["club_id"]),
)
```

- Python のタプルは**左から順に**比べる。第 1 要素で決まらなければ第 2 要素…。
- **bool で None を最後に**: `c["next_event_date"] is None` は `False < True` なので、予定ありが先、予定なし（None）が最後。`or date.max` は None 同士を比較で落とさないための代替値。
- 最後に `club_id` を置くので、同順位でも結果が**安定**する（毎回同じ並び）。

**(b) `-値` で降順**（`get_popular_clubs`）

```python
counted.sort(key=lambda t: (-t[0], t[1]["id"]))
```

件数は降順、同数は club_id 昇順（I-F契約 1.2）。数値は `-` を付ければ降順にできる。

**(c) おすすめ**（`get_recommendations`）

```python
key=lambda c: (-c["score"], c["next_event_date"] is None, c["next_event_date"] or date.max, c["club_id"])
```

(a)(b) の合わせ技。score 降順 → 次回開催が近い順（予定なしは最後）→ club_id。

**(d) 2 段ソートで「未読を先頭」**（`application_service.list_received_applications`）

```python
rows.sort(key=lambda a: (a["applied_at"], a["id"]), reverse=True)  # 新しい順
rows.sort(key=lambda a: 0 if a["id"] in unread_application_ids else 1)  # 未読を先頭
```

Python の `sort` は**安定ソート**。後から掛けた「未読か」が第一キー、同じ区分の中では先に掛けた「新しい順」が保たれる（SP-40）。

**(e) 「今週」は月曜〜日曜**（`get_this_week_clubs`）

```python
sunday = today + timedelta(days=6 - today.weekday())
```

`weekday()` は月曜 = 0。範囲は PM 裁定で [今日, 今週の日曜]（docstring）。

### 5.8 #26 未読件数は 1 本に集約（single source of truth）

```python
def count_unread(employee_id: str) -> int:
    """自分あての未読通知件数（SP-70）。"""
    return notifications_repo.count_unread(employee_id)
```

docstring: 「未読件数は SP-70 の算出値を 1 本だけ持つ。サイドバー（SP-01）もこの関数を使い、別集計は作らない。」画面ごとに数え直すと、画面間で数字がずれる。

同じ考え方が `application_service._is_first_time`（初参加の判定、設計.md 5.4）と `_event_datetime`（日時の組み立て）にもある。「判定・変換を 1 か所に集めて、全員がそれを呼ぶ」。

```python
def _is_first_time(club_id: int, employee_id: str) -> bool:
    if club_members_repo.is_member(club_id, employee_id):
        return False
    if applications_repo.has_past_non_canceled(club_id, employee_id):
        return False
    return True
```

### 5.9 #26 通知の検証

```python
NOTIFICATION_TYPES = ("申込", "キャンセル", "メッセージ", "スタンプ", "中止")
...
if type_ not in NOTIFICATION_TYPES:
    raise ValidationError(f"unknown notification type: {type_!r}")
if not body or not body.strip():
    raise ValidationError("body is required")
```

DB の `notifications_type_check` / `notifications_body_not_blank_check` と同じ内容を service 側にも置く。service は**親切なエラー**、DB は**最後の砦**（2.3）。

### 5.10 #24 N+1 クエリの気配: `get_popular_clubs`

```python
for club in clubs_repo.search({}):
    count = 0
    for application in applications_repo.list_by_organizer_club(club["id"]):
        ...
```

部活 N 件につき、`list_by_organizer_club` が内部で events と applications の 2 回、計 **2N 回 + 最初の 1 回**の問い合わせを発行する。これを **N+1 クエリ**と呼ぶ。`search_employees` も、所属部活の取得で部活ごとに `list_members` を呼ぶ同型の形になっている。

- MVP のデータ量では許容した可能性があるが、**docstring に判断の記載はなく、性能の実測もない（未確認）**。
- 改善の方向（実装はしていない）: 1 回の問い合わせで全部活分をまとめて取り、Python 側で数える。
- 後続チームへ: データが増える画面では、**ループの中で repository を呼んでいないか**をレビューの観点にする。

**もう一つの注意**: `get_popular_clubs` は `clubs_repo.search({})` を使う。この関数は `is_active` の部活のみ返す（clubs_repo の docstring）ので、非公開の部活は人気集計に入らない。

---

## 6. 総まとめ: 全体を貫く 6 本の背骨

| # | 背骨 | 実例 |
|---|---|---|
| 1 | **層の責務** | 文言は画面、ルールは service、読み書きは repository（1 章） |
| 2 | **DRY: 1 か所に集約** | `from db.client import supabase`、`count_unread`、`_is_first_time`、`_event_datetime`、`NOTIFICATION_TYPES` |
| 3 | **多層防御** | 入力 → service の検証 → DB の CHECK / 一意制約（`notify`、`record_*`、`applications_one_active_per_employee_idx`） |
| 4 | **ロジックと文言の分離** | `ConflictError.reason`、`AuthenticationError()`（5.2、5.1） |
| 5 | **セキュリティ基本** | Secrets をコードに書かない、`hmac.compare_digest`、認証エラーを曖昧に、2 層エスケープ（2.2、5.1、3.4） |
| 6 | **TZ と正規化** | `ZoneInfo("Asia/Tokyo")`、aware にそろえる、JSON 往復で比較（5.5、5.6） |

**新しい repository / service を書くときのチェックリスト**
- [ ] `from db.client import supabase` を使っている（独自の `create_client` なし）
- [ ] 「存在しない」を `None` / `[]` / `False` / `0` で返している
- [ ] ユーザー入力を LIKE / `or_` に埋めるなら、2 層のエスケープを通している
- [ ] 「今日」の境界（含む・含まない）を、既存の関数と食い違わせていない
- [ ] 日時は aware で比較している（naive と混ぜない）
- [ ] 画面の文言を service に書いていない（例外の種類と `reason` で伝える）
- [ ] 同じ判定・集計を別の場所に書き足していない
- [ ] Secrets・キーの値をコード、issue、PR に貼っていない

---

## 出典

- 実コード（`origin/main` 7834ef0）: `app/frontend/db/client.py`、`app/frontend/services/{errors,auth_service,search_service,action_log_service,notification_service,application_service}.py`、`app/frontend/repositories/{employees,activities,clubs,club_members,events,applications,messages,notifications,action_logs}_repo.py`
- スキーマ: `supabase/migrations/202609280001_create_initial_schema.sql`、`202609300001_action_logs_apply_requires_club.sql`
- 背景文書: `実装ガイド/I-F契約.md`（0.1、0.4、1.2）、`実装ガイド/環境セットアップ.md`（2〜3章）、`仕様.md`（SP-07、SP-11 ほか）、`要件.md`（N-05）、`ナレッジ/実践ナレッジ.md`

## 未確認

- Wave0 の #8 の作成作業そのもの（プロジェクトの作成手順の実施記録）は、手順書（`環境セットアップ.md`）から読み取った内容であり、実施結果は確認していない。
- 各 repository / service のテスト結果・合格状況は確認していない。この記事は挙動の解説であり、品質保証ではない。
- `auth_service.login` で ID 不在時にも `compare_digest` を実行する意図、repository の `date.today()` と service の JST 日付のずれが実害になるか、N+1 の性能影響は、いずれも未確認。
- 画面層（`screens/`）の実装との結合は、この記事の範囲外。
- 技術監修（だーあさ本人・terao による内容確認）は未実施。
