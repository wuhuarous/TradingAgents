"""结构化输出辅助 — 确保 Agent 输出可解析 JSON"""
import json
import re


def extract_json(text: str) -> dict:
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        return json.loads(match.group())
    return {}


def parse_rating(rating_text: str) -> dict:
    data = extract_json(rating_text)
    score = min(10, max(1, int(data.get("score", 5))))
    confidence = min(1.0, max(0.0, float(data.get("confidence", 0.5))))
    return {
        "score": score,
        "confidence": confidence,
        "reasoning": str(data.get("reasoning", "")),
    }
