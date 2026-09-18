"""分析页：客户画像展示 / 重新分析 / 原始 JSON。"""
from __future__ import annotations

import gradio as gr

import services
import storage
from ui.common import (cfg_from_ui, click_locked, profile_dumps, profile_editor, profile_loads, refresh_button,
                       render_profile, safe)


def build(shared: dict) -> tuple[list, callable]:
    customer_dd, prov, key, model, proxy = (shared["customer"], shared["provider"], shared["key"],
                                           shared["model"], shared["proxy"])
    with gr.Row():
        gr.Markdown("### 客户画像")
        btn = gr.Button("🧠 重新分析画像", variant="primary", scale=0)
        refresh_btn = refresh_button()
    profile_md = gr.Markdown(render_profile(None), buttons=["copy"])
    with gr.Accordion("✏️ 手工修正画像（JSON，改完点保存）", open=False):
        gr.Markdown("AI 分析有偏差时可以直接改这里的字段（如 personality、taboos），保存后立即生效，"
                    "之后「重新分析」会在你改过的版本基础上增量更新。")
        profile_json, save_btn = profile_editor()

    def _view(c):
        return render_profile(c), profile_dumps((c or {}).get("profile"))

    @safe
    def run(cid, p, k, m, px, progress=gr.Progress()):
        progress(0.2, desc="分析中…")
        services.analyze(cid, cfg_from_ui(p, k, m, px))
        gr.Info("画像已更新")
        return _view(storage.load(cid))

    @safe
    def save_edit(cid, text):
        services.update_profile(cid, profile_loads(text))
        gr.Info("画像已保存")
        return _view(storage.load(cid))

    ev_run = click_locked(btn.click, run, [customer_dd, prov, key, model, proxy], [profile_md, profile_json], [btn])
    ev_save = save_btn.click(save_edit, [customer_dd, profile_json], [profile_md, profile_json])

    def refresh(cid):
        return _view(storage.load(cid) if cid else None)

    events = [ev_run, ev_save, refresh_btn.click(lambda: None)]
    return [profile_md, profile_json], refresh, events
