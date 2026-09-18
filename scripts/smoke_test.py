"""连通性测试：对每个已配置 key 的引擎发一条文本请求，可选再发一张图片。

用法：
  .venv\\Scripts\\python scripts\\smoke_test.py            # 只测文本
  .venv\\Scripts\\python scripts\\smoke_test.py test.png   # 同时测图片输入
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ai_engine as ai  # noqa: E402
from config import PROVIDERS  # noqa: E402

args = [a for a in sys.argv[1:] if a != "--proxy"]
use_proxy = "--proxy" in sys.argv
image = args[0] if args else None

for cfg in PROVIDERS.values():
    cfg = cfg.with_override(use_proxy=use_proxy)
    if cfg.proxy:
        print(f"  （经代理 {cfg.proxy}）")
    print(f"\n=== {cfg.label}  model={cfg.model}  base_url={cfg.base_url}")
    if not cfg.ready:
        print("  跳过：未配置 API Key")
        continue
    try:
        print("  文本：", ai.chat_text(cfg, "你是测试助手，只用一句话回答。", "用一句话介绍你自己。", max_tokens=200)[:120])
    except ai.AIError as e:
        print("  文本失败：", e)
    if image:
        try:
            print("  图片：", ai.chat_with_images(cfg, "只用一句话回答。", "描述这张图片。", [image], max_tokens=200)[:120])
        except ai.AIError as e:
            print("  图片失败：", e)
