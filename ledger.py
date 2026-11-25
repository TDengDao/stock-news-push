# -*- coding: utf-8 -*-
"""推荐台账：记录每日盘前推荐，并在盘后计算 1/3/5 日后的表现。"""
import datetime
import json
import pathlib

BASE = pathlib.Path(__file__).parent
DATA_DIR = BASE / "data"
LEDGER = DATA_DIR / "ledger.json"


def load():
    try:
        rows = json.loads(LEDGER.read_text(encoding="utf-8"))
        return rows if isinstance(rows, list) else []
    except Exception:
        return []


def save(rows):
    DATA_DIR.mkdir(exist_ok=True)
    LEDGER.write_text(
        json.dumps(rows[-500:], ensure_ascii=False, indent=2),
        encoding="utf-8")


def add_picks(date, phase, picks):
    """picks: [{'code','name','price','score','verdict'}]。"""
    if not picks:
        return
    rows = load()
    rows.append({"date": date, "phase": phase, "picks": picks})
    save(rows)


def review_codes(today):
    """只取 1/3/5 日前盘前推荐涉及的股票代码，避免抓取全量历史。"""
    targets = set()
    today_date = datetime.date.fromisoformat(today)
    for days in (1, 3, 5):
        targets.add((today_date - datetime.timedelta(days=days)).isoformat())
    codes = set()
    for row in load():
        if row.get("date") in targets and row.get("phase") == "premarket":
            for p in row.get("picks") or []:
                if p.get("code"):
                    codes.add(p["code"])
    return codes


def review(today, current_prices):
    """返回 1/3/5 个自然日前盘前推荐的收益摘要。"""
    rows = load()
    out = []
    today_date = datetime.date.fromisoformat(today)
    for days in (1, 3, 5):
        target = (today_date - datetime.timedelta(days=days)).isoformat()
        rets = []
        for row in rows:
            if row.get("date") != target or row.get("phase") != "premarket":
                continue
            for p in row.get("picks") or []:
                code = p.get("code")
                now = (current_prices or {}).get(code)
                base = p.get("price")
                try:
                    base = float(base)
                    now = float(now)
                    if base > 0:
                        rets.append(round((now / base - 1) * 100, 2))
                except Exception:
                    continue
        if rets:
            out.append({
                "days": days,
                "date": target,
                "count": len(rets),
                "avg": round(sum(rets) / len(rets), 2),
                "win": round(100 * sum(1 for r in rets if r > 0) / len(rets)),
                "best": max(rets),
                "worst": min(rets),
            })
    return out
