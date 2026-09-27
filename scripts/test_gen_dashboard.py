#!/usr/bin/env python3
"""gen_dashboard.py の集計ロジックに対する単体テスト（U-xx相当）。

外部ネットワークは呼ばない。サンプルのIssue/PR/Milestoneデータで
aggregate_by_assignee / aggregate_by_milestone / recent_merged_prs を検証する。

実行:
  python3 scripts/test_gen_dashboard.py
"""

import sys
import unittest
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
