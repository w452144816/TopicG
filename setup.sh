#!/usr/bin/env bash
# 一键部署（Linux / macOS）
#   ./setup.sh          # 按 requirements.txt 安装
#   ./setup.sh --lock   # 按 requirements.lock.txt 完整锁定版本安装
set -e
cd "$(dirname "$0")"

REQ=requirements.txt
[ "$1" = "--lock" ] && REQ=requirements.lock.txt

if [ ! -d .venv ]; then
  echo "创建虚拟环境 .venv ..."
  python3 -m venv .venv
fi

echo "安装依赖（$REQ）..."
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r "$REQ"

if [ ! -f .env ]; then
  cp .env.example .env
  echo "已生成 .env，请填入 API Key 和代理设置"
fi

echo
echo "完成。启动：  .venv/bin/python app.py"
echo "连通测试：    .venv/bin/python scripts/smoke_test.py"
