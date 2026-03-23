#!/usr/bin/env python3
"""
LLM Router — 统一模型调用层，根据任务类型自动路由到最优 LLM。

所有 pipeline 脚本和 orchestrator 通过此模块调用模型，不再直接硬编码 API。

功能：
- 根据 task_type 自动选择模型
- Ollama 忙时自动降级到 API
- 统一 token 计费和成本追踪
- 限流控制（Ollama 串行、API 并发上限）
- 故障转移

Usage:
    from llm_router import LLMRouter
    router = LLMRouter()
    result = router.call("stage4_filter", prompt, system_prompt)
    # router 自动决定用 27b 本地还是 flash API

    # 或 CLI
    python3 scripts/dify/llm_router.py --status        # 查看路由表和成本
    python3 scripts/dify/llm_router.py --test           # 测试所有模型
"""

import json
import os
import time
import threading
import sqlite3
import argparse
from pathlib import Path
from datetime import datetime

# ============================================================
# Model Registry
# ============================================================

MODELS = {
    # Ollama 本地模型
    "ollama:qwen3.5:2b": {
        "provider": "ollama",
        "endpoint": "http://localhost:11434/api/generate",
        "model_id": "qwen3.5:2b",
        "cost_per_1m_input": 0,
        "cost_per_1m_output": 0,
        "max_concurrent": 1,
        "trust_env": False,
    },
    "ollama:qwen3.5:9b": {
        "provider": "ollama",
        "endpoint": "http://localhost:11434/api/generate",
        "model_id": "qwen3.5:9b",
        "cost_per_1m_input": 0,
        "cost_per_1m_output": 0,
        "max_concurrent": 1,
        "trust_env": False,
    },
    "ollama:qwen3.5:27b": {
        "provider": "ollama",
        "endpoint": "http://localhost:11434/api/generate",
        "model_id": "qwen3.5:27b",
        "cost_per_1m_input": 0,
        "cost_per_1m_output": 0,
        "max_concurrent": 1,
        "trust_env": False,
    },
    # DashScope API
    "dashscope:qwen3.5-flash": {
        "provider": "dashscope",
        "endpoint": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        "model_id": "qwen3.5-flash",
        "api_key_env": "DASHSCOPE_API_KEY",
        "cost_per_1m_input": 0.2,   # ¥
        "cost_per_1m_output": 0.6,
        "max_concurrent": 5,
        "trust_env": False,
    },
    "dashscope:qwen3.5-plus": {
        "provider": "dashscope",
        "endpoint": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        "model_id": "qwen3.5-plus",
        "api_key_env": "DASHSCOPE_API_KEY",
        "cost_per_1m_input": 0.8,
        "cost_per_1m_output": 2.0,
        "max_concurrent": 5,
        "trust_env": False,
    },
    # 灵雅代理 (Claude)
    "lingya:claude-opus-4-6": {
        "provider": "lingya",
        "endpoint": "${L0_API_ENDPOINT}/v1/chat/completions",
        "model_id": "claude-opus-4-6",
        "api_key_env": "L0_API_KEY",
        "cost_per_1m_input": 5.0,
        "cost_per_1m_output": 25.0,
        "max_concurrent": 1,
        "trust_env": False,
    },
    "lingya:claude-sonnet-4-6": {
        "provider": "lingya",
        "endpoint": "${L0_API_ENDPOINT}/v1/chat/completions",
        "model_id": "claude-sonnet-4-6",
        "api_key_env": "L0_API_KEY",
        "cost_per_1m_input": 1.5,
        "cost_per_1m_output": 7.5,
        "max_concurrent": 2,
        "trust_env": False,
    },
}

# ============================================================
# Routing Table: task_type → preferred model → fallback
# ============================================================

ROUTES = {
    # Stage1
    "stage1_split": {
        "preferred": "ollama:qwen3.5:2b",
        "fallback": None,  # 2b 没有 API 替代，必须等 Ollama
        "reason": "切分必须用 2b，无 API 替代",
    },
    "stage1_annotate": {
        "preferred": "ollama:qwen3.5:9b",
        "fallback": None,
        "reason": "标注必须用 9b，无 API 替代",
    },
    # Stage4
    "stage4_filter": {
        "preferred": "ollama:qwen3.5:27b",
        "fallback": "dashscope:qwen3.5-flash",
        "reason": "预过滤优先本地 27b（免费），Ollama 忙时降级 flash",
    },
    "stage4_extract": {
        "preferred": "lingya:claude-opus-4-6",
        "fallback": None,  # 质量要求高，不降级
        "reason": "核心提取必须 Opus，质量不可降级",
    },
    "stage4_quality": {
        "preferred": "ollama:qwen3.5:27b",
        "fallback": "dashscope:qwen3.5-flash",
        "reason": "质控优先本地 27b，忙时降级 flash",
    },
    # Stage5
    "stage5_recipe": {
        "preferred": "dashscope:qwen3.5-flash",
        "fallback": "ollama:qwen3.5:27b",
        "reason": "食谱提取 flash 够用且快，Ollama 空闲时可用 27b",
    },
    # OCR
    "ocr": {
        "preferred": "dashscope:qwen3.5-flash",
        "fallback": None,
        "reason": "OCR 只能用 DashScope flash",
    },
    # 项目管理（Dify/orchestrator 用）
    "management": {
        "preferred": "dashscope:qwen3.5-flash",
        "fallback": "ollama:qwen3.5:9b",
        "reason": "管理任务用最便宜的 flash",
    },
}


# ============================================================
# Router
# ============================================================

class LLMRouter:
    def __init__(self, db_path=None):
        self.db_path = db_path or Path.home() / "culinary-engine" / "data" / "llm_usage.db"
        self._init_db()
        self._sessions = {}  # provider → requests.Session
        self._locks = {}     # model_key → threading.Semaphore

        for key, model in MODELS.items():
            self._locks[key] = threading.Semaphore(model["max_concurrent"])

    def _init_db(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT DEFAULT (datetime('now')),
                task_type TEXT,
                model_key TEXT,
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                cost_yuan REAL DEFAULT 0,
                latency_ms INTEGER DEFAULT 0,
                status TEXT DEFAULT 'ok',
                book_id TEXT DEFAULT ''
            )
        """)
        conn.commit()
        conn.close()

    def _get_session(self, provider):
        if provider not in self._sessions:
            import requests
            s = requests.Session()
            s.trust_env = False
            self._sessions[provider] = s
        return self._sessions[provider]

    def _is_ollama_available(self):
        try:
            s = self._get_session("ollama")
            r = s.get("http://localhost:11434/api/ps", timeout=2)
            models = r.json().get("models", [])
            return len(models) == 0  # Available if nothing running
        except Exception:
            return False

    def resolve(self, task_type):
        """Resolve task_type to the best available model."""
        route = ROUTES.get(task_type)
        if not route:
            return "dashscope:qwen3.5-flash", f"Unknown task type '{task_type}', using flash"

        preferred = route["preferred"]
        fallback = route.get("fallback")

        # Check if preferred model is available
        model = MODELS[preferred]
        if model["provider"] == "ollama":
            if self._is_ollama_available():
                return preferred, route["reason"]
            elif fallback:
                return fallback, f"Ollama busy → fallback to {fallback}"
            else:
                return preferred, f"Ollama busy but no fallback, must wait"
        else:
            return preferred, route["reason"]

    def call(self, task_type, prompt, system_prompt="", book_id="",
             temperature=0.1, max_tokens=4096):
        """Route and call the appropriate model."""
        model_key, reason = self.resolve(task_type)
        model = MODELS[model_key]

        # Acquire concurrency slot
        self._locks[model_key].acquire()
        start = time.time()

        try:
            if model["provider"] == "ollama":
                result = self._call_ollama(model, prompt, system_prompt,
                                           temperature, max_tokens)
            else:
                result = self._call_openai_compatible(model, prompt, system_prompt,
                                                      temperature, max_tokens)

            latency = int((time.time() - start) * 1000)

            # Log usage
            input_tokens = result.get("input_tokens", 0)
            output_tokens = result.get("output_tokens", 0)
            cost = (input_tokens * model["cost_per_1m_input"] +
                    output_tokens * model["cost_per_1m_output"]) / 1_000_000

            self._log_usage(task_type, model_key, input_tokens, output_tokens,
                            cost, latency, "ok", book_id)

            result["model_key"] = model_key
            result["cost_yuan"] = cost
            result["latency_ms"] = latency
            return result

        except Exception as e:
            latency = int((time.time() - start) * 1000)
            self._log_usage(task_type, model_key, 0, 0, 0, latency,
                            f"error: {str(e)[:100]}", book_id)
            raise
        finally:
            self._locks[model_key].release()

    def _call_ollama(self, model, prompt, system_prompt, temperature, max_tokens):
        s = self._get_session("ollama")
        payload = {
            "model": model["model_id"],
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        if system_prompt:
            payload["system"] = system_prompt

        r = s.post(model["endpoint"], json=payload, timeout=300)
        r.raise_for_status()
        data = r.json()

        return {
            "text": data.get("response", ""),
            "input_tokens": data.get("prompt_eval_count", 0),
            "output_tokens": data.get("eval_count", 0),
        }

    def _call_openai_compatible(self, model, prompt, system_prompt,
                                 temperature, max_tokens):
        s = self._get_session(model["provider"])
        endpoint = model["endpoint"]

        # Resolve env vars in endpoint
        if "${" in endpoint:
            import re
            for m in re.finditer(r'\$\{(\w+)\}', endpoint):
                val = os.environ.get(m.group(1), "")
                endpoint = endpoint.replace(m.group(0), val)

        api_key = os.environ.get(model.get("api_key_env", ""), "")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model["model_id"],
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        r = s.post(endpoint,
                    headers={"Authorization": f"Bearer {api_key}",
                             "Content-Type": "application/json"},
                    json=payload, timeout=300)
        r.raise_for_status()
        data = r.json()

        choice = data.get("choices", [{}])[0]
        usage = data.get("usage", {})

        return {
            "text": choice.get("message", {}).get("content", ""),
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
        }

    def _log_usage(self, task_type, model_key, input_tokens, output_tokens,
                   cost, latency, status, book_id):
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.execute(
                """INSERT INTO usage (task_type, model_key, input_tokens, output_tokens,
                   cost_yuan, latency_ms, status, book_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (task_type, model_key, input_tokens, output_tokens,
                 cost, latency, status, book_id))
            conn.commit()
            conn.close()
        except Exception:
            pass

    # ============================================================
    # Reporting
    # ============================================================

    def get_usage_report(self, days=7):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row

        # By model
        by_model = conn.execute("""
            SELECT model_key,
                   COUNT(*) as calls,
                   SUM(input_tokens) as total_input,
                   SUM(output_tokens) as total_output,
                   SUM(cost_yuan) as total_cost,
                   AVG(latency_ms) as avg_latency
            FROM usage
            WHERE timestamp > datetime('now', ?)
            GROUP BY model_key
        """, (f"-{days} days",)).fetchall()

        # By task type
        by_task = conn.execute("""
            SELECT task_type,
                   COUNT(*) as calls,
                   SUM(cost_yuan) as total_cost
            FROM usage
            WHERE timestamp > datetime('now', ?)
            GROUP BY task_type
        """, (f"-{days} days",)).fetchall()

        # Total
        total = conn.execute("""
            SELECT COUNT(*) as calls,
                   SUM(input_tokens) as total_input,
                   SUM(output_tokens) as total_output,
                   SUM(cost_yuan) as total_cost
            FROM usage
            WHERE timestamp > datetime('now', ?)
        """, (f"-{days} days",)).fetchone()

        conn.close()

        return {
            "period_days": days,
            "by_model": [dict(r) for r in by_model],
            "by_task": [dict(r) for r in by_task],
            "total": dict(total) if total else {},
        }

    def print_status(self):
        ollama_free = self._is_ollama_available()
        print(f"=== LLM Router Status ===")
        print(f"Ollama: {'✅ idle' if ollama_free else '🔄 busy'}")
        print(f"")
        print(f"{'Task Type':<20s} {'Preferred':<25s} {'Fallback':<25s} {'Would Use':<25s}")
        print(f"{'-'*95}")
        for task_type, route in ROUTES.items():
            resolved, reason = self.resolve(task_type)
            fb = route.get('fallback') or '—'
            print(f"{task_type:<20s} {route['preferred']:<25s} "
                  f"{fb:<25s} {resolved:<25s}")

        # Usage report
        report = self.get_usage_report()
        if report["by_model"]:
            print(f"\n=== Usage (last 7 days) ===")
            for m in report["by_model"]:
                print(f"  {m['model_key']:<30s} {m['calls']:>5d} calls  "
                      f"¥{m['total_cost'] or 0:.2f}  "
                      f"avg {m['avg_latency'] or 0:.0f}ms")
            t = report["total"]
            print(f"  {'TOTAL':<30s} {t.get('calls', 0):>5d} calls  "
                  f"¥{t.get('total_cost', 0) or 0:.2f}")


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--status", action="store_true", help="Show routing table and usage")
    parser.add_argument("--test", action="store_true", help="Test all models")
    args = parser.parse_args()

    router = LLMRouter()

    if args.status:
        router.print_status()
    elif args.test:
        print("Testing all models...")
        for task_type in ROUTES:
            model_key, reason = router.resolve(task_type)
            print(f"\n  {task_type} → {model_key} ({reason})")
            if "ollama" in model_key and not router._is_ollama_available():
                print(f"    ⏸ Ollama busy, skip")
                continue
            try:
                result = router.call(task_type, "Say OK", book_id="test")
                print(f"    ✅ \"{result['text'][:30]}\" "
                      f"({result['input_tokens']}+{result['output_tokens']} tokens, "
                      f"¥{result['cost_yuan']:.4f}, {result['latency_ms']}ms)")
            except Exception as e:
                print(f"    ❌ {e}")
    else:
        router.print_status()


if __name__ == "__main__":
    main()
