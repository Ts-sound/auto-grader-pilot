"""Screen capture helpers. Must call init_dpi() before any grab on scaled displays."""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import hashlib
from pathlib import Path

from PIL import Image

_DPI_DONE = False


def init_dpi() -> str:
    """Make the process DPI-aware so coordinates match physical pixels.

    Without this, a 2560x1600 @175% screen reports 1463x914 and every region is wrong.
    """
    global _DPI_DONE
    if _DPI_DONE:
        return "already"
    try:
        # PROCESS_PER_MONITOR_DPI_AWARE_V2
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        _DPI_DONE = True
        return "per-monitor-v2"
    except (AttributeError, OSError):
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        _DPI_DONE = True
        return "shcore"
    except (AttributeError, OSError):
        ctypes.windll.user32.SetProcessDPIAware()
        _DPI_DONE = True
        return "system"


def can_control_mouse() -> bool:
    """探一下当前进程能不能真正移动鼠标。

    低完整性级别（沙箱/受限令牌）下 SetCursorPos 会静默失败，点击全落空，
    先探一次比跑到第 50 张卷子才发现要强。
    """
    try:
        user32 = ctypes.windll.user32
        pt = ctypes.wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        return bool(user32.SetCursorPos(pt.x, pt.y))
    except Exception:  # noqa: BLE001
        return False


def grab(region: tuple[int, int, int, int] | None = None) -> Image.Image:
    import pyautogui

    img = pyautogui.screenshot(region=region) if region else pyautogui.screenshot()
    return img.convert("RGB")


def save(img: Image.Image, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    return path


def fingerprint(img: Image.Image, size: int = 16) -> str:
    """Tiny perceptual-ish hash: downscale to grayscale then md5 the bytes."""
    small = img.convert("L").resize((size, size), Image.Resampling.BILINEAR)
    return hashlib.md5(small.tobytes()).hexdigest()[:16]


def diff_ratio(a: Image.Image, b: Image.Image) -> float:
    """Fraction of pixels that differ noticeably. Cheap, good enough for 'new paper'."""
    if a.size != b.size:
        return 1.0
    ga, gb = a.convert("L"), b.convert("L")
    pa, pb = ga.tobytes(), gb.tobytes()
    changed = sum(1 for x, y in zip(pa, pb) if abs(x - y) > 24)
    return changed / len(pa)

