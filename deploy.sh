#!/usr/bin/env bash
# 财经早报 · VPS 一键部署脚本
# 用法（在 VPS 上，项目目录内执行）：
#   chmod +x deploy.sh && sudo ./deploy.sh
set -e

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
PY="${PYTHON:-python3}"
RUN_TIME="${RUN_TIME:-0 8 * * *}"   # 默认每天 8:00（北京时间，需服务器时区为 Asia/Shanghai）

echo "==> 项目目录: $APP_DIR"
echo "==> Python: $($PY --version 2>&1)"

echo "==> 设置时区为 Asia/Shanghai（如已是则跳过）"
timedatectl set-timezone Asia/Shanghai 2>/dev/null || echo "    时区设置失败，请手动执行 timedatectl set-timezone Asia/Shanghai"

echo "==> 安装依赖"
$PY -m pip install -q -r requirements.txt

echo "==> 检查配置文件"
if [ ! -f config.yaml ]; then
  cp config.example.yaml config.yaml
  echo "    已生成 config.yaml，请先编辑填写 SendKey / 邮箱等信息后再运行本脚本"
  exit 0
fi

echo "==> 试跑一次（dry-run，不推送）"
$PY main.py --dry-run | tail -5

echo "==> 配置 cron: $RUN_TIME"
CRON_LINE="$RUN_TIME cd $APP_DIR && $PY main.py >> $APP_DIR/run.log 2>&1"
( crontab -l 2>/dev/null | grep -vF "$APP_DIR/main.py" ; echo "$CRON_LINE" ) | crontab -
echo "    当前 crontab:"
crontab -l | grep "$APP_DIR/main.py"

echo ""
echo "✅ 部署完成。日报每天 $(echo $RUN_TIME | awk '{print $2":"$1}') 推送。"
echo "   手动测试推送: cd $APP_DIR && $PY main.py"
echo "   查看日志:     tail -f $APP_DIR/run.log"
