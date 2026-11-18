"""Entry point: agp --config config.yaml [--once] [--dry-run] [--debug]"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from . import capture, config as config_mod, controller as controller_mod


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agp", description="auto grader pilot")
    parser.add_argument("-c", "--config", default="config.yaml")
    parser.add_argument("--once", action="store_true", help="grade one paper then exit")
    parser.add_argument("--dry-run", action="store_true", help="no clicks, no typing")
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="打印分数，等你在终端回车/输入数字/按 s 之后再提交",
    )
    parser.add_argument("--debug", action="store_true", help="DEBUG logging")
    parser.add_argument("--max-rounds", type=int, default=0)
    parser.add_argument("--runs-dir", default="runs")
    args = parser.parse_args(argv)

    dpi = capture.init_dpi()
    cfg = config_mod.load(args.config)
    run_dir = Path(args.runs_dir) / datetime.now().strftime("%Y-%m-%dT%H-%M-%S")

    ctl = controller_mod.Controller(
        cfg, run_dir, dry_run=args.dry_run, debug=args.debug, confirm=args.confirm
    )
    ctl.log.info("dpi=%s run_dir=%s", dpi, run_dir)
    if not args.dry_run and not capture.can_control_mouse():
        ctl.log.warning(
            "当前进程无法移动鼠标（低权限/沙箱里跑），点击不会生效；"
            "请在普通 PowerShell 窗口里运行，别在受限终端里跑"
        )
    try:
        ctl.run(max_rounds=args.max_rounds, once=args.once)
    except KeyboardInterrupt:
        ctl.log.info("interrupted")
    except Exception as exc:  # noqa: BLE001 - pyautogui.FailSafeException included
        ctl.log.exception("crashed: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
