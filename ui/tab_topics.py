"""话题生成页。"""
from __future__ import annotations

import gradio as gr

import services
import storage
from ui.common import cfg_from_ui, refresh_button, render_topics, safe, topics_plain

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
    topics_md = gr.Markdown("> 点击生成。")
    plain = gr.Textbox(label="纯文本（便于复制）", lines=6)
    with gr.Accordion("历史生成记录", open=False):
        history_md = gr.Markdown(_history_md(None))

    @safe
    def run(cid, pur, num, p, k, m, px, progress=gr.Progress()):
        progress(0.2, desc="生成中…")
        topics = services.generate_topics(cid, pur, int(num), cfg_from_ui(p, k, m, px))
        return render_topics(topics), topics_plain(topics), _history_md(storage.load(cid))

    ev_run = btn.click(run, [customer_dd, purpose, n, prov, key, model, proxy], [topics_md, plain, history_md])

    def refresh(cid):
        c = storage.load(cid) if cid else None
        latest = c["topics_history"][0]["topics"] if c and c.get("topics_history") else []
        return (render_topics(latest) if latest else "> 点击生成。", topics_plain(latest), _history_md(c))

    events = [ev_run, refresh_btn.click(lambda: None)]
    return [topics_md, plain, history_md], refresh, events
