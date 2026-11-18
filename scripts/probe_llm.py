"""换模型 / 换服务的回归测试：列模型 → ping → 读图提取 → 简答评分，全流程带断言。

    py scripts/probe_llm.py                      # 用 config.yaml 的配置 + 现成样例图
    py scripts/probe_llm.py --live               # 不用样例图，直接截当前屏幕的 page 区域
    py scripts/probe_llm.py --config other.yaml

退出码 0 = 全过；1 = 有失败项，逐条打印实际值和期望值。
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agp import capture, config as config_mod  # noqa: E402
from agp.vision import Vision  # noqa: E402

SAMPLE = ROOT / "assets" / "samples" / "page_for_vision.png"

# (学生答案, 期望分数) —— 换模型时这张表就是验收标准，按自己题组改
SCORE_CASES = [
    ("①促进当地经济发展 ②提供就业岗位", 4),
    ("增加当地农民收入", 2),
    ("老师好 我今天没带笔", 0),
    ("", 0),
]


def list_models(base_url: str) -> list[str]:
    url = base_url.rstrip("/") + "/models"
    with urllib.request.urlopen(url, timeout=15) as resp:
        body = json.loads(resp.read().decode())
    return [m.get("id") or m.get("model") for m in body.get("data", body.get("models", []))]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-c", "--config", default=str(ROOT / "config.yaml"))
    ap.add_argument("--live", action="store_true", help="从当前屏幕截 page 区域，而不是用样例图")
    ap.add_argument("--image", default=str(SAMPLE))
    ap.add_argument(
        "--only",
        default="all",
        choices=["all", "models", "ping", "vision", "score"],
        help="一步一步测：先 models，再 ping，再 vision，最后 score",
    )
    args = ap.parse_args()
    want = lambda step: args.only in ("all", step)  # noqa: E731

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    cfg = config_mod.load(args.config)
    vcfg = cfg["vision"]
    key = json.loads(Path(cfg["grading"]["answer_key"]).read_text(encoding="utf-8-sig"))
    sub = key["questions"][key.get("default_question", "3")]["subs"][-1]

    def say(*parts) -> None:
        print(*parts, flush=True)  # 立刻可见，不等进程结束

    failures: list[str] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        say(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))
        if not ok:
            failures.append(name)

    # 1. 模型列表
    if want("models"):
        try:
            models = list_models(vcfg["base_url"])
            check("models", True, f"{len(models)} 个: {models}")
            check("model 配置在列表里", vcfg["model"] in models, f"config 用的是 {vcfg['model']}")
        except Exception as exc:  # noqa: BLE001
            check("models", False, f"{vcfg['base_url']}/models 打不开: {exc}")

    vision = Vision(vcfg, logging.getLogger("probe"))

    # 2. 纯文本 ping
    if want("ping"):
        t0 = time.time()
        try:
            reply = vision.ping()
            check("text ping", bool(reply), f"{time.time() - t0:.1f}s, 回复={reply!r}")
        except Exception as exc:  # noqa: BLE001
            check("text ping", False, f"{time.time() - t0:.1f}s 后失败: {exc}")

    # 3. 读图提取
    texts: dict[str, str] = {}
    if want("vision"):
        try:
            if args.live:
                capture.init_dpi()
                img = capture.grab(config_mod.box(cfg, "page"))
            else:
                if not Path(args.image).exists():
                    raise SystemExit(
                        f"样例图不在: {args.image}\n"
                        "样图含学生笔迹/密号，没进仓库。用 --live 截当前屏幕，或 --image 指定自己的图。"
                    )
                from PIL import Image

                img = Image.open(args.image)
            t0 = time.time()
            say(f"... 读图中 ({img.size})，本地 27B 约 15s")
            got = vision.read(img)["data"]
            texts = {str(s.get("标号", "")).strip(): str(s.get("文本", "")).strip() for s in got.get("子题", [])}
            check(
                "vision read",
                bool(texts) and any(texts.values()),
                f"{time.time() - t0:.1f}s, 标号={list(texts)}",
            )
            for label, text in texts.items():
                say(f"      {label}: {text!r}")
            check("提取到 (3)", "(3)" in texts, f"题号={got.get('题号')!r} 置信度={got.get('置信度')}")
        except Exception as exc:  # noqa: BLE001
            check("vision read", False, str(exc))

    # 4. 评分
    if want("score"):
        cases = list(SCORE_CASES)
        if texts.get("(3)"):
            cases.insert(0, (texts["(3)"], None))  # 真实卷面，只打印不算对错
        for text, expect in cases:
            label = text.replace("\n", " ")[:28] or "(空白)"
            t0 = time.time()
            try:
                say(f"... 评分中 {label!r}")
                got = vision.score(sub, text)
                score = int(round(float(got.get("分数"))))
                if expect is None:
                    say(f"INFO  score {label!r} -> {score}  理由={got.get('理由', '')}")
                else:
                    check(f"score {label!r} == {expect}", score == expect,
                          f"{time.time() - t0:.1f}s, 实际 {score}，理由={got.get('理由', '')}")
            except Exception as exc:  # noqa: BLE001
                check(f"score {label!r}", False, f"{time.time() - t0:.1f}s 后失败: {exc}")

    say()
    if failures:
        say(f"❌ {len(failures)} 项失败: {failures}")
        return 1
    say("✅ 全过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
