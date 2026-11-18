"""手动核对截图区域：按 config.yaml 抓一遍，存成 PNG 让你肉眼比对。

    py scripts/snapshot_regions.py            # 抓 page / answer / header 三块
    py scripts/snapshot_regions.py --open     # 抓完直接打开文件夹
    py scripts/snapshot_regions.py --region answer

跑之前把阅卷页面切到前台，别让别的窗口盖住 —— 它截的是屏幕实际画面。
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agp import capture, config as config_mod  # noqa: E402


def focus_window(title_part: str) -> bool:
    """把标题包含 title_part 的窗口拉到最前（比 SetForegroundWindow 顶用）。"""
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    found: list[int] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        buf = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, buf, 512)
        if title_part in buf.value:
            found.append(hwnd)
            return False
        return True

    user32.EnumWindows(cb, 0)
    if not found:
        return False
    user32.SwitchToThisWindow(found[0], True)
    import time

    time.sleep(0.8)
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-c", "--config", default=str(ROOT / "config.yaml"))
    ap.add_argument("--region", action="append", help="只抓指定区域，可重复；默认全部")
    ap.add_argument("--focus", help="先把标题包含这段文字的窗口拉到前台，例如 --focus 上河口")
    ap.add_argument("--open", action="store_true", help="抓完打开输出目录")
    args = ap.parse_args()

    dpi = capture.init_dpi()
    if args.focus:
        print(f"{'已切到前台' if focus_window(args.focus) else '没找到该窗口'}: {args.focus}", flush=True)
    cfg = config_mod.load(args.config)
    names = args.region or list(cfg["regions"])

    out_dir = ROOT / "runs" / ("snap-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"dpi={dpi}  输出目录: {out_dir}", flush=True)
    ok = True
    for name in names:
        try:
            box = config_mod.box(cfg, name)
        except KeyError:
            print(f"SKIP  {name}: config 里没有这个 region", flush=True)
            ok = False
            continue
        img = capture.grab(box)
        path = out_dir / f"{name}.png"
        capture.save(img, path)
        expected = (box[2], box[3])
        flag = "OK  " if img.size == expected else "WARN"
        print(f"{flag}  {name:8s} region={box} -> {img.size}  {path.name}", flush=True)
        if img.size != expected:
            print(f"      期望 {expected}，实际 {img.size}（显示器缩放/分辨率变了？）", flush=True)
            ok = False

    print("\n看一眼 answer.png：应该只剩答题卡白纸，不能带右侧打分板、也不能缺上下边缘。", flush=True)
    if args.open:
        subprocess.run(["explorer", str(out_dir)])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
