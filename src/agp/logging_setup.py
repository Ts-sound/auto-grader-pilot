"""Logging: console + per-run file + events.jsonl."""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

LOG_FORMAT = "%(asctime)s %(levelname)-5s %(message)s"
DATE_FORMAT = "%H:%M:%S"


def setup(run_dir: Path, debug: bool = False) -> logging.Logger:
    run_dir.mkdir(parents=True, exist_ok=True)
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # 中文不乱码
    logger = logging.getLogger("agp")
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    logger.handlers.clear()
    logger.propagate = False

    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    logger.addHandler(console)

    file_handler = logging.FileHandler(run_dir / "run.log", encoding="utf-8")
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-5s %(name)s %(message)s")
    )
    logger.addHandler(file_handler)
    return logger


def events_writer(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    fh = path.open("a", encoding="utf-8")

    def write(event: dict) -> None:
        event = {"ts": datetime.now().isoformat(timespec="seconds"), **event}
        fh.write(json.dumps(event, ensure_ascii=False) + "\n")
        fh.flush()

    return write
