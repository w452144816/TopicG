"""统一 AI 调用层：所有引擎都走 Anthropic 兼容协议，只换 base_url / api_key / model。

为兼容 MiniMax 等第三方兼容层，这里只用最小参数集（model / max_tokens / system / messages），
不传 thinking / output_config / fallbacks 等参数。
"""
from __future__ import annotations

import base64
import json
import mimetypes
import re
from pathlib import Path
from typing import Any

import anthropic
import httpx2

from config import ProviderConfig


class AIError(Exception):
    """转换成中文提示的调用错误，UI 直接展示 str(e)。"""


_MEDIA = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
          ".webp": "image/webp", ".gif": "image/gif"}


def get_client(cfg: ProviderConfig) -> anthropic.Anthropic:
    if not cfg.ready:
        raise AIError(f"{cfg.label} 未配置 API Key，请在 .env 或页面顶部填入。")
    # SDK 默认客户端会无条件把系统 HTTP(S)_PROXY 挂载上去，trust_env 管不到；
    # 这里用显式 mounts 覆盖所有 scheme：配置了代理就走 cfg.proxy，否则真直连。
    # 建连 5 秒超时（域名有多个 IP 时会逐个尝试）：网络不通时快速报错，而不是挂满 180 秒（超时必须设在自建 http_client 上）
    timeout = anthropic.Timeout(180.0, connect=5.0)
    transport = httpx2.HTTPTransport(proxy=cfg.proxy or None)
    http_client = anthropic.DefaultHttpxClient(
        timeout=timeout, trust_env=False,
        mounts={"all://": transport, "http://": transport, "https://": transport},
    )
    return anthropic.Anthropic(api_key=cfg.api_key, base_url=cfg.base_url, timeout=timeout, max_retries=0,
                               http_client=http_client)


def _image_block(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    media = _MEDIA.get(p.suffix.lower()) or mimetypes.guess_type(p.name)[0] or "image/png"
    data = base64.standard_b64encode(p.read_bytes()).decode("utf-8")
    return {"type": "image", "source": {"type": "base64", "media_type": media, "data": data}}


def _text_of(response: anthropic.types.Message) -> str:
    return "".join(b.text for b in response.content if b.type == "text").strip()


def chat(cfg: ProviderConfig, system: str, messages: list[dict[str, Any]], max_tokens: int = 4096) -> str:
    client = get_client(cfg)
    try:
        resp = client.messages.create(
            model=cfg.model, max_tokens=max_tokens, system=system, messages=messages,
        )
    except anthropic.AuthenticationError as e:
        raise AIError(f"{cfg.label} 鉴权失败，请检查 API Key。({e.status_code})") from e
    except anthropic.RateLimitError as e:
        raise AIError(f"{cfg.label} 触发限流，请稍后重试。({e.status_code})") from e
    except anthropic.APIStatusError as e:
        raise AIError(f"{cfg.label} 接口返回错误 {e.status_code}：{_short(e.message)}") from e
    except anthropic.APIConnectionError as e:
        via = f"，代理 {cfg.proxy}" if cfg.proxy else ""
        raise AIError(f"无法连接 {cfg.label}（{cfg.base_url}{via}）：{_short(str(e))}") from e
    if resp.stop_reason == "refusal":
        raise AIError(f"{cfg.label} 拒绝了本次请求（安全策略）。")
    text = _text_of(resp)
    if not text:
        raise AIError(f"{cfg.label} 返回了空内容（stop_reason={resp.stop_reason}）。")
    return text


def chat_text(cfg: ProviderConfig, system: str, user_text: str, max_tokens: int = 4096) -> str:
    return chat(cfg, system, [{"role": "user", "content": user_text}], max_tokens)


def chat_with_images(cfg: ProviderConfig, system: str, user_text: str,
                     image_paths: list[str | Path], max_tokens: int = 4096) -> str:
    if not cfg.supports_vision:
        raise AIError(f"{cfg.label} 当前配置不支持图片输入，请切换到 Claude 进行图片提取。")
    content: list[dict[str, Any]] = [_image_block(p) for p in image_paths]
    content.append({"type": "text", "text": user_text})
    try:
        return chat(cfg, system, [{"role": "user", "content": content}], max_tokens)
    except AIError as e:
        if "400" in str(e):
            raise AIError(f"{e} —— 该模型可能不支持图片输入，请切换引擎或改用文本录入。") from e
        raise


_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)


def parse_json(text: str) -> Any:
    """宽松解析：去围栏 → 直接 loads → 抓第一个 {…} 或 […]。"""
    cleaned = _FENCE.sub("", text.strip()).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    for opener, closer in (("{", "}"), ("[", "]")):
        s, e = cleaned.find(opener), cleaned.rfind(closer)
        if s != -1 and e > s:
            try:
                return json.loads(cleaned[s:e + 1])
            except json.JSONDecodeError:
                continue
    raise AIError("模型输出不是合法 JSON，原文：\n" + text[:800])


def chat_json(cfg: ProviderConfig, system: str, user_text: str,
              image_paths: list[str | Path] | None = None, max_tokens: int = 4096) -> Any:
    system = system.rstrip() + "\n\n只输出 JSON，不要任何解释、前后缀或 Markdown 围栏。"
    if image_paths:
        raw = chat_with_images(cfg, system, user_text, image_paths, max_tokens)
    else:
        raw = chat_text(cfg, system, user_text, max_tokens)
    return parse_json(raw)


def _short(s: str, n: int = 300) -> str:
    return s if len(s) <= n else s[:n] + "…"
