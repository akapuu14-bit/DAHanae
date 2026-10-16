"""デモ版の注記（Issue #45）：ログイン画面とサイドバーに1行ずつ出ること。"""
import unittest

from lc_base import LcTestCase
from components.sidebar import DEMO_BANNER


def captions(elements):
    return [c.value for c in elements]


class DemoBanner(LcTestCase):
    def test_login_screen_shows_banner_once(self):
        at = self.app()  # 未ログイン＝ログイン画面
        self.assertEqual(captions(at.caption).count(DEMO_BANNER), 1)

    def test_logged_in_sidebar_shows_banner_once_main_has_none(self):
        at = self.app("E003")
        self.assertEqual(captions(at.sidebar.caption).count(DEMO_BANNER), 1)
        self.assertEqual(captions(at.main.caption).count(DEMO_BANNER), 0)


if __name__ == "__main__":
    unittest.main()
