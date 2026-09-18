"""上传文件预处理：把图片 / 文本 / 表格 / zip 统一展开成录入材料。

expand_uploads(paths, workdir) -> list[Material]
  Material = {"kind": "image", "path": ...}
           | {"kind": "text",  "content": ..., "label": "来源说明"}
zip 会递归解开（图片、txt/md、csv/xlsx/xls），忽略其它类型与 macOS 垃圾文件。
"""
from __future__ import annotations

import csv
import io
import zipfile
from pathlib import Path
from typing import Any

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
TEXT_EXT = {".txt", ".md", ".log"}
TABLE_EXT = {".xlsx", ".xlsm", ".xls", ".csv"}
ZIP_EXT = {".zip"}
ACCEPTED_EXT = sorted(IMAGE_EXT | TEXT_EXT | TABLE_EXT | ZIP_EXT)

MAX_TABLE_CHARS = 6000     # 单张表转文本上限，超出截断并注明
MAX_ROWS = 400
MAX_ZIP_FILES = 200


class IngestError(Exception):
    pass


def _decode(raw: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "gb18030", "utf-16"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _rows_to_text(rows: list[list[Any]], title: str) -> str:
    lines = [f"【表格：{title}】"]
    total = len(rows)
    for r in rows[:MAX_ROWS]:
        cells = ["" if v is None else str(v).strip() for v in r]
        if any(cells):
            lines.append(" | ".join(cells))
    text = "\n".join(lines)
    if total > MAX_ROWS:
        text += f"\n（共 {total} 行，仅展示前 {MAX_ROWS} 行）"
    if len(text) > MAX_TABLE_CHARS:
        text = text[:MAX_TABLE_CHARS] + "\n（内容过长已截断）"
    return text


def table_to_texts(path: Path) -> list[tuple[str, str]]:
    """返回 [(label, text)]，xlsx 每个 sheet 一条。"""
    ext = path.suffix.lower()
    if ext == ".csv":
        rows = list(csv.reader(io.StringIO(_decode(path.read_bytes()))))
        return [(f"{path.name}", _rows_to_text(rows, path.name))]
    if ext in (".xlsx", ".xlsm"):
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        out = []
        for ws in wb.worksheets:
            rows = [list(r) for r in ws.iter_rows(values_only=True)]
            if any(any(v not in (None, "") for v in r) for r in rows):
                out.append((f"{path.name} / {ws.title}", _rows_to_text(rows, f"{path.name} / {ws.title}")))
        wb.close()
        return out
    if ext == ".xls":
        raise IngestError(f"{path.name}：旧版 .xls 暂不支持，请用 Excel 另存为 .xlsx 或 .csv 后再上传。")
    raise IngestError(f"不支持的表格格式：{path.name}")


def _is_junk(name: str) -> bool:
    base = Path(name).name
    return base.startswith("._") or base == ".DS_Store" or "__MACOSX" in name or base.startswith("~$")


def _extract_zip(path: Path, workdir: Path) -> list[Path]:
    target = workdir / (path.stem + "_unzipped")
    target.mkdir(parents=True, exist_ok=True)
    out: list[Path] = []
    with zipfile.ZipFile(path) as zf:
        members = [m for m in zf.infolist() if not m.is_dir() and not _is_junk(m.filename)]
        if len(members) > MAX_ZIP_FILES:
            raise IngestError(f"{path.name} 内文件过多（{len(members)} 个），单次最多 {MAX_ZIP_FILES} 个。")
        for m in members:
            ext = Path(m.filename).suffix.lower()
            if ext not in IMAGE_EXT | TEXT_EXT | TABLE_EXT | ZIP_EXT:
                continue
            # zip 里的中文文件名常为 cp437 误编码，尝试修正
            name = m.filename
            try:
                name = name.encode("cp437").decode("gbk")
            except (UnicodeEncodeError, UnicodeDecodeError):
                pass
            dst = target / Path(name).name
            if dst.exists():
                dst = target / f"{dst.stem}_{m.CRC:08x}{dst.suffix}"
            dst.write_bytes(zf.read(m))
            out.append(dst)
    return out


def expand_uploads(paths: list[str | Path], workdir: Path, _depth: int = 0) -> list[dict[str, Any]]:
    """把上传的文件列表展开成材料。workdir 用于存放 zip 解出的文件。"""
    materials: list[dict[str, Any]] = []
    for p in paths or []:
        path = Path(p)
        ext = path.suffix.lower()
        if ext in IMAGE_EXT:
            materials.append({"kind": "image", "path": path})
        elif ext in TEXT_EXT:
            materials.append({"kind": "text", "content": _decode(path.read_bytes()), "label": path.name})
        elif ext in TABLE_EXT:
            for label, text in table_to_texts(path):
                materials.append({"kind": "text", "content": text, "label": label})
        elif ext in ZIP_EXT:
            if _depth >= 2:
                raise IngestError(f"{path.name}：压缩包嵌套过深。")
            inner = _extract_zip(path, workdir)
            materials.extend(expand_uploads(inner, workdir, _depth + 1))
        else:
            raise IngestError(f"不支持的文件类型：{path.name}（支持 {', '.join(ACCEPTED_EXT)}）")
    return materials
