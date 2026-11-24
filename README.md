# 财经新闻日报推送（GitHub Actions / VPS 双方案）

每天早上自动抓取 A股行情、板块热点、宏观/大宗/币圈要闻，用 DeepSeek 对当日热点股做 AI 分析，生成日报推送到微信，并自动发布成网页归档。

## 功能

- **🎯 AI 决策仪表盘**：每天自动从「新闻提及个股 + 涨幅榜龙头」中挑选 6 只热点股，由 DeepSeek 输出评分（0-100）、买入/观望/卖出建议、风险警报、利好催化
- **📊 大盘复盘**：四大指数、涨跌家数（二分法精确统计全市场 5500+ 只）、涨停/跌停家数、板块涨跌榜
- **📰 要闻分类**：宏观 / 大宗商品 / 币圈 / 综合，自动去重归类
- **🪙 币圈行情**：BTC/ETH 实时价格与 24h 涨跌
- **📱 微信推送**：Server酱（可扩展邮件/TG/企业微信/钉钉）
- **🌐 网页版**：GitHub Pages 自动归档，历史日报随时翻

**两种部署方式：**
- 🅰 **GitHub Actions**（推荐，零成本、免服务器）：每天 8:00 自动跑 + 自动发布网页
- 🅱 **自己的 VPS**：cron 定时，数据全部本地留存

## 网页效果

- 首页（历史归档）：`https://<用户名>.github.io/stock-news-push/`
- 今日最新：`https://<用户名>.github.io/stock-news-push/latest.html`

---

## 方案 A：GitHub Actions 部署（推荐）

### 1. 推送代码到 GitHub

```bash
cd stock-news-push
git init && git add -A
git commit -m "init: 财经早报 daily report bot"
# 先在 GitHub 网页建一个空仓库（网页版需要 Public），然后：
git remote add origin https://github.com/你的用户名/stock-news-push.git
git push -u origin main
```

> `config.yaml`（含密钥）已被 `.gitignore` 排除，不会被提交。

### 2. 配置 Secrets

仓库页面 → **Settings → Secrets and variables → Actions → New repository secret**

- `SERVERCHAN_SENDKEY`：Server酱 SendKey（`SCT` 开头）
- `DEEPSEEK_API_KEY`：DeepSeek API Key（`sk-` 开头，用于 AI 决策仪表盘）

### 3. 开启 GitHub Pages

仓库 **Settings → Pages → Build and deployment → Source 选 Deploy from a branch → Branch 选 `gh-pages` / root → Save**。（首次运行会自动创建 gh-pages 分支）

### 4. 测试

**Actions** 标签页 → 左侧「财经早报」→ **Run workflow** → 选中 main 分支运行。
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
| A股指数（上证/深成/创业板/科创50） | 腾讯行情（主）/ 东方财富（备） |
| 板块涨跌榜 | 东方财富（涨跌分开请求，绕开单页 100 条限制） |
| 涨跌家数 / 涨跌停 | 东方财富 clist 二分页边界统计 + 涨跌停池 |
| 财经快讯 | 东方财富 7x24 + 新浪 7x24（去重 + 关键词分类） |
| 选股候选 | 快讯个股提及 + 当日涨幅榜（过滤 ETF/ST） |
| BTC/ETH 价格 | CoinGecko 免费接口 |
| 个股分析 | DeepSeek（deepseek-chat），需 DEEPSEEK_API_KEY |

### 文件说明（新增）

| 文件 | 作用 |
|---|---|
| `llm.py` | DeepSeek 决策仪表盘分析 |
| `gen_site_index.py` | 生成 GitHub Pages 历史归档索引 |

> ⚠️ AI 分析仅为公开信息的自动化解读，不构成投资建议。

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
