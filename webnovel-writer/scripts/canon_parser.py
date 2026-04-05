#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
原作 TXT 解析器（同人模式）

功能：
- 读取原作 TXT 文件，自动检测编码
- 识别章节结构（支持常见中文网文章节格式）
- 创建 .webnovel/canon/ 目录结构
- 生成 source_meta.json（原作元信息）
- 生成 Canon 模板骨架文件（供 AI 在 /webnovel-init 同人流程中填充）
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

from runtime_compat import enable_windows_utf8_stdio
from security_utils import atomic_write_json

if sys.platform == "win32":
    enable_windows_utf8_stdio()


# ---------------------------------------------------------------------------
# 章节识别
# ---------------------------------------------------------------------------

# 中文数字映射
_CN_DIGITS = {
    "零": 0, "〇": 0, "一": 1, "二": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
    "百": 100, "千": 1000, "万": 10000,
}

# 章节标题正则（按优先级排列）
_CHAPTER_PATTERNS = [
    # 第X章 / 第X回 / 第X节 (支持中文数字和阿拉伯数字)
    re.compile(
        r"^\s*第\s*([零〇一二三四五六七八九十百千万\d]+)\s*[章回节话]\s*(.*)",
        re.UNICODE,
    ),
    # Chapter X / CHAPTER X
    re.compile(r"^\s*[Cc]hapter\s+(\d+)\s*(.*)", re.UNICODE),
    # 纯数字开头：001. / 001、/ 001：
    re.compile(r"^\s*(\d{1,4})\s*[.、：:]\s*(.*)", re.UNICODE),
]


def _cn_to_int(s: str) -> int:
    """将中文数字字符串转为整数（简化实现，覆盖常见情况）。"""
    if s.isdigit():
        return int(s)
    result = 0
    current = 0
    for ch in s:
        val = _CN_DIGITS.get(ch)
        if val is None:
            continue
        if val >= 10:
            if current == 0:
                current = 1
            current *= val
            if val >= 10000:
                result += current
                current = 0
        else:
            current = val
    result += current
    return result if result > 0 else 0


def _detect_encoding(file_path: Path) -> str:
    """尝试检测文件编码：优先 UTF-8，回退 GBK。"""
    for enc in ("utf-8", "utf-8-sig", "gbk", "gb18030", "big5"):
        try:
            file_path.read_text(encoding=enc)
            return enc
        except (UnicodeDecodeError, LookupError):
            continue
    return "utf-8"


def _split_chapters(lines: list[str]) -> list[dict]:
    """将文本行拆分为章节列表。"""
    chapters: list[dict] = []
    current_chapter: dict | None = None

    for line_no, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            if current_chapter is not None:
                current_chapter["lines"].append(line)
            continue

        matched = False
        for pattern in _CHAPTER_PATTERNS:
            m = pattern.match(stripped)
            if m:
                chapter_num_raw = m.group(1)
                chapter_title = m.group(2).strip() if m.group(2) else ""
                chapter_num = _cn_to_int(chapter_num_raw)

                if current_chapter is not None:
                    chapters.append(current_chapter)

                current_chapter = {
                    "number": chapter_num,
                    "number_raw": chapter_num_raw,
                    "title": chapter_title,
                    "start_line": line_no + 1,
                    "lines": [line],
                }
                matched = True
                break

        if not matched and current_chapter is not None:
            current_chapter["lines"].append(line)
        elif not matched and current_chapter is None:
            # 章节前的内容（如简介/序言）
            if chapters or any(line.strip() for line in lines[:line_no]):
                if not chapters or chapters[0].get("number") != 0:
                    current_chapter = {
                        "number": 0,
                        "number_raw": "0",
                        "title": "序章/简介",
                        "start_line": 1,
                        "lines": [line],
                    }

    if current_chapter is not None:
        chapters.append(current_chapter)

    return chapters


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def parse_canon(
    source_path: str,
    project_dir: str,
    *,
    source_title: str = "",
    encoding: str = "",
) -> None:
    src = Path(source_path).expanduser().resolve()
    if not src.exists():
        raise SystemExit(f"原作文件不存在: {src}")

    project_path = Path(project_dir).expanduser().resolve()

    # 检测编码
    enc = encoding or _detect_encoding(src)
    print(f"使用编码: {enc}")

    text = src.read_text(encoding=enc)
    lines = text.splitlines()
    total_chars = len(text)

    print(f"文件总字符数: {total_chars:,}")
    print(f"文件总行数: {len(lines):,}")

    # 拆分章节
    chapters = _split_chapters(lines)
    print(f"识别到章节数: {len(chapters)}")

    if not chapters:
        # 无法识别章节，将整个文件作为一个块
        chapters = [{
            "number": 1,
            "number_raw": "1",
            "title": "全文",
            "start_line": 1,
            "lines": lines,
        }]
        print("未识别到章节标记，将全文作为单一块处理。")

    # 创建目录结构
    canon_dir = project_path / ".webnovel" / "canon"
    for sub in ("characters", "source_chapters"):
        (canon_dir / sub).mkdir(parents=True, exist_ok=True)

    # 生成 source_meta.json
    chapter_list = []
    for ch in chapters:
        content = "\n".join(ch["lines"])
        chapter_list.append({
            "number": ch["number"],
            "number_raw": ch["number_raw"],
            "title": ch["title"],
            "char_count": len(content),
            "start_line": ch["start_line"],
        })

    meta = {
        "source_title": source_title or src.stem,
        "source_file": str(src),
        "encoding": enc,
        "total_chapters": len(chapters),
        "total_chars": total_chars,
        "total_lines": len(lines),
        "parsed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "chapter_list": chapter_list,
    }

    meta_path = canon_dir / "source_meta.json"
    atomic_write_json(meta_path, meta, use_lock=False, backup=False)
    print(f"已生成: {meta_path}")

    # 生成 Canon 骨架模板
    title = source_title or src.stem

    _write_if_missing(
        canon_dir / "world.md",
        f"# {title} - 原作世界观\n\n"
        "> 由 AI 解析原作 TXT 后填充。\n\n"
        "## 世界结构\n\n"
        "## 势力格局\n\n"
        "## 社会规则\n\n"
        "## 地理版图\n\n"
        "## 核心规则/禁忌\n",
    )

    _write_if_missing(
        canon_dir / "power_system.md",
        f"# {title} - 原作力量体系\n\n"
        "> 由 AI 解析原作 TXT 后填充。\n\n"
        "## 体系名称\n\n"
        "## 等级划分（从低到高）\n\n"
        "## 突破条件/规则\n\n"
        "## 能力获取方式\n\n"
        "## 硬限制\n",
    )

    _write_if_missing(
        canon_dir / "relationships.md",
        f"# {title} - 原作关系网络\n\n"
        "> 由 AI 解析原作 TXT 后填充。\n\n"
        "## 主要关系\n\n"
        "## 阵营划分\n\n"
        "## 关键冲突关系\n",
    )

    _write_if_missing(
        canon_dir / "timeline.md",
        f"# {title} - 原作时间线\n\n"
        "> 由 AI 解析原作 TXT 后填充。\n\n"
        "## 关键事件\n\n"
        "## 主线剧情节点\n",
    )

    # 统计与输出
    print(f"\nCanon 解析完成:")
    print(f"  原作: {title}")
    print(f"  章节: {len(chapters)}")
    print(f"  总字符: {total_chars:,}")
    print(f"  输出目录: {canon_dir}")
    print(f"\n生成文件:")
    print(f"  - {meta_path.relative_to(project_path)}")
    print(f"  - .webnovel/canon/world.md")
    print(f"  - .webnovel/canon/power_system.md")
    print(f"  - .webnovel/canon/relationships.md")
    print(f"  - .webnovel/canon/timeline.md")
    print(f"  - .webnovel/canon/characters/ (待 AI 填充)")


def _write_if_missing(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return
    path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="原作 TXT 解析器（同人模式）——解析原作文件，提取章节结构，生成 Canon 资料骨架。"
    )
    parser.add_argument("source_txt", help="原作 TXT 文件路径")
    parser.add_argument("project_dir", help="项目目录")
    parser.add_argument("--source-title", default="", help="原作名称（默认使用文件名）")
    parser.add_argument(
        "--encoding", default="",
        help="指定编码（默认自动检测，支持 utf-8/gbk/gb18030/big5）",
    )

    args = parser.parse_args()
    parse_canon(
        args.source_txt,
        args.project_dir,
        source_title=args.source_title,
        encoding=args.encoding,
    )


if __name__ == "__main__":
    main()
