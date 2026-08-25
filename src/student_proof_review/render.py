"""Public report production and deterministic PDF verification."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageStat

from .workflow import _case_file, load_case


TEX_TEMPLATE = r"""% !TEX program = xelatex
\documentclass[11pt,a4paper,UTF8]{ctexart}
\usepackage[margin=1.85cm,headheight=15pt]{geometry}
\usepackage{amsmath,amssymb,mathtools}
\usepackage{enumitem}
\usepackage{fancyhdr}
\usepackage{microtype}
\setlength{\parindent}{2em}
\setlength{\parskip}{0.35em}
\linespread{1.14}
\setcounter{secnumdepth}{0}
\providecommand{\tightlist}{%
  \setlength{\itemsep}{0pt}\setlength{\parskip}{0pt}}
\setlist[itemize]{leftmargin=2em,itemsep=0.2em,topsep=0.2em}
\setlist[enumerate]{leftmargin=2.4em,itemsep=0.25em,topsep=0.2em}
\pagestyle{fancy}
\fancyhf{}
\lhead{学生解答审查}
\rhead{@@TITLE@@}
\cfoot{\thepage}
\renewcommand{\headrulewidth}{0.4pt}
\begin{document}
\begin{center}
{\Large\bfseries @@TITLE@@\par}
\vspace{0.35em}
{\small 结论、缺口定位与最小修补}
\end{center}

@@BODY@@

\end{document}
"""


def _public_markdown(audit_path: Path) -> str:
    lines = audit_path.read_text(encoding="utf-8").splitlines()
    blocked = ("qwen", "ocr", "视觉识别", "模型调用", "内部记录")
    return "\n".join(
        line
        for line in lines
        if not any(token in line.lower() for token in blocked)
    ) + "\n"


def _pandoc_to_latex(markdown: str) -> str:
    lines = markdown.splitlines()
    normalized: list[str] = []
    removed_title = False
    for line in lines:
        if not removed_title and line.startswith("# "):
            removed_title = True
            continue
        heading = re.match(r"^(#{2,})\s+(.*)$", line)
        if heading:
            line = "#" * (len(heading.group(1)) - 1) + " " + heading.group(2)
        normalized.append(line)
    try:
        result = subprocess.run(
            ["pandoc", "-f", "gfm+tex_math_dollars", "-t", "latex"],
            input="\n".join(normalized) + "\n",
            text=True,
            capture_output=True,
            check=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("未找到 Pandoc；请先安装 pandoc。") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"Pandoc 转换失败：{exc.stderr.strip()}") from exc
    return result.stdout


def _escape_title(title: str) -> str:
    return title.replace("&", r"\&").replace("%", r"\%").replace("_", r"\_")


def build_report(case_dir: Path, allow_draft: bool = False) -> Path:
    metadata = load_case(case_dir)
    audit = case_dir / "audit.md"
    if not audit.is_file():
        raise RuntimeError(f"找不到审查稿：{audit}")
    audit_text = audit.read_text(encoding="utf-8")
    if "待填写" in audit_text and not allow_draft:
        raise RuntimeError("审查稿仍包含“待填写”。完成数学审查后再生成正式 PDF，或使用 --draft。")

    report_dir = case_dir / "report"
    build_dir = report_dir / "build"
    build_dir.mkdir(parents=True, exist_ok=True)
    body = _pandoc_to_latex(_public_markdown(audit))
    tex = TEX_TEMPLATE.replace("@@TITLE@@", _escape_title(str(metadata["title"]))).replace("@@BODY@@", body)
    tex_path = build_dir / "review.tex"
    tex_path.write_text(tex, encoding="utf-8")
    try:
        subprocess.run(
            ["latexmk", "-xelatex", "-interaction=nonstopmode", "-halt-on-error", "review.tex"],
            cwd=build_dir,
            text=True,
            capture_output=True,
            check=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("未找到 latexmk；请安装 XeLaTeX/latexmk。") from exc
    except subprocess.CalledProcessError as exc:
        tail = (exc.stdout + "\n" + exc.stderr)[-3000:]
        raise RuntimeError(f"XeLaTeX 编译失败：\n{tail}") from exc

    pdf = build_dir / "review.pdf"
    target = report_dir / "学生解答审查.pdf"
    shutil.copy2(pdf, target)
    metadata["stages"]["audit"] = "completed" if not allow_draft else "draft"
    metadata["stages"]["report"] = "draft" if allow_draft else "completed"
    metadata["report"] = {"file": str(target.relative_to(case_dir))}
    _case_file(case_dir).write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def _render_pdf(pdf: Path, rendered: Path) -> list[Path]:
    rendered.mkdir(parents=True, exist_ok=True)
    prefix = rendered / "page"
    try:
        subprocess.run(
            ["pdftoppm", "-r", "160", "-png", str(pdf), str(prefix)],
            text=True,
            capture_output=True,
            check=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("未找到 pdftoppm；请安装 Poppler。") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"PDF 渲染失败：{exc.stderr.strip()}") from exc
    pages = sorted(rendered.glob("page-*.png"))
    if not pages:
        raise RuntimeError("PDF 渲染后没有生成页面。")
    return pages


def verify_report(case_dir: Path, vision_check: bool = False) -> Path:
    from .qwen import vision

    pdf = case_dir / "report" / "学生解答审查.pdf"
    if not pdf.is_file():
        raise RuntimeError("请先生成 PDF，再进行核验。")
    rendered = case_dir / "internal" / "rendered"
    pages = _render_pdf(pdf, rendered)
    checks = []
    for page in pages:
        with Image.open(page).convert("L") as image:
            stat = ImageStat.Stat(image)
            nonwhite_ratio = sum(pixel < 245 for pixel in image.getdata()) / (image.width * image.height)
            checks.append(
                {"page": page.name, "width": image.width, "height": image.height, "mean_gray": round(stat.mean[0], 2), "nonwhite_ratio": round(nonwhite_ratio, 5)}
            )
    failures = [item for item in checks if item["nonwhite_ratio"] < 0.001]
    qa_lines = ["# PDF 核验", "", "## 机械检查", ""]
    for item in checks:
        qa_lines.append(f"- {item['page']}：{item['width']}x{item['height']}，非白像素比例 {item['nonwhite_ratio']}")
    if failures:
        raise RuntimeError(f"存在近乎空白的页面：{failures}")
    qa_lines.append("- 结果：通过。PDF 可渲染，且每页均含有效内容。")

    if vision_check:
        qa_lines.extend(["", "## 页面版式复核", ""])
        prompt = (
            "只检查这页数学评审 PDF 的版式，不审查数学内容。检查文字公式重叠、裁切、"
            "中文和符号可读性、页边距、标题和段落间距。先写合格或不合格，再列问题。"
            "不要提及模型、识别工具或 OCR。"
        )
        for page in pages:
            qa_lines.append(f"### {page.name}\n")
            qa_lines.append(vision([page], prompt, max_tokens=1200))
    qa_path = case_dir / "internal" / "pdf_qa.md"
    qa_path.write_text("\n".join(qa_lines) + "\n", encoding="utf-8")

    metadata = load_case(case_dir)
    metadata["stages"]["verification"] = "completed"
    metadata["verification"] = {"file": str(qa_path.relative_to(case_dir)), "vision_layout_check": vision_check}
    _case_file(case_dir).write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return qa_path


def deliver_report(case_dir: Path, destination: Path) -> Path:
    pdf = case_dir / "report" / "学生解答审查.pdf"
    if not pdf.is_file():
        raise RuntimeError("请先生成 PDF。")
    destination = destination.expanduser().resolve()
    if not destination.is_dir():
        raise RuntimeError(f"目标目录不存在：{destination}")
    title = str(load_case(case_dir)["title"]).replace("/", "-")
    target = destination / f"{title}.pdf"
    shutil.copy2(pdf, target)
    return target
