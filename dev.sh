#!/usr/bin/env bash
# 开发模式：改任何 .py 文件保存后页面自动重载。正式使用仍用 python app.py
cd "$(dirname "$0")"
export GRADIO_SERVER_PORT="${1:-7860}"
exec .venv/bin/gradio app.py --watch-dirs .
