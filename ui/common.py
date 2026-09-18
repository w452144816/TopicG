"""UI 公共工具：引擎配置读取、错误转换、Markdown 渲染。"""
from __future__ import annotations

import functools
from typing import Any, Callable

import gradio as gr

import storage
from ai_engine import AIError
from config import ProviderConfig, get_provider


def cfg_from_ui(provider_label: str, key_override: str, model_override: str,
                use_proxy: bool | None = None) -> ProviderConfig:
    return get_provider(provider_label, key_override or "", model_override or "", use_proxy)


def safe(fn: Callable) -> Callable:
    """把 AIError / 其他异常转成 gr.Error 弹窗，不让页面卡死。"""
    @functools.wraps(fn)
    def wrapper(*a, **kw):
        try:
            return fn(*a, **kw)
        except AIError as e:
            raise gr.Error(str(e), duration=8)
        except gr.Error:
            raise
        except Exception as e:  # noqa: BLE001
            raise gr.Error(f"发生错误：{type(e).__name__}: {e}", duration=10)
    return wrapper


def customer_dropdown_update(selected: str | None = None) -> dict:
    ch = storage.choices()
    ids = [v for _, v in ch]
    value = selected if selected in ids else (ids[0] if ids else None)
    return gr.update(choices=ch, value=value)


def _li(items: Any) -> str:
    if not items:
        return "- （无）"
    if isinstance(items, str):
        return f"- {items}"
    return "\n".join(f"- {x}" for x in items)


def render_profile(c: dict[str, Any] | None) -> str:
    if not c:
        return "> 请先选择客户。"
    p = c.get("profile")
    head = f"## {c['name']}  \n标签：{'、'.join(c.get('tags') or []) or '无'} ｜ 录入材料 {len(c.get('raw_inputs', []))} 条"
    if not p:
        return head + "\n\n> 尚未分析。请在录入材料后点击「重新分析」。"
    b = p.get("basic") or {}
    basic = " ｜ ".join(f"{k}：{v}" for k, v in [("性别", b.get("gender")), ("年龄", b.get("age_range")),
                                                  ("城市", b.get("city")), ("职业", b.get("occupation")),
                                                  ("公司", b.get("company"))] if v)
    return f"""{head}

> **一句话总结**：{p.get('summary') or '信息不足'}
> 分析时间：{p.get('analyzed_at', '')} ｜ 引擎：{p.get('provider', '')}

### 基本信息
{basic or '信息不足'}

### 性格与沟通风格
**性格**：{p.get('personality') or '信息不足'}

**沟通偏好**：{p.get('communication_style') or '信息不足'}

### 兴趣点
{_li(p.get('interests'))}

### 需求 / 痛点
{_li(p.get('pain_points'))}

### 关系阶段
{p.get('relationship_stage') or '信息不足'}

### 近期事件（可跟进）
{_li(p.get('recent_events'))}

### 切入机会
{_li(p.get('opportunities'))}

### ⚠️ 禁忌 / 避免
{_li(p.get('taboos'))}
"""


def render_topics(topics: list[dict[str, Any]]) -> str:
    if not topics:
        return "> 暂无话题。"
    out = []
    for i, t in enumerate(topics, 1):
        out.append(f"""### {i}. {t.get('title', '')}
**开场白**：{t.get('opening_line', '')}

- **为什么合适**：{t.get('why', '')}
- **注意点**：{t.get('risk', '')}
- **客户回应后可接**：{t.get('follow_up', '')}
""")
    return "\n".join(out)


def topics_plain(topics: list[dict[str, Any]]) -> str:
    return "\n\n".join(f"【{t.get('title', '')}】\n{t.get('opening_line', '')}" for t in topics)


def render_replies(replies: list[dict[str, Any]]) -> str:
    if not replies:
        return "> 暂无回复。"
    return "\n\n".join(
        f"### {r.get('style', '')}\n{r.get('reply', '')}\n\n> {r.get('note', '')}" for r in replies)


def replies_plain(replies: list[dict[str, Any]]) -> str:
    return "\n\n".join(f"[{r.get('style', '')}]\n{r.get('reply', '')}" for r in replies)


def render_inputs(c: dict[str, Any] | None) -> str:
    if not c or not c.get("raw_inputs"):
        return "> 该客户还没有录入材料。"
    out = []
    for i, item in enumerate(c["raw_inputs"], 1):
        if item.get("type") == "note":
            out.append(f"**{i}. [纠正/备注] {item.get('added_at', '')}**\n  - {item.get('content', '')}")
            continue
        ex = item.get("extracted") or {}
        src = ex.get("source_summary", "") if isinstance(ex, dict) else ""
        quotes = ex.get("key_quotes", []) if isinstance(ex, dict) else []
        out.append(f"**{i}. [{'图片' if item['type'] == 'image' else '文本'}] {item.get('added_at', '')}** ｜ {src}\n"
                   + (("\n".join(f"  - {q}" for q in quotes[:3])) if quotes else ""))
    return "\n\n".join(out)
