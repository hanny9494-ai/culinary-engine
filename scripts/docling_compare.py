#!/usr/bin/env python3
"""对比 Docling vs 现有 pipeline。"""

from __future__ import annotations

import json
import re
from pathlib import Path


def pick_first_existing(paths: list[Path]) -> Path:
    for path in paths:
        if path.exists():
            return path
    raise FileNotFoundError("No candidate path exists:\n" + "\n".join(str(p) for p in paths))


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def heading_stats(text: str) -> tuple[list[str], list[str]]:
    headings = re.findall(r"^#{1,3}\s+(.+)$", text, re.MULTILINE)
    garbled = [h for h in headings if any(c in h for c in "¤‡¥§©®™")]
    return headings, garbled


def weird_heading_count(headings: list[str]) -> int:
    count = 0
    for h in headings:
        letters = re.findall(r"[A-Za-z\u4e00-\u9fff]", h)
        if len(letters) < max(2, len(h) // 4):
            count += 1
    return count


def main() -> None:
    repo_output = Path("/Users/jeff/Documents/New project/culinary-engine/output/bread_science_yoshino")
    old_md = pick_first_existing(
        [
            Path.home() / "l0-knowledge-engine/output/bread_science_yoshino/raw_merged.md",
            repo_output / "raw_merged.md",
        ]
    )
    old_toc = pick_first_existing(
        [
            Path.home() / "l0-knowledge-engine/output/bread_science_yoshino/toc_candidate.json",
            repo_output / "toc_candidate.json",
        ]
    )
    new_md = Path.home() / "l0-knowledge-engine/output/bread_science_yoshino/docling_test/docling_merged.md"
    new_chunks = Path.home() / "l0-knowledge-engine/output/bread_science_yoshino/docling_test/chunks_docling.json"
    new_structure = Path.home() / "l0-knowledge-engine/output/bread_science_yoshino/docling_test/docling_structure.json"

    print("=== 现有Pipeline ===")
    print(f"Markdown来源: {old_md}")
    print(f"TOC来源: {old_toc}")
    old_text = load_text(old_md)
    old_headings, old_garbled = heading_stats(old_text)
    print(f"Markdown长度: {len(old_text)}字符")
    print(f"Heading总数: {len(old_headings)}")
    print(f"乱码Heading: {len(old_garbled)}")
    print(f"异常Heading(宽松规则): {weird_heading_count(old_headings)}")
    if old_garbled[:5]:
        print(f"乱码样例: {old_garbled[:5]}")

    print("\n=== Docling ===")
    print(f"Markdown来源: {new_md}")
    print(f"结构JSON: {new_structure}")
    new_text = load_text(new_md)
    new_headings, new_garbled = heading_stats(new_text)
    print(f"Markdown长度: {len(new_text)}字符")
    print(f"Heading总数: {len(new_headings)}")
    print(f"乱码Heading: {len(new_garbled)}")
    print(f"异常Heading(宽松规则): {weird_heading_count(new_headings)}")
    if new_headings[:10]:
        print(f"前10个Heading: {new_headings[:10]}")

    chunks = json.loads(new_chunks.read_text(encoding="utf-8"))
    print(f"\nChunks: {len(chunks)}")
    print("前3个chunk预览:")
    for c in chunks[:3]:
        preview = c["full_text"][:80].replace("\n", " ")
        print(f"  [{c['chunk_idx']}] ({len(c['full_text'])}字符) {preview}...")

    print("\n=== bread_science_yoshino 对比报告 ===")
    print("指标 | 现有Pipeline | Docling")
    print(f"Markdown总长度 | {len(old_text)}字符 | {len(new_text)}字符")
    print(f"Heading总数 | {len(old_headings)} | {len(new_headings)}")
    print(f"乱码Heading | {len(old_garbled)} | {len(new_garbled)}")
    print(f"异常Heading(宽松规则) | {weird_heading_count(old_headings)} | {weird_heading_count(new_headings)}")
    print(f"Chunk数量 | 未切分 | {len(chunks)}")
    print("处理耗时 | ~多步人工+云API | 见 docling_extract.py 运行输出")
    print("依赖 | MinerU云 + qwen-vl云 + merge + 2b | Docling本地")
    print(f"前10个Heading对比:\n现有: {old_headings[:10]}\nDocling: {new_headings[:10]}")

    if len(new_garbled) == 0 and weird_heading_count(new_headings) < weird_heading_count(old_headings):
        verdict = "Docling显著改善了 heading 乱码问题，值得继续扩大试点。"
    elif len(new_garbled) < len(old_garbled):
        verdict = "Docling减少了明显乱码，但还需要继续检查 chunk 边界和正文质量。"
    else:
        verdict = "Docling没有明显解决 heading 乱码问题，暂时不建议替换现有流程。"
    print(f"结论: {verdict}")


if __name__ == "__main__":
    main()
