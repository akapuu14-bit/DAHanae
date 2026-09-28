#!/usr/bin/env python3
"""gen_dashboard.py の集計ロジックに対する単体テスト（U-xx相当）。

外部ネットワークは呼ばない。サンプルのIssue/PR/Milestoneデータで
aggregate_by_assignee / aggregate_by_milestone / recent_merged_prs を検証する。

実行:
  python3 scripts/test_gen_dashboard.py
"""

import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import gen_dashboard as gd  # noqa: E402


def sample_items():
    return [
        {  # Issue: closed, area:be, assignee alice
            "number": 1,
            "title": "Supabaseスキーマ作成",
            "state": "closed",
            "assignees": [{"login": "alice"}],
            "labels": [{"name": "area:be"}, {"name": "type:feature"}],
            "milestone": {"title": "〜9/29 アプリのカタチ"},
        },
        {  # Issue: open, area:ui, assignee bob
            "number": 2,
            "title": "S03部活検索",
            "state": "open",
            "assignees": [{"login": "bob"}],
            "labels": [{"name": "area:ui"}],
            "milestone": {"title": "〜9/29 アプリのカタチ"},
        },
        {  # Issue: open, 未アサイン
            "number": 3,
            "title": "共通部品 rule_notice",
            "state": "open",
            "assignees": [],
            "labels": [{"name": "area:pdm"}],
            "milestone": None,
        },
        {  # PR: merged, area:be, assignee alice
            "number": 10,
            "title": "feat: repositories/ 実装",
            "state": "closed",
            "assignees": [{"login": "alice"}],
            "labels": [{"name": "area:be"}],
            "milestone": None,
            "html_url": "https://github.com/example/repo/pull/10",
            "user": {"login": "alice"},
            "pull_request": {"merged_at": "2026-09-27T10:00:00Z"},
        },
        {  # PR: closed but NOT merged（対象外。Milestoneにも紐づく）
            "number": 11,
            "title": "wip: 未マージPR",
            "state": "closed",
            "assignees": [{"login": "bob"}],
            "labels": [],
            "milestone": {"title": "〜9/29 アプリのカタチ"},
            "html_url": "https://github.com/example/repo/pull/11",
            "user": {"login": "bob"},
            "pull_request": {"merged_at": None},
        },
    ]


def sample_milestones():
    return [
        {"title": "〜9/29 アプリのカタチ", "due_on": "2026-09-29T14:59:59Z", "state": "open"},
        {"title": "〜10/2 8割", "due_on": "2026-10-02T14:59:59Z", "state": "open"},
    ]


class TestAggregateByAssignee(unittest.TestCase):
    def test_counts_open_closed_and_areas(self):
        board = gd.aggregate_by_assignee(sample_items())
        # alice: Issue#1(closed) + PR#10(closed/merged) = 2 closed, area:be x2
        self.assertEqual(board["alice"]["closed"], 2)
        self.assertEqual(board["alice"]["open"], 0)
        self.assertEqual(board["alice"]["areas"]["area:be"], 2)
        # bob: Issue#2(open)のみ。PR#11(closed but未マージ)は完了に数えず、
        # 集計そのものから除外する（T-016: kurosuの横断レビュー指摘の修正）
        self.assertEqual(board["bob"]["open"], 1)
        self.assertEqual(board["bob"]["closed"], 0)
        # 未アサイン: Issue#3(open)
        self.assertEqual(board[gd.UNASSIGNED]["open"], 1)

    def test_closed_but_unmerged_pr_excluded_from_counts(self):
        board = gd.aggregate_by_assignee(sample_items())
        # PR#11分がclosedにもopenにも計上されていないこと
        total_bob = board["bob"]["open"] + board["bob"]["closed"]
        self.assertEqual(total_bob, 1, "未マージclosed PRはopen/closedどちらにも数えない")

    def test_unassigned_bucket_used_when_no_assignees(self):
        board = gd.aggregate_by_assignee(sample_items())
        self.assertIn(gd.UNASSIGNED, board)


class TestAggregateByMilestone(unittest.TestCase):
    def test_progress_percentage(self):
        result = gd.aggregate_by_milestone(sample_items(), sample_milestones())
        by_title = {r["title"]: r for r in result}
        m1 = by_title["〜9/29 アプリのカタチ"]
        # Issue#1(closed) + Issue#2(open) が紐づく → 1/2 = 50%
        # PR#11（同じMilestoneに紐づくが、closedで未マージ）は集計から除外される
        # （T-016: kurosuの横断レビュー指摘の修正。totalが3にならないことを確認）
        self.assertEqual(m1["total"], 2)
        self.assertEqual(m1["closed"], 1)
        self.assertEqual(m1["pct"], 50)

        m2 = by_title["〜10/2 8割"]
        self.assertEqual(m2["total"], 0)
        self.assertEqual(m2["pct"], 0)

    def test_sorted_by_due_date(self):
        result = gd.aggregate_by_milestone(sample_items(), sample_milestones())
        due_dates = [r["due_on"] for r in result]
        self.assertEqual(due_dates, sorted(due_dates))


class TestRecentMergedPrs(unittest.TestCase):
    def test_only_merged_prs_included(self):
        prs = gd.recent_merged_prs(sample_items())
        numbers = [p["number"] for p in prs]
        self.assertIn(10, numbers)
        self.assertNotIn(11, numbers, "マージされていないPRは含めない")

    def test_area_labels_attached(self):
        prs = gd.recent_merged_prs(sample_items())
        pr10 = next(p for p in prs if p["number"] == 10)
        self.assertEqual(pr10["areas"], ["area:be"])


class TestIsPullRequestAndMerged(unittest.TestCase):
    def test_is_pull_request(self):
        items = sample_items()
        self.assertFalse(gd.is_pull_request(items[0]))  # Issue
        self.assertTrue(gd.is_pull_request(items[3]))   # PR

    def test_is_merged(self):
        items = sample_items()
        self.assertTrue(gd.is_merged(items[3]))   # merged_at あり
        self.assertFalse(gd.is_merged(items[4]))  # merged_at なし


class TestRenderDoesNotCrash(unittest.TestCase):
    def test_html_fragments_render_without_error(self):
        board = gd.aggregate_by_assignee(sample_items())
        ms = gd.aggregate_by_milestone(sample_items(), sample_milestones())
        prs = gd.recent_merged_prs(sample_items())
        html_assignees = gd.render_assignee_cards(board)
        html_milestones = gd.render_milestone_bars(ms)
        html_prs = gd.render_recent_prs(prs)
        for fragment in (html_assignees, html_milestones, html_prs):
            self.assertIsInstance(fragment, str)
            self.assertGreater(len(fragment), 0)


class TestDeadlineBadge(unittest.TestCase):
    TODAY = date(2026, 9, 28)

    def test_overdue_open_is_late_with_days(self):
        label, cls = gd.deadline_badge(False, "2026-09-25T14:59:59Z", self.TODAY)
        self.assertEqual(label, "遅延 3日")
        self.assertEqual(cls, "badge-late")

    def test_future_open_is_within_deadline(self):
        label, cls = gd.deadline_badge(False, "2026-10-02T14:59:59Z", self.TODAY)
        self.assertEqual(label, "期限内(残4日)")
        self.assertEqual(cls, "badge-ok")

    def test_closed_is_done_even_if_overdue(self):
        label, cls = gd.deadline_badge(True, "2026-09-01T14:59:59Z", self.TODAY)
        self.assertEqual(label, "完了")
        self.assertEqual(cls, "badge-done")

    def test_due_today(self):
        label, cls = gd.deadline_badge(False, "2026-09-28T14:59:59Z", self.TODAY)
        self.assertEqual(label, "本日締切")
        self.assertEqual(cls, "badge-today")

    def test_no_milestone_does_not_crash(self):
        self.assertEqual(gd.deadline_badge(False, None, self.TODAY), ("期限未設定", "badge-none"))
        self.assertEqual(gd.deadline_badge(False, "broken", self.TODAY), ("期限未設定", "badge-none"))


class TestAssigneeBreakdown(unittest.TestCase):
    TODAY = date(2026, 9, 28)

    def items(self):
        return [
            {"number": 1, "title": "遅れてるタスク", "state": "open",
             "assignees": [{"login": "alice"}], "labels": [{"name": "area:be"}],
             "html_url": "https://github.com/example/repo/issues/1",
             "milestone": {"title": "〜9/29 アプリのカタチ", "due_on": "2026-09-25T14:59:59Z"}},
            {"number": 2, "title": "終わったタスク", "state": "closed",
             "assignees": [{"login": "alice"}], "labels": [],
             "html_url": "https://github.com/example/repo/issues/2",
             "milestone": {"title": "〜9/29 アプリのカタチ", "due_on": "2026-09-25T14:59:59Z"}},
            {"number": 3, "title": "<script>alert(1)</script>", "state": "open",
             "assignees": [], "labels": [],
             "html_url": "https://github.com/example/repo/issues/3", "milestone": None},
        ]

    def test_tasks_attached_to_board_entries(self):
        board = gd.aggregate_by_assignee(self.items())
        self.assertEqual([t["number"] for t in board["alice"]["tasks"]], [1, 2])
        t1 = board["alice"]["tasks"][0]
        self.assertEqual(t1["assignee"], "alice")
        self.assertFalse(t1["done"])
        self.assertEqual(t1["milestone_title"], "〜9/29 アプリのカタチ")
        self.assertEqual(t1["areas"], ["area:be"])

    def test_card_has_details_with_task_rows_and_badges(self):
        board = gd.aggregate_by_assignee(self.items())
        out = gd.render_assignee_cards(board, self.TODAY)
        self.assertIn("<details", out)
        self.assertIn("内訳を開く", out)
        self.assertIn("#1 遅れてるタスク", out)
        self.assertIn("遅延 3日", out)
        self.assertIn("完了", out)
        self.assertIn("担当: alice", out)
        self.assertIn("期限: 2026-09-25", out)
        self.assertIn('target="_blank" rel="noopener"', out)

    def test_unassigned_and_no_milestone_visible_without_crash(self):
        board = gd.aggregate_by_assignee(self.items())
        out = gd.render_assignee_cards(board, self.TODAY)
        self.assertIn(f"担当: {gd.UNASSIGNED}", out)
        self.assertIn("期限未設定", out)
        self.assertIn("Milestone未設定", out)

    def test_title_is_html_escaped(self):
        board = gd.aggregate_by_assignee(self.items())
        out = gd.render_assignee_cards(board, self.TODAY)
        self.assertNotIn("<script>alert(1)</script>", out)
        self.assertIn("&lt;script&gt;", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
