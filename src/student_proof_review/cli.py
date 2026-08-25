"""Command-line interface for the student proof review workflow."""

from __future__ import annotations

import argparse
from pathlib import Path

from .qwen import preflight
from .render import build_report, deliver_report, verify_report
from .workflow import create_case, status, transcribe_case


def _path(value: str) -> Path:
    return Path(value).expanduser().resolve()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="student-proof-review", description="学生证明审查流水线")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("preflight", help="检查本地 Qwen3.8 27B 服务和模型")

    create = sub.add_parser("create", help="创建一个审查任务")
    create.add_argument("--case-name", required=True)
    create.add_argument("--title", required=True)
    create.add_argument("--image", action="append", required=True, type=_path)
    create.add_argument("--output-root", type=_path, default=Path("outputs").resolve())

    transcribe = sub.add_parser("transcribe", help="进行本地视觉转写")
    transcribe.add_argument("case_dir", type=_path)
    transcribe.add_argument("--rotate", type=int, default=0, choices=(0, 90, 180, 270))

    report = sub.add_parser("report", help="从 audit.md 编译公开 PDF")
    report.add_argument("case_dir", type=_path)
    report.add_argument("--draft", action="store_true", help="允许审查稿尚有待填写项")

    verify = sub.add_parser("verify", help="渲染并核验 PDF")
    verify.add_argument("case_dir", type=_path)
    verify.add_argument("--vision", action="store_true", help="额外执行本地版式复核")

    deliver = sub.add_parser("deliver", help="将完成的 PDF 复制到指定目录")
    deliver.add_argument("case_dir", type=_path)
    deliver.add_argument("--destination", required=True, type=_path)

    show = sub.add_parser("status", help="查看任务状态")
    show.add_argument("case_dir", type=_path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "preflight":
        info = preflight()
        print("本地 Qwen3.8 27B 服务已通过核对。")
        print(f"端点：{info['base_url']}")
        return 0
    if args.command == "create":
        case = create_case(args.output_root, args.case_name, args.title, args.image)
        print(case)
        return 0
    if args.command == "transcribe":
        print(transcribe_case(args.case_dir, args.rotate))
        return 0
    if args.command == "report":
        print(build_report(args.case_dir, args.draft))
        return 0
    if args.command == "verify":
        print(verify_report(args.case_dir, args.vision))
        return 0
    if args.command == "deliver":
        print(deliver_report(args.case_dir, args.destination))
        return 0
    if args.command == "status":
        print(status(args.case_dir))
        return 0
    raise AssertionError(f"unhandled command: {args.command}")
