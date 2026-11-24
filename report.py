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


def build_markdown(d):
    lines = [f"# 财经早报 · {d['date']}", ""]

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
.foot{{color:#999;font-size:12px;margin-top:32px;border-top:1px solid #eee;
padding-top:12px}}
</style></head><body>
<h1>财经早报 · {d['date']}</h1>
<h2>大盘指数</h2>
<table><tr><th>指数</th><th>点位</th><th>涨跌幅</th></tr>{rows}</table>
<h2>板块热点</h2>
<p><b>领涨</b>：{up_line}</p>
<p><b>领跌</b>：{down_line}</p>
{f'<h2>币圈行情</h2><table><tr><th>币种</th><th>价格(USD)</th><th>24h</th></tr>{crypto_rows}</table>' if crypto_rows else ''}
{sections}
<p class="foot">数据来源：东方财富、新浪财经、CoinGecko · 仅供信息参考，不构成投资建议</p>
</body></html>"""


def build_telegram_text(d):
    """Telegram/Server酱 用的纯文本精简版。"""
    idx = " | ".join(
        f"{x['name']} {x['pct']:+.2f}%" for x in d["index"])
    up = "、".join(f"{x['name']}+{x['pct']}%" for x in d["sector_up"][:6])
    lines = [f"📰 财经早报 {d['date']}", "", f"📊 大盘：{idx}",
             f"🔥 领涨：{up}"]
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
    return "\n".join(lines)
