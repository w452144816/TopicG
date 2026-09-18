"""话题生成页。"""
from __future__ import annotations

import gradio as gr

import services
import storage
from ui.common import (cfg_from_ui, click_locked, index_choices, refresh_button, render_topics, rewrite_row, safe,
                       topics_plain)

PURPOSES = ["日常维护 / 刷存在感", "破冰 / 重新建立联系", "推进业务 / 促成合作", "节日 / 纪念日问候",
            "跟进上次聊到的事", "试探需求"]


def _history_md(c) -> str:
    if not c or not c.get("topics_history"):
        return "> 暂无历史记录。"
    out = []
    for h in c["topics_history"][:5]:
        titles = "、".join(t.get("title", "") for t in h.get("topics", []))
        out.append(f"- **{h.get('generated_at')}** ｜ {h.get('purpose')} ｜ {h.get('provider')}：{titles}")
    return "\n".join(out)


def build(shared: dict) -> tuple[list, callable]:
    customer_dd, prov, key, model, proxy = (shared["customer"], shared["provider"], shared["key"],
                                           shared["model"], shared["proxy"])
    with gr.Row():
        gr.Markdown("### 话题生成\n基于客户画像，生成可直接发送的开场白。")
        refresh_btn = refresh_button()
    with gr.Row():
        purpose = gr.Dropdown(PURPOSES, value=PURPOSES[0], label="话题目的", allow_custom_value=True)
        n = gr.Slider(1, 10, value=5, step=1, label="数量")
        btn = gr.Button("💡 生成话题", variant="primary")
        regen = gr.Button("🔁 再来一批（避开上一批）", variant="secondary")
    topics_md = gr.Markdown("> 点击生成。", buttons=["copy"])
    rw_idx, rw_style, rw_btn = rewrite_row("不满意哪条？选中后按要求改写开场白")
    plain = gr.Textbox(label="纯文本（点右上角图标一键复制）", lines=6, buttons=["copy"])
    with gr.Accordion("历史生成记录", open=False):
        history_md = gr.Markdown(_history_md(None))

    VIEW = [topics_md, plain, rw_idx, history_md]
    LOCK = [btn, regen, rw_btn]

    def _latest(c):
        return c["topics_history"][0]["topics"] if c and c.get("topics_history") else []

    def _view(c):
        topics = _latest(c)
        return (render_topics(topics) if topics else "> 点击生成。", topics_plain(topics),
                gr.update(choices=index_choices(topics, "title"), value=None), _history_md(c))

    @safe
    def run(cid, pur, num, p, k, m, px, progress=gr.Progress()):
        progress(0.2, desc="生成中…")
        services.generate_topics(cid, pur, int(num), cfg_from_ui(p, k, m, px))
        return _view(storage.load(cid))

    @safe
    def run_again(cid, pur, num, p, k, m, px, progress=gr.Progress()):
        progress(0.2, desc="换角度生成中…")
        avoid = [t.get("title", "") for h in (storage.load(cid) or {}).get("topics_history", [])[:3]
                 for t in h.get("topics", [])]
        services.generate_topics(cid, pur, int(num), cfg_from_ui(p, k, m, px), avoid=avoid)
        return _view(storage.load(cid))

    @safe
    def rewrite(cid, idx, style, p, k, m, px, progress=gr.Progress()):
        if idx is None:
            raise gr.Error("请先选择要改写的话题。")
        progress(0.3, desc="改写中…")
        services.rewrite_topic(cid, int(idx), style, cfg_from_ui(p, k, m, px))
        gr.Info("已改写并写入历史记录")
        return _view(storage.load(cid))

    GEN_IN = [customer_dd, purpose, n, prov, key, model, proxy]
    ev_run = click_locked(btn.click, run, GEN_IN, VIEW, LOCK)
    ev_regen = click_locked(regen.click, run_again, GEN_IN, VIEW, LOCK)
    ev_rw = click_locked(rw_btn.click, rewrite, [customer_dd, rw_idx, rw_style, prov, key, model, proxy], VIEW, LOCK)

    def refresh(cid):
        return _view(storage.load(cid) if cid else None)

    events = [ev_run, ev_regen, ev_rw, refresh_btn.click(lambda: None)]
    return VIEW, refresh, events
