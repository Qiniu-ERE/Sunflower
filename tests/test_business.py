import pathlib
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


if __name__ == "__main__":
    unittest.main()
