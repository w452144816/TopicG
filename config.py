"""引擎配置：从 .env 读取各 provider 的 key / base_url / model。"""
from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data" / "customers"
load_dotenv(BASE_DIR / ".env")


@dataclass(frozen=True)
class ProviderConfig:
    key: str            # 内部标识 minimax / claude
    label: str          # 页面显示名
    api_key: str
    base_url: str
    model: str
    supports_vision: bool = True
    proxy: str = ""     # 为空则直连

    def with_override(self, api_key: str = "", model: str = "", use_proxy: bool | None = None) -> "ProviderConfig":
        """页面临时覆盖 key / model / 是否走代理（不落盘）。"""
        proxy = self.proxy
        if use_proxy is not None:
            proxy = PROXY_URL if use_proxy else ""
        return replace(
            self,
            api_key=api_key.strip() or self.api_key,
            model=model.strip() or self.model,
            proxy=proxy,
        )

    @property
    def ready(self) -> bool:
        return bool(self.api_key)


# 可选 HTTP 代理，例如 http://192.168.80.222:3128；PROXY_ENABLED 控制默认是否启用
PROXY_URL = os.getenv("PROXY_URL", "").strip()
PROXY_ENABLED = bool(PROXY_URL) and os.getenv("PROXY_ENABLED", "false").lower() == "true"
_DEFAULT_PROXY = PROXY_URL if PROXY_ENABLED else ""

PROVIDERS: dict[str, ProviderConfig] = {
    "minimax": ProviderConfig(
        key="minimax",
        label="MiniMax",
        api_key=os.getenv("MINIMAX_API_KEY", ""),
        base_url=os.getenv("MINIMAX_BASE_URL", "https://api.minimaxi.com/anthropic"),
        model=os.getenv("MINIMAX_MODEL", "MiniMax-M2.5"),
        supports_vision=os.getenv("MINIMAX_SUPPORTS_VISION", "true").lower() == "true",
        proxy=_DEFAULT_PROXY,
    ),
    "claude": ProviderConfig(
        key="claude",
        label="Claude",
        api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        base_url=os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com"),
        model=os.getenv("ANTHROPIC_MODEL", "claude-opus-5"),
        supports_vision=True,
        proxy=_DEFAULT_PROXY,
    ),
}

DEFAULT_PROVIDER = os.getenv("DEFAULT_PROVIDER", "minimax")
if DEFAULT_PROVIDER not in PROVIDERS:
    DEFAULT_PROVIDER = "minimax"

LABEL_TO_KEY = {p.label: p.key for p in PROVIDERS.values()}
PROVIDER_LABELS = list(LABEL_TO_KEY)


def get_provider(key_or_label: str, api_key_override: str = "", model_override: str = "",
                 use_proxy: bool | None = None) -> ProviderConfig:
    key = LABEL_TO_KEY.get(key_or_label, key_or_label)
    cfg = PROVIDERS.get(key) or PROVIDERS[DEFAULT_PROVIDER]
    return cfg.with_override(api_key_override, model_override, use_proxy)
