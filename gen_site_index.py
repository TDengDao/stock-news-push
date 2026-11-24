# -*- coding: utf-8 -*-
"""为 GitHub Pages 生成归档索引页 index.html。
用法: python gen_site_index.py <site_dir>
扫描目录下所有 YYYY-MM-DD.html，按日期倒序生成索引。"""
import pathlib
import re
import sys

TEMPLATE = """<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>财经早报 · 历史归档</title>
<style>
body{{font-family:-apple-system,"Microsoft YaHei",sans-serif;max-width:720px;
margin:0 auto;padding:24px;color:#222;background:#fff;line-height:1.7}}
h1{{border-bottom:2px solid #c0392b;padding-bottom:8px}}
.btn{{display:inline-block;background:#c0392b;color:#fff;padding:10px 18px;
border-radius:8px;text-decoration:none;margin:12px 0}}
ul{{list-style:none;padding:0}}
li{{border-bottom:1px solid #f0f0f0;padding:10px 0}}
li a{{color:#333;text-decoration:none}} li a:hover{{color:#c0392b}}
.tag{{color:#999;font-size:13px;margin-left:8px}}
.foot{{color:#999;font-size:12px;margin-top:32px;border-top:1px solid #eee;
padding-top:12px}}
</style></head><body>
<h1>📈 财经早报 · 历史归档</h1>
<p>每日 A股大盘 / 板块热点 / 市场统计 / AI 决策仪表盘 / 宏观·大宗·币圈要闻</p>
<p><a class="btn" href="latest.html">查看今日最新日报 →</a></p>
<h2>历史报告</h2>
<ul>{items}</ul>
<p class="foot">自动生成 · 数据来源：东方财富、新浪财经、腾讯行情、CoinGecko ·
AI 分析由 DeepSeek 提供 · 仅供信息参考，不构成投资建议</p>
</body></html>"""


def main():
    site = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "site")
    site.mkdir(exist_ok=True)
    files = sorted(
        [p for p in site.glob("*.html")
         if re.fullmatch(r"\d{4}-\d{2}-\d{2}\.html", p.name)],
        reverse=True)
    items = []
    for i, p in enumerate(files):
        date = p.stem
        tag = "<span class='tag'>最新</span>" if i == 0 else ""
        items.append(f"<li><a href='{p.name}'>{date} 财经早报</a>{tag}</li>")
    (site / "index.html").write_text(
        TEMPLATE.format(items="\n".join(items) or "<li>暂无报告</li>"),
        encoding="utf-8")
    print(f"索引已生成: {site}/index.html（{len(files)} 份报告）")


if __name__ == "__main__":
    main()
