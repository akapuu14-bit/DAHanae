"""S-xx 黒箱 Phase2 T1 / 層 α-R のテスト本体（AppTest＋実DB 読取のみ）。

このファイルは「何を確かめるか」だけを持つ。土台（self.app / self.table / self.env / self.today）は呼び出し側が与える:
  - 実DB: tests/test_sxx_appt_ar_real.py の SxxAR（sxx_real.RealAppCase）
  - ハーネス自体の動作確認: tests/sxx_ar_dryrun.py の Dry（合成データ。実DBの結果ではない）
期待値は、DBの生テーブルを読んでPythonで仕様の定義から組み立てる（画面・serviceの実装をなぞらない）。
データは実DBから探す。条件に合うデータが無いときは、合格にせず skip にして理由を出す。
"""

import re
from datetime import date

from sxx_common import RULE, click_label, collect, joined

WEEKDAYS = "月火水木金土日"
EMPTY_CLUBS = "条件に合う部活がありません。条件を減らして探してみてください"
EMPTY_PEOPLE = "条件に合う人がいません。条件を減らして探してみてください"
LEVEL_FILTERS = {
    "初心者向け": {"初心者歓迎", "レベル問わず"},
    "経験者向け": {"経験者向け", "レベル問わず"},
}


def d(value):
    return value if isinstance(value, date) else date.fromisoformat(str(value)[:10])


def fmt_date(day):
    return f"{day.month}/{day.day}（{WEEKDAYS[day.weekday()]}）"


class ArCases:
    # ---------- データの準備（読取のみ） ----------
    def employees(self):
        return self.table("employees")

    def clubs(self):
        return self.table("clubs")

    def active_clubs(self):
        return [c for c in self.clubs() if c["is_active"]]

    def activity_map(self):
        return {a["id"]: a for a in self.table("activities")}

    def interests_of(self):
        out = {}
        for row in self.table("employee_interests"):
            out.setdefault(row["employee_id"], {})[row["activity_id"]] = row["level"]
        return out

    def members_of(self):
        out = {}
        for row in self.table("club_members"):
            out.setdefault(row["club_id"], set()).add(row["employee_id"])
        return out

    def organizer_ids(self):
        return {c["organizer_id"] for c in self.clubs()}

    def pick(self, items, what):
        if not items:
            self.skipTest(f"実DBに{what}が無い")
        return items[0]

    def ids_with_prefix(self, at, prefix):
        out = []
        for b in at.button:
            if b.key and b.key.startswith(prefix) and b.key[len(prefix):].isdigit():
                out.append(int(b.key[len(prefix):]))
        return out

    def after(self, at, marker, offset=1):
        values = collect(at)
        self.assertIn(marker, values, f"『{marker}』が画面に無い")
        return values[values.index(marker) + offset]

    # ---------- S-02 / S-24 / S-44 ロール ----------
    def roles(self):
        organizers = self.organizer_ids()
        admins = [e for e in self.employees() if e.get("is_admin")]
        organizer_only = [e for e in self.employees() if e["id"] in organizers and not e.get("is_admin")]
        general = [e for e in self.employees() if e["id"] not in organizers and not e.get("is_admin")]
        return admins, organizer_only, general

    def sidebar_labels(self, at):
        return [b.label for b in at.sidebar.button]

    def test_S02_manage_menu_only_for_organizer_and_admin(self):
        admins, organizers, general = self.roles()
        g = self.pick(general, "一般社員（幹事でも運営者でもない）")
        self.assertNotIn("部活の管理", self.sidebar_labels(self.app(g["id"])))
        for who, group in (("幹事", organizers), ("運営者", admins)):
            if not group:
                continue
            labels = self.sidebar_labels(self.app(group[0]["id"]))
            self.assertIn("部活の管理", labels, who)
            self.assertEqual(labels[labels.index("自分のプロフィール") + 1], "部活の管理", who)
        self.assertTrue(organizers or admins, "幹事も運営者も実DBに居ない")

    def test_S24_received_tab_only_for_organizer(self):
        _, organizers, general = self.roles()
        o = self.pick(organizers, "幹事（運営者でない）")
        self.assertEqual([t.label for t in self.app(o["id"], page="messages").tabs], ["自分の申込", "届いた申込"])
        g = self.pick(general, "一般社員")
        self.assertEqual(len(self.app(g["id"], page="messages").tabs), 0)

    def test_S44_admin_scope_and_new_button(self):
        admins, organizers, general = self.roles()
        if admins:
            at = self.app(admins[0]["id"], page="club_admin")
            self.assertEqual(len(at.selectbox(key="club_admin_picker").options), len(self.clubs()))  # 非公開も含む全部活
            self.assertIn("club_admin_new_open", [b.key for b in at.button])
        o = self.pick(organizers, "幹事（運営者でない）")
        at = self.app(o["id"], page="club_admin")
        mine = [c for c in self.clubs() if c["organizer_id"] == o["id"]]
        self.assertEqual(len(at.selectbox(key="club_admin_picker").options), len(mine))
        self.assertNotIn("club_admin_new_open", [b.key for b in at.button])
        g = self.pick(general, "一般社員")
        self.assertIn("管理できる部活がありません", [i.value for i in self.app(g["id"], page="club_admin").info])

    # ---------- S-07 実在社員でログイン ----------
    def test_S07_real_employee_logs_in_to_home(self):
        import streamlit as st

        try:
            password = st.secrets["common_password"]
        except Exception:
            self.skipTest("共通パスワード（secrets の common_password）が読めない")
        e = self.pick(self.employees(), "社員")
        at = self.app(None)
        fields = {t.label: t for t in at.text_input}
        fields["社員ID"].set_value(e["id"].lower())  # 大文字小文字は区別しない
        fields["パスワード"].set_value(password)
        at = click_label(at, "ログインする")
        self.assertEqual(at.session_state["current_page"], "home")
        self.assertEqual(at.session_state["employee_id"], e["id"])
        self.assertIn(f"{e['name']}さん、こんにちは。", [m.value for m in at.markdown])

        bad = self.app(None)
        fields = {t.label: t for t in bad.text_input}
        fields["社員ID"].set_value(e["id"])
        fields["パスワード"].set_value(password + "x")
        bad = click_label(bad, "ログインする")
        self.assertIn("社員IDかパスワードが違います。入力内容を確認してください", [x.value for x in bad.error])
        self.assertIsNone(bad.session_state["employee_id"])

    # ---------- S-11 ホーム ----------
    def week_oracle(self):
        today = self.today()
        sunday = today.fromordinal(today.toordinal() + 6 - today.weekday())
        active = {c["id"] for c in self.active_clubs()}
        first = {}
        for e in self.table("events"):
            day = d(e["event_date"])
            if e["status"] == "予定" and e["club_id"] in active and today <= day <= sunday:
                first[e["club_id"]] = min(first.get(e["club_id"], day), day)
        return [cid for cid, _ in sorted(first.items(), key=lambda kv: (kv[1], kv[0]))]

    def popular_oracle(self):
        today = self.today()
        active = {c["id"] for c in self.active_clubs()}
        events = {e["id"]: e for e in self.table("events")}
        counts = {}
        for a in self.table("applications"):
            e = events.get(a["event_id"])
            if not e or e["club_id"] not in active or e["status"] != "予定":
                continue
            day = d(e["event_date"])
            if (day.year, day.month) == (today.year, today.month) and a["is_first_time"] and a["status"] != "キャンセル":
                counts[e["club_id"]] = counts.get(e["club_id"], 0) + 1
        return [cid for cid, _ in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]

    def test_S11_home_week_popular_and_level_toggle(self):
        e = self.pick(self.employees(), "社員")
        at = self.app(e["id"])
        self.assertFalse(at.exception)
        subs = [s.value for s in at.subheader]
        for h in ("今週開催の部活", "今月の人気部活", "あなたにおすすめ"):
            self.assertIn(h, subs)
        self.assertEqual(self.ids_with_prefix(at, "home_week_"), self.week_oracle()[:4])
        self.assertEqual(self.ids_with_prefix(at, "home_popular_"), self.popular_oracle()[:3])
        if not self.week_oracle():
            self.assertIn("今週開催予定の部活はまだありません", [i.value for i in at.info])
        self.assertEqual(at.radio(key="home_level_filter").options, ["初心者向け", "経験者向け"])
        clubs = {c["id"]: c for c in self.clubs()}
        for choice, levels in LEVEL_FILTERS.items():
            with self.subTest(choice=choice):
                at.radio(key="home_level_filter").set_value(choice).run()
                self.assertFalse(at.exception)
                for cid in self.ids_with_prefix(at, "home_recommend_"):
                    self.assertIn(clubs[cid]["level"], levels)

    # ---------- S-12 おすすめ ----------
    def recommend_oracle(self, e):
        interests = self.interests_of().get(e["id"], {})
        joined_clubs = {cid for cid, ms in self.members_of().items() if e["id"] in ms}
        slots = set(e.get("available_slots") or [])
        out = {}
        for c in self.active_clubs():
            if c["id"] in joined_clubs:
                continue
            score = (c["activity_id"] in interests) + (c["location"] == e["location"]) + (c["slot"] in slots)
            if score:
                out[c["id"]] = score
        return out, joined_clubs

    def test_S12_recommendations_have_score_reason_and_exclude_joined(self):
        best = None
        for e in self.employees()[:60]:
            scores, joined_clubs = self.recommend_oracle(e)
            if scores and joined_clubs and (best is None or len(scores) > len(best[1])):
                best = (e, scores, joined_clubs)
        e, scores, joined_clubs = self.pick([best] if best else [], "おすすめが出る所属済みの社員")
        clubs = {c["id"]: c for c in self.clubs()}
        at = self.app(e["id"])
        shown_any = False
        for choice, levels in LEVEL_FILTERS.items():
            with self.subTest(choice=choice):
                at.radio(key="home_level_filter").set_value(choice).run()
                expected = {cid: s for cid, s in scores.items() if clubs[cid]["level"] in levels}
                shown = self.ids_with_prefix(at, "home_recommend_")
                self.assertEqual(len(shown), min(3, len(expected)))
                self.assertTrue(set(shown) <= set(expected))
                self.assertFalse(set(shown) & joined_clubs)  # 所属済みは出ない
                captions = [c.value for c in at.caption if c.value.startswith("一致度 ")]
                self.assertEqual(len(captions), len(shown))
                for cid, caption in zip(shown, captions):
                    self.assertRegex(caption, rf"^一致度 {expected[cid]}点｜.+が一致$")
                if expected:
                    self.assertEqual(expected[shown[0]], max(expected.values()))  # 先頭は最高点
                shown_any = shown_any or bool(shown)
        if not shown_any:
            self.skipTest("画面に出るおすすめが無かった")

    # ---------- S-13 / S-14 部活検索 ----------
    def club_oracle(self, c):
        activities = self.activity_map()

        def category(club):
            return (activities.get(club["activity_id"]) or {}).get("category")

        out = set()
        for club in self.active_clubs():
            if c.get("categories") and category(club) not in c["categories"]:
                continue
            if c.get("locations") and club["location"] not in c["locations"]:
                continue
            if c.get("slots") and club["slot"] not in c["slots"]:
                continue
            if c.get("levels") and club["level"] not in c["levels"]:
                continue
            if c.get("keyword"):
                k = c["keyword"].lower()
                act = (activities.get(club["activity_id"]) or {}).get("name") or ""
                if not any(k in (x or "").lower() for x in (club["name"], club["message"], act)):
                    continue
            out.add(club["id"])
        return out

    def set_club_conditions(self, at, c):
        for key, field in (("club_search_categories", "categories"), ("club_search_locations", "locations"),
                           ("club_search_slots", "slots"), ("club_search_levels", "levels")):
            if c.get(field):
                at.multiselect(key=key).set_value(c[field])
        if c.get("keyword"):
            at.text_input(key="club_search_keyword").set_value(c["keyword"])
        return at.run()

    def shown_club_count(self, at):
        for m in at.markdown:
            found = re.fullmatch(r"(\d+)件の部活が見つかりました", m.value)
            if found:
                return int(found.group(1))
        self.assertIn(EMPTY_CLUBS, [i.value for i in at.info])
        return 0

    def test_S13_search_screen_and_or_matches_data(self):
        active = self.active_clubs()
        activities = self.activity_map()
        locs = sorted({c["location"] for c in active})
        cats = sorted({(activities.get(c["activity_id"]) or {}).get("category") for c in active} - {None})
        slots = sorted({c["slot"] for c in active})
        levels = sorted({c["level"] for c in active})
        first = self.pick(active, "有効な部活")
        keyword = (first["name"] or "")[:3]
        cases = []
        if len(locs) >= 2:
            cases.append(("拠点OR", {"locations": locs[:2]}))
        if cats and locs:
            cases.append(("カテゴリ×拠点AND", {"categories": [cats[0]], "locations": [locs[0]]}))
        cases += [("曜日・時間帯", {"slots": slots[:1]}), ("レベル", {"levels": levels[:1]}),
                  ("キーワード", {"keyword": keyword}),
                  ("組合せ", {"locations": locs[:1], "slots": slots[:1], "levels": levels[:2]})]
        for name, conditions in cases:
            with self.subTest(case=name):
                at = self.set_club_conditions(self.app(self.pick(self.employees(), "社員")["id"], page="club_search"), conditions)
                self.assertFalse(at.exception)
                want = self.club_oracle(conditions)
                self.assertEqual(self.shown_club_count(at), len(want))
                self.assertEqual(set(self.ids_with_prefix(at, "club_search_")), want)

    def test_S14_result_cards_show_required_rows(self):
        at = self.app(self.pick(self.employees(), "社員")["id"], page="club_search")
        active = {c["id"]: c for c in self.active_clubs()}
        self.assertEqual(self.shown_club_count(at), len(active))
        text = joined(at)
        shown = self.ids_with_prefix(at, "club_search_")
        self.assertEqual(set(shown), set(active))
        for cid in shown[:8]:
            c = active[cid]
            with self.subTest(club=cid):
                self.assertIn(f"#### {c['icon']} {c['name']}", [m.value for m in at.markdown])
                self.assertIn(f"{c['location']}・{c['slot']}", text)
                self.assertIn(f"費用：{c['fee']}　活動後：{c['after_activity']}", text)
                if c.get("mood_tags"):
                    self.assertIn(" ／ ".join(c["mood_tags"]), [x.value for x in at.caption])
        self.assertEqual(len([m for m in at.markdown if False]) + text.count("次回開催："), len(shown))

    # ---------- S-17 / S-18 / S-58 部活詳細 ----------
    def test_S17_club_detail_shows_all_sections_and_facts(self):
        employees = {e["id"]: e for e in self.employees()}
        members = self.members_of()
        for c in self.active_clubs()[:4]:
            with self.subTest(club=c["id"]):
                at = self.app(self.pick(self.employees(), "社員")["id"], page="club_detail", target_club_id=c["id"])
                self.assertFalse(at.exception)
                self.assertEqual(at.title[0].value, f"{c['icon']} {c['name']}")
                subs = [s.value for s in at.subheader]
                for h in ("基本情報", "どんな部活？", "参加の前に", "活動後の過ごし方", "開催一覧", "幹事"):
                    self.assertIn(h, subs)
                text = joined(at)
                for needle in (c["location"], c["frequency"], f"社会人から始めた人：{c['fact_adult_starters']}",
                               f"途中参加・途中で抜ける：{c['join_leave']}", c["after_activity"], c["message"] or ""):
                    self.assertIn(needle, text)
                self.assertIn(RULE, [i.value for i in at.info])
                org = employees[c["organizer_id"]]
                self.assertIn(f"{org['name']}（{org['dept']}・{org['joined_year']}年入社・{org['entry_type']}）", text)
                self.assertIn(f"メンバー（{len(members.get(c['id'], set()))}名）", text)

    def test_S18_events_in_date_order_with_counts_and_canceled(self):
        today = self.today()
        by_club = {}
        for e in self.table("events"):
            if d(e["event_date"]) >= today:
                by_club.setdefault(e["club_id"], []).append(e)
        active = {c["id"] for c in self.active_clubs()}
        candidates = sorted((cid for cid in by_club if cid in active), key=lambda cid: -len(by_club[cid]))
        cid = self.pick(candidates, "今日以降の開催がある有効な部活")
        events = sorted(by_club[cid], key=lambda e: (d(e["event_date"]), e["id"]))
        apps = {}
        for a in self.table("applications"):
            if a["status"] == "申込済み":
                apps.setdefault(a["event_id"], []).append(a)
        viewer = next(e["id"] for e in self.employees()
                      if e["id"] not in {a["applicant_id"] for lst in apps.values() for a in lst})
        at = self.app(viewer, page="club_detail", target_club_id=cid)
        dates = [re.match(r"^\*\*(\d{1,2}/\d{1,2}（.）)", m.value).group(1)
                 for m in at.markdown if re.match(r"^\*\*\d{1,2}/\d{1,2}（.）", m.value)]
        self.assertEqual(dates, [fmt_date(d(e["event_date"])) for e in events])
        planned = [e for e in events if e["status"] == "予定"]
        want_counts = sorted((len(apps.get(e["id"], [])), sum(1 for a in apps.get(e["id"], []) if a["is_first_time"]))
                             for e in planned)
        got = sorted(tuple(int(x) for x in m.groups()) for m in
                     (re.fullmatch(r"参加：(\d+)名（うち初参加 (\d+)名）", v.value) for v in at.markdown) if m)
        self.assertEqual(got, want_counts)
        self.assertEqual([m.value for m in at.markdown].count("中止"), len(events) - len(planned))

    FORBIDDEN_KEYS = {"is_admin", "available_slots", "interests_public", "slots_public"}
    ALLOWED_PERSON_KEYS = {"id", "name", "dept", "joined_year", "entry_type"}

    def test_S58_club_detail_people_expose_only_needed_columns(self):
        viewer = self.pick(self.employees(), "社員")["id"]
        checked = 0
        for c in self.active_clubs()[:5]:
            detail = self.env.search_service.get_club_detail(c["id"], viewer)
            people = [detail["organizer"]] + list(detail["members"])
            for person in people:
                with self.subTest(club=c["id"], person=person.get("id")):
                    self.assertFalse(set(person) & self.FORBIDDEN_KEYS)
                    self.assertTrue(set(person) <= self.ALLOWED_PERSON_KEYS, set(person) - self.ALLOWED_PERSON_KEYS)
                checked += 1
        self.assertGreater(checked, 0)

    # ---------- S-28 届いた申込 ----------
    def test_S28_received_tab_shows_applicants_first_time_mark_and_stamp(self):
        events = {e["id"]: e for e in self.table("events")}
        clubs = {c["id"]: c for c in self.clubs()}
        employees = {e["id"]: e for e in self.employees()}
        by_org = {}
        for a in self.table("applications"):
            ev = events.get(a["event_id"])
            if ev:
                by_org.setdefault(clubs[ev["club_id"]]["organizer_id"], []).append(a)
        org = self.pick(sorted(by_org, key=lambda o: -len(by_org[o])), "申込が届いている幹事")
        at = self.app(org, page="messages")
        self.assertFalse(at.exception)
        subs = [s.value for s in at.subheader]
        for a in by_org[org]:
            name = employees[a["applicant_id"]]["name"]
            with self.subTest(application=a["id"]):
                self.assertIn(f"{name}{' 🔰初参加' if a['is_first_time'] else ''}", subs)
        stamps = {a["id"] for a in by_org[org]
                  if a["status"] == "申込済み" and a["is_first_time"] and not a.get("confirmed_at")}
        self.assertEqual(set(self.ids_with_prefix(at, "messages_stamp_")), stamps)

    # ---------- S-32 通知一覧 ----------
    def test_S32_notifications_newest_first_and_unread_bold(self):
        rows = self.table("notifications")
        counts = {}
        for n in rows:
            counts[n["recipient_id"]] = counts.get(n["recipient_id"], 0) + 1
        who = self.pick([r for r, n in sorted(counts.items(), key=lambda kv: -kv[1]) if n >= 2], "通知を2件以上持つ社員")
        mine = sorted((n for n in rows if n["recipient_id"] == who), key=lambda n: (str(n["created_at"]), n["id"]), reverse=True)
        at = self.app(who, page="notifications")
        shown = [(m.value.startswith("**"), re.search(r"【(.+?)】", m.value).group(1))
                 for m in at.markdown if re.match(r"^(\*\*)?【.+?】", m.value)]
        want = [(n["read_at"] is None, n["type"]) for n in mine]
        if len({str(n["created_at"]) for n in mine}) == len(mine):
            self.assertEqual(shown, want)
        else:  # 同時刻があるときは順序を問わず中身だけ照合
            self.assertEqual(sorted(shown), sorted(want))

    # ---------- S-35 / S-36 / S-37 社員検索 ----------
    def employee_oracle(self, c):
        interests = self.interests_of()
        members = self.members_of()
        out = set()
        for e in self.employees():
            if c.get("name") and re.sub(r"\s+", "", c["name"]).lower() not in (e["name"] or "").lower():
                continue
            if c.get("depts") and e["dept"] not in c["depts"]:
                continue
            if c.get("locations") and e["location"] not in c["locations"]:
                continue
            if c.get("slots") and not (e["slots_public"] and set(e.get("available_slots") or []) & set(c["slots"])):
                continue
            if c.get("interests") and not (e["interests_public"] and set(interests.get(e["id"], {})) & set(c["interests"])):
                continue
            if c.get("club_id") is not None and e["id"] not in members.get(c["club_id"], set()):
                continue
            out.add(e["id"])
        return out

    def set_employee_conditions(self, at, c):
        if c.get("name"):
            at.text_input(key="employee_search_name").set_value(c["name"])
        for field, key in (("depts", "employee_search_depts"), ("locations", "employee_search_locations"),
                           ("interests", "employee_search_interests"), ("slots", "employee_search_slots")):
            if c.get(field):
                at.multiselect(key=key).set_value(c[field])
        if c.get("club_id") is not None:
            at.selectbox(key="employee_search_club").set_value(c["club_id"])
        return at.run()

    def shown_people_count(self, at):
        for m in at.markdown:
            found = re.fullmatch(r"(\d+)名見つかりました", m.value)
            if found:
                return int(found.group(1))
        self.assertIn(EMPTY_PEOPLE, [i.value for i in at.info])
        return 0

    def test_S35_employee_search_screen_matches_data(self):
        interests = self.interests_of()
        full = next((e for e in self.employees()
                     if e["interests_public"] and e["slots_public"] and interests.get(e["id"]) and e.get("available_slots")
                     and any(e["id"] in ms for ms in self.members_of().values())), None)
        e = self.pick([full] if full else [], "全項目で絞れる（公開・興味/時間/所属あり）社員")
        club_id = next(cid for cid, ms in self.members_of().items() if e["id"] in ms)
        activity = sorted(interests[e["id"]])[0]
        cases = [
            ("名前", {"name": e["name"][:2]}),
            ("部署＋拠点", {"depts": [e["dept"]], "locations": [e["location"]]}),
            ("興味", {"interests": [activity]}),
            ("参加可能時間", {"slots": [e["available_slots"][0]]}),
            ("所属部活", {"club_id": club_id}),
            ("組合せ", {"name": e["name"][:2], "depts": [e["dept"]], "interests": [activity], "club_id": club_id}),
        ]
        for name, conditions in cases:
            with self.subTest(case=name):
                at = self.set_employee_conditions(self.app(e["id"], page="employee_search"), conditions)
                self.assertFalse(at.exception)
                want = self.employee_oracle(conditions)
                self.assertEqual(self.shown_people_count(at), len(want))
                shown = {b.key[len("employee_search_profile_"):] for b in at.button
                         if b.key and b.key.startswith("employee_search_profile_")}
                self.assertTrue(shown <= want)
                self.assertEqual(len(shown), min(20, len(want)))

    def unique_name(self, e):
        return sum(1 for x in self.employees() if x["name"] == e["name"]) == 1

    def card_lines(self, at, name):
        values = collect(at)
        marker = f"#### {name}"
        self.assertIn(marker, values, f"{name} のカードが無い")
        start = values.index(marker)
        return values[start + 1: start + 4]

    def test_S36_private_values_are_not_used_or_shown_in_search(self):
        interests = self.interests_of()
        viewer = self.pick(self.employees(), "社員")["id"]
        private = [e for e in self.employees()
                   if not e["interests_public"] and interests.get(e["id"]) and self.unique_name(e)]
        p = self.pick(private, "興味を非公開にしていて興味を持つ社員")
        activity_ids = sorted(interests[p["id"]])
        activities = self.activity_map()
        # 結果表示: カードの興味は「非公開」で、値は出ない
        at = self.set_employee_conditions(self.app(viewer, page="employee_search"), {"name": p["name"]})
        lines = self.card_lines(at, p["name"])
        self.assertIn("興味：非公開", lines)
        self.assertNotIn(activities[activity_ids[0]]["name"], "".join(lines))
        # 検索条件: その興味を条件にしても出ない
        at = self.set_employee_conditions(self.app(viewer, page="employee_search"),
                                          {"name": p["name"], "interests": [activity_ids[0]]})
        self.assertNotIn(f"employee_search_profile_{p['id']}", [b.key for b in at.button])
        # 対照: 公開の人は同じ操作で出る
        public = [e for e in self.employees()
                  if e["interests_public"] and interests.get(e["id"]) and self.unique_name(e) and e["id"] != viewer]
        q = self.pick(public, "興味を公開していて興味を持つ社員")
        at = self.set_employee_conditions(self.app(viewer, page="employee_search"),
                                          {"name": q["name"], "interests": [sorted(interests[q["id"]])[0]]})
        self.assertIn(f"employee_search_profile_{q['id']}", [b.key for b in at.button])

    def test_S36_private_slots_are_not_used_in_search(self):
        viewer = self.pick(self.employees(), "社員")["id"]
        private = [e for e in self.employees() if not e["slots_public"] and e.get("available_slots") and self.unique_name(e)]
        p = self.pick(private, "参加可能時間を非公開にしていて時間を持つ社員")
        at = self.set_employee_conditions(self.app(viewer, page="employee_search"),
                                          {"name": p["name"], "slots": [p["available_slots"][0]]})
        self.assertNotIn(f"employee_search_profile_{p['id']}", [b.key for b in at.button])
        self.assertNotIn(p["available_slots"][0], joined(at).replace("参加可能時間", ""))  # 結果にも時間は出ない

    def test_S37_result_cards_show_required_fields(self):
        interests = self.interests_of()
        members = self.members_of()
        activities = self.activity_map()
        active = {c["id"]: c for c in self.active_clubs()}
        viewer = self.pick(self.employees(), "社員")["id"]
        targets = [e for e in self.employees() if e["interests_public"] and interests.get(e["id"])
                   and self.unique_name(e) and any(e["id"] in members.get(cid, set()) for cid in active)]
        for e in targets[:3]:
            with self.subTest(employee=e["id"]):
                at = self.set_employee_conditions(self.app(viewer, page="employee_search"), {"name": e["name"]})
                text = joined(at)
                self.assertIn(f"{e['dept']}・{e['location']}・{e['joined_year']}年入社・{e['entry_type']}", text)
                got = "、".join(f"{activities[a]['name']}（{interests[e['id']][a]}）" for a in sorted(interests[e["id"]]))
                self.assertIn(f"興味：{got}", text)
                clubs = "、".join(active[cid]["name"] for cid in sorted(active) if e["id"] in members.get(cid, set()))
                self.assertIn(f"所属部活：{clubs or 'なし'}", text)
        self.pick(targets, "公開の興味と所属部活を持つ社員")

    # ---------- S-40 他人のプロフィール ----------
    def test_S40_other_profile_follows_public_settings(self):
        interests = self.interests_of()
        activities = self.activity_map()
        viewer = self.pick(self.employees(), "社員")["id"]
        checked = 0
        for e in self.employees():
            if e["id"] == viewer or not interests.get(e["id"]):
                continue
            at = self.app(viewer, page="employee_profile", target_employee_id=e["id"])
            shown = self.after(at, "興味・経験")
            first = sorted(interests[e["id"]])[0]
            line = f"・{activities[first]['name']}（{interests[e['id']][first]}）"
            with self.subTest(employee=e["id"], interests_public=e["interests_public"]):
                if e["interests_public"]:
                    self.assertEqual(shown, line)
                else:
                    self.assertEqual(shown, "非公開")
                    self.assertNotIn(line, collect(at))
            slots = self.after(at, "参加可能時間")
            with self.subTest(employee=e["id"], slots_public=e["slots_public"]):
                if e["slots_public"]:
                    self.assertEqual(slots, "、".join(e["available_slots"]) if e.get("available_slots") else "まだ登録されていません")
                else:
                    self.assertEqual(slots, "非公開")
            checked += 1
            if checked >= 12:
                break
        self.assertGreater(checked, 0)

    # ---------- S-60 操作履歴の蓄積の形 ----------
    def test_S60_action_logs_are_usable_for_kpi(self):
        rows = self.table("action_logs")
        if not rows:
            self.skipTest("操作履歴が実DBに無い")
        time_key = next((k for k in ("created_at", "logged_at", "occurred_at", "at") if k in rows[0]), None)
        employee_ids = {e["id"] for e in self.employees()}
        club_ids = {c["id"] for c in self.clubs()}
        for r in rows:
            with self.subTest(log=r.get("id")):
                self.assertIn(r["employee_id"], employee_ids)
                self.assertIn(r["action"], {"search_club", "view_club", "apply"})
                if time_key:
                    self.assertTrue(r[time_key])
                if r["action"] == "search_club":
                    self.assertIsInstance(r.get("conditions"), dict)
                else:
                    self.assertIn(r.get("club_id"), club_ids)
        if time_key is None:
            self.skipTest("日時の列が操作履歴の行に見当たらない（列名を確認）")
