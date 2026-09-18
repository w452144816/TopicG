"""资料录入页：上传截图 / 粘贴文本 → AI 提取 → 存档（可选立即分析）。"""
from __future__ import annotations

import gradio as gr

import ingest
import services
import storage
from ui.common import cfg_from_ui, render_inputs, safe


def build(shared: dict) -> tuple[list, callable]:
    customer_dd, prov, key, model, proxy = (shared["customer"], shared["provider"], shared["key"],
                                           shared["model"], shared["proxy"])
    gr.Markdown("### 录入客户资料\n上传聊天截图 / 朋友圈截图（可多张），或粘贴文字记录。AI 会提取客户信息并追加到该客户的存档。")
    with gr.Row():
        with gr.Column():
            files = gr.File(label="文件（可多选）：截图 png/jpg/webp ｜ 文本 txt/md ｜ 表格 xlsx/csv ｜ zip 压缩包（自动解开）",
                            file_count="multiple", file_types=ingest.ACCEPTED_EXT, type="filepath")
            hint = gr.Textbox(label="补充说明（可选）", placeholder="例如：截图里右侧绿色气泡是我，左侧是客户")
        with gr.Column():
            text = gr.Textbox(label="文字记录（可选）", lines=12,
                              placeholder="粘贴聊天记录、备忘、名片信息等")
    with gr.Row():
        auto = gr.Checkbox(label="录入后立即更新画像（增量：在现有画像基础上补充修正）", value=True)
        btn = gr.Button("🔍 追加录入并提取", variant="primary")
    result = gr.JSON(label="本次提取结果")

    with gr.Row():
        note = gr.Textbox(label="纠正 / 备注（你确定的关于该客户的事实，权重最高，不经 AI 提取）", lines=2, scale=4,
                          placeholder="例如：王总其实不喝茶，喝咖啡；他儿子今年升高一了；别在周一上午打扰他")
        note_btn = gr.Button("📌 追加备注", scale=1)

    gr.Markdown("#### 该客户已录入的材料（可持续追加，越多画像越准）")
    inputs_md = gr.Markdown(render_inputs(None))
    with gr.Row():
        del_idx = gr.Number(label="删除第几条材料（序号）", precision=0, value=None, scale=1)
        del_btn = gr.Button("删除该条", scale=0)

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

    @safe
    def do_note(cid, txt, do_auto, p, k, m, px, progress=gr.Progress()):
        services.add_note(cid, txt)
        if do_auto:
            progress(0.5, desc="更新画像中…")
            services.analyze(cid, cfg_from_ui(p, k, m, px))
        gr.Info("备注已追加" + ("，画像已更新" if do_auto else ""))
        return render_inputs(storage.load(cid)), ""

    note_btn.click(do_note, [customer_dd, note, auto, prov, key, model, proxy], [inputs_md, note])

    @safe
    def do_del(cid, idx):
        if not idx:
            raise gr.Error("请输入要删除的材料序号。")
        services.remove_input(cid, int(idx) - 1)
        gr.Info("已删除，建议重新分析画像")
        return render_inputs(storage.load(cid)), None

    del_btn.click(do_del, [customer_dd, del_idx], [inputs_md, del_idx])

    def refresh(cid):
        return (render_inputs(storage.load(cid) if cid else None),)

    return [inputs_md], refresh
