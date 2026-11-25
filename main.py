# -*- coding: utf-8 -*-
"""财经新闻日报 · 入口
用法: python main.py [--dry-run] [--config config.yaml]
--dry-run: 只生成日报不推送
环境变量: DEEPSEEK_API_KEY（可选，启用 AI 决策仪表盘）
"""
import argparse
import datetime
import json
import os
import pathlib
import sys

import yaml

import fetchers
import ledger
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

    phase = (os.environ.get("RUN_PHASE") or "postclose").strip().lower()
    if phase not in ("premarket", "midday", "postclose"):
        phase = "postclose"
    force = (os.environ.get("RUN_FORCE") or "").strip() in ("1", "true")
    # Actions 机器是 UTC；运行时段内 UTC 日期与北京日期一致，与 fetchers.gather 取到的日期相同
    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    marker = BASE / "data" / "pushed" / f"{today}-{phase}.json"

    # 防重复：多个定时层（GitHub cron / 外部调度）可能同时触发，
    # 今天该阶段已成功推送过就直接退出。RUN_FORCE=1 可强制重推。
    if not args.dry_run and not force and marker.exists():
        print(f"[SKIP] 今日 {phase} 已推送过（存在 {marker.name}），退出")
        return

    print("[1/4] 抓取数据 ...")
    d = fetchers.gather()
    d["phase"] = phase
    d["phase_label"] = {"premarket": "盘前预判", "midday": "午盘快照",
                        "postclose": "盘后复盘"}[phase]

    print("[2/4] AI 决策仪表盘分析 ...")
    has_key = bool(os.environ.get("DEEPSEEK_API_KEY", "").strip())
    cands = d.get("candidates") or []
    print(f"      候选股票 {len(cands)} 只, API Key {'已配置' if has_key else '未配置'}")
    dash = llm.analyze(cands, d.get("news") or {})
    if dash:
        d["dashboard"] = dash
        print(f"      分析完成: {len(dash)} 只")
    else:
        print("      跳过（无候选股 / 无 Key / 分析失败）")

    if dash:
        by_code = {c["code"]: c for c in (d.get("candidates") or [])}
        for a in dash:
            src = by_code.get(a.get("code")) or {}
            for k in ("pe", "pb", "roe"):
                if k in src:
                    a[k] = src[k]

    if not args.dry_run:
        if phase == "premarket":
            picks = []
            dash_by = {a.get("code"): a for a in dash}
            for c in d.get("candidates") or []:
                a = dash_by.get(c["code"]) or {}
                picks.append({"code": c["code"], "name": c["name"],
                              "price": c["price"],
                              "score": a.get("score"),
                              "verdict": a.get("verdict", "观望")})
            ledger.add_picks(d["date"], "premarket", picks)
            print(f"      台账已记录 {len(picks)} 只盘前推荐")
        elif phase == "postclose":
            codes = ledger.review_codes(d["date"])
            prices = fetchers.fetch_quotes(codes) if codes else {}
            d["review"] = ledger.review(d["date"], prices)
            print(f"      复盘 {len(d['review'])} 个时间窗口")
        else:
            print("      午盘快照：不写台账、不复盘")

    print(f"      数据源状态: {d.get('sources')}")

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
    results = pusher.push_all(cfg, f"财经早报 {d['date']} {d['phase_label']}", tg_text, html)
    for name, ok, msg in results:
        mark = "OK " if ok else "FAIL"
        print(f"      [{mark}] {name}: {msg}")
    if results and not any(ok for _, ok, _ in results):
        sys.exit(1)

    # 推送成功后写标记，工作流会把它提交回仓库，供下一次运行判重
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps(
        {"date": today, "phase": phase,
         "pushed_at": datetime.datetime.utcnow().isoformat() + "Z"},
        ensure_ascii=False), encoding="utf-8")
    print(f"      已写入推送标记: data/pushed/{marker.name}")
    # 本运行确实推送过的标志（不提交），工作流据此决定是否发布网站
    (BASE / ".pushed_this_run").write_text("1", encoding="utf-8")


if __name__ == "__main__":
    main()
