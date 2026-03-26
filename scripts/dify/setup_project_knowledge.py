#!/usr/bin/env python3
"""
Dify Workflow 1: project-knowledge chatbot
创建 Knowledge Base + 导入文档 + 创建 Chatbot App + 配置 RAG

Usage:
    python3 scripts/dify/setup_project_knowledge.py
"""

import json
import time
import base64
import requests
from pathlib import Path

# ============================================================
# Config
# ============================================================
DIFY_URL = "http://localhost"
EMAIL = "hanny9494@gmail.com"
PASSWORD = "Jeffery96352101"

DATASET_NAME = "culinary-engine-status"
DATASET_DESC = "项目状态、技术决策、pipeline进度、架构文档"

APP_NAME = "project-knowledge"
APP_DESC = "查询餐饮研发引擎项目状态"

DOCS_TO_UPLOAD = [
    Path.home() / "culinary-engine" / "STATUS.md",
    Path(__file__).resolve().parent.parent.parent / "CLAUDE.md",
]

SYSTEM_PROMPT = """你是餐饮研发引擎（culinary-engine）的项目知识库助手。
你的职责是回答关于项目状态、pipeline进度、技术决策的问题。

回答规则：
1. 只基于 Knowledge Base 中的文档回答，不编造
2. 涉及数字（L0条数、chunks数量、完成率）时给出精确值
3. 涉及状态时明确标注：✅完成 / 🔄进行中 / ⏳待做
4. 如果文档中没有相关信息，说"STATUS.md 中未记录此信息"
5. 回答用中文，简洁直接

你知道的关键概念：
- L0 = 科学原理图谱（核心层）
- Stage1 = OCR+切分+标注
- Stage4 = 开放扫描提取L0原理
- Stage5 = 食谱结构化提取
- 17域 = protein_science等17个科学领域分类
- 七层架构：L0/L1/L2a/L2b/L2c/FT/L3/L6"""


# ============================================================
# Dify Console API client (cookie + CSRF auth)
# ============================================================
class Dify:
    def __init__(self, base_url, email, password):
        self.base = base_url.rstrip("/")
        self.s = requests.Session()
        self.s.trust_env = False  # bypass http_proxy

        # Login (password must be base64 encoded for Dify 1.13)
        encoded_pwd = base64.b64encode(password.encode()).decode()
        r = self.s.post(f"{self.base}/console/api/login",
                        headers={"Content-Type": "application/json"},
                        json={"email": email, "password": encoded_pwd})
        r.raise_for_status()

        # Auth = cookies; CSRF token goes in header
        self.token = self.s.cookies.get("access_token")
        csrf = self.s.cookies.get("csrf_token")
        if not self.token:
            raise RuntimeError(f"Login failed: {r.text}")
        self.s.headers["X-CSRF-Token"] = csrf
        self.s.headers["Content-Type"] = "application/json"
        print(f"✓ Logged in as {email}")

    def get(self, path, **kw):
        r = self.s.get(f"{self.base}{path}", **kw)
        r.raise_for_status()
        return r.json()

    def post_json(self, path, payload):
        r = self.s.post(f"{self.base}{path}", json=payload)
        r.raise_for_status()
        return r.json()

    def post_multipart(self, path, files, data=None):
        """POST multipart/form-data (no Content-Type header — let requests set it)."""
        csrf = self.s.headers.get("X-CSRF-Token", "")
        r = self.s.post(
            f"{self.base}{path}",
            headers={"X-CSRF-Token": csrf, "Content-Type": None},
            files=files, data=data or {})
        r.raise_for_status()
        return r.json()

    def delete(self, path):
        r = self.s.delete(f"{self.base}{path}")
        r.raise_for_status()
        try:
            return r.json()
        except Exception:
            return {"result": "ok"}


def find_by_name(items, name):
    for item in items:
        if item.get("name") == name:
            return item
    return None


# ============================================================
# Step 1: Create or reuse Knowledge Base
# ============================================================
def setup_dataset(dify):
    print("\n--- Step 1: Knowledge Base ---")
    datasets = dify.get("/console/api/datasets", params={"page": 1, "limit": 100})
    existing = find_by_name(datasets.get("data", []), DATASET_NAME)

    if existing:
        dataset_id = existing["id"]
        print(f"  Reusing existing dataset: {dataset_id}")
        # Clean old documents
        docs = dify.get(f"/console/api/datasets/{dataset_id}/documents",
                        params={"page": 1, "limit": 100})
        for doc in docs.get("data", []):
            print(f"  Deleting old doc: {doc['name']}")
            dify.delete(f"/console/api/datasets/{dataset_id}/documents/{doc['id']}")
    else:
        result = dify.post_json("/console/api/datasets", {
            "name": DATASET_NAME,
            "description": DATASET_DESC,
            "indexing_technique": "high_quality",
            "permission": "all_team_members",
        })
        dataset_id = result["id"]
        print(f"  Created dataset: {dataset_id}")

    return dataset_id


# ============================================================
# Step 2: Upload documents (file upload → document create)
# ============================================================
def upload_docs(dify, dataset_id):
    print("\n--- Step 2: Upload Documents ---")
    doc_ids = []

    for fpath in DOCS_TO_UPLOAD:
        if not fpath.exists():
            print(f"  SKIP (not found): {fpath}")
            continue
        print(f"  Uploading: {fpath.name} ({fpath.stat().st_size} bytes)")

        # Step A: Upload file to Dify file store
        with open(fpath, "rb") as f:
            file_result = dify.post_multipart(
                "/console/api/files/upload",
                files={"file": (fpath.name, f, "text/markdown")},
                data={"source": "datasets"})
        file_id = file_result["id"]
        print(f"    file_id={file_id}")

        # Step B: Create document in dataset referencing the file
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
                        "max_tokens": 1000,
                        "chunk_overlap": 200,
                    }
                }
            },
            "data_source": {
                "type": "upload_file",
                "info_list": {
                    "data_source_type": "upload_file",
                    "file_info_list": {
                        "file_ids": [file_id]
                    }
                }
            },
            "doc_form": "text_model",
            "doc_language": "Chinese",
        }
        result = dify.post_json(
            f"/console/api/datasets/{dataset_id}/documents", payload)
        docs = result.get("documents", [])
        batch = result.get("batch", "")
        for doc in docs:
            doc_ids.append((doc["id"], batch, fpath.name))
            print(f"    doc_id={doc['id']}, batch={batch}")

    return doc_ids


# ============================================================
# Step 3: Wait for indexing
# ============================================================
def wait_indexing(dify, dataset_id, doc_ids, timeout=300):
    print("\n--- Step 3: Indexing ---")
    if not doc_ids:
        print("  No documents to index")
        return

    start = time.time()
    pending = {d[0] for d in doc_ids}

    while pending and (time.time() - start) < timeout:
        docs = dify.get(f"/console/api/datasets/{dataset_id}/documents",
                        params={"page": 1, "limit": 100})
        for doc in docs.get("data", []):
            if doc["id"] in pending and doc.get("indexing_status") == "completed":
                pending.discard(doc["id"])
                print(f"  ✓ {doc['name']} indexed ({doc.get('word_count', '?')} words, "
                      f"{doc.get('tokens', '?')} tokens)")
        if pending:
            time.sleep(3)

    if pending:
        print(f"  ⚠ Timeout: {len(pending)} docs still indexing")
    else:
        print("  ✓ All documents indexed")


# ============================================================
# Step 4: Create Chatbot App
# ============================================================
def setup_app(dify, dataset_id):
    print("\n--- Step 4: Chatbot App ---")
    apps = dify.get("/console/api/apps", params={"page": 1, "limit": 100})
    existing = find_by_name(apps.get("data", []), APP_NAME)

    if existing:
        app_id = existing["id"]
        print(f"  Reusing existing app: {app_id}")
    else:
        result = dify.post_json("/console/api/apps", {
            "name": APP_NAME,
            "mode": "chat",
            "description": APP_DESC,
            "icon_type": "emoji",
            "icon": "🍳",
        })
        app_id = result["id"]
        print(f"  Created app: {app_id}")

    return app_id


# ============================================================
# Step 5: Configure model + prompt + knowledge base
# ============================================================
def configure_app(dify, app_id, dataset_id):
    print("\n--- Step 5: Configure App ---")

    config = {
        "pre_prompt": SYSTEM_PROMPT,
        "prompt_type": "simple",
        "model": {
            "provider": "openai_api_compatible",
            "name": "qwen3.5-plus",
            "mode": "chat",
            "completion_params": {
                "temperature": 0.1,
                "max_tokens": 2000,
                "top_p": 0.9,
            }
        },
        "dataset_query_variable": "",
        "dataset_configs": {
            "retrieval_model": "multiple",
            "datasets": {
                "datasets": [
                    {"dataset": {"enabled": True, "id": dataset_id}},
                ]
            },
            "reranking_enable": False,
            "top_k": 5,
            "score_threshold_enabled": True,
            "score_threshold": 0.5,
        },
        "user_input_form": [],
        "opening_statement": "",
        "suggested_questions": [
            "哪些书还没跑 Stage4？",
            "当前 L0 有多少条？",
            "Stage5 食谱提取用什么模型？",
        ],
        "more_like_this": {"enabled": False},
        "sensitive_word_avoidance": {"enabled": False},
        "speech_to_text": {"enabled": False},
        "text_to_speech": {"enabled": False},
        "retriever_resource": {"enabled": True},
        "agent_mode": {"enabled": False, "tools": []},
        "file_upload": {"image": {"enabled": False}},
    }

    try:
        dify.post_json(f"/console/api/apps/{app_id}/model-config", config)
        print("  ✓ Model config set (qwen3.5-plus + RAG)")
    except requests.HTTPError as e:
        print(f"  ⚠ Auto-config failed ({e})")
        print("  → Please configure the model manually in Dify UI:")
        print(f"    1. Open {DIFY_URL}/app/{app_id}/configuration")
        print(f"    2. Set model to qwen3.5-plus")
        print(f"    3. Add Knowledge Base: {DATASET_NAME}")
        print(f"    4. Set system prompt (already saved if app was created)")


# ============================================================
# Step 6: Get or create App API key
# ============================================================
def get_api_key(dify, app_id):
    print("\n--- Step 6: API Key ---")
    try:
        keys = dify.get(f"/console/api/apps/{app_id}/api-keys")
        if keys.get("data"):
            key = keys["data"][0]["token"]
            print(f"  Existing key: {key[:20]}...")
            return key
    except Exception:
        pass

    try:
        result = dify.post_json(f"/console/api/apps/{app_id}/api-keys", {})
        key = result.get("token", result.get("data", {}).get("token", ""))
        print(f"  Created key: {key[:20]}...")
        return key
    except Exception as e:
        print(f"  ⚠ Could not create API key: {e}")
        print("  → Create manually: Dify UI → App → API Access")
        return ""


# ============================================================
# Step 7: Test
# ============================================================
def test_chatbot(api_key):
    if not api_key:
        print("\n--- Step 7: Test (SKIPPED - no API key) ---")
        return

    print("\n--- Step 7: Test ---")
    s = requests.Session()
    s.trust_env = False

    questions = [
        "当前 L0 有多少条？",
        "哪些书还没跑 Stage4？",
    ]

    for q in questions:
        print(f"\n  Q: {q}")
        try:
            r = s.post(
                f"{DIFY_URL}/v1/chat-messages",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "inputs": {},
                    "query": q,
                    "response_mode": "blocking",
                    "user": "setup-test",
                },
                timeout=60,
            )
            r.raise_for_status()
            answer = r.json().get("answer", "(no answer)")
            print(f"  A: {answer[:300]}{'...' if len(answer) > 300 else ''}")
        except Exception as e:
            print(f"  ⚠ {e}")


# ============================================================
# Main
# ============================================================
def main():
    print("=" * 60)
    print("Dify Workflow 1: project-knowledge chatbot")
    print("=" * 60)

    dify = Dify(DIFY_URL, EMAIL, PASSWORD)

    dataset_id = setup_dataset(dify)
    doc_ids = upload_docs(dify, dataset_id)
    wait_indexing(dify, dataset_id, doc_ids)
    app_id = setup_app(dify, dataset_id)
    configure_app(dify, app_id, dataset_id)
    api_key = get_api_key(dify, app_id)

    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"  Dataset:  {DATASET_NAME} ({dataset_id})")
    print(f"  App:      {APP_NAME} ({app_id})")
    if api_key:
        print(f"  API Key:  {api_key[:20]}...")
    print(f"  Web UI:   {DIFY_URL}/app/{app_id}/overview")
    print(f"  Chat API: {DIFY_URL}/v1/chat-messages")

    # Save config for sync script and other workflows
    config_path = Path(__file__).parent / "dify_config.json"
    config_path.write_text(json.dumps({
        "base_url": DIFY_URL,
        "dataset_id": dataset_id,
        "dataset_name": DATASET_NAME,
        "app_id": app_id,
        "app_name": APP_NAME,
        "api_key": api_key,
        "docs": [str(p) for p in DOCS_TO_UPLOAD],
    }, indent=2, ensure_ascii=False))
    print(f"  Config:   {config_path}")

    test_chatbot(api_key)


if __name__ == "__main__":
    main()
