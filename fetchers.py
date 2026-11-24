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


# 东财有多个可轮换的行情域名，避免单域名限流
EM_HOSTS = ["push2.eastmoney.com", "push2delay.eastmoney.com",
            "82.push2.eastmoney.com", "91.push2.eastmoney.com"]


def _em_get(path_with_query, tries=2):
    """依次尝试东财各域名，任一成功即返回。path 需以 / 开头。"""
    last = None
    for host in EM_HOSTS:
        try:
            return _get("https://" + host + path_with_query, tries=tries)
        except Exception as e:
            last = e
            time.sleep(1)
    raise last


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
    """东财行业/概念板块涨幅榜与跌幅榜。
    注意 clist 单页上限 100 条，涨/跌分别用不同排序请求。"""
    base = ("/api/qt/clist/get?pn=1&pz=100&np=1&fltt=2&fid=f3"
            "&fs=m:90+t:2&fields=f3,f14&po=")
    up_diff = _em_get(base + "1").json()["data"]["diff"]
    down_diff = _em_get(base + "0").json()["data"]["diff"]
    up = [{"name": x["f14"], "pct": x["f3"]} for x in up_diff[:top]]
    down = [{"name": x["f14"], "pct": x["f3"]} for x in down_diff[:5]]
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


_BREADTH_CACHE = {}


def _page_f3(pn, pz=100):
    """取按涨跌幅降序排列的第 pn 页（1-based），返回 f3 列表。"""
    if pn in _BREADTH_CACHE:
        return _BREADTH_CACHE[pn]
    path = ("/api/qt/clist/get?pn={}&pz={}&po=1&np=1&fltt=2&fid=f3"
            "&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23&fields=f3").format(pn, pz)
    diff = _em_get(path).json()["data"]["diff"]
    vals = [x.get("f3") for x in diff]
    _BREADTH_CACHE[pn] = vals
    return vals


def _count_breadth(pz=100):
    """二分定位「上涨/平盘/下跌」的分界页，返回 (上涨家数, 上涨+平盘家数)。"""
    _BREADTH_CACHE.clear()
    first = _page_f3(1, pz)
    total = len(first)
    # 估算总页数
    path0 = ("/api/qt/clist/get?pn=1&pz=1&po=1&np=1&fltt=2&fid=f3"
             "&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23&fields=f3")
    total_all = _em_get(path0).json()["data"].get("total") or total
    pages = (total_all + pz - 1) // pz

    def first_val(pn):
        v = _page_f3(pn, pz)
        return v[0] if v else None

    def boundary(cond):
        """找第一个满足 cond(页首值) 的页号。"""
        lo, hi = 1, pages
        while lo < hi:
            mid = (lo + hi) // 2
            v = first_val(mid)
            if v is None:
                return lo
            if cond(v):
                hi = mid
            else:
                lo = mid + 1
        return lo

    def count_until(pn_end, pred):
        """统计前 pn_end-1 页中满足 pred 的数量 + 第 pn_end 页内的数量。"""
        n = (pn_end - 1) * pz
        for v in _page_f3(pn_end, pz):
            if v is None:
                break
            if pred(v):
                n += 1
        return n

    # 第一个「页首 <= 0」的页 → 上涨数量
    pn_up = boundary(lambda v: v <= 0)
    up = 0
    if pn_up > 1:
        prev = _page_f3(pn_up - 1, pz)
        up = (pn_up - 2) * pz + sum(1 for v in prev if isinstance(v, (int, float)) and v > 0)
    up += sum(1 for v in _page_f3(pn_up, pz) if isinstance(v, (int, float)) and v > 0)

    # 第一个「页首 < 0」的页 → 上涨+平盘数量
    pn_flat = boundary(lambda v: v < 0)
    upflat = 0
    if pn_flat > 1:
        prev = _page_f3(pn_flat - 1, pz)
        upflat = (pn_flat - 2) * pz + sum(
            1 for v in prev if isinstance(v, (int, float)) and v >= 0)
    upflat += sum(1 for v in _page_f3(pn_flat, pz) if isinstance(v, (int, float)) and v >= 0)
    return up, upflat, total_all


def fetch_market_stats():
    """全市场统计：涨跌家数 + 涨停/跌停数。
    东财 clist 单页上限 100 条，因此涨跌家数改用指数行情接口的 f104/f105/f106，
    涨跌停数用涨停池/跌停池接口（准确值）。"""
    stats = {"up": None, "down": None, "flat": None,
             "limit_up": None, "limit_down": None, "src": []}

    # 1) 涨跌家数：上证指数行情附带的全市场统计字段
    try:
        path = ("/api/qt/stock/get?"
                "ut=fa5fd1943c7b386f172d6893dbfba10b&invt=2&fltt=2"
                "&fields=f104,f105,f106&secid=1.000001")
        d = _em_get(path).json().get("data") or {}
        if isinstance(d.get("f104"), (int, float)) and \
                isinstance(d.get("f105"), (int, float)):
            stats["up"], stats["down"] = int(d["f104"]), int(d["f105"])
            stats["flat"] = int(d.get("f106") or 0)
            stats["src"].append("index_breadth")
        else:
            print("      [stat] breadth字段缺失:", str(d)[:100])
    except Exception as e:
        print("      [stat] breadth失败:", type(e).__name__, str(e)[:80])

    # 2) 涨停 / 跌停家数：涨停池、跌停池接口
    today = datetime.date.today().strftime("%Y%m%d")
    pools = [("limit_up", "getTopicZTPool", "fbt:asc"),
             ("limit_down", "getTopicDTPool", "fund:asc")]
    for key, api, sort in pools:
        try:
            url = (f"https://push2ex.eastmoney.com/{api}?ut=7eea3edcaed734bea9cbfc24409ed989"
                   f"&dpt=wz.ztzt&Pageindex=0&pagesize=1&sort={sort}&date={today}")
            d = _get(url).json().get("data") or {}
            cnt = d.get("tc", d.get("total"))
            if isinstance(cnt, int):
                stats[key] = cnt
                stats["src"].append(api)
            else:
                print(f"      [stat] {api} 无计数:", str(d)[:100])
        except Exception as e:
            print(f"      [stat] {api} 失败:", type(e).__name__, str(e)[:80])

    # 3) 涨跌家数：利用 f3 降序 + 二分查找页边界，精确统计（约12次请求）
    if stats["up"] is None:
        try:
            up, upflat, total_all = _count_breadth()
            stats["up"] = up
            stats["flat"] = max(upflat - up, 0)
            stats["down"] = max(total_all - upflat, 0)
            stats["src"].append("bisect")
        except Exception as e:
            print("      [stat] 二分统计失败:", type(e).__name__, str(e)[:60])

    # 全部字段都拿不到才算失败
    if all(stats[k] is None for k in ("up", "down", "limit_up", "limit_down")):
        raise RuntimeError("市场统计接口均不可用")
    return stats


def _is_tradable_stock(code, name):
    """过滤 ETF/基金/转债/北交所等，只保留沪深主板、创业板、科创板个股。"""
    if not code or len(code) != 6:
        return False
    if code[0] not in ("0", "3", "6"):
        return False
    bad = ("ETF", "LOF", "基金", "转债", "债", "ST", "退")
    return not any(b in name for b in bad)


def fetch_top_gainers(n=8):
    """当日涨幅榜（排除ST、退市、ETF、低价股），作为动态选股池。"""
    path = ("/api/qt/clist/get?pn=1&pz=100&po=1"
            "&np=1&fltt=2&fid=f3"
            "&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23"
            "&fields=f2,f3,f12,f14")
    diff = _em_get(path).json()["data"]["diff"]
    out = []
    for x in diff:
        name = x.get("f14") or ""
        price = x.get("f2")
        if not isinstance(price, (int, float)) or price < 2:
            continue
        if not _is_tradable_stock(x.get("f12", ""), name):
            continue
        out.append({"code": x["f12"], "name": name,
                    "price": price, "pct": x["f3"]})
        if len(out) >= n:
            break
    return out


def fetch_candidates(news_list, max_n=6):
    """动态选股候选：新闻提及个股 + 当日涨幅榜龙头，去重后取前 N 只。"""
    picked, seen = [], set()

    def add(code, name, price, pct):
        if code in seen or len(picked) >= max_n:
            return
        if not _is_tradable_stock(code, name):
            return
        seen.add(code)
        picked.append({"code": code, "name": name,
                       "price": price, "pct": pct})

    # 1) 新闻中被提及的个股（东财 stockList 格式如 "1.600941"）
    news_codes = []
    for n in news_list:
        for c in n.get("stocks") or []:
            parts = c.split(".")
            if len(parts) == 2 and parts[0] in ("0", "1") and len(parts[1]) == 6:
                news_codes.append(parts[1])
    if news_codes:
        q = ",".join(("s_sh" if c.startswith(("6", "9")) else "s_sz") + c
                     for c in news_codes[:12])
        try:
            text = _get("https://qt.gtimg.cn/q=" + q,
                        headers={**HEADERS, "Referer": "https://gu.qq.com/"}).text
            for m in re.finditer(r'v_s_(\w+)="([^"]+)"', text):
                f = m.group(2).split("~")
                if len(f) > 6:
                    add(f[2], f[1], float(f[3]), float(f[5]))
        except Exception:
            pass

    # 2) 涨幅榜龙头补足
    try:
        for g in fetch_top_gainers(10):
            add(g["code"], g["name"], g["price"], g["pct"])
    except Exception:
        pass
    return picked


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
         "news": {}, "crypto": [], "sources": {},
         "market_stats": None, "candidates": []}

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
    stats = step("市场统计", fetch_market_stats)
    if stats:
        d["market_stats"] = stats
    # 动态选股候选：依赖快讯里的个股提及
    all_news = [n for items in d["news"].values() for n in items]
    cands = step("选股候选", fetch_candidates, all_news)
    if cands:
        d["candidates"] = cands

    # 全部成功则标记 sources 为 ok
    for k in ["行情指数", "板块榜单", "财经快讯", "币价", "市场统计", "选股候选"]:
        d["sources"].setdefault(k, "ok")
    return d


if __name__ == "__main__":
    d = gather()
    print(d["date"], "指数:", [(x["name"], x["pct"]) for x in d["index"]])
    print("领涨板块:", [x["name"] for x in d["sector_up"][:5]])
    print("宏观条数:", len(d["news"]["宏观"]), "大宗:", len(d["news"]["大宗商品"]),
          "币圈:", len(d["news"]["币圈"]), "综合:", len(d["news"]["综合"]))
    print("币价:", d["crypto"])
