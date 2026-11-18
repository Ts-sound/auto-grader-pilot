from __future__ import annotations

import unittest

from agp import grade

KEY = {
    "questions": {
        "3": {
            "full_marks": 7,
            "subs": [
                {"label": "(2)", "points": 3, "keys": ["夏季", "昼长夜短", "公转"], "mode": "each"},
                {"label": "(3)", "points": 4, "keys": ["促进当地经济发展", "提供就业岗位"], "mode": "each"},
            ],
        },
        "*": {"full_marks": 5, "subs": [{"label": "(1)", "points": 5, "keys": ["A"], "mode": "all"}]},
    }
}


def extracted(subs, qid="3"):
    return {"题号": qid, "子题": [{"标号": k, "文本": v} for k, v in subs.items()]}


class GradeTest(unittest.TestCase):
    def test_full_marks_all_keywords_hit(self):
        out = grade.grade(KEY, extracted({"(2)": "夏季 昼长夜短 公转", "(3)": "①促进当地经济发展 ②提供就业岗位"}))
        self.assertEqual(out["score"], 7)
        self.assertEqual(out["max"], 7)

    def test_each_mode_partial_by_keyword_ratio(self):
        out = grade.grade(KEY, extracted({"(2)": "夏季 昼长夜短", "(3)": "促进当地经济发展"}))
        # (2) 2/3*3 = 2.0, (3) 1/2*4 = 2.0
        self.assertEqual(out["score"], 4.0)

    def test_half_point_rounding(self):
        out = grade.grade(KEY, extracted({"(2)": "夏季", "(3)": "提供就业岗位"}))
        self.assertEqual(out["score"], 3.0)

    def test_all_mode_needs_every_keyword(self):
        self.assertEqual(grade.grade(KEY, extracted({"(1)": "选 A 吧"}, qid="9"))["score"], 5)
        self.assertEqual(grade.grade(KEY, extracted({"(1)": "选 B"}, qid="9"))["score"], 0)

    def test_normalize_fullwidth_and_punct(self):
        self.assertEqual(grade.normalize("（Ａ） 夏 季，"), "A夏季")

    def test_unknown_qid_without_wildcard_errors(self):
        out = grade.grade({"questions": {"3": KEY["questions"]["3"]}}, extracted({"(2)": "夏季"}, qid="99"))
        self.assertTrue(out["error"])

    def test_empty_text_scores_zero(self):
        self.assertEqual(grade.grade(KEY, extracted({}))["score"], 0.0)

    def test_alias_any_variant_counts(self):
        k = {
            "questions": {
                "3": {
                    "full_marks": 4,
                    "subs": [
                        {
                            "label": "(3)",
                            "points": 4,
                            "mode": "each",
                            "keys": [
                                "增加当地农民收入|促进当地经济发展",
                                "增加就业岗位|提供就业岗位",
                                "带动了相关产业发展|带动相关产业",
                                "改善了大气环境|改善大气环境",
                            ],
                        }
                    ],
                }
            }
        }
        # 学生写的是同义说法，4 个采分点都该给分
        text = "①促进当地经济发展 ②提供就业岗位 ③带动相关产业 ④改善大气环境"
        self.assertEqual(grade.grade(k, extracted({"(3)": text}))["score"], 4.0)
        # 只命中 3 个 → 3 分
        self.assertEqual(
            grade.grade(k, extracted({"(3)": "促进当地经济发展 提供就业岗位 带动相关产业"}))["score"], 3.0
        )

    # ---------- mode=ai ----------

    AI_KEY = {
        "questions": {
            "3": {
                "full_marks": 7,
                "subs": [
                    {"label": "(2)", "points": 3, "mode": "each", "keys": ["夏季", "昼长夜短", "公转"]},
                    {"label": "(3)", "points": 4, "mode": "ai", "rubric": "四个采分点",
                     "keys": ["增加当地农民收入", "增加就业岗位"]},
                ],
            }
        }
    }

    def test_ai_sub_uses_scorer(self):
        calls = []

        def scorer(sub, text):
            calls.append((sub["label"], text))
            return {"分数": 3, "理由": "漏了一个采分点"}

        out = grade.grade(self.AI_KEY, extracted({"(2)": "夏季 昼长夜短 公转", "(3)": "增加收入"}), ai_scorer=scorer)
        self.assertEqual(out["score"], 6.0)  # 3 + 3
        self.assertEqual(calls, [("(3)", "增加收入")])
        self.assertEqual(out["detail"][1]["reason"], "漏了一个采分点")

    def test_ai_score_is_clamped_and_integer(self):
        def scorer(_sub, _text):
            return {"分数": 9.9}

        out = grade.grade(self.AI_KEY, extracted({"(3)": "x"}), ai_scorer=scorer)
        self.assertEqual(out["detail"][1]["points"], 4.0)  # 不超过满分

        def scorer_round_down(_sub, _text):
            return {"分数": 2.3}

        out = grade.grade(self.AI_KEY, extracted({"(3)": "x"}), ai_scorer=scorer_round_down)
        self.assertEqual(out["detail"][1]["points"], 2.0)  # 2.3 -> 2

        def scorer_round_up(_sub, _text):
            return {"分数": 2.6}

        out = grade.grade(self.AI_KEY, extracted({"(3)": "x"}), ai_scorer=scorer_round_up)
        self.assertEqual(out["detail"][1]["points"], 3.0)  # 2.6 -> 3
        self.assertEqual(out["detail"][1]["points"] % 1, 0.0)

    def test_ai_failure_falls_back_to_keywords(self):
        def scorer(_sub, _text):
            raise RuntimeError("boom")

        out = grade.grade(self.AI_KEY, extracted({"(3)": "增加当地农民收入"}), ai_scorer=scorer)
        sub = out["detail"][1]
        self.assertTrue(sub["fallback"])
        self.assertEqual(sub["points"], 2.0)  # 2 个关键词命中 1 个 / 4 分 = 2 分

    def test_ai_mode_without_scorer_refuses(self):
        out = grade.grade(self.AI_KEY, extracted({"(3)": "随便写"}))
        self.assertIn("error", out["detail"][1])
        self.assertEqual(out["detail"][1]["points"], 0.0)

    def test_default_question_used_when_id_unreadable(self):
        key = {"default_question": "3", "questions": {"3": KEY["questions"]["3"]}}
        out = grade.grade(key, {"题号": "", "子题": [{"标号": "(2)", "文本": "夏季 昼长夜短 公转"}]})
        self.assertEqual(out["题号"], "3")
        self.assertEqual(out["score"], 3)

    # ---------- per_key：按「条」给分 ----------

    PER_KEY = {
        "questions": {
            "3": {
                "full_marks": 4,
                "subs": [
                    {
                        "label": "(3)",
                        "points": 4,
                        "mode": "ai",
                        "per_key": 2,
                        "keys": ["增加当地农民收入", "增加就业岗位", "带动相关产业发展", "改善大气环境"],
                    }
                ],
            }
        }
    }

    def test_per_key_fallback_gives_two_per_hit(self):
        def boom(_sub, _text):
            raise RuntimeError("api down")

        one = grade.grade(self.PER_KEY, extracted({"(3)": "增加当地农民收入"}), ai_scorer=boom)
        self.assertEqual(one["detail"][0]["points"], 2)

        two = grade.grade(self.PER_KEY, extracted({"(3)": "增加当地农民收入 增加就业岗位"}), ai_scorer=boom)
        self.assertEqual(two["detail"][0]["points"], 4)

    def test_per_key_capped_at_full_marks(self):
        def boom(_sub, _text):
            raise RuntimeError("api down")

        all4 = grade.grade(
            self.PER_KEY,
            extracted({"(3)": "增加当地农民收入 增加就业岗位 带动相关产业发展 改善大气环境"}),
            ai_scorer=boom,
        )
        self.assertEqual(all4["detail"][0]["points"], 4)  # 封顶，不会 8 分


if __name__ == "__main__":
    unittest.main()

