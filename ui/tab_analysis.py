"""分析页：客户画像展示 / 重新分析 / 原始 JSON。"""
from __future__ import annotations

import gradio as gr

import services
import storage
from ui.common import cfg_from_ui, render_profile, safe


def build(shared: dict) -> tuple[list, callable]:
    customer_dd, prov, key, model, proxy = (shared["customer"], shared["provider"], shared["key"],
                                           shared["model"], shared["proxy"])
    with gr.Row():
        gr.Markdown("### 客户画像")
        btn = gr.Button("🧠 重新分析画像", variant="primary", scale=0)
    profile_md = gr.Markdown(render_profile(None))
    with gr.Accordion("原始画像 JSON", open=False):
        profile_json = gr.JSON()

    @safe
    def run(cid, p, k, m, px, progress=gr.Progress()):
        progress(0.2, desc="分析中…")
        services.analyze(cid, cfg_from_ui(p, k, m, px))
        c = storage.load(cid)
        gr.Info("画像已更新")
        return render_profile(c), c["profile"]

    btn.click(run, [customer_dd, prov, key, model, proxy], [profile_md, profile_json])

    def refresh(cid):
        c = storage.load(cid) if cid else None
        return render_profile(c), (c or {}).get("profile")

    return [profile_md, profile_json], refresh
