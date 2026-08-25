"""Strict local client used only for visual transcription and layout screening."""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Iterable

import requests

from .config import APPROVED_MODEL_NAME, configured_base_url, configured_model


def _mime_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".png":
        return "image/png"
    return mimetypes.guess_type(path.name)[0] or "application/octet-stream"


def preflight(timeout: int = 10) -> dict[str, object]:
    """Confirm the live endpoint lists the only model permitted by this project."""
    base_url = configured_base_url()
    requested = configured_model()
    try:
        response = requests.get(f"{base_url}/models", timeout=timeout)
        response.raise_for_status()
        data = response.json().get("data", [])
    except Exception as exc:
        raise RuntimeError(
            f"无法读取本地模型服务 {base_url}/models：{exc}。请先启动 Qwen3.8 27B 服务。"
        ) from exc

    model_ids = [str(item.get("id", "")) for item in data if isinstance(item, dict)]
    approved = [item for item in model_ids if APPROVED_MODEL_NAME in item]
    if not approved:
        raise RuntimeError(
            "本地服务未报告获准的 Qwen3.8 27B 主模型；为避免路由错误，本次任务已停止。"
        )
    if APPROVED_MODEL_NAME not in requested:
        raise RuntimeError("当前配置不是获准的 Qwen3.8 27B 模型。")
    return {"base_url": base_url, "requested_model": requested, "live_models": model_ids}


def vision(image_paths: Iterable[Path], prompt: str, *, max_tokens: int = 6000) -> str:
    info = preflight()
    content: list[dict[str, object]] = []
    for path in image_paths:
        payload = base64.b64encode(path.read_bytes()).decode("ascii")
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:{_mime_type(path)};base64,{payload}"},
            }
        )
    content.append({"type": "text", "text": prompt})
    try:
        response = requests.post(
            f"{info['base_url']}/chat/completions",
            json={
                "model": info["requested_model"],
                "temperature": 0,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": content}],
            },
            timeout=420,
        )
        response.raise_for_status()
        text = response.json()["choices"][0]["message"]["content"]
    except Exception as exc:
        raise RuntimeError(f"本地视觉转写调用失败：{exc}") from exc
    if not isinstance(text, str) or not text.strip():
        raise RuntimeError("本地视觉转写返回为空。")
    return text.strip()
