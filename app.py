"""客户话题生成器 Demo —— Gradio 入口。

启动：  .venv\\Scripts\\python app.py
访问：  http://127.0.0.1:7860
"""
from __future__ import annotations

import os

# 系统若设置了 HTTP(S)_PROXY，Gradio 启动自检 localhost 会被送去代理而 403，这里把本机地址排除掉
for _var in ("NO_PROXY", "no_proxy"):
    _cur = os.environ.get(_var, "")
    os.environ[_var] = ",".join(x for x in [_cur, "127.0.0.1", "localhost"] if x)

import gradio as gr  # noqa: E402

import storage
from config import DEFAULT_PROVIDER, PROVIDERS, PROVIDER_LABELS, PROXY_ENABLED, PROXY_URL
from ui import tab_analysis, tab_chat, tab_customers, tab_guide, tab_intake, tab_me, tab_topics
from ui.common import customer_dropdown_update


def status_md(label: str, key_override: str, model_override: str, use_proxy: bool) -> str:
    from ui.common import cfg_from_ui
    cfg = cfg_from_ui(label, key_override, model_override, use_proxy)
    ok = "✅ 已配置" if cfg.ready else "❌ 未配置 Key"
    via = f" ｜ **代理**：`{cfg.proxy}`" if cfg.proxy else " ｜ 直连"
    return f"**引擎**：{cfg.label} ｜ **模型**：`{cfg.model}` ｜ **地址**：`{cfg.base_url}`{via} ｜ {ok}"


def build() -> gr.Blocks:
    with gr.Blocks(title="客户话题生成器") as demo:
        gr.Markdown("# 🗣️ 客户话题生成器 Demo\n录入客户资料 → AI 建立画像 → 生成话题 / 回复 / 对话陪练")

        with gr.Row():
            provider = gr.Radio(PROVIDER_LABELS, value=PROVIDERS[DEFAULT_PROVIDER].label,
                                label="AI 引擎", scale=1)
            customer = gr.Dropdown(choices=storage.choices(), label="当前客户",
                                   value=(storage.choices() or [(None, None)])[0][1], scale=2)
            refresh_all_btn = gr.Button("🔄 刷新全部", scale=0, min_width=110)
        with gr.Accordion("引擎高级设置（临时覆盖，不落盘）", open=False):
            with gr.Row():
                key_override = gr.Textbox(label="API Key 覆盖", type="password", placeholder="留空则用 .env")
                model_override = gr.Textbox(label="模型名覆盖", placeholder="留空则用 .env")
                use_proxy = gr.Checkbox(
                    label=f"走 HTTP 代理 {PROXY_URL}" if PROXY_URL else "走 HTTP 代理（请先在 .env 设置 PROXY_URL）",
                    value=PROXY_ENABLED, interactive=bool(PROXY_URL))
        status = gr.Markdown(status_md(PROVIDERS[DEFAULT_PROVIDER].label, "", "", PROXY_ENABLED))
        for comp in (provider, key_override, model_override, use_proxy):
            comp.change(status_md, [provider, key_override, model_override, use_proxy], [status])

        shared = {"provider": provider, "customer": customer, "key": key_override, "model": model_override,
                  "proxy": use_proxy}

        tabs = []
        with gr.Tabs() as tabs_comp:
            shared["tabs"] = tabs_comp  # 供各页切换标签页（如新增客户后跳到资料录入）
            for tid, title, mod in [("guide", "📖 使用说明", tab_guide), ("me", "🙋 我的建模", tab_me),
                                    ("customers", "👥 客户管理", tab_customers), ("intake", "📥 资料录入", tab_intake),
                                    ("analysis", "🧠 分析页", tab_analysis), ("topics", "💡 话题生成", tab_topics),
                                    ("chat", "💬 聊天回复", tab_chat)]:
                with gr.Tab(title, id=tid):
                    tabs.append(mod.build(shared))

        all_outputs = [o for outs, _, _ in tabs for o in outs]

        def refresh_all(cid):
            vals = []
            for _, fn, _ in tabs:
                vals.extend(fn(cid))
            return vals

        # 切换客户 / 打开页面：全局刷新
        customer.change(refresh_all, [customer], all_outputs)
        demo.load(lambda: customer_dropdown_update(None), None, [customer]).then(
            refresh_all, [customer], all_outputs)
        # 顶部「刷新全部」：先重读客户列表（保持当前选中），再刷新所有模块
        refresh_all_btn.click(customer_dropdown_update, [customer], [customer]).then(
            refresh_all, [customer], all_outputs)
        # 各模块的提交 / 分析 / 删除以及模块内的小刷新按钮完成后，自动全局刷新
        # （refresh_all 不写 customer 下拉框，避免与 customer.change 互相触发）
        for _, _, events in tabs:
            for ev in events:
                ev.then(refresh_all, [customer], all_outputs)
    return demo


# 模块级 demo：供 `gradio app.py`（开发热重载模式，见 dev.ps1）使用
demo = build()


def parse_args():
    import argparse
    ap = argparse.ArgumentParser(description="客户话题生成器 Demo")
    ap.add_argument("--port", type=int, default=int(os.getenv("GRADIO_SERVER_PORT", 0)) or None,
                    help="端口，不填则从 7860 起自动找空闲端口")
    ap.add_argument("--host", default=os.getenv("GRADIO_SERVER_NAME", "127.0.0.1"),
                    help="监听地址，0.0.0.0 允许局域网访问")
    ap.add_argument("--share", action="store_true", help="生成 gradio.live 公网临时链接（72 小时有效）")
    ap.add_argument("--open", action="store_true", help="启动后自动打开浏览器")
    return ap.parse_args()


if __name__ == "__main__":
    args = parse_args()
    demo.launch(server_name=args.host, server_port=args.port, share=args.share, inbrowser=args.open)
