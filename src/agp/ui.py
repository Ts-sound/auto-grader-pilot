"""UI actions: template matching with a coordinate fallback, plus typing and waiting."""

from __future__ import annotations

import time
from pathlib import Path

from . import capture


class UI:
    def __init__(self, cfg: dict, logger, dry_run: bool = False):
        import pyautogui

        pyautogui.FAILSAFE = True  # slam the mouse into a corner to abort
        pyautogui.PAUSE = 0.08
        self.g = pyautogui
        self.log = logger
        self.dry = dry_run
        self.controls = cfg["controls"]
        self.templates = Path(cfg.get("templates_dir", "assets/templates"))
        self.confidence = float(self.controls.get("confidence", 0.85))
        self.stale = cfg["loop"].get("settle_s", 1.0)

    # ---------- primitives ----------

    def find(self, template_name: str):
        path = self.templates / f"{template_name}.png"
        if not path.exists():
            return None
        try:
            box = self.g.locateOnScreen(str(path), confidence=self.confidence)
        except Exception as exc:  # noqa: BLE001 - opencv missing or grab failed
            self.log.warning("locate %s failed: %s", template_name, exc)
            return None
        if not box:
            return None
        return self.g.center(box)

    def click(self, point: tuple[float, float], why: str) -> None:
        x, y = int(point[0]), int(point[1])
        self.log.debug("click (%d,%d) %s", x, y, why)
        if not self.dry:
            self.g.click(x, y)

    def click_control(self, key: str) -> None:
        """controls[key] = {templates: [...], point: [x, y]} — template first, point as fallback."""
        spec = self.controls[key]
        for name in spec.get("templates", []):
            point = self.find(name)
            if point:
                self.click(point, key)
                return
        fallback = spec.get("point")
        if fallback:
            self.log.warning("%s: template miss, using fallback point", key)
            self.click(tuple(fallback), key)
            return
        raise RuntimeError(f"{key}: no template hit and no fallback point")

    # ---------- actions ----------

    def set_score(self, score: float) -> str:
        """Prefer the 打分板 digit buttons (that is what 点击打分 expects), else type it."""
        digits = self.controls.get("digits", {})
        key = str(int(score)) if float(score).is_integer() else None
        if key and key in digits:
            x, y = digits[key]
            self.click((x, y), f"digit {key}")
            return f"digit button {key}"
        return self.type_score(score)

    def type_score(self, score: float) -> str:
        self.click_control("score_input")
        text = f"{score:g}"
        self.log.debug("type score %s", text)
        if not self.dry:
            self.g.hotkey("ctrl", "a")
            self.g.typewrite(text, interval=0.05)
        return f"typed {text}"

    def submit(self) -> None:
        self.click_control("submit")
        time.sleep(self.stale)

    # ---------- waiting ----------

    def wait_next(self, region, baseline, timeout_s: float, ratio: float):
        """Poll the answer region until it differs from baseline (new paper)."""
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            time.sleep(0.8)
            try:
                img = capture.grab(region)
            except Exception as exc:  # noqa: BLE001
                self.log.warning("grab during wait failed: %s", exc)
                continue
            if baseline is None or capture.diff_ratio(baseline, img) >= ratio:
                return img
        return None
