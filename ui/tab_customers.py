"""客户管理页：列表 / 新增 / 删除 / 标签编辑。"""
from __future__ import annotations

import gradio as gr

import services
import storage
from ui.common import customer_dropdown_update, refresh_button, safe

COLUMNS = ["ID", "姓名", "标签", "录入条数", "已分析", "更新时间"]


def table_rows() -> list[list]:
    return [[c["id"], c["name"], "、".join(c.get("tags") or []), len(c.get("raw_inputs", [])),
             "是" if c.get("profile") else "否", c.get("updated_at", "")] for c in storage.list_customers()]


def build(shared: dict) -> tuple[list, callable]:
    customer_dd = shared["customer"]
    with gr.Row():
        gr.Markdown("### 客户列表\n每位客户对应一份独立存档（JSON）。点击表格某行可选中该客户。")
        refresh_btn = refresh_button()
    table = gr.Dataframe(value=table_rows(), headers=COLUMNS, interactive=False, wrap=True)

    with gr.Row():
        with gr.Column():
            gr.Markdown("#### 新增客户")
            name_in = gr.Textbox(label="姓名 / 称呼", placeholder="例如：王总、李姐")
            tags_in = gr.Textbox(label="标签（逗号分隔）", placeholder="例如：地产, 华东, 重点客户")
            add_btn = gr.Button("➕ 新增客户", variant="primary")
        with gr.Column():
            gr.Markdown("#### 编辑 / 删除当前客户")
            edit_tags = gr.Textbox(label="当前客户标签（逗号分隔）")
            save_tags_btn = gr.Button("保存标签")
            confirm = gr.Checkbox(label="我确认删除当前选中的客户及其全部资料", value=False)
            del_btn = gr.Button("🗑 删除当前客户", variant="stop")

    @safe
    def add(name, tags):
        if not name.strip():
            raise gr.Error("请输入客户姓名。")
        c = storage.create(name, tags.replace("，", ",").split(","))
        gr.Info(f"已新增客户「{c['name']}」")
        return table_rows(), customer_dropdown_update(c["id"]), "", ""

    ev_add = add_btn.click(add, [name_in, tags_in], [table, customer_dd, name_in, tags_in])

    @safe
    def delete(cid, ok):
        if not cid:
            raise gr.Error("未选中客户。")
        if not ok:
            raise gr.Error("请先勾选确认框再删除。")
        c = storage.load(cid)
        storage.delete(cid)
        gr.Info(f"已删除客户「{c['name'] if c else cid}」")
        return table_rows(), customer_dropdown_update(None), False

    ev_del = del_btn.click(delete, [customer_dd, confirm], [table, customer_dd, confirm])

    @safe
    def save_tags(cid, tags):
        c = services.update_tags(cid, tags)
        gr.Info("标签已保存")
        return table_rows(), customer_dropdown_update(c["id"])

    ev_tags = save_tags_btn.click(save_tags, [customer_dd, edit_tags], [table, customer_dd])

    def on_select(evt: gr.SelectData):
        rows = table_rows()
        idx = evt.index[0] if isinstance(evt.index, (list, tuple)) else evt.index
        if 0 <= idx < len(rows):
            return customer_dropdown_update(rows[idx][0])
        return gr.update()

    table.select(on_select, None, [customer_dd])

    def refresh(cid):
        c = storage.load(cid) if cid else None
        return table_rows(), "、".join(c.get("tags") or []) if c else ""

    events = [ev_add, ev_del, ev_tags, refresh_btn.click(lambda: None)]
    return [table, edit_tags], refresh, events
