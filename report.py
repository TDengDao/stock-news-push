# -*- coding: utf-8 -*-
"""日报生成模块：Markdown + 简洁 HTML。"""
import html as _html


def _pct_color(pct):
    # 中国习惯：涨红跌绿
    cls = "up" if pct > 0 else ("down" if pct < 0 else "flat")
    sign = "+" if pct > 0 else ""
    return f'<span class="{cls}">{sign}{pct}%</span>'


def _esc(s):
    return _html.escape(str(s))


def _fmt_dashboard_item(a):
    """单只股票的仪表盘文本块（Markdown）。"""
    icon = {"买入": "🔴", "卖出": "🟢", "观望": "🟡"}.get(a.get("verdict"), "⚪")
    lines = [f"#### {icon} {a.get('name')}({a.get('code')}) · "
             f"{a.get('verdict')} · 评分 {a.get('score')}",
             f"- 📌 {a.get('summary', '')}",
             f"- ℹ️ {a.get('key_info', '')}"]
    vals = []
    if a.get("pe") is not None:
        vals.append(f"PE {a['pe']}")
    if a.get("pb") is not None:
        vals.append(f"PB {a['pb']}")
    if a.get("roe") is not None:
        vals.append(f"ROE {a['roe']}%")
    if vals:
        lines.append("- 💹 " + " · ".join(vals))
    risks = a.get("risks") or []
    poss = a.get("positives") or []
    if risks:
        lines.append("- ⚠️ 风险：" + "；".join(risks))
    if poss:
        lines.append("- ✨ 利好：" + "；".join(poss))
    if a.get("latest"):
        lines.append("- 📰 " + a["latest"])
    return "\n".join(lines)


def build_markdown(d):
    lines = [f"# 财经早报 · {d['date']} · {d.get('phase_label', '全天')}", ""]

    dash = [a for a in (d.get("dashboard") or []) if isinstance(a, dict)]
    if dash:
        lines.append("## 🎯 决策仪表盘（AI 动态选股）")
        lines.append("")
        lines.append(f"> 今日分析 **{len(dash)}** 只市场热点股 · "
                     f"买入:{sum(1 for a in dash if a.get('verdict') == '买入')} "
                     f"观望:{sum(1 for a in dash if a.get('verdict') == '观望')} "
                     f"卖出:{sum(1 for a in dash if a.get('verdict') == '卖出')}")
        lines.append("")
        for a in dash:
            lines.append(_fmt_dashboard_item(a))
        lines.append("")

    review = d.get("review") or []
    if review:
        lines.append("## 📈 历史推荐复盘")
        for r in review:
            if not r.get("count"):
                continue
            lines.append(f"- **{r['days']} 日前（{r['date']}）** 推荐 {r['count']} 只 · "
                         f"平均 {r['avg']:+.2f}% · 上涨占比 {r['win']}% · "
                         f"最好 {r['best']:+.2f}% / 最差 {r['worst']:+.2f}%")
        lines.append("")

    lines.append("## 大盘指数")
    lines.append("| 指数 | 点位 | 涨跌幅 |")
    lines.append("|---|---|---|")
    for x in d["index"]:
        sign = "+" if x["pct"] > 0 else ""
        lines.append(f"| {x['name']} | {x['price']} | {sign}{x['pct']}% |")
    lines.append("")

    lines.append("## 板块热点")
    lines.append("- **领涨**: " + "、".join(
        f"{x['name']}(+{x['pct']}%)" if x["pct"] > 0 else f"{x['name']}({x['pct']}%)"
        for x in d["sector_up"]))
    lines.append("- **领跌**: " + "、".join(
        f"{x['name']}({x['pct']}%)" for x in d["sector_down"]))
    lines.append("")

    stats = d.get("market_stats") or {}
    if stats:
        rows = []
        if stats.get("up") is not None and stats.get("down") is not None:
            t = f"- 上涨 **{stats['up']}** 家 | 下跌 **{stats['down']}** 家"
            if stats.get("flat") is not None:
                t += f" | 平盘 {stats['flat']} 家"
            rows.append(t)
        if stats.get("limit_up") is not None:
            t = f"- 涨停 **{stats['limit_up']}** 只"
            if stats.get("limit_down") is not None:
                t += f" | 跌停 **{stats['limit_down']}** 只"
            rows.append(t)
        if rows:
            lines.append("## 市场概览")
            lines.extend(rows)
            lines.append("")

    if d["crypto"]:
        lines.append("## 币圈行情")
        lines.append("| 币种 | 价格(USD) | 24h |")
        lines.append("|---|---|---|")
        for x in d["crypto"]:
            sign = "+" if x["pct"] > 0 else ""
            lines.append(f"| {x['name']} | {x['price']:,} | {sign}{x['pct']}% |")
        lines.append("")

    for cat in ["宏观", "大宗商品", "币圈", "综合"]:
        items = d["news"].get(cat) or []
        if not items:
            continue
        lines.append(f"## {cat}要闻（{len(items)}条）")
        for n in items[:15]:
            title = n["title"] or n["summary"][:50]
            body = n["summary"]
            ts = f"`{n['time']}` " if n["time"] else ""
            lines.append(f"- {ts}**{title}**" if body != title else f"- {ts}{body}")
            if body != title:
                lines.append(f"  > {body}")
        lines.append("")

    failed = {k: v for k, v in (d.get("sources") or {}).items() if v != "ok"}
    if failed:
        lines.append("⚠️ 部分数据源本次不可用: " +
                     ", ".join(f"{k}({v})" for k, v in failed.items()))
        lines.append("")

    lines.append("---")
    lines.append("*数据来源：东方财富、新浪财经、CoinGecko。本报告仅为信息聚合，不构成投资建议。*")
    return "\n".join(lines)


def build_html(d, md_text):
    rows = "".join(
        f"<tr><td>{_esc(x['name'])}</td><td>{x['price']}</td>"
        f"<td>{_pct_color(x['pct'])}</td></tr>"
        for x in d["index"])
    crypto_rows = "".join(
        f"<tr><td>{_esc(x['name'])}</td><td>{x['price']:,}</td>"
        f"<td>{_pct_color(x['pct'])}</td></tr>"
        for x in d["crypto"])
    up_line = " · ".join(f"{_esc(x['name'])} +{x['pct']}%" for x in d["sector_up"])
    down_line = " · ".join(f"{_esc(x['name'])} {x['pct']}%" for x in d["sector_down"])

    dash_html = ""
    dash = [a for a in (d.get("dashboard") or []) if isinstance(a, dict)]
    if dash:
        cards = ""
        for a in dash:
            v = a.get("verdict", "观望")
            color = {"买入": "#d63031", "卖出": "#00b894"}.get(v, "#fdcb6e")
            risks = "".join(f"<li>{_esc(r)}</li>" for r in (a.get("risks") or []))
            poss = "".join(f"<li>{_esc(p)}</li>" for p in (a.get("positives") or []))
            cards += f"""<div class="card">
<div class="card-head"><b>{_esc(a.get('name'))}({_esc(a.get('code'))})</b>
<span class="verdict" style="background:{color}">{_esc(v)} · {_esc(a.get('score'))}分</span></div>
<p>{_esc(a.get('summary',''))}</p>
<p><small>ℹ️ {_esc(a.get('key_info',''))}</small></p>
{f'<p class="risk"><b>⚠️ 风险</b></p><ul>{risks}</ul>' if risks else ''}
{f'<p class="pos"><b>✨ 利好</b></p><ul>{poss}</ul>' if poss else ''}
{f'<p><small>📰 {_esc(a["latest"])}</small></p>' if a.get("latest") else ''}
</div>"""
        dash_html = f"<h2>🎯 决策仪表盘（AI 动态选股，共{len(dash)}只）</h2>{cards}"

    review_html = ""
    review = d.get("review") or []
    review_items = [
        f"<li>{r['days']} 日前（{r['date']}）推荐 {r['count']} 只 · "
        f"平均 {r['avg']:+.2f}% · 上涨占比 {r['win']}%</li>"
        for r in review if r.get("count")]
    if review_items:
        review_html = "<h2>📈 历史推荐复盘</h2><ul>" + "".join(review_items) + "</ul>"

    stats_html = ""
    stats = d.get("market_stats") or {}
    if stats:
        bits = []
        if stats.get("up") is not None and stats.get("down") is not None:
            bits.append(f"上涨 <b class=\"up\">{stats['up']}</b> 家 · "
                        f"下跌 <b class=\"down\">{stats['down']}</b> 家"
                        + (f" · 平盘 {stats['flat']} 家" if stats.get("flat") is not None else ""))
        if stats.get("limit_up") is not None:
            bits.append(f"涨停 <b class=\"up\">{stats['limit_up']}</b> 只"
                        + (f" · 跌停 <b class=\"down\">{stats['limit_down']}</b> 只"
                           if stats.get("limit_down") is not None else ""))
        if bits:
            stats_html = "<h2>市场概览</h2><p>" + "<br>".join(bits) + "</p>"

    sections = ""
    for cat in ["宏观", "大宗商品", "币圈", "综合"]:
        items = d["news"].get(cat) or []
        if not items:
            continue
        lis = "".join(
            f"<li><b>{_esc(n['title'] or n['summary'][:50])}</b>"
            f"<br><small>{_esc(n['summary'])}</small></li>"
            for n in items[:15])
        sections += f"<h3>{_esc(cat)}要闻（{len(items)}条）</h3><ul>{lis}</ul>"

    return f"""<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8">
<title>财经早报 {d['date']}</title>
<style>
body{{font-family:-apple-system,"Microsoft YaHei",sans-serif;max-width:720px;
margin:0 auto;padding:24px;color:#222;background:#fff;line-height:1.6}}
h1{{border-bottom:2px solid #c0392b;padding-bottom:8px}}
h2{{margin-top:28px}} h3{{margin-top:20px}}
table{{border-collapse:collapse;width:100%}}
td,th{{border-bottom:1px solid #eee;padding:6px 10px;text-align:left}}
.up{{color:#d63031;font-weight:bold}} .down{{color:#00b894;font-weight:bold}}
.flat{{color:#999}} small{{color:#666}}
.card{{border:1px solid #eee;border-radius:10px;padding:12px 14px;margin:12px 0;
box-shadow:0 1px 3px rgba(0,0,0,.04)}}
.card-head{{display:flex;justify-content:space-between;align-items:center;
border-bottom:1px dashed #eee;padding-bottom:6px;margin-bottom:6px}}
.verdict{{color:#fff;padding:2px 10px;border-radius:12px;font-size:13px}}
.risk{{color:#c0392b;margin-bottom:2px}} .pos{{color:#00a86b;margin-bottom:2px}}
ul{{margin:4px 0 4px 20px;padding:0}}
.foot{{color:#999;font-size:12px;margin-top:32px;border-top:1px solid #eee;
padding-top:12px}}
</style></head><body>
<h1>财经早报 · {d['date']} · {_esc(d.get('phase_label', '全天'))}</h1>
{dash_html}
{review_html}
<h2>大盘指数</h2>
<table><tr><th>指数</th><th>点位</th><th>涨跌幅</th></tr>{rows}</table>
{stats_html}
<h2>板块热点</h2>
<p><b>领涨</b>：{up_line}</p>
<p><b>领跌</b>：{down_line}</p>
{f'<h2>币圈行情</h2><table><tr><th>币种</th><th>价格(USD)</th><th>24h</th></tr>{crypto_rows}</table>' if crypto_rows else ''}
{sections}
<p class="foot">数据来源：东方财富、新浪财经、腾讯行情、CoinGecko ·
AI 分析由 DeepSeek 生成 · 仅供信息参考，不构成投资建议</p>
</body></html>"""


def build_telegram_text(d):
    """Telegram/Server酱 用的纯文本精简版。"""
    idx = " | ".join(
        f"{x['name']} {x['pct']:+.2f}%" for x in d["index"])
    up = "、".join(f"{x['name']}+{x['pct']}%" for x in d["sector_up"][:6])
    lines = [f"📰 财经早报 {d['date']} · {d.get('phase_label', '全天')}", "", f"📊 大盘：{idx}",
             f"🔥 领涨：{up}"]
    stats = d.get("market_stats") or {}
    if stats:
        t = []
        if stats.get("up") is not None:
            t.append(f"{stats['up']}涨/{stats['down']}跌")
        if stats.get("limit_up") is not None:
            t.append(f"涨停{stats['limit_up']}")
        if t:
            lines.append("📈 " + " · ".join(t))
    dash = [a for a in (d.get("dashboard") or []) if isinstance(a, dict)]
    if dash:
        lines.append("")
        lines.append("🎯 AI决策仪表盘：")
        for a in dash[:6]:
            icon = {"买入": "🔴", "卖出": "🟢", "观望": "🟡"}.get(
                a.get("verdict"), "⚪")
            lines.append(f"{icon} {a.get('name')}({a.get('code')}) "
                         f"{a.get('verdict')} {a.get('score')}分 — "
                         f"{a.get('summary', '')}")
    review = d.get("review") or []
    for r in review:
        if r.get("count"):
            lines.append(f"📈 {r['days']}日前推荐复盘：平均 {r['avg']:+.2f}% · "
                         f"上涨占比 {r['win']}%")
    if d["crypto"]:
        crypto = " | ".join(
            f"{x['name']} {x['price']:,}({x['pct']:+.2f}%)" for x in d["crypto"])
        lines.append(f"🪙 币价：{crypto}")
    for cat, emoji in [("宏观", "🏛"), ("大宗商品", "🛢"), ("币圈", "🪙"), ("综合", "📌")]:
        items = d["news"].get(cat) or []
        if items:
            lines.append("")
            lines.append(f"{emoji} {cat}要闻：")
            for n in items[:8]:
                text = n["title"] or n["summary"][:50]
                lines.append(f"• {text}")
    lines.append("")
    lines.append("⚠️ 本内容由公开数据与 AI 自动生成，仅供参考，不构成投资建议。")
    return "\n".join(lines)
