"""Vision step: one screenshot -> structured answers, any OpenAI-compatible endpoint.

Uses stdlib urllib so the only hard deps are pillow (image) and nothing else.
"""

from __future__ import annotations

import base64
import io
import json
import re
import time
import urllib.error
import urllib.request

from PIL import Image

PROMPT = """你是阅卷助手的“读题”模块。图片是网上阅卷系统的一屏截图，包含：
1) 顶部蓝色标题栏，右侧有“题号：第X题”；
2) 中间是学生答题卡的扫描图，每题前面有 (1)(2)(3) 这类小标号和分值。

任务：只做识别，不要评分。输出 JSON，不要输出任何别的文字：
{
  "题号": "从标题栏读到的题号数字，读不到就填空字符串",
  "全部分值": 7,
  "子题": [{"标号": "(2)", "文本": "学生手写答案的转录（看不清就写 [?]）"}],
  "置信度": 0.0
}

规则：
- 文本只转录学生写的内容，不要补充、不要纠错、不要解释。
- 完全认不出的字用 [?] 占位。
- 置信度是 0~1 的小数，表示你对转录准确度的判断。
"""

SCORE_PROMPT = """你是初中地理阅卷老师。请给下面这道简答题打分。

评分标准（采分点各 1 分，意对即可，言之有理就给分）：
{rubric}

学生答案（OCR 转录，[?] 表示认不出的字）：
\"\"\"
{text}
\"\"\"

要求：
- 分数范围 0~{points} 分，**只能是整数**（0、1、2、3…），不要给小数。
- 只要学生表达了某个采分点的意思就算给分，不要求和标准表述一字不差。
- 与采分点无关、答非所问、空着 = 0 分。
只输出 JSON，不要输出其他文字：{{"分数": 0, "理由": "一句话说明扣分/给分点"}}
"""

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)


def parse_json(text: str) -> dict:
    """Tolerant JSON extraction: fences, leading prose, trailing junk."""
    if not text:
        raise ValueError("empty model output")
    m = _FENCE.search(text)
    candidate = m.group(1) if m else text
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start < 0 or end <= start:
        raise ValueError(f"no JSON object in model output: {text[:200]!r}")
    return json.loads(candidate[start : end + 1])


def _data_url(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


class Vision:
    def __init__(self, cfg: dict, logger):
        self.cfg = cfg
        self.log = logger
        if not cfg.get("base_url") or not cfg.get("model"):
            raise ValueError(
                "vision.base_url / vision.model 没配好（检查 AGP_BASE_URL、AGP_MODEL 环境变量）"
            )
        self.url = cfg["base_url"].rstrip("/") + "/chat/completions"
        self.retries = int(cfg.get("retries", 3))
        self.timeout = float(cfg.get("timeout_s", 40))
        # 推理模型默认会先吐一长串思考，占满 token 还拖慢一倍以上；关掉更稳
        self.extra: dict = {}
        if cfg.get("disable_thinking", True):
            self.extra["chat_template_kwargs"] = {"enable_thinking": False}
        if cfg.get("max_tokens"):
            self.extra["max_tokens"] = int(cfg["max_tokens"])

    def _post(self, payload: dict) -> dict:
        req = urllib.request.Request(
            self.url,
            data=json.dumps(payload).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.cfg.get('api_key', '')}",
            },
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode())

    def read(self, img: Image.Image) -> dict:
        payload = {
            "model": self.cfg["model"],
            "temperature": 0,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": PROMPT},
                        {"type": "image_url", "image_url": {"url": _data_url(img)}},
                    ],
                }
            ],
            **self.extra,
        }
        last: Exception | None = None
        for attempt in range(1, self.retries + 1):
            try:
                body = self._post(payload)
                raw = body["choices"][0]["message"]["content"] or ""
                return {"raw": raw, "data": parse_json(raw)}
            except urllib.error.HTTPError as exc:
                detail = exc.read()[:300].decode(errors="replace")
                last = RuntimeError(f"HTTP {exc.code}: {detail}")
            except Exception as exc:  # noqa: BLE001 - network/parse retry the same way
                last = exc
            self.log.warning("vision attempt %d/%d failed: %s", attempt, self.retries, last)
            if attempt < self.retries:
                time.sleep(2**attempt)
        raise RuntimeError(f"vision failed after {self.retries} attempts: {last}")

    def ping(self) -> str:
        """连通性探针：一句话往返，返回回复文本（空 = 服务活着但没吐出内容）。"""
        body = self._post(
            {
                "model": self.cfg["model"],
                "temperature": 0,
                "max_tokens": 256,
                "messages": [{"role": "user", "content": "只回复两个字：收到"}],
                **self.extra,
            }
        )
        return (body["choices"][0]["message"]["content"] or "").strip()

    def score(self, sub: dict, text: str) -> dict:
        """简答题 AI 评分：只发文本，不发图，便宜且够用。"""
        points = float(sub["points"])
        rubric = sub.get("rubric") or "；".join(sub.get("keys", []))
        prompt = SCORE_PROMPT.format(rubric=rubric, text=text or "(空白)", points=points)
        payload = {
            "model": self.cfg["model"],
            "temperature": 0,
            "messages": [{"role": "user", "content": prompt}],
            **self.extra,
        }
        last: Exception | None = None
        for attempt in range(1, self.retries + 1):
            try:
                body = self._post(payload)
                raw = body["choices"][0]["message"]["content"] or ""
                return parse_json(raw)
            except Exception as exc:  # noqa: BLE001
                last = exc
                self.log.warning("score attempt %d/%d failed: %s", attempt, self.retries, exc)
                if attempt < self.retries:
                    time.sleep(2**attempt)
        raise RuntimeError(f"AI 评分失败: {last}")

