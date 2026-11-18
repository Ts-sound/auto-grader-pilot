"""Scoring: pure functions, no screen, no network. Unit-tested."""

from __future__ import annotations

import re
import unicodedata

_PUNCT = re.compile(r"[\s，。、；：！？,.;:!?（）()【】\[\]“”\"'’‘\-—…·]")

MODES = ("all", "any", "each")


def _int_points(value: float) -> int:
    """分数只能取整数：四舍五入，不出现 2.5 这种。"""
    return int(value + 0.5)


def normalize(text: str) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)  # 全角 -> 半角
    return _PUNCT.sub("", text).upper()


def _alts(key: str) -> list[str]:
    """一个采分点可以写成 "增加就业岗位|提供就业岗位"，任一命中即算这一分。"""
    return [normalize(a) for a in key.split("|") if normalize(a)]


def _sub_score(sub: dict, text: str) -> dict:
    points = float(sub["points"])
    keys = [k for k in sub.get("keys", []) if k]
    norm_text = normalize(text)
    mode = sub.get("mode", "all")
    if mode not in MODES:
        raise ValueError(f"unknown mode {mode!r}")

    hits = [k for k in keys if any(alt in norm_text for alt in _alts(k))]
    per_key = sub.get("per_key")
    if per_key is not None:
        # 按「条」给分：答对一条得 per_key 分，封顶 points
        points_got = min(points, float(per_key) * len(hits))
        return {
            "label": sub.get("label", ""),
            "points": _int_points(points_got),
            "max": points,
            "keys_hit": hits,
            "keys_miss": [k for k in keys if k not in hits],
            "text": text,
        }

    if mode == "each":
        ratio = len(hits) / len(keys) if keys else 0.0
    elif mode == "any":
        ratio = 1.0 if hits else 0.0
    else:  # all
        ratio = 1.0 if len(hits) == len(keys) else 0.0

    return {
        "label": sub.get("label", ""),
        "points": _int_points(points * ratio),
        "max": points,
        "keys_hit": hits,
        "keys_miss": [k for k in keys if k not in hits],
        "text": text,
    }


def _ai_score(sub: dict, text: str, scorer) -> dict:
    """简答题：交给模型给 0~满分，模型挂了就退回关键词兜底。"""
    points = float(sub["points"])
    label = sub.get("label", "")
    base = {"label": label, "max": points, "text": text}
    if scorer is None:
        return {**base, "points": 0.0, "error": "mode=ai 但没有配 ai_scorer，拒绝瞎给分"}
    try:
        got = scorer(sub, text)
        raw = float(got.get("分数"))
        pts = max(0, min(int(points), _int_points(raw)))
        return {**base, "points": pts, "reason": str(got.get("理由", ""))}
    except Exception as exc:  # noqa: BLE001 - 任何模型/解析问题都兜底，不能因此丢分
        fb = _sub_score({**sub, "mode": "each"}, text)
        fb["fallback"] = f"AI 评分失败，退回关键词: {exc}"
        return fb


def grade(answer_key: dict, extracted: dict, ai_scorer=None) -> dict:
    """extracted: {"题号": "3", "子题": [{"标号": "(2)", "文本": "..."}]}

    ai_scorer(sub_spec, text) -> {"分数": float, "理由": str}，只为 mode=ai 的子题调用。
    """
    qid = str(extracted.get("题号", "")).strip()
    questions = answer_key.get("questions", {})
    default_q = str(answer_key.get("default_question", "")).strip()
    # 标题栏的「题号」经常是空的或读不出来 —— 固定的题组用 default_question 兜底
    resolved = qid if qid in questions else (default_q or qid)
    spec = questions.get(resolved) or questions.get("*")
    if spec is None:
        return {
            "题号": qid,
            "error": f"no answer key for 题号 {qid!r}",
            "score": None,
            "max": None,
            "detail": [],
        }
    qid = resolved

    texts = {
        str(item.get("标号", "")).strip(): str(item.get("文本", ""))
        for item in extracted.get("子题", [])
    }

    detail = []
    for sub in spec.get("subs", []):
        label = str(sub.get("label", "")).strip()
        text = texts.get(label, "")
        if sub.get("mode") == "ai":
            detail.append(_ai_score(sub, text, ai_scorer))
        else:
            detail.append(_sub_score(sub, text))

    total = sum(d["points"] for d in detail)
    max_total = sum(d["max"] for d in detail)
    if spec.get("full_marks") is not None:
        max_total = float(spec["full_marks"])
    total = min(total, max_total)
    return {"题号": qid, "score": total, "max": max_total, "detail": detail}

