"""业务逻辑：录入提取、画像分析、话题生成、回复生成、对话模拟。"""
from __future__ import annotations

from typing import Any

import ai_engine as ai
import prompts
import storage
from config import ProviderConfig


def _as_list(data: Any, item_key: str, wrapper_keys: tuple[str, ...]) -> list[dict[str, Any]]:
    """把模型返回的 list / {"topics": [...]} / 单个对象 统一成 list。"""
    if isinstance(data, dict):
        if item_key in data:            # 单个对象
            return [data]
        for k in wrapper_keys:
            if isinstance(data.get(k), list):
                return data[k]
        for v in data.values():         # 任意一个 list 字段
            if isinstance(v, list):
                return v
        raise ai.AIError("结果格式异常，请重试。原文：" + str(data)[:300])
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    raise ai.AIError("结果格式异常，请重试。")


def _require(cid: str) -> dict[str, Any]:
    c = storage.load(cid)
    if not c:
        raise ai.AIError("请先在「客户管理」中选择或新建一个客户。")
    return c


def intake(cid: str, text: str, image_files: list[str], provider: ProviderConfig,
           customer_hint: str = "") -> list[dict[str, Any]]:
    """提取图片与文本中的客户信息并存档，返回本次新增的 raw_inputs。"""
    c = _require(cid)
    hint = f"客户是「{c['name']}」。{customer_hint}".strip()
    added: list[dict[str, Any]] = []
    for f in image_files or []:
        saved = storage.save_image(cid, f)
        extracted = ai.chat_json(provider, prompts.EXTRACT_SYSTEM,
                                 f"{hint}\n请从这张截图中提取客户信息。", image_paths=[saved])
        added.append({"type": "image", "content": saved, "extracted": extracted,
                      "added_at": storage.now(), "provider": provider.label})
    if text and text.strip():
        extracted = ai.chat_json(provider, prompts.EXTRACT_SYSTEM,
                                 f"{hint}\n请从下面的文字记录中提取客户信息：\n\n{text.strip()}")
        added.append({"type": "text", "content": text.strip(), "extracted": extracted,
                      "added_at": storage.now(), "provider": provider.label})
    if not added:
        raise ai.AIError("请至少上传一张图片或粘贴一段文本。")
    c["raw_inputs"].extend(added)
    storage.save(c)
    return added


def analyze(cid: str, provider: ProviderConfig) -> dict[str, Any]:
    c = _require(cid)
    if not c["raw_inputs"]:
        raise ai.AIError("该客户还没有任何录入材料，请先在「资料录入」中添加。")
    profile = ai.chat_json(provider, prompts.PROFILE_SYSTEM, prompts.build_profile_input(c), max_tokens=6000)
    if not isinstance(profile, dict):
        raise ai.AIError("画像结果格式异常，请重试。")
    profile["analyzed_at"] = storage.now()
    profile["provider"] = f"{provider.label} / {provider.model}"
    c["profile"] = profile
    storage.save(c)
    return profile


def generate_topics(cid: str, purpose: str, n: int, provider: ProviderConfig) -> list[dict[str, Any]]:
    c = _require(cid)
    if not c.get("profile"):
        raise ai.AIError("该客户尚未分析，请先在「分析页」生成画像。")
    topics = ai.chat_json(provider, prompts.TOPICS_SYSTEM, prompts.build_topics_input(c, purpose, n), max_tokens=6000)
    topics = _as_list(topics, "opening_line", ("topics", "items", "data"))
    c["topics_history"].insert(0, {"generated_at": storage.now(), "purpose": purpose,
                                   "provider": provider.label, "topics": topics})
    c["topics_history"] = c["topics_history"][:20]
    storage.save(c)
    return topics


def generate_replies(cid: str, incoming: str, styles: list[str], provider: ProviderConfig) -> list[dict[str, Any]]:
    c = _require(cid)
    if not incoming.strip():
        raise ai.AIError("请粘贴客户发来的消息。")
    if not styles:
        styles = ["亲切"]
    ctx = "\n".join(f"{'我' if m['role'] == 'user' else '客户'}：{m['content']}" for m in c["chat_history"][-8:])
    replies = ai.chat_json(provider, prompts.REPLY_SYSTEM, prompts.build_reply_input(c, incoming, styles, ctx))
    replies = _as_list(replies, "reply", ("replies", "items", "data"))
    return replies


def roleplay_turn(cid: str, mode: str, user_msg: str, provider: ProviderConfig) -> list[dict[str, str]]:
    """mode: customer（AI 扮演客户）/ assistant（AI 做助手）。返回完整 chat_history。"""
    c = _require(cid)
    if not user_msg.strip():
        raise ai.AIError("请输入内容。")
    history = c["chat_history"]
    history.append({"role": "user", "content": user_msg.strip()})
    msgs = [{"role": m["role"], "content": m["content"]} for m in history[-20:]]
    if msgs[0]["role"] != "user":
        msgs = msgs[1:]
    reply = ai.chat(provider, prompts.roleplay_system(mode, c), msgs, max_tokens=2000)
    history.append({"role": "assistant", "content": reply})
    storage.save(c)
    return history


def clear_chat(cid: str) -> None:
    c = _require(cid)
    c["chat_history"] = []
    storage.save(c)


def update_tags(cid: str, tags_text: str) -> dict[str, Any]:
    c = _require(cid)
    c["tags"] = [t.strip() for t in tags_text.replace("，", ",").split(",") if t.strip()]
    storage.save(c)
    return c
