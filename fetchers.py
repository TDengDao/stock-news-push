# -*- coding: utf-8 -*-
"""数据抓取模块：全部使用免费公开接口，无需 API Key。"""
import re
import datetime
import time

import requests

# 独立会话并禁用系统代理，避免 VPS/本机环境变量里的代理干扰直连
_session = requests.Session()
_session.trust_env = False

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://quote.eastmoney.com/",
}

# 关键词分类（用于快讯归类）
KEYWORDS = {
    "宏观": ["央行", "美联储", "国务院", "财政部", "关税", "CPI", "GDP", "PMI",
             "降准", "降息", "LPR", "汇率", "政策", "发改委", "证监会", "统计局",
             "贸易", "进出口", "通胀", "加息", "利率"],
    "大宗商品": ["原油", "黄金", "白银", "铜", "铁矿", "煤炭", "天然气", "大豆",
                "焦炭", "螺纹", "运价", "波罗的海", "镍", "钴", "锂", "期货"],
    "币圈": ["比特币", "以太坊", "加密", "稳定币", "USDT", "币圈", "数字货币",
             "虚拟资产", "区块链", "矿机"],
}


def _get(url, tries=3, **kw):
    """带重试的 GET；headers 参数与默认 HEADERS 合并。"""
    headers = {**HEADERS, **kw.pop("headers", {})}
    last_err = None
    for i in range(tries):
        try:
            r = _session.get(url, headers=headers, timeout=15, **kw)
            r.raise_for_status()
            return r
        except Exception as e:
            last_err = e
            if i < tries - 1:
                time.sleep(2)
    raise last_err


def fetch_index_snapshot():
    """A股核心指数快照：上证、深成、创业板、科创50。
    优先腾讯行情（稳定），失败则回退东财。"""
    try:
        url = ("https://qt.gtimg.cn/q=s_sh000001,s_sz399001,"
               "s_sz399006,s_sh000688")
        text = _get(url, headers={**HEADERS,
                    "Referer": "https://gu.qq.com/"}).text
        out = []
        for m in re.finditer(r'v_s_\w+="([^"]+)"', text):
            f = m.group(1).split("~")
            if len(f) > 6:
                # 格式: 市场~名称~代码~点位~涨跌~涨跌幅~...
                out.append({"name": f[1], "price": float(f[3]),
                            "pct": float(f[5]), "chg": float(f[4])})
        if out:
            return out
    except Exception:
        pass
    # 回退：东财
    url = ("https://push2.eastmoney.com/api/qt/ulist.np/get?fltt=2"
           "&secids=1.000001,0.399001,0.399006,1.000688&fields=f2,f3,f4,f12,f14")
    data = _get(url).json()["data"]["diff"]
    return [{"name": x["f14"], "price": x["f2"], "pct": x["f3"], "chg": x["f4"]}
            for x in data]


def fetch_sector_rank(top=10):
    """东财行业/概念板块涨幅榜与跌幅榜。"""
    url = ("https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=500&po=1"
           "&np=1&fltt=2&fid=f3&fs=m:90+t:2&fields=f3,f14")
    diff = _get(url).json()["data"]["diff"]
    diff.sort(key=lambda x: x["f3"], reverse=True)
    up = [{"name": x["f14"], "pct": x["f3"]} for x in diff[:top]]
    down = [{"name": x["f14"], "pct": x["f3"]} for x in reversed(diff[-5:])]
    return up, down


def fetch_em_news(size=40):
    """东财 7x24 全球快讯。返回 [(time, title, summary, stock_list)]。"""
    url = ("https://np-weblist.eastmoney.com/comm/web/getFastNewsList"
           "?client=web&biz=web_724&fastColumn=102&sortEnd=&pageSize={}"
           "&req_trace=1".format(size))
    data = _get(url, headers={**HEADERS,
              "Referer": "https://kuaixun.eastmoney.com/"}).json()
    items = (data.get("data") or {}).get("fastNewsList") or []
    out = []
    for x in items:
        out.append({
            "time": x.get("showTime", "")[11:16],
            "title": (x.get("title") or "").strip(),
            "summary": (x.get("summary") or "").strip(),
            "stocks": x.get("stockList") or [],
        })
    return out


def fetch_sina_news(size=30):
    """新浪财经 7x24 快讯。返回 [(time, text)]。"""
    url = ("https://zhibo.sina.com.cn/api/zhibo/feed?page=1&page_size={}"
           "&zhibo_id=152&tag_id=0".format(size))
    data = _get(url).json()
    items = (data.get("result", {}).get("data", {}).get("feed", {}) or {}).get("list", [])
    out = []
    for x in items:
        text = re.sub(r"<[^>]+>", "", x.get("rich_text", "")).strip()
        t = (x.get("create_time") or "")[11:16] if x.get("create_time") else ""
        if text:
            out.append({"time": t, "title": text[:60], "summary": text, "stocks": []})
    return out


def classify(news_list):
    """按关键词把快讯分成 宏观 / 大宗 / 币圈 / 综合。"""
    buckets = {"宏观": [], "大宗商品": [], "币圈": [], "综合": []}
    for n in news_list:
        text = n["title"] + n["summary"]
        hit = None
        for cat, words in KEYWORDS.items():
            if any(w in text for w in words):
                hit = cat
                break
        buckets[hit or "综合"].append(n)
    return buckets


def dedup(news_list, limit=60):
    """按标题去重（东财和新浪常有条目重复）。"""
    seen, out = set(), []
    for n in news_list:
        key = n["title"][:20]
        if key and key not in seen:
            seen.add(key)
            out.append(n)
    return out[:limit]


def fetch_crypto(ids="bitcoin,ethereum"):
    """CoinGecko 币价（免 Key，频率限制内可用）。"""
    try:
        url = ("https://api.coingecko.com/api/v3/simple/price?ids={}"
               "&vs_currencies=usd&include_24hr_change=true".format(ids))
        data = _get(url).json()
        out = []
        name_map = {"bitcoin": "BTC", "ethereum": "ETH"}
        for k, v in data.items():
            out.append({"name": name_map.get(k, k),
                        "price": v["usd"],
                        "pct": round(v.get("usd_24h_change", 0) or 0, 2)})
        return out
    except Exception:
        return []


def gather():
    """汇总全部数据，返回日报所需的结构化字典。
    单个数据源失败不影响整体，失败信息记录在 sources 字段。"""
    today = datetime.date.today().strftime("%Y-%m-%d")
    d = {"date": today, "index": [], "sector_up": [], "sector_down": [],
         "news": {}, "crypto": [], "sources": {}}

    def step(name, fn, *a, **kw):
        try:
            return fn(*a, **kw)
        except Exception as e:
            d["sources"][name] = "FAIL: {}".format(type(e).__name__)
            return None

    idx = step("行情指数", fetch_index_snapshot)
    if idx:
        d["index"] = idx
    ranks = step("板块榜单", fetch_sector_rank)
    if ranks:
        d["sector_up"], d["sector_down"] = ranks
    news = step("财经快讯", lambda: dedup(
        fetch_em_news(40) + fetch_sina_news(30)))
    if news:
        d["news"] = classify(news)
    crypto = step("币价", fetch_crypto)
    if crypto:
        d["crypto"] = crypto

    # 全部成功则标记 sources 为 ok
    for k in ["行情指数", "板块榜单", "财经快讯", "币价"]:
        d["sources"].setdefault(k, "ok")
    return d


if __name__ == "__main__":
    d = gather()
    print(d["date"], "指数:", [(x["name"], x["pct"]) for x in d["index"]])
    print("领涨板块:", [x["name"] for x in d["sector_up"][:5]])
    print("宏观条数:", len(d["news"]["宏观"]), "大宗:", len(d["news"]["大宗商品"]),
          "币圈:", len(d["news"]["币圈"]), "综合:", len(d["news"]["综合"]))
    print("币价:", d["crypto"])
