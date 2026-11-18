"""Config loading: YAML + ${ENV} expansion + light validation."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

_ENV = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def _yaml():
    try:
        import yaml
    except ModuleNotFoundError as exc:  # 换解释器最容易踩这个
        raise SystemExit(
            f"{exc}\n"
            f"当前解释器: {os.sys.executable}\n"
            "装依赖：py -3.14 -m pip install -e .\n"
            "或换一个已装好的解释器运行，例如 python scripts\\snapshot_regions.py"
        ) from None
    return yaml


def _expand(value: Any) -> Any:
    if isinstance(value, str):
        return _ENV.sub(lambda m: os.environ.get(m.group(1), ""), value)
    if isinstance(value, dict):
        return {k: _expand(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand(v) for v in value]
    return value


def load(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8-sig") as fh:
        cfg = _expand(_yaml().safe_load(fh) or {})
    for key in ("vision", "regions", "controls", "grading"):
        if key not in cfg:
            raise ValueError(f"config missing section: {key}")
    return cfg


def box(cfg: dict, name: str) -> tuple[int, int, int, int]:
    """(left, top, width, height) -> pyautogui-compatible region tuple."""
    r = cfg["regions"][name]
    return int(r["left"]), int(r["top"]), int(r["width"]), int(r["height"])

