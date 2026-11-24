# -*- coding: utf-8 -*-
"""财经新闻日报 · 入口
用法: python main.py [--dry-run] [--config config.yaml]
--dry-run: 只生成日报不推送
环境变量: DEEPSEEK_API_KEY（可选，启用 AI 决策仪表盘）
"""
import argparse
import pathlib
import sys

import yaml

import fetchers
import llm
import pusher
import report

BASE = pathlib.Path(__file__).parent


def load_config(path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="只生成不推送")
    parser.add_argument("--config", default=str(BASE / "config.yaml"))
    args = parser.parse_args()

    cfg = load_config(args.config)

    print("[1/4] 抓取数据 ...")
    d = fetchers.gather()

    print("[2/4] AI 决策仪表盘分析 ...")
    dash = llm.analyze(d.get("candidates") or [], d.get("news") or {})
    if dash:
        d["dashboard"] = dash
        print(f"      分析完成: {len(dash)} 只")
    else:
        print("      跳过（无 DEEPSEEK_API_KEY 或分析失败）")

    print("[3/4] 生成日报 ...")
    md = report.build_markdown(d)
    html = report.build_html(d, md)
    tg_text = report.build_telegram_text(d)

    out_dir = BASE / "output"
    out_dir.mkdir(exist_ok=True)
    (out_dir / f"{d['date']}.md").write_text(md, encoding="utf-8")
    (out_dir / f"{d['date']}.html").write_text(html, encoding="utf-8")
    # GitHub Pages: 当日最新报告（索引页由 gen_site_index.py 生成）
    (out_dir / "latest.html").write_text(html, encoding="utf-8")
    print(f"      已保存: output/{d['date']}.md / .html")

    if args.dry_run:
        print("[4/4] dry-run 模式，跳过推送")
        print(tg_text[:1000])
        return

    print("[4/4] 推送 ...")
    results = pusher.push_all(cfg, f"财经早报 {d['date']}", tg_text, html)
    for name, ok, msg in results:
        mark = "OK " if ok else "FAIL"
        print(f"      [{mark}] {name}: {msg}")
    if results and not any(ok for _, ok, _ in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
