# 部活コンシェルジュ I/F契約（services / repositories）

作成：Takahiro（設計担当）　作成日：2026-09-27

## 0. 本書の位置づけと決定事項

`設計.md`（層分離・5フロー）・`仕様.md`（SP-01〜SP-78）を一次情報に、`services/` 5本・`repositories/` 9本の関数シグネチャを1つに確定する。フロント（あかぷ／mirin）・バックエンド（だーあさ／terao）ともに、この契約に従って実装する。契約にない呼び方（別の引数名・別の戻り値形式）は使わない。

### 0.1 今日の衝突（関数 vs クラス）の解消

**services / repositories はどちらもモジュールレベルの関数として実装する（クラスは作らない）。**

- 理由：`設計.md` 5章の処理フロー記述がすでに `application_service.apply(event_id, applicant_id, message_text)` のようなモジュール関数呼び出しの形で書かれており、この形を正とする。
- 呼び出し側は `from services import application_service` のように**モジュールをインポートし、`application_service.apply(...)` の形で呼ぶ**。`ApplicationService()` のようなインスタンス化はしない。
- 状態（DB接続など）はモジュール内のトップレベルで保持する（`db/client.py` が生成する1つのSupabaseクライアントを、各`repositories`モジュールがimportして共有する）。サービス・リポジトリのどちらも、呼び出しのたびに新しいオブジェクトを作らない。
- テスト時のモック差し替えは、`unittest.mock.patch("services.application_service.applications_repo", ...)` のようにモジュール属性の差し替えで行う（クラスのDIコンテナは使わない）。

### 0.2 データアクセス層の追加確定事項

`設計.md` 1章のディレクトリ構成には `repositories/` が9本（employees, activities, clubs, events, applications, messages, notifications, action_logs, club_members）挙げられているが、`employee_interests` テーブル（仕様.md 3.1）へのアクセスがどのrepositoryに属するか明記がなかった。ここで確定する：

**`employee_interests` へのアクセスは `employees_repo.py` に含める**（興味・経験は社員に強く紐づくデータであり、独立ファイルを増やさずrepositoriesの本数（9）を`設計.md`の構成どおりに保つため）。

### 0.3 命名規則

- 関数名は動詞スネークケース（`get`, `search`, `insert`, `update_status` など）。
- IDを受け取る引数は `_id` サフィックス（`event_id`, `applicant_id` など）。型はテーブル定義（仕様.md 3.1）に準拠（`employees.id`はtext、他の主キーはinteger）。
- 一覧を返す関数は `list_*` または `search`、件数のみ返す関数は `count_*`。
- 真偽判定は `is_*` / `exists_*` / `has_*`。
- 日時は `datetime`（タイムゾーンaware、N-05準拠）。日付は`date`、時刻は`time`。

### 0.4 エラーハンドリング方針

`services/errors.py` に共通例外を定義し、すべてのservice関数はこれらのみを送出する（repositoriesは基本的にDBエラーをそのまま伝播させてよいが、想定内の「存在しない」は`None`や空リストを返し例外にしない）。

| 例外クラス | 用途 |
|---|---|
| `ValidationError` | 入力不正（必須未入力、選択肢外の値など） |
| `NotFoundError` | 対象のレコードが存在しない |
| `ConflictError` | 重複申込・キャンセル期限超過・中止済み開催への申込など、状態の競合 |
| `AuthenticationError` | ログイン失敗（SP-11） |
| `PermissionDeniedError` | 権限不足（SP-74の範囲外の操作） |

画面側（`screens/*.py`）は、これらの例外を`try/except`で受け、仕様.mdに定めるエラーメッセージ文言（例：SP-11「社員IDかパスワードが違います。入力内容を確認してください」）を表示する。**エラーメッセージの文言はservice層では組み立てず、画面側で例外の種類に応じて仕様書どおりの文言を出す**（文言をservice/repositoryに持たせると、画面ごとの文言差異（例：SP-31の「すでに申し込み済みです」と「この開催には申し込みできません」の出し分け）に対応しづらいため）。

## 1. services（5本）

### 1.1 `services/auth_service.py`（対応SP: SP-01, SP-63, SP-11）

```
login(employee_id: str, password: str) -> dict
    社員ID（大文字小文字を区別しない）と共通パスワード（st.secrets["common_password"]）を照合する。
    戻り値: 成功時、employees_repo.get_by_id() の社員レコード（dict）。
    例外: AuthenticationError（ID・パスワードいずれかが不一致のとき。どちらが誤りかは呼び出し側に伝えない＝単一の例外で表現する）。
    前提: employee_id は "E001" 形式を想定するが、大文字小文字の正規化はこの関数の内部で行う（呼び出し側は正規化しない）。

get_role(employee_id: str, club_id: int | None = None) -> str
    戻り値: "admin"（employees.is_admin=True） / "organizer"（club_idが指定され、その部活のclubs.organizer_idと一致） / "member"（それ以外）。
    club_id を省略した場合、is_admin のみで "admin" / "member" を返す（幹事判定はclub_id必須）。
    例外: club_id を指定したが該当する部活が存在しない場合は NotFoundError。

is_organizer(employee_id: str) -> bool
    「部活を指定せず、その社員がどこかの部活の幹事か」を判定する（SP-01：サイドバーの「部活の管理」は幹事・運営者にのみ表示）。
    戻り値: どこかの部活で clubs.organizer_id が employee_id と一致すれば True、1件も一致しなければ False。
    運営者（employees.is_admin）かどうかは見ない（運営者の判定は get_role の "admin"）。サイドバーの表示可否は get_role(employee_id) == "admin" または is_organizer(employee_id) で決める。
    例外: なし（該当する社員・部活がなくても False を返す）。
    実装方針: clubs_repo.list_by_organizer(employee_id)（2.3に既存）が1件以上返せば True とする。新規のrepository関数は不要。
    根拠: SP-01、SP-77（幹事は clubs.organizer_id で持つ）、設計.md 5.6（get_role は is_admin と clubs.organizer_id を見る。幹事は担当部活のみ）。
    get_role の club_id=None の挙動（is_admin のみで "admin" / "member"）は変えない。
```

### 1.2 `services/search_service.py`（対応SP: SP-16, SP-17, SP-64, SP-65, SP-75）

```
search_clubs(conditions: dict) -> list[dict]
    conditions のキー: "categories"（list[str], 活動カテゴリ）, "locations"（list[str]）, "slots"（list[str], 曜日/時間帯）, "levels"（list[str]）, "keyword"（str）。
    指定しないキーは省略可（未指定＝条件にしない、仕様.md SP-20）。
    戻り値: is_active=trueの部活を、次回開催日が近い順（予定の開催がない部活は最後）に並べたdictのリスト。各dictはカード表示（SP-21）に必要な項目（部活名・拠点・活動時間・次回開催日・雰囲気タグ・費用・活動後の過ごし方・club_id等）を含む。
    各dictのキー（「部活カードdict」。下記の他の関数でも共通）:
      "club_id"(int, = clubs.id), "name"(str), "icon"(str), "location"(str), "slot"(str), "schedule_note"(str|None), "mood_tags"(clubsのmood_tagsと同じ型), "fee"(clubsのfeeと同じ型), "fee_note"(str|None), "after_activity"(str), "next_event_date"(date | None)。
      キー名は clubs テーブルの列名（仕様.md 3.1）に一致させる。ただし主キーのみ、「id」だと events.id・activities.id と取り違えやすいため "club_id" とする（値は clubs.id）。
      "next_event_date" は events.event_date のうち、その部活の status が「予定」の開催で最も近い日付（SP-20, SP-21）。予定の開催がない部活は None。
    例外: なし（条件に合わない場合は空リストを返す。0件時の文言はSP-22どおり画面側で出す）。

search_employees(conditions: dict, requester_id: str, limit: int = 20, offset: int = 0) -> tuple[list[dict], int]
    conditions のキー: "name"（str, 部分一致）, "depts"（list[str]）, "locations"（list[str]）, "interests"（list[int], activity_id）, "club_id"（int | None, 「指定なし」はNone）, "slots"（list[str]）。
    requester_id: 検索している本人の社員ID。非公開判定と、本人自身の非公開項目の特別表示（SP-65「本人には値と（他の人には非公開）を表示」）に使う。
    戻り値: (該当社員のdictリスト, 全該当件数)。dictリストは limit/offset でページングされたもの（SP-51の「20件ずつ、もっと見る」に対応）。
    例外: なし。

get_recommendations(employee_id: str) -> list[dict]
    自分の興味・拠点・参加可能時間（非公開設定に関わらず本人分は使う。SP-75裁定#19）と、各部活の活動・拠点・時間帯の一致数をスコアとして算出し、スコア降順で部活のdictリスト（一致理由の説明文つき）を返す。
    戻り値が空の場合は空リスト（0件時の文言はSP-18どおり画面側で出す）。
    各dictのキー: 部活カードdict（上記search_clubsと同じキー）に加えて
      "score"(int, 一致度スコア。自分の興味・拠点・参加可能時間と部活の活動・拠点・時間帯が一致した項目の数。SP-18, SP-75),
      "reason"(str, 一致した項目を並べた説明文。画面はそのまま表示する。SP-75「一致項目をおすすめ理由として表示」)。
    並びは "score" の降順。

get_this_week_clubs() -> list[dict]
    ホーム（S02）の「今週開催の部活」用（SP-16, SP-75, SP-08）。
    今週＝月曜〜日曜（SP-08）に status が「予定」の開催がある部活を、開催日が近い順に返す。is_active=trueの部活のみ（SP-20と同じ扱い）。
    戻り値: 部活カードdict（search_clubsと同じキー）のリスト。このリストでは "next_event_date" は「今週の予定の開催のうち最も近い開催日」とする。
    件数の絞り込み（SP-16の「最大4件」）は行わない。該当する部活をすべて返し、先頭4件の切り出し（[:4]）と0件時の案内文は画面側が持つ（表示件数は画面の仕様であり、サービスは並びだけを保証するため）。
    例外: なし（0件のときは空リスト）。

get_popular_clubs() -> list[dict]
    ホーム（S02）の「今月の人気部活」用（SP-17, SP-75）。
    今月の開催への申込のうち、is_first_time が true かつ status がキャンセル以外のものを部活ごとに数え、件数の多い順に返す。
    戻り値: 部活カードdict（search_clubsと同じキー）に加えて "rank"(int, 1始まりの順位＝並び順の通し番号) を持つdictのリスト。集計対象が0件の部活は含めない。
    件数の絞り込み（SP-17の「上位3件」）は行わない。集計できた部活を順位つきですべて返し、先頭3件の切り出し（[:3]）と0件時の案内文は画面側が持つ。
    同数のときの並び：仕様に定めがないため、club_id の昇順で決める（テスト・表示を毎回同じにするためだけの決め。順位は通し番号とし同順位は作らない）。
    例外: なし（0件のときは空リスト）。
```

### 1.3 `services/application_service.py`（対応SP: SP-66〜SP-68, SP-72）

```
apply(event_id: int, applicant_id: str, message_text: str | None) -> dict
    申込処理（仕様.md SP-66）を行う。手順は設計.md 5.1のとおり：開催状態・開始時刻の確認→重複申込確認→初参加判定→applications登録→メッセージ登録（任意）→幹事への通知（幹事本人の申込は除く）→操作履歴記録。
    戻り値: {"application_id": int, "is_first_time": bool}
    例外:
      - NotFoundError（event_idが存在しない）
      - ConflictError（開催が「予定」でない・開始時刻を過ぎている・同じ開催に「申込済み」の申込が既にある。理由の判別は画面側でSP-31の文言を出し分けるため、ConflictErrorの引数に理由コード（"not_open" | "already_applied"）を含める）
      - ValidationError（message_text が極端に長い等、将来のバリデーション拡張用。MVPでは基本的に発生しない）

cancel(application_id: int, requester_id: str) -> None
    キャンセル処理（仕様.md SP-67）。申込者本人のみ、開催の開始時刻より前（ちょうど・超過は不可）まで可能。
    例外:
      - NotFoundError（application_idが存在しない）
      - PermissionDeniedError（requester_idが申込者本人でない）
      - ConflictError（既にキャンセル済み、または開催の開始時刻に達している）

list_my_applications(employee_id: str) -> list[dict]
    自分の申込一覧（メッセージ画面「自分の申込」タブ用。SP-37）。開催日が近い順、終わった開催・キャンセルは後ろ。

list_received_applications(organizer_id: str) -> list[dict]
    自分が幹事を務める部活への申込一覧（メッセージ画面「届いた申込」タブ用。SP-40）。未読の通知がある申込を先頭、そのあとは新しい順。

confirm_stamp(application_id: int, organizer_id: str) -> None
    「確認したよ」スタンプ処理（SP-72）。is_first_timeがtrueの申込にのみ有効。
    例外:
      - NotFoundError
      - PermissionDeniedError（organizer_idがその部活の幹事でない）
      - ConflictError（is_first_timeがfalse、または既に確認済み＝confirmed_atがある）
```

### 1.4 `services/notification_service.py`（対応SP: SP-70, SP-71）

```
count_unread(employee_id: str) -> int
    自分あての未読通知件数（サイドバー・SP-01表示用。SP-70の算出値そのもので、別集計は行わない）。

list_notifications(employee_id: str) -> list[dict]
    通知一覧（S07用。新しい順、未読フラグ付き。SP-44）。

mark_read_for_messages_screen(employee_id: str) -> None
    メッセージ画面（S06）を開いたときに呼ぶ。自分あての「申込」「キャンセル」「メッセージ」「スタンプ」の通知を既読にする（SP-36）。

mark_read_all(employee_id: str) -> None
    通知一覧画面（S07）を開いたときに呼ぶ。自分あての通知をすべて既読にする（SP-46）。

notify(recipient_id: str, type_: str, *, application_id: int | None = None, event_id: int | None = None, body: str) -> None
    通知を1件作成する内部共通関数。application_service・screens/club_admin.py（開催中止のお知らせ、Should）から呼ぶ。
    type_ は "申込" | "キャンセル" | "メッセージ" | "スタンプ" | "中止" のいずれか（仕様.md 4.9）。
```

### 1.5 `services/action_log_service.py`（対応SP: SP-76）

```
record_search(employee_id: str, conditions: dict) -> None
    部活検索の操作履歴（search_club）。直前に記録した検索条件と同じ場合は記録しない（二重記録防止）。

record_view_club(employee_id: str, club_id: int) -> None
    部活詳細閲覧の操作履歴（view_club）。直前に記録したview_clubと同じ部活を連続で開き直した場合は記録しない（2026-09-27テスト設計フィードバック反映、仕様.md SP-76）。

record_apply(employee_id: str, club_id: int) -> None
    申込完了の操作履歴（apply）。application_service.apply() の成功時にこの関数を呼ぶ。
```

「直前に記録した内容」の比較は、`action_logs_repo.get_last(employee_id, action)` でDBから取得した最新の記録と比較する方式に統一する（`session_state`での比較は、アプリ再起動やタブ跨ぎで壊れるため採用しない。設計.md 5.5の記述は本書で以下のとおり確定・上書きする：比較はDB参照で行う）。

## 2. repositories（9本）

各`repositories/*.py`はSQL/Supabaseクエリの組み立てをここに閉じ込め、`services/`からのみ呼ばれる。画面（`screens/*.py`）からrepositoriesを直接呼ばない。

### 2.1 `repositories/employees_repo.py`（employees, employee_interests）

```
get_by_id(employee_id: str) -> dict | None            # 大文字小文字を区別せず検索
search(conditions: dict, limit: int, offset: int) -> list[dict]
count(conditions: dict) -> int
update_public_settings(employee_id: str, *, interests_public: bool | None = None, slots_public: bool | None = None) -> None
get_interests(employee_id: str) -> list[dict]           # [{"activity_id":..,"activity_name":..,"level":..}, ...]
set_interests(employee_id: str, interests: list[dict]) -> None   # SP-57（Should）の編集保存用
```

### 2.2 `repositories/activities_repo.py`（activities）

```
list_all() -> list[dict]
get(activity_id: int) -> dict | None
```

### 2.3 `repositories/clubs_repo.py`（clubs）

```
get(club_id: int) -> dict | None
search(conditions: dict) -> list[dict]
list_by_organizer(organizer_id: str) -> list[dict]
list_all_for_admin() -> list[dict]                      # 運営者向け：全部活
create(data: dict) -> int
update(club_id: int, data: dict) -> None
```

### 2.4 `repositories/club_members_repo.py`（club_members）

```
is_member(club_id: int, employee_id: str) -> bool
list_members(club_id: int) -> list[dict]
add_member(club_id: int, employee_id: str, joined_at=None) -> None
remove_member(club_id: int, employee_id: str) -> None
```

### 2.5 `repositories/events_repo.py`（events）

```
get(event_id: int) -> dict | None
list_upcoming_by_club(club_id: int) -> list[dict]        # 今日以降、日付順
list_upcoming_all_with_club() -> list[dict]               # ホーム「今週開催の部活」集計用（clubとjoin）
get_last_meeting_place(club_id: int) -> str | None
create(data: dict) -> int
update(event_id: int, data: dict) -> None
set_status(event_id: int, status: str) -> None
```

### 2.6 `repositories/applications_repo.py`（applications）

```
get(application_id: int) -> dict | None
exists_active(event_id: int, applicant_id: str) -> bool
insert(event_id: int, applicant_id: str, is_first_time: bool) -> int
update_status(application_id: int, status: str, *, canceled_at=None, confirmed_at=None) -> None
has_past_non_canceled(club_id: int, employee_id: str) -> bool
list_by_applicant(applicant_id: str) -> list[dict]
list_by_organizer_club(club_id: int) -> list[dict]
list_participants(event_id: int) -> list[dict]            # 開催の参加者一覧（初参加印つき）
```

### 2.7 `repositories/messages_repo.py`（messages）

```
list_by_application(application_id: int) -> list[dict]
insert(application_id: int, sender_id: str, body: str) -> int
```

### 2.8 `repositories/notifications_repo.py`（notifications）

```
count_unread(employee_id: str) -> int
list_by_recipient(employee_id: str) -> list[dict]
insert(recipient_id: str, type_: str, *, application_id=None, event_id=None, body: str) -> int
mark_read(employee_id: str, types: list[str]) -> None
mark_read_all(employee_id: str) -> None
```

### 2.9 `repositories/action_logs_repo.py`（action_logs）

```
insert(employee_id: str, action: str, *, club_id=None, conditions=None) -> int
get_last(employee_id: str, action: str) -> dict | None
```

- `insert`の引数は`action`ごとに次のとおり必須とする（DBの`action_logs_shape_check`と同じ条件）。
  - `search_club`：`conditions`が必須
  - `view_club` / `apply`：`club_id`が必須（`club_id=None`のままでは記録できない）
- 条件を満たさない`insert`は、DBのCHECK制約が拒否する（最後の防御）。事前検証をどの層で行うか、例外の型は実装時に確定する。

## 3. 保留

本書の範囲で新たに判断が必要となった項目のうち、すでに確定した0.2節・action_log_serviceの比較方式以外に未確定のものはない。設計.md 8章の保留のうち、applicationsの一意制約設計は2026-09-28に`status='申込済み'`条件付き部分一意インデックスとサービス層の事前存在確認を併用すると確定した。申込の二重送信対策とmood_tagsバリデーション位置は本書の対象外（実装着手時にだーあさ・teraoが確定する、実装計画.md 3章のとおり）。外部公開・実データ利用前のSupabase Auth＋RLSはIssue #45で扱う。
