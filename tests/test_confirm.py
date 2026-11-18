from __future__ import annotations

import unittest

from agp.controller import Controller

GRADED = {
    "题号": "3",
    "score": 5,
    "max": 7,
    "detail": [
        {"label": "(2)", "points": 3, "max": 3, "keys_hit": ["夏季"], "keys_miss": []},
        {"label": "(3)", "points": 2, "max": 4, "reason": "只有一条采分点"},
    ],
}


def make(inputs):
    ctl = object.__new__(Controller)  # 只测交互，不构造 UI / Vision
    it = iter(inputs)
    return ctl, (lambda _prompt: next(it))


class AskSubmitTest(unittest.TestCase):
    def test_enter_submits_suggested_score(self):
        ctl, fed = make([""])
        self.assertEqual(ctl.ask_submit(GRADED, input_fn=fed), ("submit", 5.0))

    def test_number_overrides_score(self):
        ctl, fed = make(["4"])
        self.assertEqual(ctl.ask_submit(GRADED, input_fn=fed), ("submit", 4.0))

    def test_override_clamped_to_max(self):
        ctl, fed = make(["99"])
        self.assertEqual(ctl.ask_submit(GRADED, input_fn=fed), ("submit", 7.0))
        ctl, fed = make(["-3"])
        self.assertEqual(ctl.ask_submit(GRADED, input_fn=fed), ("submit", 0.0))

    def test_skip_and_quit(self):
        ctl, fed = make(["s"])
        self.assertEqual(ctl.ask_submit(GRADED, input_fn=fed)[0], "skip")
        ctl, fed = make(["Q"])
        self.assertEqual(ctl.ask_submit(GRADED, input_fn=fed)[0], "quit")

    def test_garbage_reprompts(self):
        ctl, fed = make(["abc", ""])
        self.assertEqual(ctl.ask_submit(GRADED, input_fn=fed), ("submit", 5.0))

    def test_eof_treated_as_skip(self):
        def boom(_prompt):
            raise EOFError

        ctl = object.__new__(Controller)
        self.assertEqual(ctl.ask_submit(GRADED, input_fn=boom)[0], "skip")


if __name__ == "__main__":
    unittest.main()
