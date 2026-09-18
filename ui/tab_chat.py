"""聊天回复页：候选回复生成 + 多轮对话模拟。"""
from __future__ import annotations

import gradio as gr

import services
import storage
from ui.common import (cfg_from_ui, click_locked, index_choices, refresh_button, render_replies, replies_plain,
                       rewrite_row, safe)

STYLES = ["正式", "亲切", "幽默", "简短", "推进业务"]
MODES = {"AI 扮演客户（陪练）": "customer", "AI 做我的助手（出主意）": "assistant"}


def _history(c) -> list[dict]:
    return [{"role": m["role"], "content": m["content"]} for m in (c or {}).get("chat_history", [])]


def build(shared: dict) -> tuple[list, callable]:
    customer_dd, prov, key, model, proxy = (shared["customer"], shared["provider"], shared["key"],
                                           shared["model"], shared["proxy"])

    with gr.Row():
        gr.Markdown("### 候选回复\n粘贴客户刚发来的消息，AI 以**你本人**的口吻和心态（来自「我的建模」）生成多种风格的回复。"
                    "风格是在你本人基础上的微调，不会变成另一个人。未建模时使用通用口吻。")
        refresh_btn = refresh_button()
    with gr.Row():
        incoming = gr.Textbox(label="客户发来的消息（Shift+Enter 直接生成）", lines=3, scale=3)
        with gr.Column(scale=2):
            styles = gr.CheckboxGroup(STYLES, value=["正式", "亲切", "幽默"], label="回复风格")
            reply_btn = gr.Button("✉️ 生成回复", variant="primary")
    replies_md = gr.Markdown("> 等待生成。", buttons=["copy"])
    replies_state = gr.State([])
    rw_idx, rw_style, rw_btn = rewrite_row("不满意哪条？选中后按要求改写")
    replies_plain_tb = gr.Textbox(label="纯文本（点右上角图标一键复制）", lines=5, buttons=["copy"])

    def _view(rs):
        return (render_replies(rs), replies_plain(rs), rs,
                gr.update(choices=index_choices(rs, "style"), value=None))

    R_VIEW = [replies_md, replies_plain_tb, replies_state, rw_idx]
    R_LOCK = [reply_btn, rw_btn]

    @safe
    def gen(cid, msg, sts, p, k, m, px, progress=gr.Progress()):
        progress(0.2, desc="生成中…")
        return _view(services.generate_replies(cid, msg, sts, cfg_from_ui(p, k, m, px)))

    @safe
    def rewrite(cid, rs, idx, style, p, k, m, px, progress=gr.Progress()):
        if idx is None or not rs:
            raise gr.Error("请先生成回复并选择要改写的那条。")
        progress(0.3, desc="改写中…")
        rs = [dict(r) for r in rs]
        rs[int(idx)]["reply"] = services.rewrite_text(cid, rs[int(idx)].get("reply", ""), style, cfg_from_ui(p, k, m, px))
        rs[int(idx)]["style"] = f"{rs[int(idx)].get('style', '')}（{style}）"
        return _view(rs)

    for trig in (reply_btn.click, incoming.submit):
        click_locked(trig, gen, [customer_dd, incoming, styles, prov, key, model, proxy], R_VIEW, R_LOCK)
    click_locked(rw_btn.click, rewrite, [customer_dd, replies_state, rw_idx, rw_style, prov, key, model, proxy],
                 R_VIEW, R_LOCK)

    gr.Markdown("---\n### 对话模拟\n「AI 扮演客户」用于练习沟通；「AI 做我的助手」帮你想怎么说。对话历史按客户保存。")
    mode = gr.Radio(list(MODES), value=list(MODES)[0], label="模式")
    chatbot = gr.Chatbot(label="对话", height="60vh", min_height=320)
    with gr.Row():
        msg = gr.Textbox(label="我说", placeholder="输入后回车发送", scale=5)
        send = gr.Button("发送", variant="primary", scale=1)
        clear = gr.Button("清空对话", variant="stop", scale=1)

    @safe
    def turn(cid, mode_label, text, p, k, m, px):
        hist = services.roleplay_turn(cid, MODES[mode_label], text, cfg_from_ui(p, k, m, px))
        return [{"role": h["role"], "content": h["content"]} for h in hist], ""

    events = [click_locked(trigger, turn, [customer_dd, mode, msg, prov, key, model, proxy], [chatbot, msg], [send])
              for trigger in (send.click, msg.submit)]

    @safe
    def do_clear(cid):
        services.clear_chat(cid)
        return []

    ev_clear = clear.click(do_clear, [customer_dd], [chatbot])

    def refresh(cid):
        return (_history(storage.load(cid) if cid else None),)

    events += [ev_clear, refresh_btn.click(lambda: None)]
    return [chatbot], refresh, events
