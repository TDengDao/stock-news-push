# 财经新闻日报推送（VPS / GitHub Actions 双方案）

每天早上自动抓取 A股行情、板块热点、宏观/大宗/币圈要闻，生成日报并推送到你的微信/邮箱/Telegram/企业微信/钉钉。全部数据源免费、无需 API Key。

**两种部署方式，任选其一：**
- 🅰 **GitHub Actions**（推荐，零成本、免服务器）：仓库定时任务，每天 8:00 自动跑，日报存为 Artifact 可回溯
- 🅱 **自己的 VPS**：cron 定时，数据全部本地留存

---

## 方案 A：GitHub Actions 部署（推荐）

### 1. 推送代码到 GitHub

```bash
cd stock-news-push
git init && git add -A
git commit -m "init: 财经早报 daily report bot"
# 先在 GitHub 网页建一个空仓库（建议 Private），然后：
git remote add origin https://github.com/你的用户名/stock-news-push.git
git push -u origin main
```

> `config.yaml`（含 SendKey）已被 `.gitignore` 排除，不会被提交。

### 2. 配置 Secret

仓库页面 → **Settings → Secrets and variables → Actions → New repository secret**

- Name: `SERVERCHAN_SENDKEY`
- Secret: 你的 Server酱 SendKey（`SCT` 开头）

### 3. 测试

**Actions** 标签页 → 左侧「财经早报」→ **Run workflow** → 选中 main 分支运行。  
跑完看日志，微信应该立刻收到日报。

### 4. 定时说明

`.github/workflows/daily.yml` 里默认 `cron: "0 0 * * *"`，即 UTC 0:00 = **北京时间早上 8:00**。
GitHub 免费版定时任务可能延迟几分钟到半小时（高峰期），属平台特性。

---

## 方案 B：VPS 部署

## 数据源

| 内容 | 来源 |
|---|---|
| A股指数（上证/深成/创业板/科创50） | 东方财富行情接口 |
| 板块涨跌榜 | 东方财富板块接口 |
| 财经快讯 | 东方财富 7x24 + 新浪 7x24（自动去重、按关键词分类） |
| BTC/ETH 价格 | CoinGecko 免费接口 |

## 快速部署（VPS）

```bash
# 一键部署（自动装依赖、设时区、配 cron）
scp -r stock-news-push root@你的VPS:/opt/stock-news
ssh root@你的VPS
cd /opt/stock-news
cp config.example.yaml config.yaml && vi config.yaml   # 先填推送配置
chmod +x deploy.sh && ./deploy.sh
```

手动部署（等价步骤）：

```bash
cd /opt/stock-news
pip3 install -r requirements.txt
cp config.example.yaml config.yaml
vi config.yaml        # 填入 Server酱 SendKey 或邮箱授权码等

python3 main.py --dry-run   # 只生成不推送，检查 output/ 下的日报
python3 main.py             # 正式跑，验证推送能收到

crontab -e
# 加入这一行（服务器时区为 Asia/Shanghai 时）：
0 8 * * * cd /opt/stock-news && /usr/bin/python3 main.py >> run.log 2>&1
```

> ⏰ **时区提醒**：cron 按服务器时区执行。VPS 是 UTC 的话，北京时间 8:00 = UTC 0:00，cron 写 `0 0 * * *`；或在服务器上执行 `timedatectl set-timezone Asia/Shanghai` 统一为北京时间。

## 支持的推送渠道（可多选）

1. **Server酱**（推荐，最简单）：https://sct.ftqq.com 申请 SendKey，微信收消息
2. **邮件**：QQ邮箱/163 等开启 SMTP，填授权码
3. **Telegram Bot**：@BotFather 建机器人
4. **企业微信群机器人**：群设置→添加机器人→复制 webhook
5. **钉钉群机器人**：安全设置选"自定义关键词"，填 `财经`

## 文件说明

```
main.py               入口：抓取→生成→推送
fetchers.py           数据抓取与分类
report.py             生成 Markdown / HTML / 精简文本
pusher.py             五种推送渠道
config.example.yaml   配置模板（复制为 config.yaml）
output/               每日日报存档（.md + .html）
```

## 自定义

- **改推送时间**：改 cron 表达式
- **改自选关注词**：改 `fetchers.py` 里的 `KEYWORDS`
- **币种扩展**：`fetch_crypto(ids="bitcoin,ethereum,solana")` 按需加
- **指数扩展**：`fetch_index_snapshot()` 的 secids 里加，如 `1.000300`(沪深300)、`100.NDX`(纳斯达克，需东财支持的美股代码)

## 免责声明

本项目仅为公开信息聚合与展示，不构成任何投资建议。
