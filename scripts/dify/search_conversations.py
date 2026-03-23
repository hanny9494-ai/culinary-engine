#!/usr/bin/env python3
"""
Search conversation history in Dify KB.

Usage:
    python3 scripts/dify/search_conversations.py "为什么选flash不选MinerU"
    python3 scripts/dify/search_conversations.py "Weaviate被去掉的原因"
    python3 scripts/dify/search_conversations.py --batch  # run all extraction queries
"""

import json
import sys
import base64
import argparse
import requests
from pathlib import Path

DIFY_URL = "http://localhost"
EMAIL = "hanny9494@gmail.com"
PASSWORD = "Jeffery96352101"
DATASET_ID = "43a926e2-666f-4234-8eb9-c29ccca63916"


def login():
    s = requests.Session()
    s.trust_env = False
    pwd = base64.b64encode(PASSWORD.encode()).decode()
    s.post(f"{DIFY_URL}/console/api/login",
           headers={"Content-Type": "application/json"},
           json={"email": EMAIL, "password": pwd})
    s.headers["X-CSRF-Token"] = s.cookies.get("csrf_token")
    s.headers["Content-Type"] = "application/json"
    return s


def search(s, query, top_k=5):
    """Search the conversation history KB."""
    r = s.get(f"{DIFY_URL}/console/api/datasets/{DATASET_ID}/hit-testing",
              params={"query": query, "top_k": top_k})
    if r.status_code != 200:
        # Try POST
        r = s.post(f"{DIFY_URL}/console/api/datasets/{DATASET_ID}/hit-testing",
                   json={"query": query, "retrieval_model": {
                       "search_method": "hybrid_search",
                       "reranking_enable": False,
                       "top_k": top_k,
                       "score_threshold_enabled": False,
                   }})
    r.raise_for_status()
    return r.json()


def format_results(results, query):
    records = results.get("records", results.get("data", []))
    print(f"\n{'='*60}")
    print(f"Query: {query}")
    print(f"Results: {len(records)}")
    print(f"{'='*60}")

    for i, rec in enumerate(records):
        segment = rec.get("segment", rec) if isinstance(rec, dict) else rec
        content = segment.get("content", str(segment))
        score = rec.get("score", segment.get("score", "?"))
        doc_name = segment.get("document", {}).get("name", "?") if isinstance(segment.get("document"), dict) else "?"
        print(f"\n--- Result {i+1} (score: {score}) [{doc_name}] ---")
        # Show first 500 chars
        print(content[:500])
        if len(content) > 500:
            print(f"... ({len(content)} chars)")


# Batch extraction queries for memory building
MEMORY_QUERIES = [
    "为什么从MinerU换到qwen3.5-flash做OCR",
    "为什么去掉Weaviate改用Neo4j内置向量",
    "为什么不用Dify做产品层",
    "为什么选LangGraph不选其他agent框架",
    "为什么新书不再跑Stage2和Stage3",
    "Stage4设计的原因和过程",
    "Ollama并发出过什么问题",
    "trust_env和代理相关的bug",
    "17域是怎么确定的",
    "qwen3.5 2b切分替代Chonkie的原因",
    "Jeff对代码风格的要求和偏好",
    "Jeff否决过什么方案",
    "食谱schema v2的设计过程",
    "Graphiti做动态记忆的决策",
    "Stage3B因果链增强的效果",
    "成本控制和API费用讨论",
    "粤菜审美和L6翻译层的讨论",
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("query", nargs="?", help="Search query")
    parser.add_argument("--batch", action="store_true", help="Run all memory extraction queries")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--output", help="Save results to file")
    args = parser.parse_args()

    s = login()

    if args.batch:
        queries = MEMORY_QUERIES
    elif args.query:
        queries = [args.query]
    else:
        print("Usage: search_conversations.py 'query' or --batch")
        return

    all_results = {}
    for q in queries:
        try:
            results = search(s, q, top_k=args.top_k)
            format_results(results, q)
            all_results[q] = results
        except Exception as e:
            print(f"\n⚠ Query failed: {q} → {e}")

    if args.output:
        Path(args.output).write_text(
            json.dumps(all_results, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8")
        print(f"\nResults saved to {args.output}")


if __name__ == "__main__":
    main()
