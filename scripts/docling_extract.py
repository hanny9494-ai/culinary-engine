#!/usr/bin/env python3
"""Docling一站式提取+切分试跑。"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from docling.chunking import HybridChunker
from docling.document_converter import DocumentConverter


def to_jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_jsonable(v) for v in value]
    if hasattr(value, "model_dump"):
        try:
            return to_jsonable(value.model_dump(mode="json"))
        except TypeError:
            return to_jsonable(value.model_dump())
    if hasattr(value, "export_to_dict"):
        return to_jsonable(value.export_to_dict())
    if hasattr(value, "__dict__"):
        return to_jsonable(vars(value))
    return str(value)


def export_markdown(doc: Any) -> str:
    if hasattr(doc, "export_to_markdown"):
        return doc.export_to_markdown()
    raise RuntimeError("Docling document does not support export_to_markdown()")


def export_structure(doc: Any) -> Any:
    if hasattr(doc, "export_to_dict"):
        return doc.export_to_dict()
    if hasattr(doc, "model_dump"):
        try:
            return doc.model_dump(mode="json")
        except TypeError:
            return doc.model_dump()
    return to_jsonable(doc)


def get_chunk_text(chunk: Any) -> str:
    for attr in ("text", "content"):
        value = getattr(chunk, attr, None)
        if isinstance(value, str) and value.strip():
            return value
    if hasattr(chunk, "export_json_dict"):
        try:
            payload = chunk.export_json_dict()
            text = payload.get("text")
            if isinstance(text, str) and text.strip():
                return text
        except Exception:
            pass
    return str(chunk)


def get_chunk_page(chunk: Any) -> int | None:
    prov = getattr(chunk, "prov", None) or []
    if not prov:
        return None
    first = prov[0]
    for attr in ("page_no", "page", "page_num"):
        value = getattr(first, attr, None)
        if isinstance(value, int):
            return value + 1 if attr == "page_no" else value
    return None


def get_chunk_label(chunk: Any) -> str:
    for attr in ("label", "kind", "type"):
        value = getattr(chunk, attr, None)
        if isinstance(value, str) and value:
            return value
    return "unknown"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Docling extraction and HybridChunker on one PDF.")
    parser.add_argument("pdf_path", help="Source PDF path")
    parser.add_argument("output_dir", help="Directory for markdown/JSON/chunk outputs")
    parser.add_argument("--book-id", default="bread_science_yoshino", help="Book id to stamp into chunk metadata")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    pdf_path = Path(args.pdf_path).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"[1/3] Docling提取: {pdf_path}")
    start = time.time()
    converter = DocumentConverter()
    result = converter.convert(str(pdf_path))
    doc = result.document
    extract_time = time.time() - start
    print(f"  提取完成: {extract_time:.1f}秒")

    md_path = output_dir / "docling_merged.md"
    md_path.write_text(export_markdown(doc), encoding="utf-8")
    print(f"  Markdown导出: {md_path}")

    json_path = output_dir / "docling_structure.json"
    json_path.write_text(
        json.dumps(to_jsonable(export_structure(doc)), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"  结构JSON导出: {json_path}")

    print("\n[2/3] HybridChunker切分")
    start2 = time.time()
    chunker = HybridChunker()
    chunks = list(chunker.chunk(doc))
    chunk_time = time.time() - start2
    print(f"  切分完成: {len(chunks)}个chunks, {chunk_time:.1f}秒")

    print("\n[3/3] 转换为标准格式")
    standard_chunks: list[dict[str, Any]] = []
    for i, chunk in enumerate(chunks):
        standard_chunks.append(
            {
                "chunk_idx": i,
                "full_text": get_chunk_text(chunk),
                "page_num": get_chunk_page(chunk),
                "source_book": args.book_id,
                "element_type": get_chunk_label(chunk),
                "meta": to_jsonable(getattr(chunk, "meta", {})),
            }
        )

    chunks_path = output_dir / "chunks_docling.json"
    chunks_path.write_text(json.dumps(standard_chunks, ensure_ascii=False, indent=2), encoding="utf-8")

    lengths = [len(c["full_text"]) for c in standard_chunks]
    short = sum(1 for l in lengths if l < 50)
    avg_len = sum(lengths) / len(lengths) if lengths else 0
    median_len = sorted(lengths)[len(lengths) // 2] if lengths else 0
    min_len = min(lengths) if lengths else 0
    max_len = max(lengths) if lengths else 0

    print("\n=== 质量报告 ===")
    print(f"总chunks: {len(standard_chunks)}")
    print(f"平均长度: {avg_len:.0f}字符")
    print(f"中位长度: {median_len}字符")
    print(f"最短: {min_len}字符")
    print(f"最长: {max_len}字符")
    print(f"短块(<50字符): {short} ({(short / len(standard_chunks) * 100 if standard_chunks else 0):.1f}%)")
    print(f"提取耗时: {extract_time:.1f}秒")
    print(f"切分耗时: {chunk_time:.1f}秒")
    print(f"总耗时: {extract_time + chunk_time:.1f}秒")
    print("\n输出文件:")
    print(f"  Markdown: {md_path}")
    print(f"  结构JSON: {json_path}")
    print(f"  Chunks: {chunks_path}")


if __name__ == "__main__":
    main()
