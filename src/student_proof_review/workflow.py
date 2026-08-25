"""Case creation, provenance, and visual transcription stages."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageOps

from .qwen import vision


TRANSCRIPTION_PROMPT = r"""
你只负责视觉转写，不判断证明是否正确，也不补全缺失的数学推理。

这是一组数学题目与学生手写作答图片。请阅读图片方向，严格按以下格式输出 Obsidian Markdown：

## 题干

逐字转写打印或清晰可见的题目。公式使用 LaTeX。

## 学生有效作答

按原有顺序转写学生最后保留的作答。被红笔或黑笔大面积明确划掉的段落不要混入本节。

## 已删除或作废部分

仅概括哪些区域被明显划掉；不要尝试恢复它们。

## 待核对处

将每个无法可靠辨认的文字、上下标、符号或图形关系写为 `[不清]`，并说明其所在位置。不要猜测。

额外要求：核对整数条件、大小关系、求和/乘积上下标、模运算、除法分母、几何图中的点名。不要提及任何模型、识别工具或 OCR。
""".strip()


AUDIT_TEMPLATE = """# {title}

## 题目

待填写：请依据原图与转写稿核对后写入题干。

## 评审结论

- 答案正确：待填写。
- 主线正确：待填写。
- 原稿完整正确：待填写。
- 总评：待填写。

## 学生方法整理

待填写：只整理学生最后保留的有效推理，不将划掉的草稿混入。

## 第一处需要修补的地方

待填写：指出第一处不能由前文推出的结论；说明缺少的条件、计算或论证。

## 最小修补

待填写：在不推翻学生主要思路的前提下，补出可直接验证的步骤。所有除法、非零条件、边界情形和等号条件均须明确。

## 给学生的建议

待填写：给出一到三条具体、可执行的建议。
"""


def _slug(value: str) -> str:
    value = value.strip()
    clean = re.sub(r"[^A-Za-z0-9._-]+", "-", value)
    return clean.strip("-.") or "review-case"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _case_file(case_dir: Path) -> Path:
    return case_dir / "case.json"


def load_case(case_dir: Path) -> dict[str, object]:
    try:
        return json.loads(_case_file(case_dir).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"找不到任务元数据：{_case_file(case_dir)}") from exc


def create_case(output_root: Path, case_name: str, title: str, images: Iterable[Path]) -> Path:
    case_dir = output_root / _slug(case_name)
    if case_dir.exists():
        raise RuntimeError(f"任务目录已存在：{case_dir}")
    image_paths = [Path(path).expanduser().resolve() for path in images]
    if not image_paths:
        raise RuntimeError("至少需要一张题目或学生作答图片。")
    for image in image_paths:
        if not image.is_file():
            raise RuntimeError(f"找不到输入文件：{image}")

    (case_dir / "input").mkdir(parents=True)
    (case_dir / "internal").mkdir()
    records = []
    for index, source in enumerate(image_paths, start=1):
        target = case_dir / "input" / f"{index:02d}_{source.name}"
        shutil.copy2(source, target)
        records.append(
            {
                "original_path": str(source),
                "copied_path": str(target.relative_to(case_dir)),
                "sha256": _sha256(target),
            }
        )
    metadata = {
        "schema": "student-proof-review/case-v1",
        "title": title,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "inputs": records,
        "stages": {"transcription": "pending", "audit": "pending", "report": "pending", "verification": "pending"},
    }
    _case_file(case_dir).write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (case_dir / "audit.md").write_text(AUDIT_TEMPLATE.format(title=title), encoding="utf-8")
    return case_dir


def _normalize_image(source: Path, target: Path, rotate: int) -> None:
    with Image.open(source) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        if rotate:
            image = image.rotate(-rotate, expand=True)
        image.save(target, quality=95)


def transcribe_case(case_dir: Path, rotate: int = 0) -> Path:
    metadata = load_case(case_dir)
    input_paths = [case_dir / str(item["copied_path"]) for item in metadata["inputs"]]
    prepared_dir = case_dir / "internal" / "prepared_images"
    prepared_dir.mkdir(parents=True, exist_ok=True)
    prepared = []
    for index, source in enumerate(input_paths, start=1):
        target = prepared_dir / f"{index:02d}.jpg"
        _normalize_image(source, target, rotate)
        prepared.append(target)

    result = vision(prepared, TRANSCRIPTION_PROMPT, max_tokens=7000)
    target = case_dir / "transcription.md"
    target.write_text(result + "\n", encoding="utf-8")
    metadata["stages"]["transcription"] = "completed"
    metadata["transcription"] = {"rotation_degrees": rotate, "file": str(target.relative_to(case_dir))}
    _case_file(case_dir).write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def status(case_dir: Path) -> str:
    metadata = load_case(case_dir)
    stages = metadata.get("stages", {})
    lines = [f"任务：{metadata.get('title', '')}", f"目录：{case_dir}", ""]
    for name in ("transcription", "audit", "report", "verification"):
        lines.append(f"- {name}: {stages.get(name, 'pending')}")
    return "\n".join(lines)
