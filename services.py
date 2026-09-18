"""业务逻辑：录入提取、画像分析、话题生成、回复生成、对话模拟。"""
from __future__ import annotations

from typing import Any

import ai_engine as ai
import ingest
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
    try:
        materials = ingest.expand_uploads(image_files or [], storage.DATA_DIR / cid / "uploads")
    except ingest.IngestError as e:
        raise ai.AIError(str(e)) from e
    if text and text.strip():
        materials.append({"kind": "text", "content": text.strip(), "label": "粘贴文本"})
    for m in materials:
        if m["kind"] == "image":
            saved = storage.save_image(cid, m["path"])
            extracted = ai.chat_json(provider, prompts.EXTRACT_SYSTEM,
                                     f"{hint}\n请从这张截图中提取客户信息。", image_paths=[saved])
            added.append({"type": "image", "content": saved, "extracted": extracted,
                          "added_at": storage.now(), "provider": provider.label})
        else:
            extracted = ai.chat_json(provider, prompts.EXTRACT_SYSTEM,
                                     f"{hint}\n请从下面的文字记录（来源：{m['label']}）中提取客户信息：\n\n{m['content']}")
            added.append({"type": "text", "content": m["content"], "label": m["label"], "extracted": extracted,
                          "added_at": storage.now(), "provider": provider.label})
    if not added:
        raise ai.AIError("请至少上传一张图片或粘贴一段文本。")
    c["raw_inputs"].extend(added)
    storage.save(c)
    return added


def add_note(cid: str, note: str) -> dict[str, Any]:
    """使用者对客户的纠正 / 备注，直接存档不经 AI 提取，建模时权重最高。"""
    c = _require(cid)
    if not note.strip():
        raise ai.AIError("备注内容为空。")
    c["raw_inputs"].append({"type": "note", "content": note.strip(), "extracted": None,
                            "added_at": storage.now(), "provider": "手动"})
    storage.save(c)
    return c


def remove_input(cid: str, index: int) -> dict[str, Any]:
    c = _require(cid)
    if 0 <= index < len(c["raw_inputs"]):
        c["raw_inputs"].pop(index)
        storage.save(c)
    return c


def analyze(cid: str, provider: ProviderConfig) -> dict[str, Any]:
    c = _require(cid)
    if not c["raw_inputs"]:
        raise ai.AIError("该客户还没有任何录入材料，请先在「资料录入」中添加。")
    profile = ai.chat_json(provider, prompts.PROFILE_SYSTEM, prompts.build_profile_input(c))
    if not isinstance(profile, dict):
        raise ai.AIError("画像结果格式异常，请重试。")
    profile["analyzed_at"] = storage.now()
    profile["provider"] = f"{provider.label} / {provider.model}"
    c["profile"] = profile
    storage.save(c)
    return profile


def generate_topics(cid: str, purpose: str, n: int, provider: ProviderConfig,
                    avoid: list[str] | None = None) -> list[dict[str, Any]]:
    """avoid：上一批话题标题，传入后要求模型换角度、不重复。"""
    c = _require(cid)
    if not c.get("profile"):
        raise ai.AIError("该客户尚未分析，请先在「分析页」生成画像。")
    topics = ai.chat_json(provider, prompts.TOPICS_SYSTEM,
                          prompts.build_topics_input(c, purpose, n, storage.load_me(), avoid))
    topics = _as_list(topics, "opening_line", ("topics", "items", "data"))
    c["topics_history"].insert(0, {"generated_at": storage.now(), "purpose": purpose,
                                   "provider": provider.label, "topics": topics})
    c["topics_history"] = c["topics_history"][:20]
    storage.save(c)
    return topics


def rewrite_text(cid: str, text: str, instruction: str, provider: ProviderConfig) -> str:
    """以"我"的口吻按要求改写一条消息（话题开场白 / 候选回复）。"""
    c = _require(cid)
    if not (text or "").strip():
        raise ai.AIError("没有可改写的内容。")
    if not (instruction or "").strip():
        raise ai.AIError("请选择或填写改写要求。")
    out = ai.chat_text(provider, prompts.REWRITE_SYSTEM,
                       prompts.build_rewrite_input(c, text, instruction, storage.load_me()), max_tokens=1000)
    return out.strip().strip('"「」“”')


def rewrite_topic(cid: str, index: int, instruction: str, provider: ProviderConfig) -> list[dict[str, Any]]:
    """改写最近一批话题中第 index 条的开场白，写回历史并返回整批。"""
    c = _require(cid)
    if not c.get("topics_history"):
        raise ai.AIError("还没有生成过话题。")
    topics = c["topics_history"][0]["topics"]
    if not 0 <= index < len(topics):
        raise ai.AIError("请选择要改写的话题。")
    t = topics[index]
    t["opening_line"] = rewrite_text(cid, t.get("opening_line", ""), instruction, provider)
    t["rewritten"] = instruction
    storage.save(c)
    return topics


def _merge_profile(base: dict[str, Any] | None, edited: Any, template: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(edited, dict):
        raise ai.AIError("画像必须是 JSON 对象（花括号包起来的键值对）。")
    base = base or {}
    merged = {**template, **edited}
    for k in ("analyzed_at", "provider"):
        if base.get(k):
            merged[k] = base[k]
    merged["edited_at"] = storage.now()
    return merged


def update_profile(cid: str, edited: Any) -> dict[str, Any]:
    """使用者手工编辑客户画像后保存。保留 analyzed_at / provider，补齐缺失字段。"""
    c = _require(cid)
    c["profile"] = _merge_profile(c.get("profile"), edited, storage.empty_profile())
    storage.save(c)
    return c["profile"]


def generate_replies(cid: str, incoming: str, styles: list[str], provider: ProviderConfig) -> list[dict[str, Any]]:
    c = _require(cid)
    if not incoming.strip():
        raise ai.AIError("请粘贴客户发来的消息。")
    if not styles:
        styles = ["亲切"]
    ctx = "\n".join(f"{'我' if m['role'] == 'user' else '客户'}：{m['content']}" for m in c["chat_history"][-8:])
    replies = ai.chat_json(provider, prompts.REPLY_SYSTEM,
                           prompts.build_reply_input(c, incoming, styles, ctx, storage.load_me()))
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
    reply = ai.chat(provider, prompts.roleplay_system(mode, c, storage.load_me()), msgs, max_tokens=2000)
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


# ---------------- 使用者本人建模 ----------------
def me_intake(text: str, image_files: list[str], provider: ProviderConfig, hint: str = "") -> list[dict[str, Any]]:
    """录入本人的聊天截图 / 自述文本，提取说话风格与人格线索。"""
    me = storage.load_me()
    who = f"使用者本人称呼：{me.get('name') or '未填'}，身份：{me.get('role') or '未填'}。{hint}".strip()
    added: list[dict[str, Any]] = []
    try:
        materials = ingest.expand_uploads(image_files or [], storage.ME_IMG_DIR.parent / "me_uploads")
    except ingest.IngestError as e:
        raise ai.AIError(str(e)) from e
    if text and text.strip():
        materials.append({"kind": "text", "content": text.strip(), "label": "粘贴文本"})
    for m in materials:
        if m["kind"] == "image":
            saved = storage.save_me_image(m["path"])
            extracted = ai.chat_json(provider, prompts.ME_EXTRACT_SYSTEM,
                                     f"{who}\n请只分析截图中「使用者本人」这一方说的话。", image_paths=[saved])
            added.append({"type": "image", "content": saved, "extracted": extracted,
                          "added_at": storage.now(), "provider": provider.label})
        else:
            extracted = ai.chat_json(provider, prompts.ME_EXTRACT_SYSTEM,
                                     f"{who}\n下面是使用者本人的聊天记录或自述文字（来源：{m['label']}），请分析：\n\n{m['content']}")
            added.append({"type": "text", "content": m["content"], "label": m["label"], "extracted": extracted,
                          "added_at": storage.now(), "provider": provider.label})
    if not added:
        raise ai.AIError("请至少上传一张图片或粘贴一段文本。")
    me["raw_inputs"].extend(added)
    storage.save_me(me)
    return added


def me_add_note(note: str) -> dict[str, Any]:
    """本人对自己的纠正 / 备注，直接存档，建模时权重最高。"""
    me = storage.load_me()
    if not note.strip():
        raise ai.AIError("备注内容为空。")
    me["raw_inputs"].append({"type": "note", "content": note.strip(), "extracted": None,
                             "added_at": storage.now(), "provider": "手动"})
    storage.save_me(me)
    return me


def me_analyze(provider: ProviderConfig) -> dict[str, Any]:
    me = storage.load_me()
    if not me["raw_inputs"]:
        raise ai.AIError("还没有录入你自己的材料，请先上传聊天截图或粘贴文字。")
    profile = ai.chat_json(provider, prompts.ME_PROFILE_SYSTEM, prompts.build_me_profile_input(me))
    if not isinstance(profile, dict):
        raise ai.AIError("画像结果格式异常，请重试。")
    profile["analyzed_at"] = storage.now()
    profile["provider"] = f"{provider.label} / {provider.model}"
    me["profile"] = profile
    storage.save_me(me)
    return profile


def me_update_profile(edited: Any) -> dict[str, Any]:
    """使用者手工编辑本人画像后保存。"""
    me = storage.load_me()
    me["profile"] = _merge_profile(me.get("profile"), edited, {})
    storage.save_me(me)
    return me["profile"]


def me_update_basic(name: str, role: str) -> dict[str, Any]:
    me = storage.load_me()
    me["name"], me["role"] = name.strip(), role.strip()
    storage.save_me(me)
    return me


def me_remove_input(index: int) -> dict[str, Any]:
    me = storage.load_me()
    if 0 <= index < len(me["raw_inputs"]):
        me["raw_inputs"].pop(index)
        storage.save_me(me)
    return me


def me_reset() -> None:
    me = storage.load_me()
    me.update({"raw_inputs": [], "profile": None})
    storage.save_me(me)
