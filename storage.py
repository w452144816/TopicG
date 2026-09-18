"""客户存档：每个客户一个 JSON 文件 data/customers/<id>.json，图片放 data/customers/<id>/images/。"""
from __future__ import annotations

import json
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from config import DATA_DIR


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _path(cid: str) -> Path:
    return DATA_DIR / f"{cid}.json"


def _img_dir(cid: str) -> Path:
    return DATA_DIR / cid / "images"


def empty_profile() -> dict[str, Any]:
    return {
        "basic": {"gender": "", "age_range": "", "city": "", "occupation": "", "company": ""},
        "personality": "", "interests": [], "communication_style": "", "pain_points": [],
        "relationship_stage": "", "recent_events": [], "taboos": [], "summary": "",
        "analyzed_at": "", "provider": "",
    }


def create(name: str, tags: list[str] | None = None) -> dict[str, Any]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    obj = {
        "id": uuid.uuid4().hex[:12],
        "name": name.strip(),
        "tags": [t.strip() for t in (tags or []) if t.strip()],
        "created_at": now(),
        "updated_at": now(),
        "raw_inputs": [],
        "profile": None,
        "topics_history": [],
        "chat_history": [],
    }
    save(obj)
    return obj


def save(obj: dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    obj["updated_at"] = now()
    target = _path(obj["id"])
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, target)


def load(cid: str) -> dict[str, Any] | None:
    p = _path(cid)
    if not cid or not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def list_customers() -> list[dict[str, Any]]:
    if not DATA_DIR.exists():
        return []
    items = []
    for p in DATA_DIR.glob("*.json"):
        try:
            items.append(json.loads(p.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
    return sorted(items, key=lambda c: c.get("updated_at", ""), reverse=True)


def delete(cid: str) -> bool:
    p = _path(cid)
    existed = p.exists()
    if existed:
        p.unlink()
    shutil.rmtree(DATA_DIR / cid, ignore_errors=True)
    return existed


def save_image(cid: str, src: str | Path) -> str:
    d = _img_dir(cid)
    d.mkdir(parents=True, exist_ok=True)
    src = Path(src)
    dst = d / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}{src.suffix.lower() or '.png'}"
    shutil.copyfile(src, dst)
    return str(dst)


def choices() -> list[tuple[str, str]]:
    """Gradio Dropdown 用的 (label, value) 列表。"""
    return [(f"{c['name']}  [{', '.join(c['tags']) or '无标签'}]", c["id"]) for c in list_customers()]
