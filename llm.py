# -*- coding: utf-8 -*-
"""DeepSeek 决策仪表盘：AI 动态选股分析。
需要环境变量 DEEPSEEK_API_KEY；没有则整个模块优雅跳过。"""
import json
import os

import requests

BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

SYSTEM_PROMPT = """你是一名严谨的A股投资分析师。根据提供的股票行情和当日相关新闻，\
对每只股票输出 JSON 分析。必须只输出一个 JSON 数组，不要输出任何其他文字。
每项格式：
{"code":"股票代码","name":"名称","score":0到100整数,
 "verdict":"买入|观望|卖出","summary":"一句话核心判断(30字内)",
 "key_info":"重要信息速览(50字内)",
 "risks":["风险1","风险2",...最多3条],
 "positives":["利好1","利好2",...最多3条],
 "latest":"最新动态(40字内)"}
评分参考：>=70 偏多，40-69 观望/震荡，<40 偏空。输入字段含 pe(动态市盈率)、\
pb(市净率)、roe(净资产收益率)，请结合估值与基本面，不要只看涨幅追高。\
判断必须基于给出的真实信息，不要编造数据；信息不足时 verdict 给"观望"并在 summary 说明。"""


def _client():
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not key:
        return None
    s = requests.Session()
    s.headers.update({"Authorization": "Bearer " + key,
                      "Content-Type": "application/json"})
    return s


def _related_news(candidates, buckets):
    """给每只候选股聚合当日相关新闻文本。"""
    for c in candidates:
        keys = [c["name"], c["code"]]
        texts = []
        for items in buckets.values():
            for n in items:
                t = n["title"] + n["summary"]
                if any(k in t for k in keys):
                    texts.append(n["summary"][:120])
        c["news"] = texts[:5] or ["当日无该股直接相关新闻，请仅基于行情判断。"]
    return candidates


def _extract_list(data):
    """从模型返回中尽力提取列表。"""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        # 常见包装键
        for k in ("stocks", "results", "data", "analysis", "items", "list"):
            v = data.get(k)
            if isinstance(v, list):
                return v
        # 兜底：第一个 list 值
        for v in data.values():
            if isinstance(v, list):
                return v
        # 单只股票被包成 dict
        if {"code", "score"} <= set(data):
            return [data]
    return []


def _normalize(items):
    """把列表里的元素规整成 dict（兼容字符串形式的 JSON 项）。"""
    out = []
    for it in items:
        if isinstance(it, str):
            try:
                it = json.loads(it)
            except Exception:
                continue
        if isinstance(it, dict) and (it.get("code") or it.get("name")):
            it.setdefault("verdict", "观望")
            try:
                it["score"] = int(float(it.get("score", 50)))
            except Exception:
                it["score"] = 50
            for k in ("risks", "positives"):
                v = it.get(k)
                if isinstance(v, str):
                    it[k] = [v]
                elif not isinstance(v, list):
                    it[k] = []
            out.append(it)
    return out


def analyze(candidates, buckets, timeout=90):
    """调用 DeepSeek 分析候选股。返回分析列表；不可用时返回 []。"""
    s = _client()
    if not s or not candidates:
        return []
    candidates = _related_news(candidates, buckets)
    payload = [{"code": c["code"], "name": c["name"],
                "price": c["price"], "pct": c["pct"],
                "pe": c.get("pe"), "pb": c.get("pb"), "roe": c.get("roe"),
                "news": c["news"]}
               for c in candidates]
    body = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",
             "content": "今日候选股票数据：\n" + json.dumps(
                 payload, ensure_ascii=False)},
        ],
        "temperature": 0.3,
        "response_format": {"type": "json_object"},
    }
    try:
        r = s.post(BASE_URL + "/chat/completions", json=body, timeout=timeout)
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"] or ""
        raw = content.strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            raw = raw[raw.find("{"):] if "{" in raw else raw
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            print("      [WARN] JSON 解析失败, 原始返回前200字:", raw[:200])
            import re
            m = re.search(r"\[.*\]", raw, re.S)
            data = json.loads(m.group(0)) if m else {}
        result = _normalize(_extract_list(data))
        if not result:
            print("      [WARN] 返回结构无法识别:", str(data)[:200])
        return result
    except Exception as e:
        print("      [WARN] DeepSeek 分析失败:", type(e).__name__, str(e)[:120])
        return []
