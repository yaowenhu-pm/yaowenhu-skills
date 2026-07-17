#!/bin/bash
# hr-autopilot 一键安装：补表结构 → 首次同步 → 装定时任务（幂等，可反复执行）
set -e
cd "$(dirname "$0")"
HERE="$(pwd)"
PY="$(command -v python3 || true)"

echo "== hr-autopilot 安装 =="
[ -n "$PY" ] || { echo "❌ 需要 python3"; exit 1; }
"$PY" -c "import requests" 2>/dev/null || "$PY" -m pip install --user requests

[ -f config.json ] || { cp config.example.json config.json; echo "→ 已生成 config.json（默认指向团队演示表格，换表请编辑 base_url）"; }
mkdir -p logs state

echo "→ 检查并补齐多维表格结构..."
"$PY" scripts/ensure_schema.py

echo "→ 首次同步请假审批..."
"$PY" scripts/sync_leave.py || true

echo "→ 安装定时任务（每小时同步审批中心请假）..."
( crontab -l 2>/dev/null | grep -v "hr-autopilot" ;
  echo "0 * * * * cd $HERE && $PY scripts/sync_leave.py >> logs/sync.log 2>&1 # hr-autopilot" ;
) | crontab -

echo ""
echo "✅ 安装完成。备忘："
echo "  · 员工管理表需绑定「飞书账号」列"
echo "  · 对话式请假：团队已有小潜常驻时开箱即用；否则跑 python3 scripts/leave_bot.py 常驻"
echo "  · 卸载：crontab -l | grep -v hr-autopilot | crontab -"
