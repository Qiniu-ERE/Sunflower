"""品牌用词：中文名统一为「太阳花」。原中文名已有既有商标（软件类别），仓库里不得再出现。"""
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
TEXT = {".py", ".md", ".html", ".json", ".sh", ".yml", ".svg", ".toml", ".txt"}
BANNED = "向" + "日葵"  # 拆开写，避免本文件自己命中


class BrandTest(unittest.TestCase):
    def test_no_trademarked_cn_name(self):
        hits = []
        for p in ROOT.rglob("*"):
            if ".git" in p.parts or not p.is_file() or p.suffix not in TEXT:
                continue
            for i, line in enumerate(p.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                if BANNED in line:
                    hits.append(f"{p.relative_to(ROOT)}:{i}")
        self.assertEqual(hits, [], "改用「太阳花」：" + ", ".join(hits[:10]))


if __name__ == "__main__":
    unittest.main()
