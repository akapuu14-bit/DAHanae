"""プロフィール画面の Cloud エラー対応：PostgREST の埋め込みの戻りの形（dict/list/None/想定外）と、一時の診断表示。

実DBは、埋め込みを関係の向きによって dict でも list でも返し、行が無ければ None を返す。偽repoはこの形を取らないため、
supabase 層を差し替えて、実repo（club_members_repo・employees_repo・events_repo）が落ちないことを確かめる。
診断表示（employee_profile）は原因確定後に削除する一時対応。
"""
import importlib.util
import unittest
from pathlib import Path
from unittest import mock

from lc_base import LcTestCase
from repositories.embed import many, one
from screens import employee_profile
from services import profile_service
from services.errors import AppError


def _fresh(name):
    """実repoのファイルを読み直す。ほかのテストが偽repoへ差し替えた関数の影響を受けないため。"""
    path = Path(__file__).resolve().parents[1] / "app" / "frontend" / "repositories" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"_real_{name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


club_members_repo = _fresh("club_members_repo")
employees_repo = _fresh("employees_repo")
events_repo = _fresh("events_repo")


class _Query:
    def __init__(self, data):
        self.data = data

    def __getattr__(self, name):  # select / eq / in_ / order / gte … はすべて自分を返す
        return lambda *a, **k: self

    def execute(self):
        return self


def _supabase(**tables):
    stub = mock.MagicMock()
    stub.table.side_effect = lambda name: _Query(tables[name])
    return stub


CLUB = {"id": 1, "name": "ランニング部", "is_active": True, "icon": "🏃", "location": "東京", "slot": "平日夜",
        "mood_tags": [], "fee": "無料", "after_activity": "なし", "events": [{"event_date": "2099-01-01", "status": "予定"}]}
EMPLOYEE = {"id": "E002", "name": "幹事", "dept": "営業"}


class EmbedHelpers(unittest.TestCase):
    def test_one(self):
        self.assertEqual(one({"a": 1}), {"a": 1})
        self.assertEqual(one([{"a": 1}, {"a": 2}]), {"a": 1})
        for bad in (None, [], "x", 1, [None, "x"]):
            self.assertIsNone(one(bad))

    def test_many(self):
        self.assertEqual(many([{"a": 1}, None, "x"]), [{"a": 1}])
        self.assertEqual(many({"a": 1}), [{"a": 1}])
        for bad in (None, "x", 1):
            self.assertEqual(many(bad), [])


class ClubsEmbedShapes(unittest.TestCase):
    def _active(self, clubs_value):
        stub = _supabase(club_members=[{"club_id": 1, "clubs": clubs_value}])
        with mock.patch.object(club_members_repo, "supabase", stub):
            return club_members_repo.list_active_clubs_by_member("E002")

    def test_dict_list_none_empty_unexpected(self):
        self.assertEqual([c["id"] for c in self._active(dict(CLUB))], [1])
        self.assertEqual([c["id"] for c in self._active([dict(CLUB)])], [1])  # list で返る形（AttributeError の疑い）
        for bad in (None, [], "x", 5):
            self.assertEqual(self._active(bad), [])

    def test_inactive_club_is_skipped_and_events_shapes(self):
        self.assertEqual(self._active({**CLUB, "is_active": False}), [])
        for events in (None, {"event_date": "2099-01-01", "status": "予定"}, "x"):
            clubs = self._active({**CLUB, "events": events})
            self.assertIsInstance(clubs[0]["events"], list)

    def test_for_employees_shapes(self):
        for value in (dict(CLUB), [dict(CLUB)], None, []):
            stub = _supabase(club_members=[{"employee_id": "E002", "club_id": 1, "clubs": value}])
            with mock.patch.object(club_members_repo, "supabase", stub):
                rows = club_members_repo.list_active_clubs_for_employees(["E002"])
            self.assertEqual(len(rows), 1 if value else 0)

    def test_members_with_employees_shapes(self):
        for value, expected in ((dict(EMPLOYEE), EMPLOYEE), ([dict(EMPLOYEE)], EMPLOYEE), (None, None), ([], None)):
            stub = _supabase(club_members=[{"club_id": 1, "employee_id": "E002", "employees": value}])
            with mock.patch.object(club_members_repo, "supabase", stub):
                rows = club_members_repo.list_members_with_employees(1)
            self.assertEqual(rows[0]["employees"], expected)

    def test_get_profile_with_list_shaped_clubs(self):
        # 実repo＋supabase層の差し替えで、プロフィール全体が list 形の clubs でも落ちない
        stub = _supabase(club_members=[{"club_id": 1, "clubs": [dict(CLUB)]}])
        with mock.patch.object(club_members_repo, "supabase", stub), \
             mock.patch.object(profile_service, "club_members_repo", club_members_repo), \
             mock.patch.object(profile_service.employees_repo, "get_by_id",
                               return_value={"id": "E002", "name": "幹事", "dept": "営業", "location": "東京",
                                             "joined_year": 2020, "entry_type": "新卒", "interests_public": True,
                                             "slots_public": True, "available_slots": []}), \
             mock.patch.object(profile_service.employees_repo, "get_interests", return_value=[]):
            profile = profile_service._get_profile("E002", "E001")
        self.assertEqual([c["club_id"] for c in profile["clubs"]], [1])


class OtherEmbedShapes(unittest.TestCase):
    def test_interests_activities_shapes(self):
        for value, name in (({"name": "走る"}, "走る"), ([{"name": "走る"}], "走る"), (None, None), ([], None)):
            rows = [{"employee_id": "E002", "activity_id": 1, "level": "初心者", "activities": value}]
            with mock.patch.object(employees_repo, "supabase", _supabase(employee_interests=rows)):
                self.assertEqual(employees_repo.get_interests("E002")[0]["activity_name"], name)
                self.assertEqual(employees_repo.get_interests_for(["E002"])["E002"][0]["activity_name"], name)

    def test_participants_employees_shapes(self):
        for value in ({"name": "太郎"}, [{"name": "太郎"}], None, []):
            events = [{"id": 1, "club_id": 1, "event_date": "2099-01-01",
                       "applications": [{"id": 1, "applicant_id": "E003", "is_first_time": False, "status": "申込済み",
                                         "employees": value}]}]
            with mock.patch.object(events_repo, "supabase", _supabase(events=events)):
                rows = events_repo.list_upcoming_by_club_with_participants(1)
            self.assertIsInstance(rows[0]["participants"][0]["employees"], dict)
            self.assertEqual(rows[0]["participants"][0]["employees"].get("name"), "太郎" if value else None)

    def test_applications_none_is_empty(self):
        events = [{"id": 1, "club_id": 1, "event_date": "2099-01-01", "applications": None}]
        with mock.patch.object(events_repo, "supabase", _supabase(events=events)):
            self.assertEqual(events_repo.list_upcoming_by_club_with_participants(1)[0]["participants"], [])


SECRET = "https://example.supabase.co key=sb_secret_ABC123 password=hunter2"


class ProfileDiagnosis(LcTestCase):
    def test_diagnosis_shows_type_place_function_only(self):
        try:
            employee_profile.state.go("存在しない画面")  # アプリ内（state.py）で ValueError
        except ValueError as error:
            text = employee_profile._diagnosis(error)
        self.assertIn("ValueError", text)
        self.assertIn("state.py", text)
        self.assertIn("go", text)
        self.assertNotIn("存在しない画面", text)  # メッセージ本文・値は出さない

    def test_error_screen_shows_diagnosis_without_secrets_and_still_raises(self):
        with mock.patch.object(profile_service, "get_profile", side_effect=AttributeError(SECRET)):
            at = self.app("E001", page="employee_profile", target_employee_id="E002")
        self.assertTrue(at.exception)  # 例外は握りつぶさず、Streamlit にも伝わる
        shown = " ".join(e.value for e in at.error)
        self.assertIn("診断用の一時表示", shown)
        self.assertIn("AttributeError", shown)
        self.assertIn("employee_profile.py", shown)
        for secret in ("example.supabase.co", "sb_secret", "hunter2", "password", "key="):
            self.assertNotIn(secret, shown)

    def test_app_error_is_also_diagnosed_and_logged(self):
        with mock.patch.object(profile_service, "get_profile", side_effect=AppError("x")), \
             self.assertLogs("screens.employee_profile", level="ERROR"):
            at = self.app("E001", page="employee_profile", target_employee_id="E002")
        self.assertIn("AppError", " ".join(e.value for e in at.error))

    def test_normal_screen_has_no_diagnosis(self):
        at = self.app("E001", page="employee_profile", target_employee_id="E002")
        self.assertFalse(at.exception)
        self.assertFalse([e for e in at.error if "診断用" in e.value])


if __name__ == "__main__":
    unittest.main()
