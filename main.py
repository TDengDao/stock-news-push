# -*- coding: utf-8 -*-
"""财经新闻日报 · 入口
用法: python main.py [--dry-run] [--config config.yaml]
--dry-run: 只生成日报不推送
"""
import argparse
import datetime
import json
import pathlib
import sys

import yaml

import fetchers
import pusher
import report

BASE = pathlib.Path(__file__).parent


def load_config(path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="只生成不推送")
    parser.add_argument("--config", default=str(BASE / "config.yaml"))
    args = parser.parse_args()

    cfg = load_config(args.config)
    print("[1/3] 抓取数据 ...")
    d = fetchers.gather()

    print("[2/3] 生成日报 ...")
    md = report.build_markdown(d)
    html = report.build_html(d, md)
    tg_text = report.build_telegram_text(d)

    out_dir = BASE / "output"
    out_dir.mkdir(exist_ok=True)
    (out_dir / f"{d['date']}.md").write_text(md, encoding="utf-8")
    (out_dir / f"{d['date']}.html").write_text(html, encoding="utf-8")
    print(f"      已保存: output/{d['date']}.md / .html")

    if args.dry_run:
        print("[3/3] dry-run 模式，跳过推送")
        print(tg_text[:800])
        return

    print("[3/3] 推送 ...")
    results = pusher.push_all(cfg, f"财经早报 {d['date']}", tg_text, html)
    for name, ok, msg in results:
        mark = "OK " if ok else "FAIL"
        print(f"      [{mark}] {name}: {msg}")
    if results and not any(ok for _, ok, _ in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
