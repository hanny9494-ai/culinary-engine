#!/usr/bin/env python3
"""
将 Claude 网页版导出的 conversations.json 转换并导入 Dify KB。

处理逻辑：
1. 只导入项目相关对话（关键词过滤）
2. 按对话拆分为独立 markdown 文档
3. 每个对话按消息轮次分段
4. 上传到 Dify conversation-history KB

Usage:
    python3 scripts/dify/import_conversations.py
"""

import json
import time
import base64
import requests
from pathlib import Path
from datetime import datetime

# ============================================================
# Config
# ============================================================
DIFY_URL = "http://localhost"
EMAIL = "hanny9494@gmail.com"
PASSWORD = "Jeffery96352101"

CONV_FILE = Path.home() / "l0-knowledge-engine/data/conversation_history/conversations.json"
DATASET_ID = "43a926e2-666f-4234-8eb9-c29ccca63916"  # conversation-history KB

# Output dir for converted markdown files
OUTPUT_DIR = Path.home() / "l0-knowledge-engine/data/conversation_history/converted"

# Conversations with these keywords in name are project-related
PROJECT_KEYWORDS = [
    "culinary", "餐饮", "研发", "stage", "pipeline", "l0", "ocr",
    "蒸馏", "切分", "chunk", "neo4j", "dify", "食谱", "recipe",
    "knowledge", "引擎", "engine", "原理", "domain", "域",
    "book", "书", "batch", "codex", "agent", "烹饪", "科学",
    "母对话", "子对话", "厨艺", "sensory", "pdf", "视觉",
    "问题驱动", "架构", "handover", "厨师",
]

# Also include by minimum message count (long conversations are likely important)
MIN_MSGS_FOR_AUTO_INCLUDE = 100


def login_dify():
    s = requests.Session()
    s.trust_env = False
    pwd = base64.b64encode(PASSWORD.encode()).decode()
    s.post(f"{DIFY_URL}/console/api/login",
           headers={"Content-Type": "application/json"},
           json={"email": EMAIL, "password": pwd})
    s.headers["X-CSRF-Token"] = s.cookies.get("csrf_token")
    s.headers["Content-Type"] = "application/json"
    return s


def is_project_related(conv):
    name = (conv.get("name") or "").lower()
    msgs = conv.get("chat_messages", [])

    # Keyword match on name
    if any(kw in name for kw in PROJECT_KEYWORDS):
        return True

    # Long conversations are likely project work
    if len(msgs) >= MIN_MSGS_FOR_AUTO_INCLUDE:
        return True

    return False


def extract_message_text(msg):
    """Extract text content from a chat message."""
    content = msg.get("content", msg.get("text", ""))

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                # Claude export: blocks have 'text' field for text content
                text = block.get("text", "")
                if isinstance(text, str) and text.strip():
                    parts.append(text)
                # Some blocks have nested 'content' which can be list
                inner = block.get("content", "")
                if isinstance(inner, str) and inner.strip():
                    parts.append(inner)
                elif isinstance(inner, list):
                    for item in inner:
                        if isinstance(item, str):
                            parts.append(item)
                        elif isinstance(item, dict):
                            t = item.get("text", "")
                            if isinstance(t, str) and t.strip():
                                parts.append(t)
        return "\n".join(parts)

    return str(content)


def conv_to_markdown(conv):
    """Convert a conversation to markdown format."""
    name = conv.get("name", "Untitled")
    created = conv.get("created_at", "")[:10]
    updated = conv.get("updated_at", "")[:10]
    summary = conv.get("summary", "")
    msgs = conv.get("chat_messages", [])

    lines = []
    lines.append(f"# {name}")
    lines.append(f"")
    lines.append(f"- Created: {created}")
    lines.append(f"- Updated: {updated}")
    lines.append(f"- Messages: {len(msgs)}")
    if summary:
        lines.append(f"- Summary: {summary}")
    lines.append(f"")
    lines.append(f"---")
    lines.append(f"")

    for i, msg in enumerate(msgs):
        sender = msg.get("sender", msg.get("role", "unknown"))
        text = extract_message_text(msg)

        if not text.strip():
            continue

        if sender in ("human", "user"):
            lines.append(f"## Human ({i+1})")
        else:
            lines.append(f"## Assistant ({i+1})")

        lines.append(f"")

        # Truncate very long messages to keep KB manageable
        if len(text) > 5000:
            lines.append(text[:5000])
            lines.append(f"\n... (truncated, {len(text)} chars total)")
        else:
            lines.append(text)

        lines.append(f"")

    return "\n".join(lines)


def upload_to_dify(s, dataset_id, filepath):
    """Upload a markdown file to Dify KB."""
    csrf = s.headers.get("X-CSRF-Token", "")

    # Step 1: Upload file
    with open(filepath, "rb") as f:
        r = s.post(f"{DIFY_URL}/console/api/files/upload",
                   headers={"X-CSRF-Token": csrf, "Content-Type": None},
                   files={"file": (filepath.name, f, "text/markdown")},
                   data={"source": "datasets"})
    if r.status_code not in (200, 201):
        print(f"    Upload failed: {r.status_code} {r.text[:200]}")
        return None
    file_id = r.json()["id"]

    # Step 2: Create document
    s.headers["Content-Type"] = "application/json"
    payload = {
        "indexing_technique": "high_quality",
        "process_rule": {
            "mode": "custom",
            "rules": {
                "pre_processing_rules": [
                    {"id": "remove_extra_spaces", "enabled": True},
                    {"id": "remove_urls_emails", "enabled": False}
                ],
                "segmentation": {
                    "separator": "\n## ",
                    "max_tokens": 1500,
                    "chunk_overlap": 200,
                }
            }
        },
        "data_source": {
            "type": "upload_file",
            "info_list": {
                "data_source_type": "upload_file",
                "file_info_list": {"file_ids": [file_id]}
            }
        },
        "doc_form": "text_model",
        "doc_language": "Chinese",
    }
    r2 = s.post(f"{DIFY_URL}/console/api/datasets/{dataset_id}/documents", json=payload)
    if r2.status_code != 200:
        print(f"    Doc create failed: {r2.status_code} {r2.text[:200]}")
        return None

    docs = r2.json().get("documents", [])
    return docs[0]["id"] if docs else None


def main():
    print("=" * 60)
    print("Import conversation history to Dify KB")
    print("=" * 60)

    # Load conversations
    with open(CONV_FILE) as f:
        conversations = json.load(f)
    print(f"Total conversations: {len(conversations)}")

    # Filter project-related
    project_convos = [c for c in conversations if is_project_related(c)]
    project_convos.sort(key=lambda c: len(c.get("chat_messages", [])), reverse=True)
    print(f"Project-related: {len(project_convos)}")

    # Convert to markdown
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    converted = []
    for conv in project_convos:
        msgs = conv.get("chat_messages", [])
        if len(msgs) == 0:
            continue

        name = conv.get("name", "Untitled")
        created = conv.get("created_at", "")[:10].replace("-", "")
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name[:40])
        filename = f"{created}_{safe_name}.md"

        md = conv_to_markdown(conv)
        filepath = OUTPUT_DIR / filename
        filepath.write_text(md, encoding="utf-8")

        size_kb = len(md.encode()) / 1024
        converted.append((filepath, name, len(msgs), size_kb))
        print(f"  ✓ {filename} ({len(msgs)} msgs, {size_kb:.0f}KB)")

    print(f"\nConverted {len(converted)} files to {OUTPUT_DIR}")

    # Upload to Dify
    print(f"\nUploading to Dify KB {DATASET_ID[:8]}...")
    s = login_dify()
    print("✓ Logged in")

    uploaded = 0
    failed = 0
    for filepath, name, msg_count, size_kb in converted:
        print(f"  Uploading: {filepath.name} ...", end=" ", flush=True)
        doc_id = upload_to_dify(s, DATASET_ID, filepath)
        if doc_id:
            print(f"✓ {doc_id[:8]}")
            uploaded += 1
        else:
            print("✗")
            failed += 1
        # Small delay to avoid rate limiting
        time.sleep(1)

    print(f"\n{'=' * 60}")
    print(f"Done: {uploaded} uploaded, {failed} failed")
    print(f"KB: {DIFY_URL} → Knowledge → conversation-history")
    print(f"Wait for indexing to complete before querying.")


if __name__ == "__main__":
    main()
