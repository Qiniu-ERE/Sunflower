import pathlib
import re
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "docs" / "business"))
import cost_model  # noqa: E402


class CostModelTest(unittest.TestCase):
    def test_readme_tables_match_csv(self):
        # README 里的数字只能由脚本从 CSV 算出来：改了 CSV 没跑 --write，这里就红
        body = cost_model.block(ROOT / "docs" / "business" / "README.md", (cost_model.BEGIN, cost_model.END))
        self.assertEqual(body, cost_model.tables().strip())
        self.assertEqual(cost_model.block(ROOT / "README.md", cost_model.SUMMARY), cost_model.summary().strip())

    def test_every_quoted_part_has_source(self):
        for row in cost_model.read("bom.csv"):
            if row["kind"] == "报价":
                self.assertTrue(row["source"].startswith("https://"), row["part"])

    def test_screen_variant_costs_more(self):
        b = cost_model.bom(cost_model.rates())
        self.assertGreater(cost_model.total(b["屏显版"], "unit_1k"), cost_model.total(b["标准版"], "unit_1k"))

    def test_standard_variant_has_no_screen(self):
        # 10-24 定：标准版花芯是不通电的固定笑脸，状态只靠花瓣灯；BOM、竞品表和文档都不能再出现标准版的屏
        # 只拦屏相关零件：标准版以后可以有自己的行（比如笑脸移印），不能有屏、屏驱和花头主控
        screen_part = re.compile(r"屏|ST7701S|GC9A01|480×480|花头主控")
        self.assertEqual([r["part"] for r in cost_model.read("bom.csv")
                          if r["variant"] == "标准版" and screen_part.search(r["part"])], [])
        self.assertTrue(cost_model.OURS["标准版"]["screen"].startswith("无屏"))
        # 旧标准版的屏型号与过关节线数；按边界匹配（紧挨中文也算命中），「110 芯」「10 芯片」不算
        old_spec = re.compile(r"(?<![\d.])1\.28″|(?<![A-Za-z0-9])GC9A01(?![A-Za-z0-9])|(?<!\d)10 芯(?!片)")
        for doc in ("README.md", "docs/business/README.md", "docs/hardware/README.md"):
            text = (ROOT / doc).read_text(encoding="utf-8")
            self.assertIsNone(old_spec.search(text), doc)


if __name__ == "__main__":
    unittest.main()
