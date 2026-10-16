"""画面を切り替えたときだけ、スクロールを先頭へ戻す script が出ること（app.py _scroll_to_top_on_page_change）。

- 開いた直後（最初の描画）は出さない
- 別の画面へ移った再実行では、移動先の画面名入りの script が1つ出る
- 同じ画面のままの再実行（ボタン操作など）では出さない
"""
import unittest

from lc_base import LcTestCase


def scroll_scripts(at):
    return [h.value for h in at.get("html") if "scrollTo(0, 0)" in h.value]


class ScrollTopOnPageChange(LcTestCase):
    def test_first_render_has_no_script(self):
        at = self.app("E003")
        self.assertEqual(scroll_scripts(at), [])

    def test_page_change_emits_script_once(self):
        at = self.app("E003")
        at.session_state["current_page"] = "employee_profile"
        at.session_state["target_employee_id"] = "E003"
        at.run()
        scripts = scroll_scripts(at)
        self.assertEqual(len(scripts), 1)
        self.assertIn("page=employee_profile", scripts[0])
        at.run()  # 同じ画面のままの再実行
        self.assertEqual(scroll_scripts(at), [])


if __name__ == "__main__":
    unittest.main()
