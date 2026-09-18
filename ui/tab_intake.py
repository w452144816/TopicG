"""资料录入页：上传截图 / 粘贴文本 → AI 提取 → 存档（可选立即分析）。"""
from __future__ import annotations

import gradio as gr

import services
import storage
from ui.common import cfg_from_ui, render_inputs, safe


def build(shared: dict) -> tuple[list, callable]:
    customer_dd, prov, key, model, proxy = (shared["customer"], shared["provider"], shared["key"],
                                           shared["model"], shared["proxy"])
    gr.Markdown("### 录入客户资料\n上传聊天截图 / 朋友圈截图（可多张），或粘贴文字记录。AI 会提取客户信息并追加到该客户的存档。")
    with gr.Row():
        with gr.Column():
            files = gr.File(label="截图（png / jpg / webp，可多选）", file_count="multiple",
                            file_types=["image"], type="filepath")
            hint = gr.Textbox(label="补充说明（可选）", placeholder="例如：截图里右侧绿色气泡是我，左侧是客户")
        with gr.Column():
            text = gr.Textbox(label="文字记录（可选）", lines=12,
                              placeholder="粘贴聊天记录、备忘、名片信息等")
    with gr.Row():
        auto = gr.Checkbox(label="提取完成后立即重新分析画像", value=True)
        btn = gr.Button("🔍 提取并存档", variant="primary")
    result = gr.JSON(label="本次提取结果")
    gr.Markdown("#### 该客户已录入的材料")
    inputs_md = gr.Markdown(render_inputs(None))

    @safe
    def run(cid, fs, hint_txt, txt, do_auto, p, k, m, px, progress=gr.Progress()):
        cfg = cfg_from_ui(p, k, m, px)
        progress(0.1, desc="提取中…")
        added = services.intake(cid, txt, fs or [], cfg, hint_txt or "")
        if do_auto:
            progress(0.7, desc="分析画像中…")
            services.analyze(cid, cfg)
        gr.Info(f"已录入 {len(added)} 条材料" + ("，画像已更新" if do_auto else ""))
        return [a["extracted"] for a in added], render_inputs(storage.load(cid)), None, ""

    btn.click(run, [customer_dd, files, hint, text, auto, prov, key, model, proxy],
              [result, inputs_md, files, text])

    def refresh(cid):
        return (render_inputs(storage.load(cid) if cid else None),)

    return [inputs_md], refresh
