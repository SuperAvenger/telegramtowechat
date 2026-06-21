#!/bin/bash
set -e
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "未找到 Python 3，请先安装 Python 3.10 或更高版本。"
  read -r -p "按回车键关闭..."
  exit 1
fi

if [ ! -x .venv/bin/python ]; then
  echo "正在创建运行环境..."
  python3 -m venv .venv
fi

if ! .venv/bin/python -c 'import aiohttp, telethon' >/dev/null 2>&1; then
  echo "正在安装依赖（首次运行需要联网）..."
  .venv/bin/pip install -r requirements.txt
fi

if [ ! -f .env ]; then
  .venv/bin/python setup_config.py
fi

echo "正在启动实时转发；保持此窗口打开。按 Ctrl+C 可停止。"
./run.sh
