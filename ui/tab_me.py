"""我的建模页：录入使用者本人的聊天截图 / 文本 → 建立人格与说话风格画像，供回复/话题模仿本人口吻。"""
from __future__ import annotations

from typing import Any

import gradio as gr

import ingest
import services
import storage
from ui.common import _li, cfg_from_ui, safe


def render_me(me: dict[str, Any]) -> str:
    head = (f"## {me.get('name') or '（未填称呼）'}  \n身份：{me.get('role') or '未填'} ｜ "
            f"已录入材料 {len(me.get('raw_inputs', []))} 条")
    p = me.get("profile")
    if not p:
        return head + "\n\n> 尚未建模。录入材料后点击「重新建模」。建模前，回复/话题会使用通用口吻。"
    return f"""{head}

> **一句话总结**：{p.get('summary') or '信息不足'}
> 建模时间：{p.get('analyzed_at', '')} ｜ 引擎：{p.get('provider', '')}

### 身份
{p.get('identity') or '信息不足'}

### 性格与心态
{p.get('personality') or '信息不足'}

### 说话风格
{p.get('speaking_style') or '信息不足'}

**标点与表情习惯**：{p.get('punctuation_emoji') or '信息不足'}

**幽默方式**：{p.get('humor') or '信息不足'}

### 口头禅 / 常用表达
{_li(p.get('signature_phrases'))}

### 价值观与原则
{_li(p.get('values'))}

### 业务推进姿态
{p.get('sales_stance') or '信息不足'}

### 🚫 我绝不会这样说（模仿硬约束）
{_li(p.get('never_say'))}

### 示范消息（本人风格）
{_li(p.get('sample_messages'))}
"""


def render_me_inputs(me: dict[str, Any]) -> str:
    items = me.get("raw_inputs", [])
    if not items:
        return "> 还没有录入材料。建议：3 到 5 张你和不同客户的聊天截图 + 一段自我描述（性格、做事原则、忌讳）。"
    out = []
    for i, item in enumerate(items, 1):
        if item.get("type") == "note":
            out.append(f"**{i}. [本人纠正/备注] {item.get('added_at', '')}**\n  - {item.get('content', '')}")
            continue
        ex = item.get("extracted") or {}
        src = ex.get("source_summary", "") if isinstance(ex, dict) else ""
        quotes = ex.get("my_quotes", []) if isinstance(ex, dict) else []
        out.append(f"**{i}. [{'图片' if item['type'] == 'image' else '文本'}] {item.get('added_at', '')}** ｜ {src}\n"
                   + ("\n".join(f"  - {q}" for q in quotes[:3]) if quotes else ""))
    return "\n\n".join(out)


def build(shared: dict) -> tuple[list, callable]:
    prov, key, model, proxy = shared["provider"], shared["key"], shared["model"], shared["proxy"]
    me = storage.load_me()

    gr.Markdown("### 我的建模\n把**你自己**的聊天截图、朋友圈、自我描述录进来，AI 会建立你的人格与说话风格画像。"
                "之后「聊天回复」「话题开场白」「对话助手」都会用**你本人的口吻和心态**来写，而不是通用客服腔。")
    with gr.Row():
        name_in = gr.Textbox(label="我的称呼", value=me.get("name", ""), placeholder="例如：小王、Wang", scale=1)
        role_in = gr.Textbox(label="我的身份 / 岗位", value=me.get("role", ""),
                             placeholder="例如：某软件公司华东区销售，主要对接地产客户", scale=3)
        save_basic = gr.Button("保存", scale=0)

    with gr.Row():
        with gr.Column():
            files = gr.File(label="我的文件（可多选）：聊天截图 ｜ 文本 txt/md ｜ 表格 xlsx/csv ｜ zip 压缩包（自动解开）",
                            file_count="multiple", file_types=ingest.ACCEPTED_EXT, type="filepath")
            hint = gr.Textbox(label="补充说明（可选）", placeholder="例如：截图里右侧绿色气泡是我；或：这是我和老客户的对话，比较随意")
        with gr.Column():
            text = gr.Textbox(label="我的自述 / 我说过的话（可选）", lines=12,
                              placeholder="例如：我说话比较直接，不喜欢客套；从不催客户，宁愿慢一点；爱用『哈哈』和 ~ ；绝对不用『亲』『宝』……\n也可以直接粘贴一段你发给客户的消息。")
    with gr.Row():
        auto = gr.Checkbox(label="录入后立即更新画像（增量：在现有画像基础上补充修正）", value=True)
        btn = gr.Button("🔍 追加录入并分析", variant="primary")
        rebuild = gr.Button("🧬 用全部材料更新画像", variant="secondary")
    result = gr.JSON(label="本次提取结果")

    with gr.Row():
        note = gr.Textbox(label="纠正 / 备注（直接告诉 AI 关于你的事实，权重最高，不经提取）", lines=2, scale=4,
                          placeholder="例如：我其实不爱用『哈哈』，更常用『嗯嗯』；我对老客户会更随意；节假日我一定会发问候")
        note_btn = gr.Button("📌 追加备注", scale=1)

    with gr.Row():
        with gr.Column(scale=3):
            gr.Markdown("#### 我的画像")
            profile_md = gr.Markdown(render_me(me))
            with gr.Accordion("原始画像 JSON", open=False):
                profile_json = gr.JSON(value=me.get("profile"))
        with gr.Column(scale=2):
            gr.Markdown("#### 已录入的材料")
            inputs_md = gr.Markdown(render_me_inputs(me))
            with gr.Row():
                del_idx = gr.Number(label="删除第几条材料（序号）", precision=0, value=None, scale=2)
                del_btn = gr.Button("删除该条", scale=1)
            confirm = gr.Checkbox(label="我确认清空全部材料与画像", value=False)
            reset_btn = gr.Button("🗑 清空我的建模", variant="stop")

    def _all():
        m = storage.load_me()
        return render_me(m), m.get("profile"), render_me_inputs(m)

    @safe
    def do_save_basic(n, r):
        services.me_update_basic(n, r)
        gr.Info("已保存")
        return _all()

    save_basic.click(do_save_basic, [name_in, role_in], [profile_md, profile_json, inputs_md])

    @safe
    def run(fs, hint_txt, txt, do_auto, p, k, m, px, progress=gr.Progress()):
        cfg = cfg_from_ui(p, k, m, px)
        progress(0.1, desc="分析材料中…")
        added = services.me_intake(txt, fs or [], cfg, hint_txt or "")
        if do_auto:
            progress(0.7, desc="建模中…")
            services.me_analyze(cfg)
        gr.Info(f"已录入 {len(added)} 条材料" + ("，画像已更新" if do_auto else ""))
        return ([a["extracted"] for a in added], *_all(), None, "")

    btn.click(run, [files, hint, text, auto, prov, key, model, proxy],
              [result, profile_md, profile_json, inputs_md, files, text])

    @safe
    def do_note(txt, do_auto, p, k, m, px, progress=gr.Progress()):
        services.me_add_note(txt)
        if do_auto:
            progress(0.5, desc="更新画像中…")
            services.me_analyze(cfg_from_ui(p, k, m, px))
        gr.Info("备注已追加" + ("，画像已更新" if do_auto else ""))
        return (*_all(), "")

    note_btn.click(do_note, [note, auto, prov, key, model, proxy], [profile_md, profile_json, inputs_md, note])

    @safe
    def do_rebuild(p, k, m, px, progress=gr.Progress()):
        progress(0.2, desc="建模中…")
        services.me_analyze(cfg_from_ui(p, k, m, px))
        gr.Info("画像已更新")
        return _all()

    rebuild.click(do_rebuild, [prov, key, model, proxy], [profile_md, profile_json, inputs_md])

    @safe
    def do_del(idx):
        if not idx:
            raise gr.Error("请输入要删除的材料序号。")
        services.me_remove_input(int(idx) - 1)
        gr.Info("已删除，建议重新建模")
        return _all()

    del_btn.click(do_del, [del_idx], [profile_md, profile_json, inputs_md])

    @safe
    def do_reset(ok):
        if not ok:
            raise gr.Error("请先勾选确认框。")
        services.me_reset()
        gr.Info("已清空")
        return (*_all(), False)

    reset_btn.click(do_reset, [confirm], [profile_md, profile_json, inputs_md, confirm])

    def refresh(_cid):
        return ()

    return [], refresh
