import os
import tempfile
import unittest

import todo


class TodoTest(unittest.TestCase):
    def setUp(self):
        fd, todo.DB = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        os.remove(todo.DB)

    def tearDown(self):
        if os.path.exists(todo.DB):
            os.remove(todo.DB)

    def test_add_numbers_from_one(self):
        self.assertEqual(todo.add("买牛奶"), 1)
        self.assertEqual(todo.add("写周报"), 2)

    def test_render_marks_done(self):
        todo.add("买牛奶")
        todo.add("写周报")
        todo.done(2)
        self.assertEqual(todo.render(todo.load()), "1. [ ] 买牛奶\n2. [x] 写周报")

    def test_done_first_item(self):
        todo.add("买牛奶")
        self.assertEqual(todo.done(1), "买牛奶")
        self.assertTrue(todo.load()[0]["done"])


if __name__ == "__main__":
    unittest.main()
