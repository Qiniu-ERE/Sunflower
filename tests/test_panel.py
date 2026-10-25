"""面板页的布局约束。门禁不带浏览器，只能查样式源码；实测用 docs/images/render.py 回放真实会话截图。"""
import pathlib
import re
import unittest

PANEL = pathlib.Path(__file__).resolve().parent.parent / "sunflower" / "web" / "panel.html"


class PanelLayoutTest(unittest.TestCase):
    def test_long_task_title_does_not_widen_panel(self):
        # body 是单列网格。列宽不钉成 minmax(0, 1fr) 时，任务名一长，标题栏的最小内容宽度会把整页撑出屏幕：
        # 10-24 彩排的真实会话回放到 1024×600，整页宽 1077 px，执行流和说话按钮被切掉右边
        css = PANEL.read_text(encoding="utf-8")
        body = re.search(r"^\s*body\s*\{([^}]*)\}", css, re.M)
        self.assertIsNotNone(body, "panel.html 里找不到 body 样式")
        self.assertRegex(body.group(1), r"grid-template-columns:\s*minmax\(0,\s*1fr\)")


if __name__ == "__main__":
    unittest.main()
