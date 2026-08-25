"""Configuration and the non-negotiable local-model policy."""

from __future__ import annotations

import os
from pathlib import Path


APPROVED_MODEL_NAME = "Qwen3.8-27B-MLX-Mixed-4.95bpw"
DEFAULT_MODEL_PATH = Path.home() / ".omlx" / "models" / APPROVED_MODEL_NAME
DEFAULT_BASE_URL = "http://127.0.0.1:8085/v1"


def configured_base_url() -> str:
    return os.environ.get("STUDENT_REVIEW_QWEN_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def configured_model() -> str:
    model = os.environ.get("STUDENT_REVIEW_QWEN_MODEL", str(DEFAULT_MODEL_PATH))
    if APPROVED_MODEL_NAME not in model:
        raise RuntimeError(
            "拒绝调用：学生证明审查流水线只能使用本地 Qwen3.8 27B 主模型。"
        )
    return model
