"""The loop: capture -> read -> score -> submit -> wait for the next paper."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from . import capture, config as config_mod, grade as grade_mod, logging_setup, ui as ui_mod, vision as vision_mod


class Controller:
    def __init__(
        self,
        cfg: dict,
        run_dir: Path,
        dry_run: bool = False,
        debug: bool = False,
        confirm: bool = False,
    ):
        self.cfg = cfg
        self.run_dir = run_dir
        self.dry = dry_run
        self.confirm = confirm
        self.log = logging_setup.setup(run_dir, debug=debug)
        self.event = logging_setup.events_writer(run_dir / "events.jsonl")
        self.answer_key = json.loads(
            Path(cfg["grading"]["answer_key"]).read_text(encoding="utf-8-sig")
        )
        self.vision = vision_mod.Vision(cfg["vision"], self.log)
        self.ui = ui_mod.UI(cfg, self.log, dry_run=dry_run)
        self.round = 0
        self._stop = threading.Event()
        self._paused = threading.Event()

    # ---------- hotkeys ----------

    def bind_hotkeys(self) -> None:
        from pynput import keyboard

        def on_press(key):
            if key == keyboard.Key.f8:
                if self._paused.is_set():
                    self._paused.clear()
                    self.log.info("[F8] resume")
                elif not self._running.is_set():
                    self.log.info("[F8] start")
                    self._running.set()
            elif key == keyboard.Key.f9 and not self._running.is_set():
                self.log.info("[F9] single round")
                self._single = True
                self._running.set()
            elif key == keyboard.Key.f10:
                self.log.info("[F10] skip current paper")
                self._skip.set()
            elif key == keyboard.Key.esc:
                self.log.info("[Esc] stop")
                self._stop.set()
                self._running.set()

        self._running = threading.Event()
        self._skip = threading.Event()
        self._single = False
        self._listener = keyboard.Listener(on_press=on_press)
        self._listener.daemon = True
        self._listener.start()

    def ask_submit(self, graded: dict, input_fn=input) -> tuple[str, float]:
        """打印分数，等人工决定：回车提交 / 输入数字改分 / s 跳过 / q 退出。"""
        total = float(graded["score"])
        print("\n" + "=" * 52, flush=True)
        print(f"  题号 {graded['题号']}    得分 {total:g} / {graded['max']:g}", flush=True)
        for d in graded["detail"]:
            note = d.get("reason") or ("命中: " + "、".join(d.get("keys_hit", []))
                                      if d.get("keys_hit") else "")
            print(f"  {d['label']:5s} {d['points']:g}/{d['max']:g}  {note}", flush=True)
        print("=" * 52, flush=True)
        print("  [Enter] 提交   [数字] 改分后提交   s 跳过这份   q 退出", flush=True)

        while True:
            try:
                raw = input_fn(f"提交 {total:g} 分? > ").strip()
            except (EOFError, KeyboardInterrupt):
                return "skip", total
            if raw == "":
                return "submit", total
            if raw.lower() in ("s", "skip"):
                return "skip", total
            if raw.lower() in ("q", "quit"):
                return "quit", total
            try:
                value = float(raw)
            except ValueError:
                print("  看不懂，直接回车=提交，或输入 0~%g 的数字" % float(graded["max"]), flush=True)
                continue
            return "submit", max(0.0, min(float(graded["max"]), value))

    def pause(self, reason: str) -> None:
        self.log.warning("PAUSE: %s", reason)
        self.event({"round": self.round, "event": "pause", "reason": reason})
        self._paused.set()
        while self._paused.is_set() and not self._stop.is_set():
            time.sleep(0.2)

    # ---------- one round ----------

    def _save_round(self, idx: int, files: dict) -> Path:
        d = self.run_dir / f"{idx:04d}"
        d.mkdir(parents=True, exist_ok=True)
        for name, payload in files.items():
            if name.endswith(".png"):
                capture.save(payload, d / name)
            else:
                (d / name).write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
                )
        return d

    def one_round(self, answer_img):
        """Returns the answer image that was just handled, or None if it was skipped/paused."""
        self.round += 1
        started = time.time()
        page_img = capture.grab(config_mod.box(self.cfg, "page"))
        if answer_img is None:
            answer_img = capture.grab(config_mod.box(self.cfg, "answer"))
        d = self._save_round(self.round, {"answer.png": answer_img, "page.png": page_img})

        result = self.vision.read(page_img)
        (d / "response.json").write_text(
            json.dumps(result["data"], ensure_ascii=False, indent=2), encoding="utf-8"
        )

        graded = grade_mod.grade(self.answer_key, result["data"], ai_scorer=self.vision.score)
        (d / "result.json").write_text(
            json.dumps(graded, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        if graded.get("error"):
            self.pause(graded["error"])
            return None

        score = graded["score"]
        self.log.info(
            "round %d 题号=%s score=%s/%s subs=%s",
            self.round,
            graded["题号"],
            score,
            graded["max"],
            [(x["label"], x["points"]) for x in graded["detail"]],
        )
        for item in graded["detail"]:
            if item.get("reason"):
                self.log.debug("%s 理由: %s", item["label"], item["reason"])
            if item.get("fallback"):
                self.log.warning("%s %s", item["label"], item["fallback"])
        self.event(
            {
                "round": self.round,
                "题号": graded["题号"],
                "score": score,
                "max": graded["max"],
                "detail": graded["detail"],
                "elapsed_ms": int((time.time() - started) * 1000),
            }
        )

        review_below = self.cfg["grading"].get("review_below")
        if not self.dry and review_below is not None and score < review_below:
            self.pause(f"score {score} below review_below {review_below}")
            return None
        if self._skip.is_set():
            self._skip.clear()
            self.log.info("skipped by F10, not submitting")
            return None

        if self.confirm:
            self.log.info("等待人工确认: 建议 %g 分", score)
            action, chosen = self.ask_submit(graded)
            if action == "quit":
                self.log.info("人工选择退出")
                self._stop.set()
                return None
            if action == "skip":
                self.log.info("人工跳过，不提交")
                self.event({"round": self.round, "event": "manual_skip", "score": graded["score"]})
                return None
            if chosen != score:
                self.log.info("人工改分 %g -> %g", score, chosen)
            else:
                self.log.info("人工确认: 按 %g 分提交", chosen)
            score = chosen

        how = self.ui.set_score(score)
        self.log.debug("set_score -> %s", how)
        self.ui.submit()
        self.log.info("已提交 %g/%g 分（%s）", score, graded["max"], how)
        self.event({"round": self.round, "event": "submitted", "how": how, "score": score})
        return answer_img

    def round_with_cursor(self, baseline):
        """跑一轮，无论成功/跳过/异常，都把鼠标放回原位。"""
        origin = None
        if self.cfg["loop"].get("restore_mouse", True):
            try:
                origin = self.ui.mouse_pos()
            except Exception as exc:  # noqa: BLE001
                self.log.debug("读鼠标位置失败: %s", exc)
        try:
            return self.one_round(baseline)
        finally:
            if origin is not None:
                self.ui.restore_mouse(origin)

    # ---------- main ----------

    def run(self, max_rounds: int = 0, once: bool = False) -> None:
        region = config_mod.box(self.cfg, "answer")
        loop_cfg = self.cfg["loop"]
        self.bind_hotkeys()
        self.log.info(
            "ready. F8 start, F9 single round, F10 skip, Esc quit. dry_run=%s", self.dry
        )

        if once:
            self._running.set()
            self._single = True
        while not self._stop.is_set():
            if not self._running.wait(0.3):
                continue
            if self._paused.is_set():
                time.sleep(0.2)
                continue

            try:
                baseline = capture.grab(region)
            except Exception as exc:  # noqa: BLE001
                self.log.warning("initial grab failed: %s", exc)
                baseline = None

            if self._single:
                self._single = False
                self._running.clear()
                self.round_with_cursor(baseline)
                if once:
                    break
                continue

            handled = self.round_with_cursor(baseline)
            if handled is None:  # paused / skipped: restart from the current screen
                continue

            next_img = self.ui.wait_next(
                region,
                handled,
                float(loop_cfg.get("next_timeout_s", 25)),
                float(loop_cfg.get("change_ratio", 0.01)),
            )
            if next_img is None:
                self.pause("no new paper within timeout")
                continue
            if max_rounds and self.round >= max_rounds:
                self.log.info("max_rounds %d reached", max_rounds)
                break

        self.log.info("stopped after %d rounds", self.round)
        self.event({"event": "stop", "rounds": self.round})


