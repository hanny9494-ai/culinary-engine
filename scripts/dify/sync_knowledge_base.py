#!/usr/bin/env python3
"""
同步 STATUS.md 到 Dify Knowledge Base（增量更新）

每次 STATUS.md 更新后运行，或作为 cron/hook 自动触发。

Usage:
    python3 scripts/dify/sync_knowledge_base.py
    python3 scripts/dify/sync_knowledge_base.py --file STATUS.md
    python3 scripts/dify/sync_knowledge_base.py --all
"""

import json
import time
import base64
import argparse
import requests
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "dify_config.json"

DIFY_URL = "http://localhost"
EMAIL = "hanny9494@gmail.com"
PASSWORD = "Jeffery96352101"

SYNC_FILES = {
    "STATUS.md": Path.home() / "culinary-engine" / "STATUS.md",
    "CLAUDE.md": Path(__file__).resolve().parent.parent.parent / "CLAUDE.md",
}


def login(base_url, email, password):
    s = requests.Session()
    s.trust_env = False
    encoded_pwd = base64.b64encode(password.encode()).decode()
    r = s.post(f"{base_url}/console/api/login",
               headers={"Content-Type": "application/json"},
               json={"email": email, "password": encoded_pwd})
    r.raise_for_status()
    token = s.cookies.get("access_token")
    s.headers["Authorization"] = f"Bearer {token}"
    s.headers["Content-Type"] = "application/json"
    return s, token


def sync_file(s, token, base_url, dataset_id, file_path):
    fname = file_path.name
    print(f"Syncing {fname}...")

    # Find existing document by name
    docs = s.get(f"{base_url}/console/api/datasets/{dataset_id}/documents",
                 params={"page": 1, "limit": 100}).json()

    old_doc = None
    for doc in docs.get("data", []):
        if doc["name"] == fname:
            old_doc = doc
            break

    # Delete old version
    if old_doc:
        print(f"  Deleting old version: {old_doc['id']}")
        s.delete(f"{base_url}/console/api/datasets/{dataset_id}/documents/{old_doc['id']}")

    # Upload new version
    process_rule = {
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
    }

    headers = {"Authorization": f"Bearer {token}"}
    with open(file_path, "rb") as f:
        r = s.post(
            f"{base_url}/console/api/datasets/{dataset_id}/document/create-by-file",
            headers=headers,
            files={"file": (fname, f, "text/markdown")},
            data={
                "process_rule": json.dumps(process_rule),
                "data_source": json.dumps({
                    "type": "upload_file",
                    "info_list": {"data_source_type": "upload_file"}
                }),
                "indexing_technique": "high_quality",
            },
        )
    r.raise_for_status()
    result = r.json()
    batch_id = result.get("batch", "")
    print(f"  Uploaded, batch={batch_id}")

    # Wait for indexing
    for _ in range(60):
        try:
            status = s.get(
                f"{base_url}/console/api/datasets/{dataset_id}/documents/{batch_id}/indexing-status"
            ).json()
            items = status.get("data", [])
            if all(d.get("indexing_status") == "completed" for d in items):
                print(f"  ✓ {fname} re-indexed")
                return
        except Exception:
            pass
        time.sleep(3)

    print(f"  ⚠ Indexing timeout for {fname}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", help="Sync specific file (e.g. STATUS.md)")
    parser.add_argument("--all", action="store_true", help="Sync all files")
    args = parser.parse_args()

    # Load config
    if not CONFIG_PATH.exists():
        print(f"ERROR: Run setup_project_knowledge.py first to create {CONFIG_PATH}")
        return
    config = json.loads(CONFIG_PATH.read_text())
    dataset_id = config["dataset_id"]

    s, token = login(DIFY_URL, EMAIL, PASSWORD)

    if args.all or not args.file:
        files = list(SYNC_FILES.values())
    else:
        if args.file in SYNC_FILES:
            files = [SYNC_FILES[args.file]]
        else:
            files = [Path(args.file)]

    for fpath in files:
        if fpath.exists():
            sync_file(s, token, DIFY_URL, dataset_id, fpath)
        else:
            print(f"SKIP (not found): {fpath}")

    print("\nDone.")


if __name__ == "__main__":
    main()
