"""离线重算：拿历史 response.json 重跑算分，改完答案/规则不用重新截图。

    python scripts/regrade.py runs/2026-11-18T11-40-00
    python scripts/regrade.py runs/2026-11-18T11-40-00 --key answers.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agp import grade  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--key", default="answers.json")
    args = ap.parse_args()

    key = json.loads(Path(args.key).read_text(encoding="utf-8-sig"))
    rows = 0
    for resp in sorted(Path(args.run_dir).glob("*/response.json")):
        data = json.loads(resp.read_text(encoding="utf-8-sig"))
        out = grade.grade(key, data)
        rows += 1
        print(
            f"{resp.parent.name}  题号={out['题号']!r}  "
            f"score={out['score']}/{out['max']}  "
            f"{'' if not out.get('error') else 'ERROR: ' + out['error']}"
        )
    print(f"{rows} rounds", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

