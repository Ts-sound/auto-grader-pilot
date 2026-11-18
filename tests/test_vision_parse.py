from __future__ import annotations

import unittest

from agp.vision import parse_json


class ParseJsonTest(unittest.TestCase):
    def test_plain_json(self):
        self.assertEqual(parse_json('{"题号": "3"}')["题号"], "3")

    def test_fenced_json(self):
        text = '好的，结果如下：\n```json\n{"题号": "3", "置信度": 0.9}\n```\n以上。'
        self.assertEqual(parse_json(text)["置信度"], 0.9)

    def test_prose_around_json(self):
        self.assertEqual(parse_json('识别结果 {"题号": "5"} 完毕')["题号"], "5")

    def test_garbage_raises(self):
        with self.assertRaises(ValueError):
            parse_json("模型今天不想干活")


if __name__ == "__main__":
    unittest.main()
