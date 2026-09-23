"""
部活コンシェルジュ MVPサンプル【見た目作り込み版】
- 機能は app.py ＋簡易ログイン・ポータル型ホーム・メッセージ・通知（デモ）。CSSを差し込んで「社内掲示板の部員募集チラシ」風にしたもの
- Streamlit 1.39 以上推奨（st.container の key を使ってCSSを当てているため）
- フォントはGoogle Fontsから読み込むので、ネット接続が必要（なければ標準フォントで表示）
実行：streamlit run app_styled.py
"""
import json
import urllib.request
from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st

st.set_page_config(page_title="部活コンシェルジュ", page_icon="📌", layout="wide")

# ---------------- デザイン（CSS） ----------------
# Streamlitは部品の見た目を直接指定できないため、CSSを文字列で差し込んで上書きしている。
# ここが「Streamlitで見た目を作り込む」ときの基本手段であり、同時に一番の制約でもある。
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Zen+Kaku+Gothic+New:wght@500;700;900&family=Noto+Sans+JP:wght@400;500;700&display=swap');

:root {
  --ink: #1F2A44;
  --muted: #5B6475;
  --board: #E6EBE4;
  --paper: #FFFFFF;
  --court: #2E7D5B;
  --tape: rgba(242, 194, 48, .85);
}

.stApp { background: var(--board); color: var(--ink); }
.stApp, .stApp p, .stApp label, .stApp input, .stApp textarea {
  font-family: 'Noto Sans JP', 'Hiragino Sans', sans-serif;
}
.stApp h1, .stApp h2, .stApp h3, .stApp h4 {
  font-family: 'Zen Kaku Gothic New', 'Hiragino Kaku Gothic ProN', sans-serif !important;
  color: var(--ink);
  letter-spacing: .02em;
}
header[data-testid="stHeader"] { background: transparent; }
[data-testid="stSidebar"] { background: var(--paper); border-right: 1px solid #D5DBD3; }

/* ボタン */
.stButton > button, .stFormSubmitButton > button {
  border-radius: 999px;
  border: 1.5px solid var(--ink);
  color: var(--ink);
  background: transparent;
  font-weight: 700;
}
.stButton > button:hover, .stFormSubmitButton > button:hover {
  border-color: var(--court); color: var(--court);
}
.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primaryFormSubmit"],
button[data-testid="stBaseButton-primary"], button[data-testid="stBaseButton-primaryFormSubmit"] {
  background: var(--court); border-color: var(--court); color: #fff;
}
.stButton > button:focus-visible { outline: 3px solid var(--tape); outline-offset: 2px; }

/* ホームの大見出し */
.hero {
  font-family: 'Zen Kaku Gothic New', sans-serif;
  font-weight: 900;
  font-size: clamp(1.9rem, 4.2vw, 3.2rem);
  line-height: 1.3;
  margin: .5rem 0 .4rem;
  color: var(--ink);
}
.hero-sub { color: var(--muted); font-size: 1.05rem; margin-bottom: 1.6rem; }
.hero-tagline { font-family: 'Zen Kaku Gothic New', sans-serif; font-weight: 700;
                font-size: clamp(1.05rem, 1.8vw, 1.35rem); color: var(--ink); margin-bottom: .8rem; }

/* 部活カード＝部員募集のチラシ */
[class*="st-key-flyer_"] {
  position: relative;
  background: var(--paper);
  padding: 1.5rem 1.2rem 1rem;
  border-radius: 3px;
  box-shadow: 0 1px 0 rgba(31,42,68,.08), 0 10px 18px -14px rgba(31,42,68,.45);
  transform: rotate(-0.7deg);
  margin: .9rem .2rem 1.2rem;
}
[data-testid="stColumn"]:nth-child(2n) [class*="st-key-flyer_"],
[data-testid="column"]:nth-child(2n) [class*="st-key-flyer_"] { transform: rotate(0.8deg); }
[class*="st-key-flyer_"]::before {
  content: "";
  position: absolute;
  top: -10px; left: 50%;
  width: 76px; height: 20px;
  background: var(--tape);
  transform: translateX(-50%) rotate(-3deg);
}
.flyer-title { font-family: 'Zen Kaku Gothic New', sans-serif; font-weight: 900; font-size: 1.45rem; }
.flyer-meta { color: var(--muted); font-size: .88rem; margin: .2rem 0 .6rem; }
.flyer-next { font-size: .9rem; margin-top: .3rem; }

/* 白い台紙（検索条件・プロフィールなど） */
[class*="st-key-panel_"] {
  background: var(--paper);
  border-radius: 12px;
  padding: 1rem 1.2rem .6rem;
  margin-bottom: 1rem;
}

/* タグ */
.chip { display: inline-block; padding: 2px 11px; border-radius: 999px;
        font-size: .78rem; font-weight: 700; margin: 0 6px 6px 0; }
.chip-beg  { background: #DDEFE5; color: #1E5E43; }
.chip-solo { background: #FFF1C2; color: #6E5200; }
.chip-exp  { background: #E3E6EE; color: var(--ink); }
.chip-same { background: #DDEFE5; color: #1E5E43; }

/* 部活詳細の要項 */
.spec { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
        gap: .6rem; margin: .8rem 0 1.4rem; }
.spec div { background: var(--paper); border-radius: 10px; padding: .7rem .9rem; }
.spec span { display: block; color: var(--muted); font-size: .78rem; }
.spec b { font-size: 1.05rem; }

.person { font-weight: 700; }
.person-sub { color: var(--muted); font-size: .85rem; }

/* 画面の横幅を抑えて、カードやボタンが間延びしないようにする */
.block-container, [data-testid="stMainBlockContainer"] { max-width: 1120px; }

/* ボタンの文字を読みやすく */
.stButton > button { min-height: 2.6rem; }
.stButton > button p, .stFormSubmitButton > button p { font-size: .95rem; font-weight: 700; }

/* ホームの大きなボタン2つ */
.st-key-big_club .stButton > button, .st-key-big_emp .stButton > button {
  min-height: 5.5rem; border-radius: 18px;
}
.st-key-big_club .stButton > button p, .st-key-big_emp .stButton > button p {
  font-family: 'Zen Kaku Gothic New', sans-serif; font-size: 1.4rem; font-weight: 900;
}
.st-key-big_emp .stButton > button { background: var(--ink); border-color: var(--ink); color: #fff; }
.st-key-big_emp .stButton > button:hover { background: #2C3A5C; border-color: #2C3A5C; color: #fff; }

/* 文字リンク風のボタン（カードの「詳しく見る」など、目立たせすぎたくないもの） */
[class*="st-key-lnk_"] .stButton > button {
  border: none; background: transparent; min-height: auto; padding: .1rem 0; color: var(--court);
}
[class*="st-key-lnk_"] .stButton > button p {
  font-size: .9rem; text-decoration: underline; text-underline-offset: 3px;
}
[class*="st-key-lnk_"] .stButton > button:hover { color: var(--ink); background: transparent; }

/* 今週開催の小さめチラシ */
[class*="st-key-flyer_week"] .flyer-title { font-size: 1.15rem; }
[class*="st-key-flyer_week"] { padding: 1.3rem 1rem .8rem; }

/* 体験参加予定・メッセージの状態 */
.flyer-trial { font-size: .85rem; font-weight: 700; color: var(--court); margin-top: .2rem; }
.chip-wait { background: #FFF1C2; color: #6E5200; }
.chip-done { background: #DDEFE5; color: #1E5E43; }

/* 人気ランキング */
.rank { display: flex; gap: .8rem; align-items: center; }
.rank-no { font-family: 'Zen Kaku Gothic New', sans-serif; font-weight: 900; font-size: 1.8rem;
           color: var(--court); width: 1.6rem; text-align: center; }

/* 台紙の下で文字が切れないように余白を確保し、行と行の間隔を広げる */
[class*="st-key-panel_"] { padding-bottom: 1.6rem; }
[class*="st-key-panel_"] [data-testid="stHorizontalBlock"] { margin-bottom: .5rem; }
.person-sub { padding-bottom: .2rem; }

/* タブの選択色をアプリの緑に揃える（標準は赤） */
.stTabs [data-baseweb="tab"][aria-selected="true"] p { color: var(--court); font-weight: 700; }
.stTabs [data-baseweb="tab-highlight"] { background-color: var(--court); }

@media (prefers-reduced-motion: reduce) { * { transition: none !important; } }
</style>
""", unsafe_allow_html=True)

SLOTS = ["平日夜", "土曜午前", "土曜午後", "日曜"]
LOCS = ["東京", "大阪"]
LEVELS = ["初心者歓迎", "レベル問わず", "経験者向け"]


# ---------------- ダミーデータ（app.pyと同じ） ----------------
def init_data():
    def emp(i, name, dept, loc, entry, interests, level, times, pub=(True, True, True)):
        return dict(id=i, name=name, dept=dept, loc=loc, entry=entry,
                    interests=interests, level=level, times=times,
                    public=dict(interests=pub[0], level=pub[1], times=pub[2]))

    employees = [
        emp(1, "山田 花子", "営業部", "東京", "新卒", ["テニス", "ランニング"], "初心者", ["平日夜", "土曜午前"]),
        emp(2, "佐藤 健", "開発部", "東京", "中途", ["麻雀", "ボードゲーム"], "経験あり", ["平日夜"], (True, False, True)),
        emp(3, "鈴木 美咲", "人事部", "東京", "新卒", ["テニス", "ヨガ"], "経験あり", ["土曜午前"]),
        emp(4, "高橋 翔", "開発部", "大阪", "異動", ["フットサル", "ランニング"], "経験あり", ["平日夜", "日曜"]),
        emp(5, "田中 由佳", "マーケティング部", "東京", "中途", ["テニス", "ボードゲーム"], "初心者", ["土曜午前"], (True, True, False)),
        emp(6, "伊藤 大輔", "営業部", "大阪", "新卒", ["フットサル", "ボードゲーム"], "初心者", ["日曜"]),
        emp(7, "渡辺 さくら", "総務部", "東京", "中途", ["ヨガ", "ランニング"], "経験あり", ["平日夜"]),
        emp(8, "中村 蓮", "開発部", "東京", "新卒", ["麻雀", "テニス"], "初心者", ["平日夜", "土曜午前"]),
        emp(9, "小林 愛", "営業部", "大阪", "中途", ["ヨガ"], "初心者", ["平日夜"], (False, False, True)),
        emp(10, "加藤 拓也", "マーケティング部", "大阪", "異動", ["ボードゲーム", "フットサル"], "経験あり", ["平日夜"]),
        emp(11, "吉田 真央", "人事部", "大阪", "新卒", ["ランニング"], "初心者", ["日曜"]),
        emp(12, "山本 隼人", "開発部", "東京", "中途", ["ランニング", "麻雀"], "経験あり", ["平日夜", "日曜"]),
    ]

    def club(i, icon, name, category, activity, loc, slot, schedule, freq, level, solo,
             organizer, members, nxt, dates, desc, first_time):
        return dict(id=i, icon=icon, name=name, category=category, activity=activity, loc=loc,
                    slot=slot, schedule=schedule, freq=freq, level=level, solo=solo,
                    organizer=organizer, members=members, next=nxt, dates=dates,
                    desc=desc, first_time=first_time)

    clubs = [
        club(1, "🎾", "テニス部", "スポーツ", "テニス", "東京", "土曜午前", "土曜 10:00〜12:00", "月2回",
             "初心者歓迎", True, 3, [3, 5, 8, 1], "9/26（土）", ["9/26（土）", "10/10（土）"],
             "半分以上が社会人になってから始めたメンバーです。ラリーが続かなくても大丈夫。終わったら近くでランチすることが多いです。",
             "ラケットは貸し出しあり。動きやすい服と運動靴だけ持ってきてください。当日は幹事が入口で待っています。"),
        club(2, "🏃", "ランニング部", "スポーツ", "ランニング", "東京", "平日夜", "水曜 19:00〜20:00", "毎週",
             "レベル問わず", True, 12, [12, 7, 1], "9/30（水）", ["9/30（水）", "10/7（水）"],
             "皇居周りを各自のペースで走ります。歩いてもOK。途中参加・途中離脱も自由です。",
             "オフィス1階に18:50集合。着替えは近くのランステーションを使っています。"),
        club(3, "🀄", "麻雀部", "ゲーム", "麻雀", "東京", "平日夜", "金曜 19:00〜", "月2回",
             "初心者歓迎", True, 2, [2, 8, 12], "10/2（金）", ["10/2（金）", "10/16（金）"],
             "ノーレート・健全麻雀です。役が分からなくても、経験者が横について教えます。",
             "最初の30分はルール説明の時間。点数計算は覚えなくて大丈夫です。"),
        club(4, "⚽", "フットサル部", "スポーツ", "フットサル", "大阪", "日曜", "日曜 10:00〜12:00", "月1回",
             "経験者向け", False, 4, [4, 6, 10], "10/4（日）", ["10/4（日）", "11/1（日）"],
             "経験者中心でゲーム形式が多めです。人数が足りないときは他社チームと合同で行うこともあります。",
             "初回はメンバーの紹介で来る方が多いです。気になる方は幹事に一度メッセージを。"),
        club(5, "🧘", "ヨガ部", "ウェルネス", "ヨガ", "東京", "平日夜", "木曜 19:00〜20:00", "月2回",
             "初心者歓迎", True, 7, [7, 3], "10/1（木）", ["10/1（木）", "10/15（木）"],
             "会議室でゆったり行うヨガです。仕事終わりにリセットしたい人向け。",
             "マットは貸し出しあり。着替えられる服を持ってきてください。"),
        club(6, "🎲", "ボードゲーム部", "ゲーム", "ボードゲーム", "大阪", "平日夜", "火曜 19:00〜21:00", "月2回",
             "初心者歓迎", True, 10, [10, 6], "9/29（火）", ["9/29（火）", "10/13（火）"],
             "軽いゲームから重いゲームまで。毎回1時間目は初めての人でもすぐ遊べるゲームにしています。",
             "会議室Bで開催。途中からの参加もOKです。"),
    ]
    # --- 追加の部活 ---
    clubs += [
        club(7, "🏀", "バスケ部", "スポーツ", "バスケットボール", "東京", "日曜", "日曜 13:00〜15:00", "月2回",
             "経験者向け", True, 12, [12, 8, 5], "", ["", "10/11（日）"],
             "学生時代の経験者が中心。試合形式でしっかり動きます。ブランクがある人も歓迎です。",
             "体育館シューズを持ってきてください。最初の30分はシュート練習なので、体を慣らしてから参加できます。"),
        club(8, "⛳", "ゴルフ部", "スポーツ", "ゴルフ", "大阪", "土曜午後", "土曜 13:00〜", "月1回",
             "経験者向け", True, 10, [10, 4], "", ["", "11/14（土）"],
             "コースを回れる人向け。打ちっぱなしの回もあるので、気になる人は幹事に相談を。",
             "コースの回は幹事が組み合わせを決めます。クラブのレンタルもできます。"),
    ]

    # --- 次回日程（「今週開催」の判定用）と、今月の体験参加数（ランキング用のダミー） ---
    next_dates = {1: date(2026, 9, 26), 2: date(2026, 9, 30), 3: date(2026, 9, 25), 4: date(2026, 10, 4),
                  5: date(2026, 9, 24), 6: date(2026, 9, 29), 7: date(2026, 9, 27), 8: date(2026, 10, 10)}
    trials = {1: 5, 2: 1, 3: 4, 4: 0, 5: 3, 6: 2, 7: 2, 8: 1}
    for c in clubs:
        d = next_dates[c["id"]]
        c["next_date"] = d
        c["next"] = f"{d.month}/{d.day}（{'月火水木金土日'[d.weekday()]}）"
        c["dates"][0] = c["next"]
        c["trials"] = trials[c["id"]]

    return {e["id"]: e for e in employees}, {c["id"]: c for c in clubs}


if "employees" not in st.session_state:
    st.session_state.employees, st.session_state.clubs = init_data()
    st.session_state.page = "home"
    st.session_state.club_id = None
    st.session_state.emp_id = None
    # 申込データ：1件の申込に、申込者と幹事のメッセージのやり取りがぶら下がる形
    st.session_state.applications = [
        {"id": 1, "club_id": 1, "applicant": 7, "date": "9/26（土）", "applied_at": "09/22 12:10",
         "messages": [{"from": 7, "text": "テニスは学生以来です。ラケットはお借りできますか？", "at": "09/22 12:10"}]},
        {"id": 2, "club_id": 1, "applicant": 2, "date": "9/26（土）", "applied_at": "09/21 18:40",
         "messages": [{"from": 2, "text": "完全な初心者ですが大丈夫でしょうか。", "at": "09/21 18:40"},
                      {"from": 3, "text": "大丈夫です！当日は入口で待っていますね。", "at": "09/21 20:05"}]},
        {"id": 3, "club_id": 3, "applicant": 1, "date": "9/25（金）", "applied_at": "09/20 09:30",
         "messages": [{"from": 1, "text": "役がほとんど分からないのですが、参加できますか？", "at": "09/20 09:30"},
                      {"from": 2, "text": "もちろんです！最初の30分でルールを説明するので安心してください。", "at": "09/20 12:15"}]},
    ]
    st.session_state.user_id = None  # ログイン中の社員（未ログインはNone）
    st.session_state.notify_log = []  # 送った通知の記録
    st.session_state.toasts = []  # 次の画面表示で出すお知らせ

EMP = st.session_state.employees
CLUB = st.session_state.clubs
APPS = st.session_state.applications

DEMO_PASSWORD = "demo"  # 簡易ログイン用。本物の認証ではない（全員共通のダミー）


def emp_code(emp_id):
    return f"E{emp_id:03d}"


# ---------------- 簡易ログイン ----------------
def login(code, password):
    for e in EMP.values():
        if emp_code(e["id"]) == code.strip().upper() and password == DEMO_PASSWORD:
            st.session_state.user_id = e["id"]
            st.session_state.page = "home"
            return True
    return False


def logout():
    st.session_state.user_id = None
    st.session_state.page = "home"


if st.session_state.user_id is None:
    st.markdown('<div class="hero">部活コンシェルジュ</div><div class="hero-tagline">社内の人と部活をつなぐ検索・マッチングサービス</div>', unsafe_allow_html=True)
    _, center, _ = st.columns([1, 2, 1])
    with center, st.container(key="panel_login"):
        st.markdown("### ログイン")
        with st.form("login_form", border=False):
            code = st.text_input("社員ID", placeholder="例：E001")
            password = st.text_input("パスワード", type="password")
            if st.form_submit_button("ログインする", type="primary", use_container_width=True):
                if login(code, password):
                    st.rerun()
                else:
                    st.error("社員IDかパスワードが違います。入力内容を確認してください。")
        st.caption(f"デモ用：社員ID E001〜E{len(EMP):03d}／パスワード {DEMO_PASSWORD}")
    st.stop()  # ログインするまで、ここから下は表示しない

# 前の操作で予約されたお知らせを表示（st.rerun()の直前に出すと消えてしまうため）
while st.session_state.toasts:
    st.toast(st.session_state.toasts.pop(0), icon="📨")


# ---------------- 共通関数 ----------------
def go(page, club_id=None, emp_id=None):
    st.session_state.page = page
    if club_id is not None:
        st.session_state.club_id = club_id
    if emp_id is not None:
        st.session_state.emp_id = emp_id


def clubs_of(emp_id):
    return [c for c in CLUB.values() if emp_id in c["members"]]


def is_public(emp, field):
    return emp["public"][field]


def now():
    return datetime.now().strftime("%m/%d %H:%M")


def apps_of_club(club_id):
    return [a for a in APPS if a["club_id"] == club_id]


def needs_reply(a):
    """最後のメッセージが申込者からなら、幹事の返信待ち"""
    return a["messages"][-1]["from"] == a["applicant"]


# ---------------- 通知 ----------------
# 通知先は .streamlit/secrets.toml に書く。書いていなければ「デモモード」で、実際には送らない。
#   [notify]
#   webhook_url = "https://hooks.slack.com/services/xxxx"  # SlackやTeamsなどの受信用URL
# ※Webhookは基本的に「チャンネルへの投稿」。個人へのDMにするには、ツールごとに別の設定が必要。
def notify_config():
    try:
        return st.secrets.get("notify", {})
    except Exception:  # secrets.toml が無いとき
        return {}


def send_webhook(url, text):
    """Webhookに通知を送る。Slackは {"text": ...} の形で受け取れる（Teamsは形式の調整が必要）"""
    req = urllib.request.Request(url, data=json.dumps({"text": text}).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=5)


def notify(to_id, text):
    """to_id の社員に通知する。結果はログに残し、画面にお知らせを出す"""
    to = EMP[to_id]
    url = notify_config().get("webhook_url")
    if not url:
        result = "デモ（未送信）"
    else:
        try:
            send_webhook(url, f"{to['name']}さんへ：{text}")
            result = "送信成功"
        except Exception:
            result = "送信失敗"
    st.session_state.notify_log.insert(0, {"日時": now(), "宛先": to["name"], "内容": text, "結果": result})
    st.session_state.toasts.append(f"{to['name']}さんに通知しました（{result}）")


def unreplied_count(user_id):
    """自分が幹事の部活で、まだ返信していない申込の数"""
    return sum(needs_reply(a) for a in APPS if CLUB[a["club_id"]]["organizer"] == user_id)


def chips(c):
    level_cls = {"初心者歓迎": "chip-beg", "レベル問わず": "chip-beg", "経験者向け": "chip-exp"}[c["level"]]
    html = f'<span class="chip {level_cls}">{c["level"]}</span>'
    if c["solo"]:
        html += '<span class="chip chip-solo">1人参加OK</span>'
    return html


def club_card(c, prefix):
    with st.container(key=f"flyer_{prefix}_{c['id']}"):
        st.markdown(f"""
<div class="flyer-title">{c['icon']} {c['name']}</div>
<div class="flyer-meta">{c['loc']}／{c['schedule']}／{c['freq']}</div>
<div>{chips(c)}</div>
<div class="flyer-next">次回 <b>{c['next']}</b>　メンバー {len(c['members'])}名</div>
{f'<div class="flyer-trial">体験参加予定 {len(apps_of_club(c["id"]))}名</div>' if apps_of_club(c["id"]) else ''}
""", unsafe_allow_html=True)
        st.button("詳しく見る", key=f"lnk_{prefix}_club_{c['id']}", on_click=go,
                  args=("club_detail",), kwargs={"club_id": c["id"]})


# ---------------- サイドバー ----------------
with st.sidebar:
    st.markdown("## 📌 部活コンシェルジュ")
    user_id = st.session_state.user_id
    me_side = EMP[user_id]
    st.markdown(f'<div class="person">{me_side["name"]}</div>'
                f'<div class="person-sub">{me_side["dept"]}・{emp_code(user_id)}</div>',
                unsafe_allow_html=True)
    st.button("ログアウト", on_click=logout, use_container_width=True)
    st.divider()
    st.button("ホーム", on_click=go, args=("home",), use_container_width=True)
    st.button("部活を探す", on_click=go, args=("club_search",), use_container_width=True)
    st.button("人を探す", on_click=go, args=("emp_search",), use_container_width=True)
    n_unreplied = unreplied_count(user_id)
    st.button("メッセージ" + (f"（未返信 {n_unreplied}）" if n_unreplied else ""),
              on_click=go, args=("messages",), use_container_width=True)
    st.button("自分のプロフィール", on_click=go, args=("profile",),
              kwargs={"emp_id": user_id}, use_container_width=True)
    st.divider()
    with st.expander(f"申込データ（{len(APPS)}件）"):
        if APPS:
            st.dataframe(pd.DataFrame([{
                "申込日時": a["applied_at"], "部活": CLUB[a["club_id"]]["name"],
                "申込者": EMP[a["applicant"]]["name"], "希望日": a["date"],
                "メッセージ数": len(a["messages"]),
                "状態": "返信待ち" if needs_reply(a) else "返信済み"} for a in APPS]), hide_index=True)
        else:
            st.caption("まだ申込はありません")
        st.caption("サンプルのためDB保存なし。再読み込みで消えます")
    log = st.session_state.notify_log
    with st.expander(f"通知ログ（{len(log)}件）"):
        mode = "送信モード" if notify_config().get("webhook_url") else "デモモード（実際には送信しません）"
        st.caption(mode)
        if log:
            st.dataframe(pd.DataFrame(log), hide_index=True)
        else:
            st.caption("まだ通知はありません")


# ---------------- 各画面 ----------------
DEMO_TODAY = date(2026, 9, 23)  # デモ用の「今日」。本番では date.today() にする


def trial_count(c):
    """今月の体験参加数＝ダミーの件数＋このアプリで申し込まれた件数"""
    return c["trials"] + len(apps_of_club(c["id"]))


def club_line(c, key):
    """ランキングやタブの中で使う、1行の部活表示"""
    a, b = st.columns([4, 1], vertical_alignment="center")
    a.markdown(f'<div class="person">{c["icon"]} {c["name"]}</div>'
               f'<div class="person-sub">{c["loc"]}／{c["schedule"]}</div>', unsafe_allow_html=True)
    b.button("見る", key=key, on_click=go, args=("club_detail",), kwargs={"club_id": c["id"]})


def page_home():
    me = EMP[st.session_state.user_id]
    st.markdown(f"""
<div class="hero">部活コンシェルジュ</div><div class="hero-tagline">社内の人と部活をつなぐ検索・マッチングサービス</div>
<div class="hero-sub">{me['name'].split()[1]}さん、今週はどの部活をのぞいてみますか？</div>
""", unsafe_allow_html=True)

    # 大きなボタン2つ
    c1, c2 = st.columns(2, gap="medium")
    c1.button("🔍　部活を探す", key="big_club", on_click=go, args=("club_search",),
              type="primary", use_container_width=True)
    c1.caption("活動・場所・曜日・レベルから、自分に合う部活を見つける")
    c2.button("👥　人を探す", key="big_emp", on_click=go, args=("emp_search",),
              use_container_width=True)
    c2.caption("名前や興味、所属部活から、部署の外にいる人を知る")

    # 今週開催の部活
    monday = DEMO_TODAY - timedelta(days=DEMO_TODAY.weekday())
    sunday = monday + timedelta(days=6)
    week = sorted([c for c in CLUB.values() if monday <= c["next_date"] <= sunday],
                  key=lambda c: c["next_date"])
    st.markdown(f"### 今週開催の部活（{len(week)}件）")
    if not week:
        st.caption("今週開催の部活はありません。「部活を探す」から来週以降の予定を見てみてください。")
    cols = st.columns(4, gap="medium")
    for i, c in enumerate(week):
        with cols[i % 4]:
            club_card(c, "week")

    # 人気ランキング ＋ 初心者向け／経験者向け
    left, right = st.columns(2, gap="large")
    with left, st.container(key="panel_rank"):
        st.markdown("### 今月の人気部活")
        st.caption("今月の体験参加が多い部活")
        ranking = sorted(CLUB.values(), key=trial_count, reverse=True)[:3]
        for i, c in enumerate(ranking, 1):
            a, b = st.columns([4, 1], vertical_alignment="center")
            a.markdown(f'<div class="rank"><span class="rank-no">{i}</span><div>'
                       f'<div class="person">{c["icon"]} {c["name"]}</div>'
                       f'<div class="person-sub">体験参加 {trial_count(c)}名・{c["loc"]}</div></div></div>',
                       unsafe_allow_html=True)
            b.button("見る", key=f"lnk_rank_{c['id']}", on_click=go,
                     args=("club_detail",), kwargs={"club_id": c["id"]})

    with right, st.container(key="panel_level"):
        t1, t2 = st.tabs(["初心者向け", "経験者向け"])
        for tab, level, prefix in [(t1, "初心者歓迎", "beg"), (t2, "経験者向け", "exp")]:
            with tab:
                for c in [c for c in CLUB.values() if c["level"] == level]:
                    club_line(c, f"lnk_{prefix}_{c['id']}")


def page_club_search():
    st.markdown("# 部活を探す")
    with st.container(key="panel_filter"):
        c1, c2, c3 = st.columns(3)
        cats = c1.multiselect("活動カテゴリ", sorted({c["category"] for c in CLUB.values()}))
        locs = c2.multiselect("拠点", LOCS)
        slots = c3.multiselect("曜日・時間帯", SLOTS)
        c4, c5, c6 = st.columns(3)
        level = c4.selectbox("レベル", ["指定なし"] + LEVELS)
        kw = c5.text_input("キーワード", placeholder="例：テニス")
        c6.write("")
        solo = c6.checkbox("1人参加OKのみ")

    result = [
        c for c in CLUB.values()
        if (not cats or c["category"] in cats)
        and (not locs or c["loc"] in locs)
        and (not slots or c["slot"] in slots)
        and (level == "指定なし" or c["level"] == level)
        and (not solo or c["solo"])
        and (not kw or kw in c["name"] + c["activity"] + c["desc"])
    ]
    st.write(f"**{len(result)}件** の部活が見つかりました")
    if not result:
        st.info("条件に合う部活がありません。条件を減らして探してみてください。")
    cols = st.columns(3, gap="large")
    for i, c in enumerate(result):
        with cols[i % 3]:
            club_card(c, "search")


def page_club_detail():
    c = CLUB[st.session_state.club_id]
    me_id = st.session_state.user_id
    me = EMP[me_id]

    st.button("← 部活一覧に戻る", on_click=go, args=("club_search",))
    st.markdown(f"# {c['icon']} {c['name']}")
    st.markdown(chips(c), unsafe_allow_html=True)
    st.markdown(f"""
<div class="spec">
  <div><span>拠点</span><b>{c['loc']}</b></div>
  <div><span>日時</span><b>{c['schedule']}</b></div>
  <div><span>頻度</span><b>{c['freq']}</b></div>
  <div><span>次回</span><b>{c['next']}</b></div>
</div>
""", unsafe_allow_html=True)

    left, right = st.columns([3, 2], gap="large")
    with left:
        with st.container(key="panel_about"):
            st.markdown("### どんな部活？")
            st.write(c["desc"])
            st.markdown("### 初参加の流れ")
            st.write(c["first_time"])

        with st.container(key="panel_apply"):
            st.markdown("### 体験参加を申し込む")
            applied = any(a["club_id"] == c["id"] and a["applicant"] == me_id for a in APPS)
            if me_id in c["members"]:
                st.success("あなたはこの部活のメンバーです")
            elif applied:
                st.info("申し込み済みです。幹事とのやり取りは「メッセージ」で確認できます。")
                st.button("メッセージを見る", key="to_messages", on_click=go, args=("messages",))
            else:
                with st.form(f"apply_{c['id']}", border=False):
                    wish = st.selectbox("参加希望日", c["dates"])
                    msg = st.text_area("幹事への一言・質問（任意）",
                                       placeholder="例：学生以来で久しぶりです。道具がなくても参加できますか？")
                    st.caption("申し込むと幹事に届き、返信は「メッセージ」で確認できます。")
                    if st.form_submit_button("体験参加を申し込む", type="primary"):
                        t = now()
                        text = msg.strip() or "体験参加を申し込みました。よろしくお願いします。"
                        APPS.append({"id": max((a["id"] for a in APPS), default=0) + 1,
                                     "club_id": c["id"], "applicant": me_id, "date": wish, "applied_at": t,
                                     "messages": [{"from": me_id, "text": text, "at": t}]})
                        notify(c["organizer"],
                               f"{me['name']}さんから{c['name']}の体験参加申込がありました（希望日 {wish}）。"
                               f"メッセージ：{text}")
                        st.rerun()

    with right:
        org = EMP[c["organizer"]]
        with st.container(key="panel_org"):
            st.markdown("### 幹事")
            st.markdown(f'<div class="person">{org["name"]}</div>'
                        f'<div class="person-sub">{org["dept"]}・{org["loc"]}・{org["entry"]}入社</div>',
                        unsafe_allow_html=True)
            st.button("幹事のプロフィールを見る", key="org_profile", on_click=go,
                      args=("profile",), kwargs={"emp_id": org["id"]})

        with st.container(key="panel_members"):
            st.markdown(f"### 参加メンバー（{len(c['members'])}名）")
            newcomers = sum(EMP[m]["entry"] in ("中途", "異動") for m in c["members"])
            trial = len(apps_of_club(c["id"]))
            st.caption(f"中途入社・異動のメンバー：{newcomers}名")
            if trial:
                st.markdown(f'<div class="flyer-trial">初めての人が {trial}名 体験参加予定です</div>',
                            unsafe_allow_html=True)
            for mid in c["members"]:
                m = EMP[mid]
                badge = ""
                if mid == me_id:
                    badge = '<span class="chip chip-exp">あなた</span>'
                elif m["dept"] == me["dept"]:
                    badge = '<span class="chip chip-same">同じ部署</span>'
                a, b = st.columns([3, 1])
                a.markdown(f'<div class="person">{m["name"]} {badge}</div>'
                           f'<div class="person-sub">{m["dept"]}</div>', unsafe_allow_html=True)
                b.button("見る", key=f"mem_{mid}", on_click=go, args=("profile",), kwargs={"emp_id": mid})


def page_emp_search():
    st.markdown("# 人を探す")
    st.caption("興味・経験・参加可能時間は、本人が公開ONにしたものだけが検索・表示されます")
    with st.container(key="panel_empfilter"):
        c1, c2, c3 = st.columns(3)
        name = c1.text_input("名前（部分一致）", placeholder="例：山田")
        depts = c2.multiselect("部署", sorted({e["dept"] for e in EMP.values()}))
        locs = c3.multiselect("拠点", LOCS)
        c4, c5, c6 = st.columns(3)
        interests = c4.multiselect("興味", sorted({i for e in EMP.values() for i in e["interests"]}))
        club_name = c5.selectbox("所属部活", ["指定なし"] + [c["name"] for c in CLUB.values()])
        times = c6.multiselect("参加可能時間", SLOTS)

    def match(e):
        if name and name.replace(" ", "") not in e["name"].replace(" ", ""):
            return False
        if depts and e["dept"] not in depts:
            return False
        if locs and e["loc"] not in locs:
            return False
        if interests and not (is_public(e, "interests") and set(interests) & set(e["interests"])):
            return False
        if club_name != "指定なし" and club_name not in [c["name"] for c in clubs_of(e["id"])]:
            return False
        if times and not (is_public(e, "times") and set(times) & set(e["times"])):
            return False
        return True

    result = [e for e in EMP.values() if match(e)]
    st.write(f"**{len(result)}名** 見つかりました")
    if not result:
        st.info("条件に合う人がいません。条件を減らして探してみてください。")
    cols = st.columns(3, gap="medium")
    for i, e in enumerate(result):
        with cols[i % 3], st.container(key=f"panel_emp_{e['id']}"):
            interest_txt = "、".join(e["interests"]) if is_public(e, "interests") else "非公開"
            club_txt = "、".join(c["name"] for c in clubs_of(e["id"])) or "なし"
            st.markdown(f"""
<div class="person" style="font-size:1.15rem">{e['name']}</div>
<div class="person-sub">{e['dept']}・{e['loc']}・{e['entry']}入社</div>
<p style="margin:.6rem 0 .2rem">興味：{interest_txt}<br>所属：{club_txt}</p>
""", unsafe_allow_html=True)
            st.button("プロフィールを見る", key=f"emp_{e['id']}", on_click=go,
                      args=("profile",), kwargs={"emp_id": e["id"]}, use_container_width=True)


def show_thread(a, viewer_id):
    """1件の申込のメッセージのやり取りを表示し、返信欄を出す"""
    for m in a["messages"]:
        mine = m["from"] == viewer_id
        with st.chat_message("user" if mine else "assistant", avatar="🙂" if mine else "👤"):
            st.markdown(f'<span class="person">{EMP[m["from"]]["name"]}</span>'
                        f'　<span class="person-sub">{m["at"]}</span>', unsafe_allow_html=True)
            st.write(m["text"])
    with st.form(f"reply_{a['id']}_{viewer_id}", clear_on_submit=True, border=False):
        text = st.text_area("メッセージを送る", height=80, label_visibility="collapsed",
                            placeholder="メッセージを入力")
        if st.form_submit_button("送信する"):
            if text.strip():
                a["messages"].append({"from": viewer_id, "text": text.strip(), "at": now()})
                club_ = CLUB[a["club_id"]]
                to_id = club_["organizer"] if viewer_id == a["applicant"] else a["applicant"]
                notify(to_id, f"{club_['name']}の体験参加について、{EMP[viewer_id]['name']}さんから"
                              f"メッセージが届きました：{text.strip()}")
                st.rerun()
            else:
                st.warning("メッセージを入力してから送信してください。")


def page_messages():
    me_id = st.session_state.user_id
    st.markdown("# メッセージ")

    my_apps = [a for a in APPS if a["applicant"] == me_id]
    received = [a for a in APPS if CLUB[a["club_id"]]["organizer"] == me_id]
    is_organizer = any(c["organizer"] == me_id for c in CLUB.values())

    # タブ名に件数を入れると、返信で件数が変わったときにタブが先頭に戻ってしまうので固定の名前にする
    labels = ["自分の申込"] + (["届いた申込（幹事）"] if is_organizer else [])
    tabs = st.tabs(labels)

    with tabs[0]:
        if not my_apps:
            st.caption("まだ体験参加の申込はありません。「部活を探す」から気になる部活を見つけてみてください。")
        for a in sorted(my_apps, key=lambda a: a["applied_at"], reverse=True):
            c = CLUB[a["club_id"]]
            org = EMP[c["organizer"]]
            status = ('<span class="chip chip-wait">幹事の返信待ち</span>' if needs_reply(a)
                      else '<span class="chip chip-done">幹事から返信あり</span>')
            with st.container(key=f"panel_mine_{a['id']}"):
                st.markdown(f'<div class="person" style="font-size:1.1rem">{c["icon"]} {c["name"]}　{status}</div>'
                            f'<div class="person-sub">希望日 {a["date"]}・幹事 {org["name"]}</div>',
                            unsafe_allow_html=True)
                with st.expander(f"やり取りを見る（{len(a['messages'])}件）", expanded=not needs_reply(a)):
                    show_thread(a, me_id)

    if is_organizer:
        with tabs[1]:
            st.caption(f"未返信 {sum(needs_reply(a) for a in received)}件")
            if not received:
                st.caption("まだ届いた申込はありません。")
            for a in sorted(received, key=lambda a: (not needs_reply(a), a["applied_at"])):
                c = CLUB[a["club_id"]]
                applicant = EMP[a["applicant"]]
                status = ('<span class="chip chip-wait">未返信</span>' if needs_reply(a)
                          else '<span class="chip chip-done">返信済み</span>')
                with st.container(key=f"panel_recv_{a['id']}"):
                    st.markdown(f'<div class="person" style="font-size:1.1rem">{applicant["name"]}さん　{status}</div>'
                                f'<div class="person-sub">{c["icon"]} {c["name"]}・希望日 {a["date"]}・'
                                f'{applicant["dept"]}・{applicant["entry"]}入社</div>', unsafe_allow_html=True)
                    with st.expander(f"やり取りを見る（{len(a['messages'])}件）", expanded=needs_reply(a)):
                        show_thread(a, me_id)


def set_public(emp_id, field):
    EMP[emp_id]["public"][field] = st.session_state[f"pub_{emp_id}_{field}"]


def page_profile():
    e = EMP[st.session_state.emp_id]
    is_me = e["id"] == st.session_state.user_id

    st.button("← 人を探すに戻る", on_click=go, args=("emp_search",))
    st.markdown(f"# {e['name']}" + ("（あなた）" if is_me else ""))
    st.caption(f"{e['dept']}・{e['loc']}・{e['entry']}入社")

    fields = [("interests", "興味", "、".join(e["interests"])),
              ("level", "経験レベル", e["level"]),
              ("times", "参加可能時間", "、".join(e["times"]))]

    left, right = st.columns([3, 2], gap="large")
    with left:
        with st.container(key="panel_profile"):
            st.markdown("### プロフィール")
            for field, label, value in fields:
                if is_public(e, field):
                    st.write(f"**{label}**：{value}")
                elif is_me:
                    st.write(f"**{label}**：{value}（他の人には非公開）")
                else:
                    st.write(f"**{label}**：非公開")
        if is_me:
            with st.container(key="panel_public"):
                st.markdown("### 公開設定")
                st.caption("名前・部署・拠点は全員に表示されます")
                for field, label, _ in fields:
                    st.toggle(f"{label}を公開する", value=e["public"][field],
                              key=f"pub_{e['id']}_{field}", on_change=set_public, args=(e["id"], field))

    with right:
        st.markdown("### 所属している部活")
        my_clubs = clubs_of(e["id"])
        if not my_clubs:
            st.caption("まだ所属している部活はありません")
        for c in my_clubs:
            club_card(c, f"prof{e['id']}")


# ---------------- ルーティング ----------------
PAGES = {
    "home": page_home,
    "club_search": page_club_search,
    "club_detail": page_club_detail,
    "emp_search": page_emp_search,
    "profile": page_profile,
    "messages": page_messages,
}
PAGES[st.session_state.page]()
