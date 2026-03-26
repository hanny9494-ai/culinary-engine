"""
Dify Console API client for culinary-engine project management.

Usage:
    from dify_client import DifyConsole
    client = DifyConsole("http://localhost", email="...", password="...")
    # or
    client = DifyConsole("http://localhost", token="existing-token")
"""

import json
import time
import requests
from pathlib import Path
from typing import Optional


class DifyConsole:
    """Thin wrapper around Dify Console API (v1.13)."""

    def __init__(self, base_url: str = "http://localhost",
                 email: str = None, password: str = None,
                 token: str = None):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.trust_env = False  # bypass http_proxy
        self.session.headers["Content-Type"] = "application/json"

        if token:
            self.token = token
        elif email and password:
            self.token = self._login(email, password)
        else:
            raise ValueError("Provide either (email, password) or token")

        self.session.headers["Authorization"] = f"Bearer {self.token}"

    def _login(self, email: str, password: str) -> str:
        r = self.session.post(f"{self.base_url}/console/api/login",
                              json={"email": email, "password": password})
        r.raise_for_status()
        data = r.json()
        # Dify 1.x returns access_token + refresh_token
        return data.get("access_token") or data.get("data", {}).get("access_token")

    # ---- Knowledge Base (Dataset) ----

    def create_dataset(self, name: str, description: str = "",
                       indexing_technique: str = "high_quality",
                       permission: str = "all_team_members") -> dict:
        r = self.session.post(f"{self.base_url}/console/api/datasets", json={
            "name": name,
            "description": description,
            "indexing_technique": indexing_technique,
            "permission": permission,
        })
        r.raise_for_status()
        return r.json()

    def list_datasets(self, page: int = 1, limit: int = 20) -> dict:
        r = self.session.get(f"{self.base_url}/console/api/datasets",
                             params={"page": page, "limit": limit})
        r.raise_for_status()
        return r.json()

    def upload_document(self, dataset_id: str, file_path: str,
                        segment_separator: str = "\n## ",
                        max_tokens: int = 1000,
                        chunk_overlap: int = 200) -> dict:
        """Upload a file to a dataset with custom segmentation."""
        headers = {"Authorization": f"Bearer {self.token}"}
        # multipart form - remove Content-Type to let requests set boundary
        process_rule = {
            "mode": "custom",
            "rules": {
                "pre_processing_rules": [
                    {"id": "remove_extra_spaces", "enabled": True},
                    {"id": "remove_urls_emails", "enabled": False}
                ],
                "segmentation": {
                    "separator": segment_separator,
                    "max_tokens": max_tokens,
                    "chunk_overlap": chunk_overlap
                }
            }
        }
        with open(file_path, "rb") as f:
            r = self.session.post(
                f"{self.base_url}/console/api/datasets/{dataset_id}/document/create-by-file",
                headers=headers,
                files={"file": (Path(file_path).name, f, "text/markdown")},
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
        return r.json()

    def list_documents(self, dataset_id: str, page: int = 1) -> dict:
        r = self.session.get(
            f"{self.base_url}/console/api/datasets/{dataset_id}/documents",
            params={"page": page, "limit": 20})
        r.raise_for_status()
        return r.json()

    def delete_document(self, dataset_id: str, document_id: str) -> dict:
        r = self.session.delete(
            f"{self.base_url}/console/api/datasets/{dataset_id}/documents/{document_id}")
        r.raise_for_status()
        return r.json()

    def get_indexing_status(self, dataset_id: str, batch_id: str) -> dict:
        r = self.session.get(
            f"{self.base_url}/console/api/datasets/{dataset_id}/documents/{batch_id}/indexing-status")
        r.raise_for_status()
        return r.json()

    def wait_indexing(self, dataset_id: str, batch_id: str,
                      timeout: int = 300, interval: int = 5):
        """Poll until indexing completes."""
        start = time.time()
        while time.time() - start < timeout:
            status = self.get_indexing_status(dataset_id, batch_id)
            docs = status.get("data", [])
            if all(d.get("indexing_status") == "completed" for d in docs):
                print(f"  Indexing complete ({len(docs)} docs)")
                return status
            processing = [d for d in docs if d.get("indexing_status") != "completed"]
            print(f"  Indexing... {len(docs)-len(processing)}/{len(docs)} done")
            time.sleep(interval)
        raise TimeoutError(f"Indexing not complete after {timeout}s")

    # ---- Apps ----

    def create_app(self, name: str, mode: str = "chat",
                   description: str = "", icon_type: str = "emoji",
                   icon: str = "🍳") -> dict:
        r = self.session.post(f"{self.base_url}/console/api/apps", json={
            "name": name,
            "mode": mode,
            "description": description,
            "icon_type": icon_type,
            "icon": icon,
        })
        r.raise_for_status()
        return r.json()

    def get_app(self, app_id: str) -> dict:
        r = self.session.get(f"{self.base_url}/console/api/apps/{app_id}")
        r.raise_for_status()
        return r.json()

    def list_apps(self, page: int = 1, limit: int = 30) -> dict:
        r = self.session.get(f"{self.base_url}/console/api/apps",
                             params={"page": page, "limit": limit})
        r.raise_for_status()
        return r.json()

    def update_app_model_config(self, app_id: str, config: dict) -> dict:
        """Update app model config (prompt, model, dataset, etc.)."""
        r = self.session.post(
            f"{self.base_url}/console/api/apps/{app_id}/model-config",
            json=config)
        r.raise_for_status()
        return r.json()

    def get_app_api_key(self, app_id: str) -> dict:
        """Get or create API key for an app."""
        r = self.session.get(
            f"{self.base_url}/console/api/apps/{app_id}/api-keys")
        r.raise_for_status()
        data = r.json()
        if data.get("data"):
            return data["data"][0]
        # Create one
        r = self.session.post(
            f"{self.base_url}/console/api/apps/{app_id}/api-keys")
        r.raise_for_status()
        return r.json()

    # ---- Convenience ----

    def find_dataset_by_name(self, name: str) -> Optional[dict]:
        datasets = self.list_datasets(limit=100)
        for ds in datasets.get("data", []):
            if ds["name"] == name:
                return ds
        return None

    def find_app_by_name(self, name: str) -> Optional[dict]:
        apps = self.list_apps(limit=100)
        for app in apps.get("data", []):
            if app["name"] == name:
                return app
        return None
