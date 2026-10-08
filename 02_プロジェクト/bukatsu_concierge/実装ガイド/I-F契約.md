# 部活コンシェルジュ I/F契約（services / repositories）

作成：Takahiro（設計担当）　作成日：2026-09-27

## 0. 本書の位置づけと決定事項

`設計.md`（層分離・5フロー）・`仕様.md`（SP-01〜SP-78）を一次情報に、`services/` 7本・`repositories/` 9本の関数シグネチャを1つに確定する。フロント（あかぷ／mirin）・バックエンド（だーあさ／terao）ともに、この契約に従って実装する。契約にない呼び方（別の引数名・別の戻り値形式）は使わない。

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

## 1. services（7本）

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

### 1.2 `services/search_service.py`（対応SP: SP-16, SP-17, SP-26, SP-27, SP-28, SP-64, SP-65, SP-75）

```
search_clubs(conditions: dict) -> list[dict]
    conditions のキー: "categories"（list[str], 活動カテゴリ）, "locations"（list[str]）, "slots"（list[str], 曜日/時間帯）, "levels"（list[str]）, "keyword"（str）。
    指定しないキーは省略可（未指定＝条件にしない、仕様.md SP-20）。
    戻り値: is_active=trueの部活を、次回開催日が近い順（予定の開催がない部活は最後）に並べたdictのリスト。各dictはカード表示（SP-21）に必要な項目（部活名・拠点・活動時間・次回開催日・雰囲気タグ・費用・活動後の過ごし方・club_id等）を含む。
    各dictのキー（「部活カードdict」。下記の他の関数でも共通）:
      "club_id"(int, = clubs.id), "name"(str), "icon"(str | None), "location"(str), "slot"(str), "schedule_note"(str|None), "mood_tags"(clubsのmood_tagsと同じ型), "fee"(clubsのfeeと同じ型), "fee_note"(str|None), "after_activity"(str), "level"(str, clubs.level。「初心者歓迎」「レベル問わず」「経験者向け」のいずれか), "next_event_date"(date | None)。
      キー名は clubs テーブルの列名（仕様.md 3.1）に一致させる。ただし主キーのみ、「id」だと events.id・activities.id と取り違えやすいため "club_id" とする（値は clubs.id）。
      "next_event_date" は events.event_date のうち、その部活の status が「予定」の開催で最も近い日付（SP-20, SP-21）。予定の開催がない部活は None。今日（日本時間）より前の開催は対象に含めない（今日の開催は含める）。
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
    所属済みの部活（club_members に登録がある部活）は結果に含めない。本人の所属は club_members_repo.list_clubs_by_member(employee_id) で判定する。

get_this_week_clubs() -> list[dict]
    ホーム（S02）の「今週開催の部活」用（SP-16, SP-75, SP-08）。
    ホームの「今週」は、今日から今週の日曜まで（両端を含む）。SP-08の週の定義（月曜〜日曜）は変えず、その週のうち今日以降かつ今週日曜までを表示範囲とする（PM裁定）。
    この範囲に status が「予定」の開催がある部活を、開催日が近い順に返す。is_active=trueの部活のみ（SP-20と同じ扱い）。
    戻り値: 部活カードdict（search_clubsと同じキー）のリスト。このリストでは "next_event_date" は「今日〜今週日曜の予定の開催のうち最も近い開催日」とする。
    件数の絞り込み（SP-16の「最大4件」）は行わない。該当する部活をすべて返し、先頭4件の切り出し（[:4]）と0件時の案内文は画面側が持つ（表示件数は画面の仕様であり、サービスは並びだけを保証するため）。
    例外: なし（0件のときは空リスト）。

get_popular_clubs() -> list[dict]
    ホーム（S02）の「今月の人気部活」用（SP-17, SP-75）。
    今月の開催への申込のうち、is_first_time が true かつ status がキャンセル以外のものを部活ごとに数え、件数の多い順に返す。
    集計対象は is_active=true の部活のみ。中止になった開催（events.status が「中止」）への申込は集計しない（PM裁定）。"next_event_date" の意味は search_clubs と同じ（今日（日本時間）以降の「予定」の開催で最も近い日）。
    戻り値: 部活カードdict（search_clubsと同じキー）に加えて "rank"(int, 1始まりの順位＝並び順の通し番号) を持つdictのリスト。集計対象が0件の部活は含めない。
    件数の絞り込み（SP-17の「上位3件」）は行わない。集計できた部活を順位つきですべて返し、先頭3件の切り出し（[:3]）と0件時の案内文は画面側が持つ。
    同数のときの並び：仕様に定めがないため、club_id の昇順で決める（テスト・表示を毎回同じにするためだけの決め。順位は通し番号とし同順位は作らない）。
    例外: なし（0件のときは空リスト）。

get_club_detail(club_id: int, viewer_id: str) -> dict
    部活詳細（S04）の表示に必要な情報をまとめて返す読み取り専用の関数（SP-26, SP-27, SP-28）。書き込みや操作履歴の記録は行わない（view_club の記録は下記「記録の分離」のとおり画面側が別に呼ぶ）。
    引数: viewer_id は閲覧している本人の社員ID。参加者の「あなた」印（is_self）と申込済み表示（is_applied）の判定にだけ使う。
    戻り値のキー:
      "club"(dict): clubs_repo.get(club_id) の全列（仕様.md 3.1）。主キーのみ "id" ではなく "club_id" に読み替える（部活カードdictと同じ。"id" キーは含めない）。
      "organizer"(dict): 幹事。キーは "id", "name", "dept", "joined_year", "entry_type"（employees の列名。SP-28）。employees_repo.get_by_id(clubs.organizer_id) から必要な列だけを取り出す。
      "members"(list[dict]): 所属メンバー。各dictは "id", "name", "dept"（SP-28）。club_members_repo.list_members(club_id) の employee_id ごとに employees_repo.get_by_id で名前・部署を解決する。幹事も club_members に登録される（SP-77）ため、幹事本人も含まれる。
      "member_count"(int): len(members)。
      "events"(list[dict]): 今日以降の開催を日付順（同日はid順）。events_repo.list_upcoming_by_club(club_id) の順序のまま。各dictのキー:
        "event_id"(int, = events.id), "event_date"(date), "start_time"(time), "end_time"(time), "meeting_place"(str), "meeting_time"(time | None), "status"("予定" | "中止"),
        "participant_count"(int), "first_timer_count"(int), "participants"(list[dict]), "is_applied"(bool)。
        "participants" の各dictは "id"(申込者の社員ID), "name", "is_first_time"(bool), "is_self"(bool, id == viewer_id)。applications.id 順。
        "is_applied": viewer_id 本人が、その開催に状態「申込済み」の申込を持つか（= participants のどれかが is_self）。SP-27 のボタン出し分け（予定・未申込→「申し込む」／予定・申込済み→「申込済み」／中止→「中止」でボタンなし）は、この値と "status" で画面側が決める。
    集計: "participant_count" は participants の件数、"first_timer_count" はそのうち is_first_time が true の件数（SP-26「参加人数（うち初参加人数）」）。applications_repo.list_participants は状態「申込済み」の申込だけを返すため、キャンセルは自然に除かれる。集計はservice内で行い、repositoryに集計関数は足さない。
    所要時間（SP-26）は start_time と end_time から画面側が計算する（キーは設けない）。
    公開範囲: employees の行には is_admin・available_slots・各公開設定などが含まれるが、上に列挙したキー以外は返さない（画面に渡す項目を契約で固定するため）。
    例外: NotFoundError（club_id に該当する部活が存在しない）。
    記録の分離（SP-32, SP-76）: 部活詳細を開いたときの view_club は、画面（screens）が action_log_service.record_view_club(employee_id, club_id) を別に呼ぶ。get_club_detail の中では呼ばない（読み取り関数に副作用を混ぜない。再描画のたびに関数が呼ばれても記録が増えないようにするため）。連続して同じ部活を開いた場合の二重記録防止は SP-76 どおり record_view_club 側が持つ。

list_departments() -> list[str]
    社員検索（S08）の部署の選択肢（SP-48）用。employees.dept の重複を除いた値を、五十音順ではなく文字列の昇順（Python の sorted と同じ）で返す。部署の独立したマスタテーブルは無い（仕様.md 3.1）ため、employees から導く。
    戻り値: 部署名の str のリスト。該当社員が0人なら空リスト。
    例外: なし。
    実装方針: 新設の employees_repo.list_departments()（2.1）を呼ぶ。画面（screens）が employees_repo を直接呼ばないよう、service 経由で選択肢を渡すための関数（0.4・2章の層分離）。

list_activities() -> list[dict]
    社員検索（S08）の興味・経験の選択肢（SP-48）と、プロフィール編集（S09, SP-57）の活動の並びに使う活動マスタ。
    戻り値: [{"id": int, "name": str}, ...]（activities の id と name のみ。id 昇順）。0件なら空リスト。
    例外: なし。
    実装方針: activities_repo.list_all()（2.2・既出）から "id" と "name" だけを取り出す。画面が activities_repo を直接呼ばないための service 経由の入口で、repository の追加は不要。
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

send_message(application_id: int, sender_id: str, body: str) -> None
    申込に紐づくやり取り（messages）へ1件送信する（メッセージ画面S06の「自分の申込」「届いた申込」両タブ。SP-37〜SP-40）。
    送信できる人: その申込の申込者本人（applications.applicant_id）と、その申込の部活の幹事（clubs.organizer_id）のみ。運営者（is_admin）でも、どちらでもない社員は送れない。
    処理: messages_repo.insert(application_id, sender_id, body) で保存し、相手に種別「メッセージ」の通知を1件送る。
      - 申込者が送ったとき → 通知の宛先は部活の幹事。幹事が送ったとき → 宛先は申込者。
      - notification_service.notify(recipient_id, "メッセージ", application_id=application_id, body=...) を呼ぶ。通知の body は「新しいメッセージがあります」に固定する（宛先が幹事でも申込者でも同じ。他の種別の文言「新しい申込があります」「申込がキャンセルされました」「幹事が確認しました」と同じく、service内で文言を組み立てず固定文を渡す）。
      - 申込者が幹事本人（幹事が自分の部活の開催に申し込んでいる）の場合、相手がいないため通知は送らない（apply と同じ扱い。メッセージの保存だけ行う）。
    body: 前後の空白を除いた文字列を保存する。空文字・空白のみは ValidationError。長さの上限は仕様に無いため、この契約では設けない。
    戻り値: なし（保存した messages の id は返さない。画面は list_my_applications / list_received_applications を取り直して表示する）。
    例外（判定の順）:
      - NotFoundError（application_id に該当する申込が存在しない）
      - PermissionDeniedError（sender_id が申込者本人でも、その部活の幹事でもない）
      - ValidationError（body が空・空白のみ）
      - ConflictError（申込が「キャンセル」状態。SP-39「キャンセル済みのため、やり取りは閲覧のみです」）。引数に理由コードは持たせない。
    画面側: キャンセル済みの申込には入力欄を出さない（SP-39）ため、この ConflictError は画面の表示と送信の間に状態が変わった場合の防御。

list_my_applications(employee_id: str) -> list[dict]
    自分の申込一覧（メッセージ画面「自分の申込」タブ用。SP-37）。開催日が近い順、終わった開催・キャンセルは後ろ。
    各dictは applications の行に "events"（開催。"events"."clubs" に部活）と "messages"（やり取り）を付けたもの。これに加えて次のキーを持つ。
      "organizer"(dict): その申込の部活の幹事。キーは "id", "name"（employees の列名）。clubs.organizer_id を employees_repo.get_by_id で解決する。画面は「幹事：○○」の表示に使う（SP-37）。
    "organizer" の解決: 幹事の社員行が見つからない場合（想定外）は {"id": clubs.organizer_id, "name": None} とし、例外にしない（一覧全体を落とさない）。
    list_received_applications には "organizer" を足さない（幹事は自分自身であり、申込者の名前は "employees" で既に付いている）。

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

### 1.6 `services/profile_service.py`（対応SP: SP-53〜SP-57, SP-65）

本人のプロフィール（S09）の参照と更新を担当する6本目のservice。search_service は「探す・見る」ための参照（部活・社員の検索や詳細）、profile_service は「ある社員のプロフィールの参照（get_profile）と、本人による更新（update_public_settings / save_profile）」を持つ。更新は本人のみが行え、他人の更新・参照の公開判断はこのserviceが持つ。社員検索の一覧（search_employees）は引き続き search_service。

```
get_profile(employee_id: str, viewer_id: str) -> dict
    社員プロフィール（S09）の表示に必要な情報をまとめて返す読み取り専用の関数（SP-53, SP-54, SP-55, SP-65）。書き込みや操作履歴の記録は行わない（操作履歴の対象は SP-76 の search_club / view_club / apply のみで、プロフィール閲覧は含まれない）。
    引数: viewer_id は閲覧している本人の社員ID。is_self の判定と、非公開項目を他人に渡さない判断（SP-54, SP-65）に使う。employee_id・viewer_id とも大文字小文字を区別しない（get_by_id と同じ）。
    戻り値のキー:
      "employee"(dict): "id", "name", "dept", "location", "joined_year", "entry_type"（employees の列名。SP-53）。これ以外の列（is_admin・available_slots・公開設定の列など）は含めない。
      "is_self"(bool): employee の id が viewer_id と一致するか。
      "interests"(list[dict] | None): employees_repo.get_interests(employee_id) の戻り値（"activity_id", "activity_name", "level"）。interests_public が false で is_self が false のときは None（値を渡さない。画面は None を「非公開」と表示する）。本人（is_self）には公開設定にかかわらず値を返す。
      "interests_public"(bool): employees.interests_public。本人の画面が「（他の人には非公開）」の表示と切り替えスイッチの初期値に使う（SP-56, SP-65）。他人が閲覧する場合も返すが、画面は本人のときだけ使う。
      "available_slots"(list[str] | None): employees.available_slots。slots_public が false で is_self が false のときは None。本人には常に値を返す。
      "slots_public"(bool): employees.slots_public。"interests_public" と同じ扱い。
      "clubs"(list[dict]): 所属部活の部活カードdict（search_clubs と同じキー）。club_members に employee_id が登録されている部活のうち is_active=true のもの。並びは club_id 昇順。"next_event_date" の定義も search_clubs と同じ。SP-55 の「3.3と同じ形」のカード表示に使う。
    例外: NotFoundError（employee_id に該当する社員が存在しない）。
    非公開の扱い: 「非公開なら他人には値を渡さない」判断はこのservice関数が行う（画面で出し分けない）。search_employees の visibility（public / self_private / hidden）と同じ考え方で、interests・available_slots の値が None のときが「他人には非公開」に当たる。名前・部署・拠点・入社年・入社区分・所属部活は常に全員に返す（SP-65）。
    実装方針: employees_repo.get_by_id・get_interests、club_members_repo.list_clubs_by_member（2.4に新規追加。その社員の所属部活ID一覧）、clubs_repo.get で部活カードdictを組み立てる。

update_public_settings(employee_id: str, requester_id: str, *, interests_public: bool | None = None, slots_public: bool | None = None) -> None
    プロフィール画面（S09）の公開・非公開の切り替え保存（SP-56。切り替えた時点で保存する）。2.1の employees_repo.update_public_settings（既出）を呼ぶservice側の入口で、新しいrepository関数は不要。
    権限: 本人のみ。requester_id が employee_id と一致しない（大文字小文字は区別しない）場合は PermissionDeniedError（運営者・幹事でも他人の公開設定は変えられない）。
    None を渡した項目は変更しない（repository と同じ）。両方 None のときは何もしない。
    例外: PermissionDeniedError / NotFoundError（employee_id に該当する社員が存在しない）。
    画面側: 画面は requester_id にログイン中の社員ID（state の employee_id）、employee_id に表示中のプロフィールの社員IDを渡す。SP-56 のとおり切り替えスイッチは本人が閲覧する場合しか出さないため、通常は両者が一致する。

save_profile(employee_id: str, requester_id: str, interests: list[dict], available_slots: list[str]) -> None
    プロフィール画面（S09）の「興味・経験」と「参加可能時間」の編集保存（SP-57、Should）。employee_interests の置き換え保存と、employees.available_slots の更新を行う。
    引数: interests は [{"activity_id": int, "level": str}, ...]（employees_repo.set_interests と同じ形）。available_slots は仕様.md 3.2 の選択肢（"平日夜" | "土曜午前" | "土曜午後" | "日曜"）の値のリスト。どちらも空リストを許す（全部外す＝0件にする）。
    権限: 本人のみ。requester_id が employee_id と一致しない場合は PermissionDeniedError。
    検証（呼び出し順に employees_repo を呼ぶ前にすべて行い、1つでも不正なら何も保存しない）:
      - interests の activity_id が activities に存在しない、level が仕様.md 3.2 の選択肢（"未経験" | "初心者" | "経験あり"）にない → ValidationError
      - interests に同じ activity_id が複数ある → ValidationError（employee_id × activity_id は重複不可。employees_repo.set_interests の「同一 activity_id は後勝ち」にはここでは頼らず、service が弾く）
      - available_slots に選択肢外の値がある、または同じ値が重複している → ValidationError
    保存: employees_repo.set_interests(employee_id, interests) と、新設の employees_repo.set_available_slots(employee_id, available_slots)（2.1）を呼ぶ。
    例外: PermissionDeniedError / ValidationError / NotFoundError（employee_id に該当する社員が存在しない）。
    注意: 2つの保存は別テーブルへの書き込みで、まとめて1トランザクションにはしない（Supabaseクライアントの制約）。検証を先に済ませるのは、不正入力で片方だけ保存される事態を避けるため。
```

### 1.7 `services/club_admin_service.py`（対応SP: SP-58〜SP-62, SP-73, SP-74）

部活管理（S10）の部活・開催・メンバーの登録と編集を担当する7本目のservice。search_service は一般社員向けの「見る」ための参照（get_club_detail など）、club_admin_service は幹事・運営者が行う部活管理の参照と更新。管理画面の編集用の取得（get_club）は表示用の get_club_detail とは別の関数で、役割を混ぜない。

権限の判定（SP-74）: 新しい権限関数は作らず、`auth_service.get_role` を使う。運営者は `get_role(requester_id) == "admin"`、その部活の幹事は `get_role(requester_id, club_id) == "organizer"`。以下で「運営者または幹事」は、どちらかが成り立つこと。どちらでもない場合は PermissionDeniedError。club_id に該当する部活が無い場合、get_role が NotFoundError を送出するため、各関数は先に NotFoundError になる。開催（event_id）を受け取る関数は events_repo.get(event_id) で club_id を求め、event_id が無ければ NotFoundError。

部活のフィールド定義（A-1裁定）:
  必須14: name, icon, activity_id, location, slot, frequency, level, fact_adult_starters, message, fee, rental, join_leave, after_activity, organizer_id
  任意4: schedule_note, fee_note, belongings_note, mood_tags（0〜3件。最大3件はDBのCHECK制約でもあるが、アプリ側でも件数と許可値を検証する。許可値は「ゆるめ」「しっかり練習」「黙々と集中」「わいわい賑やか」「おしゃべり多め」「少人数」）
  上記18項目以外に fields で受け取るのは is_active のみ（update_club で運営者だけが変更できる。create_club では受け取らず、新規作成時は true で作る）。id・updated_at など上記以外のキーが fields に含まれる場合は ValidationError。
  備考: 必須/任意の最終定義は開発仕様書v0.1で、相違があればそちらで上書きする。選択肢の許可値（location, slot, frequency, level, fact_adult_starters, fee, rental, join_leave, after_activity）は仕様.md 3.2・DBのCHECK制約と同じで、アプリ側でも事前に検証する。
  ※ DBでは icon・message は NOT NULL でないが、アプリ側では必須として検証する（上記必須14は SP-59 の「必須が空なら保存しない」に対応）。

ValidationError の理由コード（ConflictError の理由コードと同じく、例外の引数に文字列で持たせ、画面側が SP-59/SP-61 の文言を出し分ける）:
  "required:<key>"（必須項目が未入力。None・空文字・空白のみ。<key> は上のフィールド名または開催の項目名）／"past_date"（開催日が今日より前）／"end_before_start"（終了時刻が開始時刻以前。同時刻も不可）／"invalid:<key>"（選択肢外・存在しない activity_id / organizer_id・mood_tags の件数超過や許可値外）／"unknown:<key>"（fields に受け付けないキーがある）。

```
list_manageable_clubs(requester_id: str) -> list[dict]
    管理画面（S10）の部活選択の一覧（SP-58）。運営者は is_active を問わず全部活（clubs_repo.list_all_for_admin）、幹事は自分が organizer_id の部活を非公開（is_active=false）も含めて（clubs_repo.list_by_organizer）、id 昇順で返す。運営者でも幹事でもない社員には空リスト（例外にしない。サイドバーの「部活の管理」の表示可否は auth_service 側で決める）。
    各dictのキー: "club_id"(int), "name"(str), "icon"(str|None), "location"(str), "slot"(str), "organizer_id"(str), "is_active"(bool)。
    例外: なし。

get_club(club_id: int, requester_id: str) -> dict
    部活情報タブ（SP-59）の編集用に、部活の全項目を返す読み取り専用の関数。表示用の search_service.get_club_detail（幹事・メンバー・開催をまとめて返す）とは別物。
    戻り値: clubs_repo.get(club_id) の全列（仕様.md 3.1）。organizer_id と is_active を含む。主キーのみ "id" ではなく "club_id" に読み替える（"id" キーは含めない）。
    権限: 運営者または幹事。
    例外: NotFoundError / PermissionDeniedError。

create_club(requester_id: str, fields: dict) -> int
    部活の新規作成（SP-58, SP-59, SP-74）。戻り値は採番された club_id。
    権限: 運営者のみ。幹事・一般社員は PermissionDeniedError。
    fields: 上の「必須14」と「任意4」のキー。is_active は受け取らず、true で作る。必須14のどれかが未入力なら ValidationError("required:<key>")（SP-59「○○を入力してください」。複数ある場合は上の列挙順で最初の1件）。
    処理: 検証 → clubs_repo.create(data) → 幹事を所属メンバーとして club_members_repo.add_member(club_id, organizer_id) に登録する（SP-77: 幹事も club_members に入る）。
    例外: PermissionDeniedError / ValidationError。

update_club(club_id: int, requester_id: str, fields: dict) -> None
    部活情報の保存（SP-59）。fields に含めたキーだけを更新する（含めないキーは変更しない）。
    権限: 運営者、または その部活の幹事。ただし organizer_id と is_active の「変更」は運営者のみ。幹事の fields に organizer_id または is_active があり、現在の値と異なる場合は PermissionDeniedError（現在と同じ値なら変更とみなさず無視する。画面がフォーム全体を送ってもよい）。
    検証: fields に含まれる必須14のキーが空になる場合は ValidationError("required:<key>")。選択肢・mood_tags・存在確認（activity_id, organizer_id）は create_club と同じ。
    処理: clubs_repo.update(club_id, data)。organizer_id が変わった場合、新しい幹事が club_members に未登録なら add_member で登録する（前の幹事は所属メンバーのまま残す。メンバーの削除は remove_club_member の操作）。
    例外（判定の順）: NotFoundError → PermissionDeniedError → ValidationError。

list_club_events(club_id: int, requester_id: str) -> list[dict]
    開催タブ（SP-60）の一覧。今日以降の開催を日付順（同日は id 順。events_repo.list_upcoming_by_club の順序のまま）で返す。中止の開催も含む。
    各dictのキー: "event_id"(int, = events.id), "event_date"(date), "start_time"(time), "end_time"(time), "meeting_place"(str), "meeting_time"(time|None), "status"("予定" | "中止"), "applicant_count"(int)。
    "applicant_count": その開催の状態「申込済み」の申込の件数（applications_repo.list_participants(event_id) の件数。キャンセルは数えない）。
    権限: 運営者または幹事。
    例外: NotFoundError / PermissionDeniedError。

create_event(club_id: int, requester_id: str, fields: dict) -> int
    開催の追加（SP-60, SP-61）。戻り値は採番された event_id。状態は「予定」で作る。
    fields のキー: 必須 "event_date"(date), "start_time"(time), "end_time"(time), "meeting_place"(str)。任意 "meeting_time"(time|None, 集合時刻)。
    検証: 必須が未入力なら ValidationError("required:<key>")。event_date が今日より前なら ValidationError("past_date")（今日は可）。end_time <= start_time なら ValidationError("end_before_start")。判定の順は required → past_date → end_before_start。
    権限: 運営者または幹事。
    例外（判定の順）: NotFoundError（club_id）→ PermissionDeniedError → ValidationError。

update_event(event_id: int, requester_id: str, fields: dict) -> None
    開催の編集（SP-60, SP-61）。fields は create_event と同じキーで、含めたキーだけを更新する。status は fields では受け取らない（変更は set_event_status）。
    検証: create_event と同じ。end_before_start は更新後の開始・終了時刻（fields に無いキーは現在の値）で判定する。"past_date" は fields に event_date を含む場合に判定する（含めない場合、過去日の既存開催の他の項目は更新できる）。
    例外（判定の順）: NotFoundError（event_id）→ PermissionDeniedError → ValidationError。

set_event_status(event_id: int, requester_id: str, status: str) -> None
    開催の「中止にする」「予定に戻す」（SP-60, SP-73）。status は "予定" | "中止"（それ以外は ValidationError("invalid:status")）。
    権限: 運営者または幹事。
    すでに同じ状態への変更は ConflictError（引数の理由コードは "same_status"）。
    中止にしたとき（B-1裁定）: events_repo.set_status を行ったあと、その開催の状態「申込済み」の申込者全員に、service側で自動的に通知する。applications_repo.list_participants(event_id) の各申込について notification_service.notify(applicant_id, "中止", application_id=その申込の id, event_id=event_id, body="開催が中止になりました")。本文は固定文（他の種別と同じく、service内で文言を組み立てない）。申込の状態は変えない（SP-73）。「予定に戻す」ときは通知しない。
    例外（判定の順）: NotFoundError → PermissionDeniedError → ValidationError → ConflictError。

list_club_members(club_id: int, requester_id: str) -> list[dict]
    メンバータブ（SP-62, Should）の一覧。club_members_repo.list_members(club_id) の各行を employees_repo.get_by_id で解決して返す。club_members の並び順のまま。
    各dictのキー: "id"(str, 社員ID), "name", "dept", "joined_at"(date|None), "is_organizer"(bool, clubs.organizer_id と一致するか)。
    権限: 運営者または幹事。
    例外: NotFoundError / PermissionDeniedError。

add_club_member(club_id: int, requester_id: str, employee_id: str) -> None
    メンバーの追加（SP-62, Should。裁定#13）。
    権限: 運営者または幹事。
    例外（判定の順）: NotFoundError（club_id、または employee_id に該当する社員がいない）→ PermissionDeniedError → ConflictError（すでに所属している。理由コード "already_member"）。
    処理: club_members_repo.is_member で重複を確認し、add_member(club_id, employee_id)。

remove_club_member(club_id: int, requester_id: str, employee_id: str) -> None
    メンバーの削除（SP-62, Should）。
    権限: 運営者または幹事。
    例外（判定の順）: NotFoundError（club_id、または employee_id がその部活の所属メンバーでない）→ PermissionDeniedError → ConflictError（employee_id が clubs.organizer_id と一致する＝幹事は削除できない。理由コード "organizer"。幹事を外すには update_club で organizer_id を変更する）。
    処理: club_members_repo.remove_member(club_id, employee_id)。

get_last_meeting_place(club_id: int) -> str | None
    開催追加フォーム（SP-60）の集合場所の初期値（前回の開催の集合場所）。events_repo.get_last_meeting_place(club_id) を呼ぶservice入口で、screens が events_repo を直接呼ばないための関数。開催が1件もない、または club_id に該当する部活がない場合は None（例外にしない）。権限の判定はしない（初期値の読み取りのみ。管理画面は権限のある人にしか開かれない）。
list_selectable_employees(requester_id: str) -> list[dict]
    部活管理画面（S10）の社員の選択肢。「幹事を選ぶ」（SP-59）と「メンバーを追加する」（SP-62）で使う。管理操作のための一覧なので、興味・参加可能時間の公開設定（SP-65）による表示制御は掛けず、全社員を返す。
    戻り値: [{"id": str, "name": str}, ...]（全社員。キーは id と name のみ。部署などは含めない）。並びは name の昇順（文字列の昇順）、同名は id の昇順で固定する。0人なら空リスト。
    権限: 運営者または幹事。幹事は「いずれかの部活の幹事」であればよい（club_id は渡さない）ため、判定は `get_role(requester_id) == "admin"` または `auth_service.is_organizer(requester_id)`（1.1）で行う。どちらでもない社員は PermissionDeniedError。
    例外: PermissionDeniedError。
    実装方針: 新設の employees_repo.list_all()（2.1）を呼ぶ。screens が employees_repo を直接呼ばないための service 経由の入口。
```

使うrepository（新規追加は employees_repo.list_all のみ。ほかは既存）: clubs_repo（get / list_by_organizer / list_all_for_admin / create / update）、events_repo（get / list_upcoming_by_club / get_last_meeting_place / create / update / set_status）、club_members_repo（is_member / list_members / add_member / remove_member）、applications_repo（list_participants）、employees_repo（get_by_id、list_selectable_employees 用に新規追加の list_all）、activities_repo（get）。通知は notification_service.notify（1.4）。

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
set_available_slots(employee_id: str, available_slots: list[str]) -> None   # 【新規追加】SP-57（Should）。employees.available_slots を置き換え保存する。空リストは「0件にする」。検証（選択肢・重複）は service 層（profile_service.save_profile）で済ませるため、repository は値をそのまま保存する
list_departments() -> list[str]                           # 【新規追加】employees.dept の重複を除いた値を昇順で返す。部署マスタは無いため employees から導く。search_service.list_departments が呼ぶ
list_all() -> list[dict]                                  # 【新規追加】全社員の "id" と "name" を、name の昇順（同名は id の昇順）で返す。公開設定（visibility）では絞らない。0人なら空リスト。club_admin_service.list_selectable_employees が呼ぶ
```

`update_public_settings` は既出のとおり（上記）。プロフィール画面からの呼び出しは、本人確認を行う `profile_service.update_public_settings(employee_id, requester_id, ...)`（1.6）を経由する。screens から employees_repo を直接呼ばない。

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
list_members(club_id: int) -> list[dict]                # club_members の行のみ（employee_id, joined_at）。名前・部署は含まない
add_member(club_id: int, employee_id: str, joined_at=None) -> None
remove_member(club_id: int, employee_id: str) -> None
list_clubs_by_member(employee_id: str) -> list[int]       # 【新規追加】その社員が所属する部活の club_id を昇順で返す。所属なしは空リスト。profile_service.get_profile の所属部活カード用
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
list_participants(event_id: int) -> list[dict]            # 状態「申込済み」の申込を id 順で。各dictは applications の行（applicant_id, is_first_time 等）＋ "employees"（申込者の社員行）
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
